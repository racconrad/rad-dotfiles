"""Selective configuration refreshes preserve unrelated files and preferences."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import install as installer


class ModuleUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir()
        self.selection = installer.load_selection(self.home)
        self.choices = self.selection['choices']
        with redirect_stdout(io.StringIO()):
            installer.apply_plan(self.home, {'.config/unrelated': (b'keep', 0o600)},
                                 ['waybar', 'base', 'desktop'], self.choices, self.selection)
        self.receipt = installer.read_receipt(self.home)
        self.profile = (self.home / '.config/raccon-dots/profile.json').read_bytes()

    def run_update(self, *extra):
        with redirect_stdout(io.StringIO()), patch.object(installer, 'install_packages') as packages, \
                patch.object(installer, 'run_setup') as setup:
            result = installer.main(['--update', '--modules', 'waybar', '--target', str(self.home), '--yes', *extra])
            packages.assert_not_called()
            setup.assert_not_called()
            return result

    def test_only_selected_module_is_copied_and_receipt_is_merged(self):
        self.assertEqual(self.run_update(), 0)
        self.assertTrue((self.home / '.config/waybar/config.jsonc').is_file())
        self.assertFalse((self.home / '.local/bin/desktop-menu').exists())
        self.assertEqual((self.home / '.config/unrelated').read_bytes(), b'keep')
        receipt = installer.read_receipt(self.home)
        self.assertEqual(receipt['modules'], self.receipt['modules'])
        self.assertEqual(receipt['selection'], self.receipt['selection'])
        self.assertEqual(receipt['files']['.config/unrelated'], self.receipt['files']['.config/unrelated'])
        self.assertEqual((self.home / '.config/raccon-dots/profile.json').read_bytes(), self.profile)

    def test_dry_run_does_not_write(self):
        before = (self.home / '.rdot').read_bytes()
        self.assertEqual(self.run_update('--dry-run'), 0)
        self.assertEqual((self.home / '.rdot').read_bytes(), before)
        self.assertFalse((self.home / '.config/waybar').exists())

    def test_update_is_idempotent(self):
        self.run_update()
        before = (self.home / '.rdot').read_bytes()
        self.run_update()
        self.assertEqual((self.home / '.rdot').read_bytes(), before)

    def test_update_rejects_uninstalled_module_before_writing(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            installer.main(['--update', '--modules', 'nvim', '--target', str(self.home), '--yes'])
        self.assertFalse((self.home / '.config/nvim').exists())

    def test_conflicting_update_options_are_rejected(self):
        for option in ('--packages', '--setup=none', '--widget-install=configure'):
            with self.subTest(option=option), redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                installer.main(['--update', '--modules', 'waybar', '--target', str(self.home), '--yes', option])

    def test_changed_files_have_a_restorable_backup(self):
        path = self.home / '.config/waybar/config.jsonc'
        path.parent.mkdir(parents=True)
        path.write_text('custom configuration')
        before = (self.home / '.rdot').read_bytes()
        self.run_update('--force-update')
        backups = sorted((self.home / '.local/state/raccon-dots/backups').iterdir())
        backup = next(p for p in reversed(backups)
                      if any(f['path'] == '.config/waybar/config.jsonc'
                             for f in json.loads((p / 'manifest.json').read_text())['files']))
        with redirect_stdout(io.StringIO()):
            installer.restore(backup, self.home)
        self.assertEqual(path.read_text(), 'custom configuration')
        self.assertEqual((self.home / '.rdot').read_bytes(), before)


class UpdateSafetyTests(ModuleUpdateTests):
    def test_local_edits_are_blocked_and_force_keeps_backup(self):
        self.run_update()
        path = self.home / '.config/waybar/config.jsonc'
        path.write_text('local edit')
        with self.assertRaisesRegex(ValueError, 'locally modified'):
            self.run_update()
        self.assertEqual(path.read_text(), 'local edit')
        self.assertEqual(self.run_update('--force-update'), 0)
        self.assertNotEqual(path.read_text(), 'local edit')

    def test_untracked_existing_destination_is_protected(self):
        path = self.home / '.config/waybar/config.jsonc'
        path.parent.mkdir(parents=True)
        path.write_text('untracked config')
        with self.assertRaisesRegex(ValueError, 'locally modified'):
            self.run_update()
        self.assertEqual(path.read_text(), 'untracked config')

    def test_changed_paths_are_shown_without_files_flag(self):
        output = io.StringIO()
        with redirect_stdout(output):
            installer.main(['--update', '--modules', 'waybar', '--target', str(self.home), '--dry-run'])
        self.assertIn('.config/waybar/config.jsonc', output.getvalue())

    def test_no_module_selection_requires_terminal(self):
        with patch('sys.stdin.isatty', return_value=False), self.assertRaisesRegex(ValueError, '--modules'):
            installer.main(['--update', '--target', str(self.home), '--yes'])

    def test_interactive_picker_only_updates_chosen_installed_module(self):
        with patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=False), \
                patch('builtins.input', side_effect=['3', 'v', 'y']), redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(['--update', '--target', str(self.home), '--plain']), 0)
        self.assertTrue((self.home / '.config/waybar/config.jsonc').exists())
        self.assertFalse((self.home / '.local/bin/desktop-menu').exists())

    def test_apply_rejects_edit_made_after_preview(self):
        path = self.home / '.config/unrelated'
        baseline = {'.config/unrelated': installer.digest(path)}
        path.write_text('concurrent edit')
        with self.assertRaisesRegex(ValueError, 'changed'):
            installer.apply_plan(self.home, {'.config/unrelated': (b'update', 0o600)},
                                 ['base'], self.choices, partial=True, expected=baseline)
        self.assertEqual(path.read_text(), 'concurrent edit')


    def test_force_flag_cannot_bypass_regular_installation(self):
        with redirect_stdout(io.StringIO()), patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            installer.main(['--force-update', '--target', str(self.home), '--yes'])
        self.assertFalse((self.home / '.config/waybar').exists())

    def test_picker_cancel_does_not_write(self):
        before = (self.home / '.rdot').read_bytes()
        with patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=False), \
                patch('builtins.input', return_value='q'), redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(['--update', '--target', str(self.home), '--plain']), 0)
        self.assertEqual((self.home / '.rdot').read_bytes(), before)

    def test_mode_only_local_change_is_protected(self):
        self.run_update()
        path = self.home / '.config/waybar/config.jsonc'
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'locally modified'):
            self.run_update()
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)


    def test_receipt_change_during_picker_aborts_update(self):
        actions = iter(['3', 'v', 'y'])
        def choose(*_):
            action = next(actions)
            if action == 'v':
                receipt = installer.read_receipt(self.home)
                receipt['modules'] = ['base']
                (self.home / '.rdot').write_text(json.dumps(receipt))
            return action
        with patch('sys.stdin.isatty', return_value=True), patch('sys.stdout.isatty', return_value=False), \
                patch('builtins.input', side_effect=choose), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'changed'):
                installer.main(['--update', '--target', str(self.home), '--plain'])
        self.assertFalse((self.home / '.config/waybar/config.jsonc').exists())
