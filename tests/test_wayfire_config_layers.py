import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

LIB = Path(__file__).resolve().parents[1] / 'modules/wayfire/files/.local/lib'
sys.path.insert(0, str(LIB))
from wayfire_config import merge, overrides, sync


class LayerTests(unittest.TestCase):
    def test_merge_preserves_case_commands_colors_and_comments(self):
        base = b'# themed: surface\n[core]\nplugins = alpha move\nbackground = \\#123456ff\n[command]\ncommand_Test = echo 100% # literal\n'
        user = b'[core]\nplugins = alpha move orbit\n[command]\ncommand_Test = echo user%\n[output:HDMI-A-1]\nmode = mirror eDP-1\n'
        result = merge(base, user).decode()
        self.assertIn('# themed: surface', result)
        self.assertIn('plugins = alpha move orbit', result)
        self.assertIn('command_Test = echo user%', result)
        self.assertIn('background = \\#123456ff', result)
        self.assertIn('[output:HDMI-A-1]', result)
        self.assertEqual(merge(base), base)

    def test_migration_only_extracts_different_values(self):
        result = overrides(b'[core]\na = 1\nb = 2\n', b'[core]\na = 1\nb = 3\n[x]\nc = 4\n')
        self.assertNotIn(b'a =', result)
        self.assertIn(b'b = 3', result)
        self.assertIn(b'[x]', result)

    def test_sync_is_atomic_private_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layer = root / 'wayfire'
            layer.mkdir()
            (layer / 'raccon.ini').write_text('[core]\na = 1\n')
            self.assertTrue(sync(root))
            output = root / 'wayfire.ini'
            stamp = output.stat().st_mtime_ns
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertFalse(sync(root))
            self.assertEqual(output.stat().st_mtime_ns, stamp)
            (layer / 'user.ini').write_text('[core]\na = 2\n')
            self.assertTrue(sync(root))
            self.assertIn('a = 2', output.read_text())
            (layer / 'user.ini').write_text('broken')
            with self.assertRaises(ValueError):
                sync(root)
            self.assertIn('a = 2', output.read_text())

    def test_watcher_recovers_after_invalid_and_atomic_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layer = root / 'wayfire'
            layer.mkdir()
            (layer / 'raccon.ini').write_text('[core]\na = 1\n')
            env = {**os.environ, 'PYTHONPATH': str(LIB), 'XDG_CONFIG_HOME': directory}
            proc = subprocess.Popen([sys.executable, '-m', 'wayfire_config', 'watch'], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.wait_for(lambda: (root / 'wayfire.ini').exists())
                (layer / 'user.ini').write_text('broken')
                time.sleep(.05)
                replacement = layer / 'replacement'
                replacement.write_text('[core]\na = 3\n')
                replacement.replace(layer / 'user.ini')
                self.wait_for(lambda: 'a = 3' in (root / 'wayfire.ini').read_text())
                self.assertIsNone(proc.poll())
            finally:
                proc.terminate()
                proc.wait(timeout=3)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail('Watcher did not update configuration')

    def test_user_override_wins_duplicate_base_options(self):
        result = merge(b'[core]\na = 1\na = 2\n', b'[core]\na = 3\n')
        self.assertNotIn(b'a = 2', result)
        self.assertEqual(result.count(b'a = 3'), 2)

    def test_set_options_preserves_other_user_settings(self):
        from wayfire_config import set_options
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layer = root / 'wayfire'
            layer.mkdir()
            (layer / 'raccon.ini').write_text('[pixdecor]\nborder_size = 1\n')
            (layer / 'user.ini').write_text('# personal\n[output:eDP-1]\nmode = auto\n')
            set_options(root, 'pixdecor', {'border_size': 4})
            self.assertIn('border_size = 4', (root / 'wayfire.ini').read_text())
            self.assertIn('# personal', (layer / 'user.ini').read_text())
            self.assertIn('[output:eDP-1]', (layer / 'user.ini').read_text())
