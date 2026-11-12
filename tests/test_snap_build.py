import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SnapBuildTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('snap_build', ROOT / 'scripts/snap_build.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temporary = tempfile.TemporaryDirectory(prefix='snap build ')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.build = self.base / 'build directory'
        self.home = self.base / 'home directory'

    def run_build(self, *extra):
        return self.module.main(['--build-dir', str(self.build), '--target-home', str(self.home), *extra])

    @patch('subprocess.run')
    def test_default_build_does_not_install_or_activate(self, run):
        self.assertEqual(self.run_build(), 0)
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], ['meson', 'setup', str(self.build), str(self.module.SOURCE),
                                  '--prefix', str(self.home / '.local'), '--libdir', 'lib'])
        self.assertEqual(calls[1], ['meson', 'compile', '-C', str(self.build)])
        self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))

    @patch('subprocess.run')
    def test_install_requires_explicit_flag(self, run):
        self.assertEqual(self.run_build('--install'), 0)
        self.assertEqual(run.call_args_list[-1].args[0],
                         ['meson', 'install', '-C', str(self.build), '--no-rebuild'])

    @patch('subprocess.run')
    def test_existing_meson_build_is_reconfigured(self, run):
        private = self.build / 'meson-private'
        private.mkdir(parents=True)
        (private / 'coredata.dat').touch()
        self.run_build()
        self.assertIn('--reconfigure', run.call_args_list[0].args[0])

    @patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, ['meson']))
    def test_build_failure_never_installs(self, run):
        self.assertEqual(self.run_build('--install'), 1)
        self.assertEqual(run.call_count, 1)

    @patch('subprocess.run')
    def test_source_directory_cannot_be_build_directory(self, run):
        with self.assertRaises(SystemExit):
            self.module.main(['--build-dir', str(self.module.SOURCE)])
        run.assert_not_called()

    @patch('subprocess.run')
    def test_root_home_is_rejected(self, run):
        with self.assertRaises(SystemExit):
            self.module.main(['--build-dir', str(self.build), '--target-home', '/'])
        run.assert_not_called()
