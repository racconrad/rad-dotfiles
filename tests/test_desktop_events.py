"""Real inotify/FIFO integration and native terminal lifecycle event regressions."""
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'modules/base/files/.local/lib'
DESKTOP = ROOT/'modules/desktop/files/.local/lib'
STYLE = ROOT/'modules/desktop-styles/files/.local/lib'
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(DESKTOP))
from raccon_events import FileEvents


class Lines:
    def __init__(self, process):
        self.process = process
        self.buffer = b''

    def get(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            ready, _, _ = select.select([self.process.stdout], [], [], max(0, deadline-time.monotonic()))
            if not ready:
                raise AssertionError('No state received before deadline')
            data = os.read(self.process.stdout.fileno(), 65536)
            if not data:
                raise AssertionError('Listener exited: ' + self.process.stderr.read().decode())
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def until(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while True:
            value = self.get(max(0, deadline-time.monotonic()))
            if predicate(value):
                return value

    def quiet(self):
        return not self.buffer and not select.select([self.process.stdout], [], [], .08)[0]


class FileEventTests(unittest.TestCase):
    def test_atomic_replace_delete_recreate_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root);target = root/'state.json'
            with FileEvents([target]) as changes:
                (root/'other').write_text('ignored')
                self.assertEqual(changes.wait(.02), set())
                for value in ('first', 'second'):
                    temp = root/'.temporary';temp.write_text(value);temp.replace(target)
                    self.assertEqual(changes.wait(.2), {target})
                target.unlink()
                self.assertEqual(changes.wait(.2), {target})
                target.write_text('recreated')
                self.assertEqual(changes.wait(.2), {target})
                self.assertEqual(changes.wait(.02), set())

    def test_idle_wait_blocks_and_decoder_completion_wakes_it(self):
        with tempfile.TemporaryDirectory() as root, FileEvents([Path(root)/'request']) as changes:
            done = threading.Event()
            worker = threading.Thread(target=lambda: (changes.wait(), done.set()), daemon=True)
            worker.start()
            self.assertFalse(done.wait(.04))
            changes.wake()
            self.assertTrue(done.wait(1))
            worker.join()


class ListenerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {**os.environ, 'HOME':str(self.home), 'XDG_RUNTIME_DIR':str(self.home/'run'),
                    'XDG_CACHE_HOME':str(self.home/'cache'), 'WALLPAPER_DIR':str(self.home/'walls'),
                    'PYTHONPATH':os.pathsep.join(map(str, (BASE, DESKTOP, STYLE)))}
        (self.home/'run').mkdir();(self.home/'walls').mkdir()

    def start(self, code=None, args=None):
        process = subprocess.Popen([sys.executable, '-u', '-c', code] if code else args,
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:process.terminate()
            process.communicate(timeout=3)
        self.addCleanup(cleanup)
        return Lines(process)

    def atomic(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name('.incoming');temp.write_text(json.dumps(value));temp.replace(path)

    def test_style_emits_atomic_changes_and_suppresses_duplicates(self):
        state = self.home/'.local/state/desktop-style/ui.json'
        self.atomic(state, {'selected':'modern'})
        output = self.start("from desktop_style import main as s;s.refresh_previews=lambda:None;s.watch()")
        self.assertEqual(output.get()['selected'], 'modern')
        self.assertTrue(output.quiet())
        self.atomic(state, {'selected':'retro'})
        self.assertEqual(output.get()['selected'], 'retro')
        self.atomic(state, {'selected':'retro'})
        self.assertTrue(output.quiet())

    def test_preview_updates_and_stops_immediately_from_file_events(self):
        path = self.home/'cache/raccon-float/preview/state.json'
        output = self.start("from raccon_menu.wall_preview import watch;watch()")
        self.assertFalse(output.get()['active'])
        self.atomic(path, {'active':True,'selection':'a','frames':['/tmp/preview/001.jpg']})
        self.assertEqual(output.get()['clip'], '/tmp/preview')
        self.atomic(path, {'active':False})
        self.assertFalse(output.get()['active'])
        self.assertTrue(output.quiet())

    def test_idle_gallery_wakes_on_new_filter_without_a_decoder(self):
        output = self.start("from raccon_menu.walls import watch_gallery;watch_gallery()")
        self.assertFalse(output.get()['loading'])
        self.assertTrue(output.quiet())
        request = self.home/'run/raccon-float-gallery.json'
        self.atomic(request, dict(section='videos', page=None, token='new-filter'))
        self.assertEqual(output.get()['section'], 'videos')
        self.assertTrue(output.quiet())

    def test_gallery_updates_current_tile_when_wallpaper_cache_changes(self):
        import hashlib
        image=self.home/'walls/image.png';image.touch()
        thumbs=self.home/'cache/raccon-float/thumbs';thumbs.mkdir(parents=True)
        (thumbs/(hashlib.sha1(str(image).encode()).hexdigest()+'.png')).write_bytes(b'cached')
        output=self.start("from raccon_menu.walls import watch_gallery;watch_gallery()")
        first=output.get()['rows'][0]['tiles'][0]
        self.assertFalse(first['current'])
        current=self.home/'cache/current-wallpaper';current.write_text(str(image)+'\n')
        updated=output.until(lambda value:value['rows'][0]['tiles'][0]['current'])
        self.assertTrue(updated['rows'][0]['tiles'][0]['current'])
        self.assertTrue(output.quiet())

    def test_music_four_subscribers_share_one_player_and_follow_card_flag(self):
        bindir = self.home/'bin';bindir.mkdir()
        control = self.home/'control';os.mkfifo(control)
        log = self.home/'players'
        fake = bindir/'playerctl'
        fake.write_text('#!'+sys.executable+'\n'+
                        'import os,sys\n'+
                        f'with open({str(log)!r},"a") as f:f.write(str(os.getpid())+"\\n")\n'+
                        'print("Playing",flush=True)\n'+
                        f'fd=os.open({str(control)!r},os.O_RDWR)\n'+
                        'with os.fdopen(fd) as f:\n'+
                        ' for line in f:\n'+
                        '  if line.strip()=="quit":break\n'+
                        '  print(line.strip(),flush=True)\n')
        fake.chmod(0o755)
        self.env['PATH'] = str(bindir)+os.pathsep+self.env['PATH']
        provider = self.home/'run/raccon-waybar-music/provider.pid'
        # Cleanup runs after the subscribers, allowing the provider to release its child.
        def cleanup_provider():
            if provider.exists():
                try:os.kill(int(provider.read_text()), signal.SIGTERM)
                except ProcessLookupError:pass
        self.addCleanup(cleanup_provider)
        outputs = [self.start(args=[sys.executable, str(DESKTOP/'raccon_music_status.py'), mode])
                   for mode in ('open','prev','play','next')]
        for output in outputs:
            self.assertEqual(output.until(lambda value:value.get('class')=='playing')['class'], 'playing')
        self.assertEqual(len(log.read_text().splitlines()), 1)
        flag = self.home/'run/raccon-music.open';flag.touch()
        for output in outputs:self.assertEqual(output.get(), {'text':''})
        flag.unlink()
        for output in outputs:self.assertEqual(output.get()['class'], 'playing')
        with control.open('w') as stream:stream.write('Paused\n')
        for output in outputs:self.assertEqual(output.get()['class'], 'paused')
        self.assertTrue(all(output.quiet() for output in outputs))
        # A provider restart reconnects all subscribers to a single new follower.
        os.kill(int(provider.read_text()), signal.SIGTERM)
        for output in outputs:self.assertEqual(output.get(), {'text':''})
        for output in outputs:output.until(lambda value:value.get('class')=='playing', timeout=4)
        self.assertEqual(len(log.read_text().splitlines()), 2)
        # Player exit restarts just the shared follower and clears all controls.
        with control.open('w') as stream:stream.write('quit\n')
        for output in outputs:self.assertEqual(output.get(), {'text':''})
        for output in outputs:output.until(lambda value:value.get('class')=='playing', timeout=4)
        self.assertEqual(len(log.read_text().splitlines()), 3)
        # Last subscriber disappearing releases the provider and its player.
        for output in outputs:
            output.process.terminate();output.process.wait(timeout=2)
        deadline = time.monotonic()+4
        while provider.exists() and time.monotonic()<deadline:time.sleep(.03)
        self.assertFalse(provider.exists())
        self.assertFalse(list(provider.parent.glob('client-*')))


class TerminalEventTests(unittest.TestCase):
    def test_native_focus_minimize_and_exit_refresh_without_polling(self):
        spec = importlib.util.spec_from_file_location('event_terminal', ROOT/'modules/kitty/files/.local/lib/raccon_terminal.py')
        terminal = importlib.util.module_from_spec(spec);spec.loader.exec_module(terminal)
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root/'state.json').write_text(json.dumps(dict(visible=True,view_id=17)))
            (root/'intent.json').write_text(json.dumps(dict(target='visible',seq=4)))
            panel = Mock();panel.state=root/'state.json';panel.intent=root/'intent.json'
            panel.wf.return_value={'info':{'id':17}}
            messages = iter([dict(event='view-unmapped',view={'id':88,'parent':17}),
                             dict(event='view-focused',view={'id':99}),
                             dict(event='view-minimized',view={'id':17}),
                             dict(event='view-unmapped',view={'id':17})])
            class Events:
                def __init__(self):self.sock=Mock()
                def __call__(self,*args):self.subscription=args
                def receive(self):return next(messages)
                def close(self):pass
            with patch.object(terminal,'RUNTIME',root), patch.object(terminal,'Panel',return_value=panel), \
                 patch.object(terminal,'Wayfire',Events), patch.object(terminal,'notify_waybar') as notify:
                terminal.watch_focus()
            panel.command.assert_called_once_with('hide',expected_seq=4)
            panel.alive.assert_called_once_with()
            self.assertEqual(notify.call_count,2)
            # Exit before subscription startup must still clear the bar once.
            panel.reset_mock();panel.alive.return_value=False
            with patch.object(terminal,'RUNTIME',root), patch.object(terminal,'Panel',return_value=panel), \
                 patch.object(terminal,'Wayfire',Events), patch.object(terminal,'notify_waybar') as notify:
                terminal.watch_focus()
            panel.alive.assert_called_once_with()
            panel.wf.assert_not_called()
            notify.assert_called_once_with()

    def test_installed_terminal_modules_update_on_dedicated_signal(self):
        import re
        path = ROOT/'modules/waybar/files/.config/waybar/config.jsonc'
        config = json.loads(re.sub(r'^\s*//.*$', '', path.read_text(), flags=re.M))
        for name in ('custom/quick-terminal','custom/quick-terminal-hide','custom/quick-terminal-close'):
            self.assertEqual(config[name]['interval'],'once')
            self.assertEqual(config[name]['signal'],9)
