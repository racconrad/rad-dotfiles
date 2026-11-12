"""Verify native floating-card residency without a compositor."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MusicVisibilityTests(unittest.TestCase):
    def test_hidden_music_stops_its_player_follower(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            binary = home / 'bin'
            binary.mkdir()
            player = binary / 'playerctl'
            player.write_text('#!' + sys.executable + '''
import os, pathlib, signal, time
log = pathlib.Path(os.environ['HOME']) / 'player-events'
with log.open('a') as out: out.write('started\\n')
def stop(*args):
    with log.open('a') as out: out.write('stopped\\n')
    raise SystemExit()
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(1)
''')
            player.chmod(0o755)
            env = {**os.environ, 'HOME': str(home), 'XDG_RUNTIME_DIR': str(home),
                   'PATH': str(binary) + os.pathsep + os.environ['PATH'],
                   'PYTHONPATH': str(ROOT / 'modules/base/files/.local/lib')}
            script = ROOT / 'modules/desktop/files/.local/lib/raccon_menu/music.py'
            child = subprocess.Popen([sys.executable, str(script)], env=env, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(json.loads(child.stdout.readline())['visible'], False)
                import time
                time.sleep(.1)
                log = home / 'player-events'
                self.assertFalse(log.exists())
                flag = home / 'raccon-music.open'
                flag.touch()
                deadline = time.monotonic() + 2
                while not log.exists() and time.monotonic() < deadline: time.sleep(.01)
                self.assertEqual(log.read_text().splitlines(), ['started'])
                flag.unlink()
                deadline = time.monotonic() + 2
                while 'stopped' not in log.read_text() and time.monotonic() < deadline: time.sleep(.01)
                self.assertEqual(log.read_text().splitlines(), ['started', 'stopped'])
            finally:
                child.terminate()
                child.communicate(timeout=3)
