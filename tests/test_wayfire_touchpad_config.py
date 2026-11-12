import configparser
from pathlib import Path
import unittest


class TouchpadConfigurationTests(unittest.TestCase):
    def test_native_touchpad_gestures(self):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        root = Path(__file__).resolve().parents[1]
        config.read(root / 'modules/wayfire/files/.config/wayfire.ini')
        self.assertEqual(config['input']['natural_scroll'], 'true')
        self.assertEqual(config['input']['click_method'], 'clickfinger')
        self.assertEqual(config['input']['3fg_drag'], '3fg-drag')
