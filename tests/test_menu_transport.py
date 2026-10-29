"""Exercise the real nonblocking FIFO path without a compositor or Eww process."""
import importlib.util
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True

SOURCE = Path(__file__).resolve().parents[1] / 'modules/desktop/files/.local/lib/raccon_menu'
spec = importlib.util.spec_from_file_location('menu_transport', SOURCE / 'transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.runtime = self.base / 'raccon-menu'
        self.runtime.mkdir()
        self.source = SOURCE / 'input.c'
        (self.runtime / 'revision').write_text(transport.source_revision(self.source))
        (self.runtime / 'mapped').write_text('1')
        os.mkfifo(self.runtime / 'control', 0o600)

    def test_missing_reader_returns_without_blocking(self):
        start = time.monotonic()
        self.assertFalse(transport.send('toggle', str(self.runtime), str(self.source)))
        self.assertLess(time.monotonic() - start, .1)

    def test_old_module_falls_back_instead_of_sending_lost_commands(self):
        (self.runtime / 'revision').write_text('old')
        self.assertFalse(transport.send('toggle', str(self.runtime), str(self.source)))

    def test_warm_cli_only_writes_a_message_and_has_no_eww_dependency(self):
        fd = os.open(self.runtime / 'control', os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, fd)
        env = {**os.environ, 'XDG_RUNTIME_DIR': str(self.base), 'HOME': str(self.base)}
        samples = []
        for _ in range(12):
            started = time.perf_counter()
            result = subprocess.run([sys.executable, str(SOURCE / 'cli.py'), 'modes'],
                env=env, capture_output=True, text=True, timeout=2)
            samples.append((time.perf_counter() - started) * 1000)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(os.read(fd, 256), b'show 2\n')
        print(f'Warm command delivery: median {statistics.median(samples):.1f} ms, max {max(samples):.1f} ms')

    def test_regular_files_are_never_treated_as_a_command_fifo(self):
        (self.runtime / 'control').unlink()
        (self.runtime / 'control').write_text('keep')
        self.assertFalse(transport.send('toggle', str(self.runtime), str(self.source)))
        self.assertEqual((self.runtime / 'control').read_text(), 'keep')

    def test_only_navigation_and_visibility_take_the_warm_path(self):
        self.assertEqual(transport.request(['session']), 'show 3')
        self.assertEqual(transport.request(['audio']), 'show 4')
        self.assertEqual(transport.request(['connections']), 'show 5')
        self.assertEqual(transport.request(['bluetooth']), 'show 6')
        self.assertEqual(transport.request(['tab', 'apps']), 'tab 1')
        self.assertIsNone(transport.request(['tab', 'invalid']))
        self.assertEqual(transport.request(['close']), 'hide')
        self.assertIsNone(transport.request(['session-action', 'poweroff']))
        self.assertIsNone(transport.request(['apply']))


if __name__ == '__main__':
    unittest.main()
