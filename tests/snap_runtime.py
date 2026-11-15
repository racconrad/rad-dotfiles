"""Private headless compositor and real GTK client for opt-in Snap tests."""
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]

CLIENT = '''import gi,sys
 gi.require_version('Gtk','3.0')
 from gi.repository import Gtk,GLib,Gdk
 GLib.set_prgname('raccon-snap-fixture')
 window=Gtk.Window(title='Snap fixture')
 window.set_default_size(500,320)
 window.set_size_request(int(sys.argv[1]),int(sys.argv[2]))
 window.add(Gtk.Label(label='Private Snap interaction fixture'))
 window.connect('destroy',Gtk.main_quit)
 window.connect('button-press-event',lambda _,e:print('BUTTON',e.button,flush=True))
 window.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
 window.connect('key-press-event',lambda _,e:print('KEY',Gdk.keyval_name(e.keyval),flush=True))
 window.show_all()
 Gtk.main()
'''.replace('\n ', '\n')


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.05)
    raise AssertionError('Private compositor condition timed out')


class PrivateCompositor:
    def __init__(self, build, minimum=(200, 150), toggle='<super> KEY_Z', detach='<super> <shift> KEY_SPACE'):
        self.temporary = tempfile.TemporaryDirectory(prefix='raccon-snap-runtime-')
        self.root = Path(self.temporary.name)
        self.processes, self.logs = [], []
        self.connection = None
        try:
            self.start(Path(build), minimum, toggle, detach)
        except BaseException:
            self.close()
            raise

    def start(self, build, minimum, toggle, detach):
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        home = self.root / 'home'
        home.mkdir()
        metadata = home / '.local/share/wayfire/metadata'
        metadata.mkdir(parents=True)
        source = ROOT / 'modules/wayfire/plugins/snap-tiling'
        shutil.copy2(source / 'snap-tiling.xml', metadata)
        config = self.root / 'wayfire.ini'
        config.write_text('[core]\nplugins = ipc ipc-rules stipc place move resize command '
                          + str((build / 'libsnap-tiling.so').resolve())
                          + '\nxwayland = false\nvwidth = 2\nvheight = 1\n'
                          '[output:HEADLESS-1]\nmode = 1280x800\nscale = 1\n'
                          '[snap-tiling]\ntoggle = ' + toggle + '\ndetach = ' + detach + '\n'
                          '[command]\nbinding_collision = <super> KEY_RIGHT\n'
                          'command_collision = touch ' + str(self.root / 'collision') + '\n')
        self.env = dict(os.environ)
        for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'WAYFIRE_SOCKET', 'WAYLAND_SOCKET',
                    'WAYFIRE_CONFIG_FILE', 'GDK_SCALE', 'GDK_DPI_SCALE'):
            self.env.pop(key, None)
        self.env.update(HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
                        XDG_CONFIG_HOME=str(home / '.config'), XDG_DATA_HOME=str(home / '.local/share'),
                        XDG_STATE_HOME=str(home / '.local/state'), XDG_CACHE_HOME=str(home / '.cache'),
                        WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1',
                        LIBGL_ALWAYS_SOFTWARE='1', GDK_BACKEND='wayland',
                        NO_AT_BRIDGE='1', GSETTINGS_BACKEND='memory',
                        DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'no-bus'))
        compositor = self.spawn(['/usr/bin/wayfire', '-d', '-c', str(config)], 'wayfire.log')
        def ready():
            if compositor.poll() is not None:
                raise AssertionError((self.root / 'wayfire.log').read_text()[-4000:])
            return next((p for p in runtime.glob('wayfire-*.socket') if p.is_socket()), None)
        address = wait_for(ready)
        self.connection = socket.socket(socket.AF_UNIX)
        self.connection.settimeout(5)
        self.connection.connect(str(address))
        self.env['WAYLAND_DISPLAY'] = next(p.name for p in runtime.glob('wayland-*') if p.is_socket())
        script = self.root / 'client.py'
        script.write_text(CLIENT)
        self.spawn([sys.executable, str(script), *map(str, minimum)], 'client.log')
        self.view = wait_for(lambda: next((v for v in self.views() if v.get('title') == 'Snap fixture'), None))
        self.call('window-rules/focus-view', {'id': self.view['id']})
        time.sleep(.15)

    def spawn(self, command, name):
        log = (self.root / name).open('w')
        self.logs.append(log)
        process = subprocess.Popen(command, env=self.env, stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        self.processes.append(process)
        return process

    def receive(self, length):
        data = b''
        while len(data) < length:
            chunk = self.connection.recv(length - len(data))
            if not chunk:
                raise AssertionError('Private compositor IPC closed')
            data += chunk
        return data

    def call(self, method, data=None):
        request = json.dumps({'method': method, 'data': data or {}}).encode()
        self.connection.sendall(struct.pack('<I', len(request)) + request)
        response = json.loads(self.receive(struct.unpack('<I', self.receive(4))[0]))
        if isinstance(response, dict) and 'error' in response:
            raise AssertionError(response)
        return response

    def views(self):
        result = self.call('window-rules/list-views')
        return result if isinstance(result, list) else result.get('views', [])

    def current(self):
        return next(v for v in self.views() if v['id'] == self.view['id'])

    def key(self, key, modifiers=()):
        for modifier in modifiers:
            self.call('stipc/feed_key', {'key': modifier, 'state': True})
        self.call('stipc/feed_key', {'key': key, 'state': True})
        self.call('stipc/feed_key', {'key': key, 'state': False})
        for modifier in reversed(modifiers):
            self.call('stipc/feed_key', {'key': modifier, 'state': False})
        time.sleep(.12)

    def open_selector(self):
        self.key('KEY_Z', ('KEY_LEFTMETA',))

    def click(self, x, y):
        self.call('stipc/move_cursor', {'x': float(x), 'y': float(y)})
        self.call('stipc/feed_button', {'combo': 'BTN_LEFT', 'mode': 'full'})
        time.sleep(.2)

    def screenshot(self, name):
        path = self.root / name
        subprocess.run(['grim', str(path)], env=self.env, check=True, capture_output=True, timeout=5)
        return path

    def close(self):
        if self.connection:
            self.connection.close()
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in self.logs:
            log.close()
        self.temporary.cleanup()
