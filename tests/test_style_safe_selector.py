"""The alternate selector must not map or contact the failing Eww window."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


class SafeSelectorTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'modules/desktop-styles/files/.local/lib/desktop_style/main.py'
        spec = importlib.util.spec_from_file_location('safe_styles', source)
        self.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.engine)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        e = self.engine
        e.HOME = Path(temp.name)
        e.CONFIG = e.HOME/'config'
        e.STATE = e.HOME/'state'
        e.save(e.CONFIG/'selector.json', {'backend': 'rofi'})
        e.save(e.STATE/'selection.json', {'style': 'glass'})
        e.eww = Mock(side_effect=AssertionError('Safe selector contacted Eww'))
        e.apply = Mock()
        e.reset = Mock()

    def choose(self, output='', code=0):
        return patch.object(self.engine.subprocess, 'run', return_value=
                            subprocess.CompletedProcess(['rofi'], code, output, ''))

    def test_open_and_toggle_cancel_without_eww_or_theme_changes(self):
        for action in (self.engine.open_selector, self.engine.toggle_selector):
            with self.choose(code=1) as run:
                action()
                self.assertEqual(len(run.call_args.kwargs['input'].splitlines()), 8)
        self.engine.apply.assert_not_called()
        self.engine.reset.assert_not_called()

    def test_valid_selection_applies_only_selected_theme(self):
        with self.choose('2\n'):
            self.engine.open_selector()
        self.engine.apply.assert_called_once_with('retro')
        self.engine.reset.assert_not_called()

    def test_current_and_invalid_selections_do_nothing(self):
        for value in ('3', '-1', '8', '99', 'bad', ''):
            with self.choose(value):
                self.engine.open_selector()
        self.engine.apply.assert_not_called()
        self.engine.reset.assert_not_called()

    def test_restore_original(self):
        with self.choose('7'):
            self.engine.toggle_selector()
        self.engine.reset.assert_called_once_with()

    def test_state_update_is_persisted_without_eww(self):
        self.engine.update(busy=False, notice='ok')
        self.assertEqual(json.loads((self.engine.STATE/'ui.json').read_text())['notice'], 'ok')

    def test_rofi_failure_is_reported(self):
        with self.choose(code=2), self.assertRaises(RuntimeError):
            self.engine.open_selector()

    def test_eww_backend_routes_toggle_to_widget_selector(self):
        e=self.engine
        e.save(e.CONFIG/'selector.json',{'backend':'eww'})
        e.eww=Mock(return_value=subprocess.CompletedProcess(['eww'],0,'',''))
        with patch.object(e,'open_selector') as opened, patch.object(e.subprocess,'run') as run, patch.object(e,'selector_daemon_running',return_value=True):
            e.toggle_selector()
        e.eww.assert_called_once_with('active-windows')
        opened.assert_called_once_with()
        run.assert_not_called()

    def test_shipped_selector_uses_eww(self):
        config=Path(__file__).resolve().parents[1]/'modules/desktop-styles/files/.config/desktop-style/selector.json'
        self.assertEqual(json.loads(config.read_text())['backend'],'eww')


if __name__ == '__main__':
    unittest.main()
