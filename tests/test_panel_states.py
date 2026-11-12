"""Service status and read-only recovery without touching host services."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'modules/desktop/files/.local/lib/raccon_menu'
sys.path.insert(0, str(LIB))
spec = importlib.util.spec_from_file_location('panel_states', LIB / 'panels.py')
panels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panels)


class PanelStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        root = patch.object(panels, 'ROOT', self.root)
        root.start()
        self.addCleanup(root.stop)

    def test_loading_failure_off_empty_and_disconnected_are_distinct(self):
        fixtures = [
            ('connections', {}, 'loading'),
            ('connections', dict(ready=True, error='NetworkManager unavailable.'), 'error'),
            ('connections', dict(ready=True, available=True), 'off'),
            ('connections', dict(ready=True, available=True, enabled=True), 'empty'),
            ('connections', dict(ready=True, available=True, enabled=True,
                                 networks=[dict(active=False)]), 'disconnected'),
            ('connections', dict(ready=True, available=True, enabled=True,
                                 networks=[dict(active=True)]), 'ready'),
            ('bluetooth', dict(ready=True, available=True, enabled=True,
                               devices=[dict(token='a', connected=False)]), 'disconnected'),
            ('bluetooth', dict(ready=True, available=True, enabled=True, scanning=True), 'loading'),
            ('audio', dict(ready=True, available=True), 'empty'),
            ('audio', dict(ready=True, available=True, outputs=[dict(token='a')],
                           inputs=[dict(token='b')]), 'ready'),
        ]
        for kind, changes, expected in fixtures:
            with self.subTest(kind=kind, expected=expected):
                frame = panels.presentation(kind, {**panels.defaults(kind), **changes})
                self.assertEqual(frame.get('status'), expected)
                if expected != 'ready':
                    self.assertTrue(frame['message'])

    def test_retry_only_wakes_allowlisted_provider(self):
        with patch.object(panels, 'configure'), patch.object(panels, 'command') as command, \
             patch.object(panels, 'bluez') as bluez:
            for kind in ('audio', 'connections', 'bluetooth'):
                panels.main(['retry', kind])
                self.assertTrue((self.root / ('refresh-' + kind)).read_text())
            with self.assertRaises(ValueError):
                panels.main(['retry', '../other'])
            command.assert_not_called()
            bluez.assert_not_called()

    def test_recovery_clears_service_error(self):
        with patch.object(panels, 'STATE', self.root), \
             patch.object(panels, 'audio_snapshot', side_effect=RuntimeError('offline')):
            failed = panels.refresh('audio')
        self.assertEqual(panels.presentation('audio', failed).get('status'), 'error')
        recovered = dict(panels.defaults('audio'), ready=True, available=True,
                         outputs=[dict(token='a')], inputs=[dict(token='b')])
        with patch.object(panels, 'STATE', self.root), \
             patch.object(panels, 'audio_snapshot', return_value=recovered):
            frame = panels.presentation('audio', panels.refresh('audio'))
        self.assertEqual(frame['status'], 'ready')
        self.assertEqual(frame['error'], '')


if __name__ == '__main__':
    unittest.main()
