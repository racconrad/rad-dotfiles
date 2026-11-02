"""One MPRIS status follower shared by all Waybar music buttons and outputs."""
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import uuid

from raccon_events import FileEvents

RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', Path.home()/'.cache'))
ROOT = RUNTIME / 'raccon-waybar-music'
# Match the music card's existing flag, including its /tmp fallback.
FLAG = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'raccon-music.open'
TIPS = dict(open='Show music player', prev='Previous',
            play='Play / Pause', next='Next')


def snapshot(status, card_open):
    icons = dict(open='󰝚', prev='󰒮', play='󰏤' if status == 'Playing' else '󰐊', next='󰒭')
    active = status in ('Playing', 'Paused') and not card_open
    return {mode: dict(text=icon, tooltip=TIPS[mode], **{'class': status.lower()})
            if active else dict(text='') for mode, icon in icons.items()}


def directory():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if ROOT.is_symlink() or ROOT.stat().st_uid != os.getuid():
        raise OSError('Invalid music runtime directory')
    ROOT.chmod(0o700)


def serve():
    directory()
    with (ROOT/'provider.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        path = ROOT/'subscribe'
        path.unlink(missing_ok=True)
        os.mkfifo(path, 0o600)
        inbox = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        (ROOT/'provider.pid').write_text(str(os.getpid()))
        clients = {}
        child = None
        status, buffered, requests, latest = '', b'', b'', None
        retry, idle_until = 0, time.monotonic() + 5
        poll = select.poll()
        poll.register(inbox, select.POLLIN)
        with FileEvents([FLAG]) as changes:
            poll.register(changes, select.POLLIN)

            def remove(fd):
                nonlocal idle_until
                poll.unregister(fd)
                name = clients.pop(fd)
                os.close(fd)
                (ROOT/name).unlink(missing_ok=True)
                if not clients:
                    idle_until = time.monotonic() + 3

            def send(fd):
                try:
                    # One small atomic pipe write; a slow/dead bar cannot block others.
                    os.write(fd, latest)
                except OSError:
                    remove(fd)

            def publish():
                nonlocal latest
                value = json.dumps(snapshot(status, FLAG.exists()), ensure_ascii=False).encode() + b'\n'
                if value == latest:
                    return
                latest = value
                for fd in tuple(clients):
                    send(fd)

            def stop_player():
                nonlocal child
                if child is None:
                    return
                if child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                child.stdout.close()
                child = None

            try:
                publish()
                while clients or time.monotonic() < idle_until:
                    now = time.monotonic()
                    if child is None and now >= retry:
                        try:
                            child = subprocess.Popen(['playerctl', '--follow', 'status'], stdin=subprocess.DEVNULL,
                                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                            os.set_blocking(child.stdout.fileno(), False)
                            poll.register(child.stdout, select.POLLIN | select.POLLHUP)
                            buffered = b''
                        except OSError:
                            stop_player()
                            retry = now + 2
                    deadlines = ([] if clients else [idle_until]) + ([] if child else [retry])
                    timeout = max(0, (min(deadlines) - time.monotonic()) * 1000) if deadlines else None
                    for fd, flags in poll.poll(timeout):
                        if fd == inbox:
                            requests += os.read(inbox, 65536)
                            while b'\n' in requests:
                                line, requests = requests.split(b'\n', 1)
                                name = os.fsdecode(line)
                                if not name.startswith('client-') or '/' in name or len(name) > 100:
                                    continue
                                client_path = ROOT/name
                                try:
                                    info = client_path.lstat()
                                    if not stat.S_ISFIFO(info.st_mode) or info.st_uid != os.getuid():
                                        continue
                                    writer = os.open(client_path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
                                except OSError:
                                    continue
                                clients[writer] = name
                                poll.register(writer, select.POLLERR | select.POLLHUP)
                                send(writer)
                            if len(requests) > 65536:
                                requests = b''
                        elif fd in clients:
                            # Closing a module's read end wakes POLLERR immediately.
                            remove(fd)
                        elif fd == changes.fileno():
                            if changes.drain():
                                publish()
                        elif child is not None and fd == child.stdout.fileno():
                            data = os.read(fd, 65536)
                            if not data:
                                poll.unregister(fd)
                                stop_player()
                                status = ''
                                retry = time.monotonic() + 2
                                publish()
                            else:
                                buffered += data
                                while b'\n' in buffered:
                                    line, buffered = buffered.split(b'\n', 1)
                                    status = line.decode(errors='replace').strip()
                                    publish()
                                if len(buffered) > 65536:
                                    buffered = b''
            finally:
                stop_player()
                for fd in tuple(clients):
                    remove(fd)
                os.close(inbox)
                path.unlink(missing_ok=True)
                (ROOT/'provider.pid').unlink(missing_ok=True)


def updates():
    directory()
    path = ROOT/('client-' + str(os.getpid()) + '-' + uuid.uuid4().hex)
    os.mkfifo(path, 0o600)
    reader = keeper = -1
    try:
        reader = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        # Keep the pipe alive only until the provider's first snapshot arrives.
        keeper = os.open(path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        with (ROOT/'start.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            launched = False
            for _ in range(60):
                try:
                    inbox = os.open(ROOT/'subscribe', os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                    try:
                        os.write(inbox, os.fsencode(path.name) + b'\n')
                    finally:
                        os.close(inbox)
                    break
                except OSError:
                    if not launched:
                        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve'],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, start_new_session=True)
                        launched = True
                    time.sleep(.025)  # Startup/reconnection only.
            else:
                raise OSError('Music status provider did not start')
        if not select.select([reader], [], [], 2)[0]:
            raise OSError('Music status subscription timed out')
        os.close(keeper)
        keeper = -1
        os.set_blocking(reader, True)
        with os.fdopen(reader) as stream:
            reader = -1
            yield from stream
    finally:
        for fd in (reader, keeper):
            if fd >= 0:
                os.close(fd)
        path.unlink(missing_ok=True)


def listen(mode):
    previous = None
    while True:
        try:
            for line in updates():
                value = json.loads(line)[mode]
                if value != previous:
                    print(json.dumps(value, ensure_ascii=False), flush=True)
                    previous = value
        except BrokenPipeError:
            return
        except (OSError, ValueError, KeyError):
            pass
        value = dict(text='')
        if value != previous:
            print(json.dumps(value), flush=True)
            previous = value
        time.sleep(1)  # Provider failure/restart only.


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    try:
        if mode == 'serve':
            def stop(*_args):
                raise SystemExit(0)
            signal.signal(signal.SIGTERM, stop)
            serve()
        elif mode in TIPS:
            listen(mode)
        else:
            raise SystemExit('Usage: waybar-music open|prev|play|next')
    except (BrokenPipeError, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    main()
