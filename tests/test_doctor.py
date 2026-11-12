"""Receipt-driven diagnostics never start or restart desktop processes."""
import hashlib
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import install
import master


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()

    def receipt(self, modules, files=None):
        records = {}
        for relative, text in (files or {}).items():
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            path.chmod(0o644)
            records[relative] = {'sha256': hashlib.sha256(text.encode()).hexdigest(), 'mode': 0o644}
        (self.home / '.rdot').write_text(json.dumps({**install.RELEASE, 'modules': modules, 'files': records}))

    def executable(self, name):
        path = self.bin / name
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(0o755)

    def report(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'PATH': str(self.bin)}), redirect_stdout(output):
            result = master.run_doctor(self.home, ROOT, as_json=True)
        return result, json.loads(output.getvalue())['checks']

    def test_minimal_install_checks_only_installed_components(self):
        self.receipt(['kitty'], {'.config/kitty/kitty.conf': 'font_size 12'})
        self.executable('kitty')
        result, checks = self.report()
        self.assertEqual(result, 0)
        self.assertTrue(any(c['name'] == 'kitty' and c['status'] == 'ok' for c in checks))
        self.assertFalse(any('Wayfire' in c['name'] for c in checks))
        self.assertFalse(any('package' in c['name'].lower() for c in checks))
        self.assertTrue(all(c['status'] == 'ok' for c in checks))

    def test_missing_executable_and_managed_file_fail(self):
        self.receipt(['kitty'], {'.config/kitty/kitty.conf': 'config'})
        (self.home / '.config/kitty/kitty.conf').unlink()
        result, checks = self.report()
        self.assertEqual(result, 1)
        self.assertTrue(any(c['name'] == 'Managed files' and c['status'] == 'fail' for c in checks))
        self.assertTrue(any(c['name'] == 'kitty' and c['status'] == 'fail' for c in checks))
        self.assertTrue(any('.config/kitty/kitty.conf' in c['detail'] and c['status'] == 'fail' for c in checks))

    def test_modified_config_warns_without_inventing_reload_requirement(self):
        self.receipt(['base'], {'.config/example': 'original'})
        (self.home / '.config/example').write_text('local edit')
        result, checks = self.report()
        self.assertEqual(result, 0)
        self.assertTrue(any(c['status'] == 'warn' and 'modified' in c['detail'].lower() for c in checks))
        self.assertFalse(any('needs-reload' in c['detail'] for c in checks))

    def test_recorded_user_unit_reports_failure_and_verified_reload(self):
        self.receipt(['base'], {'.config/systemd/user/example.service': '[Service]\nExecStart=/bin/false\n'})
        self.executable('systemctl')
        completed = subprocess.CompletedProcess([], 0, 'ActiveState=failed\nResult=exit-code\nNeedDaemonReload=yes\n', '')
        with patch('subprocess.run', return_value=completed) as run:
            result, checks = self.report()
        self.assertEqual(result, 1)
        self.assertTrue(any(c['status'] == 'fail' and 'exit-code' in c['detail'] for c in checks))
        self.assertTrue(any(c['status'] == 'warn' and 'needs-reload' in c['detail'] for c in checks))
        self.assertTrue(all(call.args[0][1:3] == ['--user', 'show'] for call in run.call_args_list))

    def test_unavailable_user_bus_is_unknown_not_healthy(self):
        self.receipt(['base'], {'.config/systemd/user/example.service': '[Service]'})
        self.executable('systemctl')
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'No user bus')):
            result, checks = self.report()
        self.assertEqual(result, 0)
        self.assertTrue(any(c['status'] == 'warn' and 'unknown' in c['detail'].lower() for c in checks))

    def test_no_receipt_does_not_claim_components_are_installed(self):
        result, checks = self.report()
        self.assertEqual(result, 0)
        self.assertTrue(any(c['status'] == 'warn' and 'receipt' in c['detail'].lower() for c in checks))
        self.assertFalse(any(c['status'] == 'ok' for c in checks))


    def test_desktop_runtime_and_resolved_alternative_executables_are_checked(self):
        self.receipt(['desktop', 'desktop-styles', 'fish', 'chromium', 'thunar'])
        for name in ('eww', 'python3', 'fish', 'chromium', 'thunar'):
            self.executable(name)
        result, checks = self.report()
        checked = {c['name'] for c in checks if c['category'] == 'Executables'}
        self.assertEqual(result, 0)
        self.assertTrue({'eww', 'python3', 'fish', 'chromium', 'thunar'} <= checked)
        self.assertFalse({'kitty', 'firefox', 'dolphin', 'zsh'} & checked)


    def test_missing_native_rebuild_tools_warn_without_claiming_runtime_failure(self):
        self.receipt(['desktop'])
        self.executable('eww')
        self.executable('python3')
        result, checks = self.report()
        self.assertEqual(result, 0)
        self.assertTrue(any(c['name'] == 'cc' and c['status'] == 'warn' and 'rebuild' in c['detail'] for c in checks))
        self.assertTrue(any(c['name'] == 'pkg-config' and c['status'] == 'warn' for c in checks))

    def test_selected_waybar_process_observation_is_not_functional_health_claim(self):
        self.receipt(['waybar'])
        self.executable('waybar')
        with patch('pathlib.Path.home', return_value=self.home), \
                patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-test'}), \
                patch('doctor.observe_processes', return_value=({'waybar'}, False)):
            result, checks = self.report()
        runtime = [c for c in checks if c['category'] == 'Runtime']
        self.assertEqual(result, 0)
        self.assertEqual(len(runtime), 1)
        self.assertEqual(runtime[0]['status'], 'ok')
        self.assertIn('process observed', runtime[0]['detail'])
        self.assertIn('not functional health proof', runtime[0]['detail'])

    def test_stopped_waybar_is_reported_only_in_current_wayland_home(self):
        self.receipt(['waybar'])
        self.executable('waybar')
        with patch('pathlib.Path.home', return_value=self.home), \
                patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-test'}), \
                patch('doctor.observe_processes', return_value=(set(), False)):
            result, checks = self.report()
        self.assertEqual(result, 0)
        self.assertTrue(any(c['category'] == 'Runtime' and c['status'] == 'warn'
                            and c['detail'] == 'Not running.' for c in checks))

    def test_foreign_home_runtime_is_not_probed(self):
        self.receipt(['waybar', 'widgets'])
        with patch('pathlib.Path.home', return_value=self.home / 'other'), \
                patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-test'}), \
                patch('doctor.observe_processes') as observe:
            _, checks = self.report()
        observe.assert_not_called()
        runtime = [c for c in checks if c['category'] == 'Runtime']
        self.assertEqual(len(runtime), 1)
        self.assertIn('Unknown', runtime[0]['detail'])

    def test_inaccessible_proc_is_unknown_not_stopped(self):
        self.receipt(['wayfire'])
        with patch('pathlib.Path.home', return_value=self.home), \
                patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-test'}), \
                patch('doctor.observe_processes', return_value=(set(), True)):
            _, checks = self.report()
        self.assertTrue(any(c['category'] == 'Runtime' and 'Unknown' in c['detail'] for c in checks))

    def test_without_wayland_session_runtime_is_not_probed(self):
        self.receipt(['waybar'])
        with patch('pathlib.Path.home', return_value=self.home), \
                patch.dict(os.environ, {'WAYLAND_DISPLAY': ''}), \
                patch('doctor.observe_processes') as observe:
            _, checks = self.report()
        observe.assert_not_called()
        self.assertTrue(any(c['category'] == 'Runtime' and 'not probed' in c['detail'] for c in checks))

    def test_process_observation_reads_only_current_uid_process_names(self):
        import doctor
        proc = self.home / 'proc'
        (proc / '123').mkdir(parents=True)
        (proc / '123/comm').write_text('waybar\n')
        (proc / 'gone').mkdir()
        observed, incomplete = doctor.observe_processes(proc)
        self.assertEqual(observed, {'waybar'})
        self.assertFalse(incomplete)
        with patch('doctor.os.getuid', return_value=-1):
            self.assertEqual(doctor.observe_processes(proc), (set(), False))

    def test_unavailable_proc_mount_is_unknown(self):
        import doctor
        self.assertEqual(doctor.observe_processes(self.home / 'absent-proc'), (set(), True))
