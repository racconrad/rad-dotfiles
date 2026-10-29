"""Short shell-only fade with an independent visibility recovery worker."""
import json
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import time


def ipc(method, data=None):
    path = os.environ.get('WAYFIRE_SOCKET')
    if not path:
        runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        path = next(iter(runtime.glob('wayfire-*.socket')), None)
    if not path:
        raise OSError('Wayfire IPC unavailable')
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(.5)
        sock.connect(str(path))
        body = json.dumps({'method': method, 'data': data or {}}).encode()
        sock.sendall(struct.pack('<I', len(body)) + body)
        def exact(n):
            result = b''
            while len(result) < n:
                part = sock.recv(n-len(result))
                if not part:
                    raise OSError('Wayfire IPC closed')
                result += part
            return result
        size = struct.unpack('<I', exact(4))[0]
        if size > 4*1024*1024:
            raise ValueError('Invalid IPC response')
        result = json.loads(exact(size))
        if isinstance(result, dict) and result.get('error'):
            raise OSError(str(result['error']))
        return result


def shell_view(view):
    app = view.get('app-id', '')
    return view.get('mapped') and (app in {
        'waybar', 'desktop-style', 'raccon-menu', 'desktop-menu',
        'swaync-control-center', 'swaync-notification-window', 'swayosd',
    } or app.startswith('rw-'))


class Fade:
    def __init__(self, request=ipc):
        self.request = request
        self.originals = {}

    def frame(self, factor):
        views = self.request('window-rules/list-views')
        if not isinstance(views, list):
            return
        for view in views:
            if not shell_view(view):
                continue
            key = view['id']
            try:
                if key not in self.originals:
                    value = self.request('wf/alpha/get-view-alpha', {'view-id': key})['alpha']
                    self.originals[key] = float(value)
                self.request('wf/alpha/set-view-alpha', {'view-id': key, 'alpha': self.originals[key]*factor})
            except (OSError, ValueError, KeyError):
                continue  # A menu may disappear during the request.

    def animate(self, opening):
        for step in range(1, 11):
            progress = step/10
            factor = 1-(1-progress)**3 if opening else (1-progress)**3
            self.frame(factor)
            time.sleep(.016)

    def restore(self):
        for key, alpha in self.originals.items():
            try:
                self.request('wf/alpha/set-view-alpha', {'view-id': key, 'alpha': alpha})
            except (OSError, ValueError):
                pass


def worker():
    fade = Fade()
    try:
        fade.animate(False)
        print('hidden', flush=True)
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            ready, _, _ = select.select([sys.stdin], [], [], .016)
            if ready:
                break  # Release or EOF (even if the parent was killed).
            fade.frame(0)
        fade.animate(True)
    except (OSError, ValueError):
        pass
    finally:
        fade.restore()


class ShellTransition:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.process = None

    def __enter__(self):
        if not self.enabled:
            return self
        env = dict(os.environ)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
        self.process = subprocess.Popen([sys.executable, '-m', 'desktop_style.transition'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, start_new_session=True)
        ready, _, _ = select.select([self.process.stdout], [], [], 2)
        if ready:
            self.process.stdout.readline()
        else:
            self.__exit__(None, None, None)
        return self

    def __exit__(self, *_):
        if self.process is None:
            return
        self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # Worker owns its recovery; never kill it with surfaces hidden.
            pass
        self.process.stdout.close()
        self.process = None


if __name__ == '__main__':
    worker()
