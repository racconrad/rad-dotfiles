"""Prepare real login assets in a disposable home; never elevate or alter SDDM."""
import configparser
import fcntl
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT/'modules/desktop-styles/files'
spec = importlib.util.spec_from_file_location('sddm_styles', FILES/'.local/lib/desktop_style/main.py')
styles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(styles)
run_process = subprocess.run


class SddmButtonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='sddm button ')
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        for name, value in (('HOME', self.home), ('STATE', self.home/'state'),
                            ('CURRENT', self.home/'current'), ('CONFIG', self.home/'config')):
            p = patch.object(styles, name, value)
            p.start(); self.addCleanup(p.stop)
        self.assets = self.home/'.local/share/raccon/sddm'
        shutil.copytree(FILES/'.local/share/raccon/sddm', self.assets)
        self.tokens = dict(style='retro', font='Silkscreen', radius=0, border=2, strict=True,
                           colors={'primary': '#abcdef', 'background': '#123456'})
        # The installed preparer reads the real portable location.
        styles.save(self.home/'.config/desktop-style/current/tokens.json', self.tokens)
        styles.save(styles.CURRENT/'tokens.json', self.tokens)
        styles.save(styles.STATE/'ui.json', dict(selected='retro', current='retro', busy=False))
        runtime = self.home/'runtime'
        self.surface = runtime/'desktop-style'
        self.surface.mkdir(parents=True)
        (self.surface/'visible').write_text('1')
        p = patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(runtime)})
        p.start(); self.addCleanup(p.stop)
        self.hide = Mock(); self.show = Mock()
        for name, value in (('close_selector', self.hide), ('open_selector', self.show)):
            p = patch.object(styles, name, value)
            p.start(); self.addCleanup(p.stop)
        self.auth_calls = []

    def run_update(self, code=0, error=None):
        def execute(argv, **kwargs):
            if argv[0] != 'pkexec':
                return run_process(argv, **kwargs)
            self.auth_calls.append(argv)
            self.hide.assert_called_once_with()
            state = styles.read(styles.STATE/'ui.json')
            self.assertTrue(state['busy']); self.assertTrue(state['sddm_busy'])
            config = configparser.ConfigParser()
            config.read(Path(argv[-1])/'theme.conf')
            self.assertEqual(config['General']['accent'], '#abcdef')
            self.assertEqual(config['General']['background'], '#123456')
            self.assertEqual(config['General']['radius'], '0')
            self.assertEqual(config['General']['animations'], 'false')
            self.assertTrue((Path(argv[-1])/'assets/font.ttf').is_file())
            if error:
                raise error
            return subprocess.CompletedProcess(argv, code, 'Backup: /var/backups/test\n', '')
        with patch.object(styles.shutil, 'which', return_value='/usr/bin/pkexec'), \
             patch.object(styles.subprocess, 'run', side_effect=execute):
            styles.apply_sddm()
        return styles.read(styles.STATE/'ui.json')

    def test_real_snapshot_authentication_and_success(self):
        state = self.run_update()
        self.assertIn('next login', state['notice'])
        self.assertFalse(state['busy']); self.assertFalse(state['sddm_busy'])
        self.show.assert_called_once_with()
        self.assertFalse(Path(self.auth_calls[0][-1]).exists())
        self.assertIn('Backup:', (styles.STATE/'sddm.log').read_text())
        self.assertEqual(self.auth_calls[0][1:3], ['/usr/bin/bash', str(self.assets/'apply.sh')])

    def test_cancellation_failure_and_timeout_release_busy_and_return(self):
        for code, error, expected in ((126, None, 'canceled'), (127, None, 'Authentication failed'),
                                     (1, None, 'Could not update'),
                                     (0, subprocess.TimeoutExpired('pkexec', 300), 'timed out')):
            with self.subTest(code=code, expected=expected):
                self.hide.reset_mock(); self.show.reset_mock()
                state = self.run_update(code, error)
                self.assertIn(expected, state['notice'])
                self.assertFalse(state['busy']); self.assertFalse(state['sddm_busy'])
                self.show.assert_called_once_with()

    def test_unapplied_style_never_requests_authentication(self):
        (styles.CURRENT/'tokens.json').unlink()
        with patch.object(styles.subprocess, 'run', side_effect=AssertionError('Unexpected elevation')):
            styles.apply_sddm()
        self.assertIn('Apply a desktop style', styles.read(styles.STATE/'ui.json')['notice'])
        self.hide.assert_not_called()

    def test_missing_assets_never_requests_authentication(self):
        (self.assets/'apply.sh').unlink()
        styles.apply_sddm()
        self.assertIn('reinstall', styles.read(styles.STATE/'ui.json')['notice'])
        self.hide.assert_not_called()

    def test_competing_theme_update_keeps_original_state(self):
        before = styles.read(styles.STATE/'ui.json')
        with (styles.STATE/'apply.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            styles.apply_sddm()
        self.assertEqual(before, styles.read(styles.STATE/'ui.json'))
        self.hide.assert_not_called()


if __name__ == '__main__':
    unittest.main()
