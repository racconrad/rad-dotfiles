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

if __name__ == '__main__':
    unittest.main()
