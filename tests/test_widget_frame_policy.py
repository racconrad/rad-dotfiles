"""Frame policy and live token publication for Collage desktop style."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'modules/desktop-styles/files/.local/lib'
sys.path.insert(0, str(LIB))
from desktop_style.appearance import resolve
spec = importlib.util.spec_from_file_location('frame_style_engine', LIB / 'desktop_style/main.py')
styles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(styles)


class FramePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / 'state'
        self.state.mkdir()
        self.current = Path(self.tmp.name) / 'current'
        self.current.mkdir()
        for key, value in (('STATE', self.state), ('CURRENT', self.current)):
            p = patch.object(styles, key, value)
            p.start()
            self.addCleanup(p.stop)
        (self.state / 'selection.json').write_text('{"style":"collage"}')
        self.tokens = self.current / 'tokens.json'
        self.tokens.write_text(json.dumps({'style': 'collage', 'colors': {}, 'widgets': {'frame': 'none'}}))

    def test_defaults_follow_style(self):
        self.assertEqual(resolve('collage', styles.PROFILES['collage'], {})['widgets']['frame'], 'none')

    def test_widget_frame_is_none(self):
        self.assertEqual(styles.widget_frame('collage'), 'none')

    def test_with_widget_frame_preserves_none(self):
        data = {'style': 'collage', 'widgets': {'frame': 'auto'}}
        self.assertEqual(json.loads(styles.with_widget_frame(json.dumps(data)))['widgets']['frame'], 'none')


if __name__ == '__main__':
    unittest.main()
