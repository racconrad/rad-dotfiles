"""Exercise card preparation and resident reuse without a compositor."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'modules/desktop/files/.local/bin'


class CardPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        binary = self.home / 'bin'
        binary.mkdir()
        lib = self.home / '.local/lib/raccon_menu'
        lib.mkdir(parents=True)
        for name in ('walls.py', 'wall_preview.py', 'backend.py'):
            (lib / name).touch()
        (lib.parent / 'raccon_events.py').touch()
        cache = self.home / '.cache/raccon-float'
        cache.mkdir(parents=True)
        module = cache / 'keyboard.so'
        module.touch()
        shutil.copy(ROOT / 'modules/desktop/files/.local/lib/raccon_menu/card_wait.py', lib / 'card_wait.py')
        shutil.copy(ROOT / 'modules/base/files/.local/lib/raccon_events.py', lib.parent / 'raccon_events.py')
        (lib / 'keyboard_build.py').write_text(f'print({str(module)!r})\n')
        self.log = self.home / 'commands'
        fake = binary / 'eww'
        fake.write_text('#!' + sys.executable + '''
import json, os, pathlib, sys
home = pathlib.Path(os.environ['HOME'])
args = sys.argv[1:]
config = args[args.index('-c') + 1]
args = args[args.index('-c') + 2:]
statefile = home / (pathlib.Path(config).name + '.json')
state = json.loads(statefile.read_text()) if statefile.exists() else {'windows': [], 'shown': 'false', 'session_visible': 'false', 'card_visible': 'false'}
with (home / 'commands').open('a') as log: log.write(json.dumps([pathlib.Path(config).name, *args]) + '\\n')
command = args[0]
if command == 'active-windows':
    print('\\n'.join(name + ': ' + name for name in state['windows']))
elif command == 'get': print(state.get(args[1], 'false'))
elif command == 'update':
    for value in args[1:]:
        key, value = value.split('=', 1); state[key] = value
elif command == 'open':
    if args[1] not in state['windows']: state['windows'].append(args[1])
    name = 'raccon-music.ready' if args[1] == 'raccon-music' else 'raccon-float-session.ready'
    (home / 'run' / name).write_text('1')
elif command == 'close':
    for name in args[1:]:
        if name in state['windows']: state['windows'].remove(name)
statefile.write_text(json.dumps(state))
''')
        fake.chmod(0o755)
        run = self.home / 'run'
        run.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'XDG_RUNTIME_DIR': str(run),
                    'PATH': str(binary) + os.pathsep + os.environ['PATH']}

    def run_card(self, name, *args):
        result = subprocess.run(['bash', str(BIN / name), *args], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_session_prepare_builds_only_hidden_session_and_is_idempotent(self):
        commands = self.run_card('raccon-float', 'prepare')
        self.assertTrue(any(c[1:3] == ['open', 'session'] for c in commands))
        self.assertFalse(any(c[1:3] == ['open', 'wallpaper'] for c in commands))
        state = json.loads((self.home / 'raccon-float.json').read_text())
        self.assertEqual(state['session_visible'], 'false')
        commands = self.run_card('raccon-float', 'prepare')
        self.assertEqual(sum(c[1:3] == ['open', 'session'] for c in commands), 1)

    def test_session_toggle_keeps_prepared_tree(self):
        self.run_card('raccon-float', 'prepare')
        self.run_card('raccon-float', 'session')
        state = json.loads((self.home / 'raccon-float.json').read_text())
        self.assertEqual(state['session_visible'], 'true')
        commands = self.run_card('raccon-float', 'close')
        self.assertFalse(any(c[1:3] == ['close', 'session'] for c in commands))
        self.assertEqual(json.loads((self.home / 'raccon-float.json').read_text())['session_visible'], 'false')

    def test_session_prepare_does_not_hide_an_open_session(self):
        self.run_card('raccon-float', 'session')
        self.run_card('raccon-float', 'prepare')
        self.assertEqual(json.loads((self.home / 'raccon-float.json').read_text())['session_visible'], 'true')

    def test_switching_from_wallpaper_shows_the_prepared_session(self):
        self.run_card('raccon-float', 'prepare')
        self.run_card('raccon-float', 'wallpaper')
        commands = self.run_card('raccon-float', 'session')
        state = json.loads((self.home / 'raccon-float.json').read_text())
        self.assertEqual(state['session_visible'], 'true')
        self.assertEqual(state['windows'], ['session'])
        self.assertEqual(sum(c[1:3] == ['open', 'session'] for c in commands), 1)

    def test_first_click_waits_for_prepare_lock_instead_of_disappearing(self):
        import fcntl
        import time
        for command, argument, key in (('raccon-float', 'session', 'session_visible'),
                                       ('raccon-music', '', 'card_visible')):
            with self.subTest(command=command):
                self.run_card(command, 'prepare')
                lockpath = self.home / f'run/{command}-{os.getuid()}.visibility.lock'
                with lockpath.open('w') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    argv = ['bash', str(BIN / command)] + ([argument] if argument else [])
                    child = subprocess.Popen(argv, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    try:
                        time.sleep(.1)
                        self.assertIsNone(child.poll())
                    finally:
                        fcntl.flock(lock, fcntl.LOCK_UN)
                        _, errors = child.communicate(timeout=3)
                    self.assertEqual(child.returncode, 0, errors)
                state = json.loads((self.home / (command + '.json')).read_text())
                self.assertEqual(state[key], 'true')

    def test_music_prepare_does_not_claim_waybar_visibility(self):
        commands = self.run_card('raccon-music', 'prepare')
        self.assertTrue(any(c[1:3] == ['open', 'raccon-music'] for c in commands))
        self.assertFalse((self.home / 'run/raccon-music.open').exists())
        self.assertEqual(json.loads((self.home / 'raccon-music.json').read_text())['card_visible'], 'false')
        commands = self.run_card('raccon-music', 'prepare')
        self.assertEqual(sum(c[1:3] == ['open', 'raccon-music'] for c in commands), 1)

    def test_new_music_tree_clears_a_stale_visibility_flag(self):
        flag = self.home / 'run/raccon-music.open'
        flag.touch()
        self.run_card('raccon-music', 'prepare')
        self.assertFalse(flag.exists())

    def test_music_prepare_preserves_an_open_card(self):
        self.run_card('raccon-music')
        self.run_card('raccon-music', 'prepare')
        self.assertTrue((self.home / 'run/raccon-music.open').exists())
        state = json.loads((self.home / 'raccon-music.json').read_text())
        self.assertEqual(state['card_visible'], 'true')

    def test_music_rebuilds_only_when_bar_anchor_changes(self):
        self.run_card('raccon-music', 'prepare')
        config = self.home / '.config/waybar/config.jsonc'
        config.parent.mkdir(parents=True)
        config.write_text('{\n  "position": "bottom"\n}')
        commands = self.run_card('raccon-music')
        opens = [c for c in commands if c[1:3] == ['open', 'raccon-music']]
        self.assertEqual(len(opens), 2)
        self.assertIn('anchor=bottom right', opens[-1])
        self.assertIn('y=4px', opens[-1])

    def test_music_toggle_reuses_tree_and_updates_waybar_flag(self):
        self.run_card('raccon-music', 'prepare')
        self.run_card('raccon-music')
        self.assertTrue((self.home / 'run/raccon-music.open').exists())
        state = json.loads((self.home / 'raccon-music.json').read_text())
        self.assertEqual(state['card_visible'], 'true')
        commands = self.run_card('raccon-music', 'close')
        self.assertFalse((self.home / 'run/raccon-music.open').exists())
        self.assertFalse(any(c[1:3] == ['close', 'raccon-music'] for c in commands))


class ReadinessTests(unittest.TestCase):
    def test_wait_observes_native_ready_after_atomic_replacement(self):
        import importlib.util
        import threading
        import time
        sys.path.insert(0, str(ROOT / 'modules/base/files/.local/lib'))
        spec = importlib.util.spec_from_file_location('card_wait', ROOT / 'modules/desktop/files/.local/lib/raccon_menu/card_wait.py')
        waiter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(waiter)
        with tempfile.TemporaryDirectory() as root:
            from unittest.mock import patch
            path = Path(root) / 'test.ready'
            path.write_text('0')
            def complete():
                time.sleep(.05)
                temporary = path.with_suffix('.tmp')
                temporary.write_text('1')
                temporary.replace(path)
            child = threading.Thread(target=complete)
            with patch.dict(os.environ, XDG_RUNTIME_DIR=root):
                child.start()
                waiter.wait_ready('test.ready', timeout=1)
                self.assertEqual(path.read_text(), '1')
                child.join()
                with self.assertRaisesRegex(RuntimeError, 'warmup'):
                    waiter.wait_ready('missing.ready', timeout=.01)
