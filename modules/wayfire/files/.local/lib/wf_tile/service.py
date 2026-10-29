"""One Wayfire command connection, one event stream and one serialized queue."""
from collections import deque
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time

from .engine import Engine, session_dir


def socket_path(tile):
    return os.environ.get('WF_TILE_SOCKET', str(session_dir(tile)/'control.sock'))


def request(tile, args):
    if not args or any(not re.fullmatch(r'[\w.:/-]+', arg, flags=re.ASCII) for arg in args):
        raise ValueError('Invalid action or argument')
    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as client:
        client.settimeout(5)
        client.connect(socket_path(tile))
        # A failed connect is safe to bootstrap. Errors after sending are not:
        # retrying could apply a move/toggle twice.
        client.sendall((' '.join(args)+'\n').encode())
        result = bytearray()
        while b'\n' not in result and len(result) < 65536:
            data = client.recv(4096)
            if not data:
                break
            result.extend(data)
        text = result.decode().strip()
        if not text.startswith('OK '):
            if text == 'OK':
                return ''
            raise RuntimeError(text or 'Tiling service did not reply')
        return text[3:]


def compile_client():
    source = Path(__file__).with_name('client.c')
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home()/'.cache')))/'wf-tile'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache/'client'
    if target.exists() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return
    temporary = cache/f'.client-{os.getpid()}'
    try:
        subprocess.run(['cc', '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(source), '-o', str(temporary)], check=True, capture_output=True, timeout=20)
        temporary.chmod(0o755)
        temporary.replace(target)
    except (OSError, subprocess.SubprocessError) as exc:
        print('wf-tile: native sender unavailable, using Python fallback:', exc, file=sys.stderr, flush=True)
    finally:
        temporary.unlink(missing_ok=True)


def claim_watch_lock(tile):
    """Upgrade only this exact helper's old observer, never the compositor."""
    lock = tile.runtime_file('wf-tile-watch.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        st = os.fstat(lock.fileno())
        identity = f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
        try:
            rows = Path('/proc/locks').read_text().splitlines()
            pid = next(int(row.split()[4]) for row in rows if identity in row.split() and 'FLOCK' in row)
            process = Path('/proc')/str(pid)
            args = [part.decode() for part in (process/'cmdline').read_bytes().split(b'\0') if part]
            expected = str(Path(tile.__file__).resolve())
            if process.stat().st_uid != os.getuid() or not any(
                    arg == 'watch' and i and str(Path(args[i-1]).resolve()) == expected for i,arg in enumerate(args)):
                raise RuntimeError('Another observer holds the tiling lock')
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(.02)
            else:
                raise RuntimeError('Previous tiling observer is still stopping')
        except (OSError, StopIteration, ValueError) as exc:
            lock.close()
            raise RuntimeError('Cannot replace the previous tiling observer') from exc
    lock.seek(0); lock.truncate(); lock.write(str(os.getpid())); lock.flush()
    return lock


def daemon(tile):
    directory = session_dir(tile)
    # Separate startup lock prevents concurrent fallback clients from replacing
    # each other's freshly started resident service.
    startup = (directory/'service.lock').open('a+')
    try:
        fcntl.flock(startup, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    watch_lock = claim_watch_lock(tile)
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    compile_client()
    ui_process = None
    ipc = events = engine = server = None
    path = Path(socket_path(tile))
    try:
        ipc, events = tile.IPC(), tile.IPC()
        # IDs are only valid for this compositor socket, including across a
        # service upgrade. Never restore stale IDs after logging in again.
        socket_stat = Path(ipc.path).stat()
        signature = json.dumps([ipc.path, socket_stat.st_ino, socket_stat.st_ctime_ns])
        identity = directory/'compositor'
        if not identity.exists() or identity.read_text() != signature:
            for name in ('history.json', 'scratch.json'):
                (directory/name).unlink(missing_ok=True)
            identity.write_text(signature)
        engine = Engine(tile, ipc)
        engine.publish_ui()
        events.call('window-rules/events/watch', {'events': ['view-focused', 'view-mapped', 'view-unmapped',
                    'view-minimized', 'view-workspace-changed', 'view-wset-changed', 'wset-workspace-changed',
                    'output-wset-changed', 'output-gain-focus', 'view-tiled']})
        events.sock.setblocking(False)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        path.unlink(missing_ok=True)
        server.bind(str(path)); path.chmod(0o600); server.listen(32); server.setblocking(False)
        if os.environ.get('WF_TILE_NO_UI') != '1':
            env = dict(os.environ)
            env['PYTHONPATH'] = str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get('PYTHONPATH', '')
            ui_process = subprocess.Popen([sys.executable, '-m', 'wf_tile.ui', str(directory/'ui.json'), str(path)],
                                          env=env, stdin=subprocess.DEVNULL)
        history = deque(maxlen=32)
        focus = ipc.call('window-rules/get-focused-view').get('info') or {}
        if focus.get('id'):
            history.appendleft(focus['id'])
        buffer = bytearray()
        pending = deque()
        gap_due = time.monotonic()
        housekeeping = 0
        with selectors.DefaultSelector() as selector:
            selector.register(server, selectors.EVENT_READ, 'server')
            selector.register(events.sock, selectors.EVENT_READ, 'events')
            while running:
                now = time.monotonic()
                timeout = min(.2, max(0, pending[0][0]-now)) if pending else .2
                for key, _ in selector.select(timeout):
                    if key.data == 'server':
                        client, _ = server.accept()
                        with client:
                            client.settimeout(.15)
                            try:
                                if hasattr(socket, 'SO_PEERCRED'):
                                    _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                                    if uid != os.getuid():
                                        raise ValueError('Wrong user')
                                raw = bytearray()
                                while b'\n' not in raw and len(raw) < 2048:
                                    data = client.recv(2048-len(raw))
                                    if not data: break
                                    raw.extend(data)
                                if not raw.endswith(b'\n') or b'\n' in raw[:-1]:
                                    raise ValueError('Invalid request')
                                args = raw.decode('ascii').strip().split()
                                if any(not re.fullmatch(r'[\w.:/-]+', arg, flags=re.ASCII) for arg in args):
                                    raise ValueError('Invalid argument')
                                if args == ['stop']:
                                    running = False; result = None
                                else:
                                    if args and args[0].endswith('-mode') and (not ui_process or ui_process.poll() is not None):
                                        raise RuntimeError('Tiling HUD unavailable; run wf-tile restart and check service.log')
                                    result = engine.execute(args)
                                    if args == ['status']:
                                        result['ui_running'] = bool(ui_process and ui_process.poll() is None)
                                    gap_due = time.monotonic()+.03
                                reply = 'OK '+(json.dumps(result, separators=(',',':')) if result is not None else '')+'\n'
                            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
                                reply = 'ERR '+str(exc).replace('\n',' ')+'\n'
                                engine.tip(str(exc))
                            try: client.sendall(reply.encode())
                            except OSError: pass
                    else:
                        data = events.sock.recv(65536)
                        if not data:
                            raise ConnectionError('Wayfire event stream closed')
                        buffer.extend(data)
                        while len(buffer)>=4:
                            size = struct.unpack('<I', buffer[:4])[0]
                            if size > 4*1024*1024:
                                raise ValueError('Wayfire event too large')
                            if len(buffer)<size+4: break
                            message = json.loads(buffer[4:size+4]); del buffer[:size+4]
                            view = message.get('view') or {}; vid = view.get('id'); event = message.get('event')
                            if event == 'view-focused' and view.get('role') == 'toplevel':
                                if vid in history: history.remove(vid)
                                history.appendleft(vid)
                            elif event == 'view-mapped' and view.get('role') == 'toplevel':
                                pending.append((time.monotonic()+.025, vid, tuple(v for v in history if v!=vid)))
                            elif event == 'view-unmapped':
                                if vid in history: history.remove(vid)
                                for slot in [slot for slot,item in engine.scratch.items() if item['id']==vid]:
                                    engine.scratch.pop(slot); engine.save_scratch()
                            if gap_due is None:
                                gap_due = time.monotonic()+.04
                now = time.monotonic()
                while pending and pending[0][0] <= now:
                    _, vid, anchors = pending.popleft()
                    try:
                        engine.adopt(vid, anchors)
                    except (RuntimeError, ValueError, KeyError) as exc:
                        print('wf-tile adopt:', exc, file=sys.stderr, flush=True)
                    gap_due = now+.04
                if gap_due is not None and gap_due <= now:
                    try:
                        engine.update_gaps()
                    except (RuntimeError, ValueError, KeyError) as exc:
                        engine.gap_error = str(exc)
                    gap_due = None
                if now >= housekeeping:
                    engine.publish_ui()
                    # Also notice theme/config edits while the desktop is idle.
                    engine.refresh_gap_config()
                    if engine.applied_gaps is None and gap_due is None:
                        gap_due = now+.04
                    housekeeping = now+.2
    finally:
        path.unlink(missing_ok=True)
        if engine:
            try:
                engine.end_modal(); engine.update_gaps(restore=True)
            except (OSError, RuntimeError, ValueError, KeyError): pass
        tile.atomic_json(directory/'ui.json', {'mode': None, 'preview': None, 'hint': None})
        if ui_process and ui_process.poll() is None:
            ui_process.terminate()
            try: ui_process.wait(timeout=2)
            except subprocess.TimeoutExpired: ui_process.kill()
        for connection in (ipc, events, server, watch_lock, startup):
            if connection: connection.close()
    return 0


def start(tile):
    directory = session_dir(tile)
    with (directory/'service.log').open('a') as log:
        subprocess.Popen([sys.executable, str(Path(tile.__file__).resolve()), 'watch'],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(150):
        try:
            request(tile, ['status'])
            return
        except (FileNotFoundError, ConnectionRefusedError):
            time.sleep(.02)
    raise RuntimeError(f'Tiling service did not start; see {directory}/service.log')


def main(tile, args):
    if not args:
        print(tile.__doc__.strip())
        return 1
    try:
        if args in (['watch'], ['daemon']):
            return daemon(tile)
        if args == ['restart']:
            try: request(tile, ['stop'])
            except (FileNotFoundError, ConnectionRefusedError): pass
            for _ in range(100):
                if not Path(socket_path(tile)).exists(): break
                time.sleep(.02)
            start(tile)
            return 0
        try:
            result = request(tile, args)
        except (FileNotFoundError, ConnectionRefusedError):
            start(tile)
            result = request(tile, args)
        if result:
            print(result)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print('wf-tile:', exc, file=sys.stderr)
        return 1
