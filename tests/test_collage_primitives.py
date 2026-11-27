import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RACCON_QML = ROOT / 'modules/quickshell/files/.config/quickshell/raccon'
QMLDIR = RACCON_QML / 'qmldir'


class CollagePrimitivesTests(unittest.TestCase):
    PRIMITIVES = {
        'Paper': {'fill', 'ink', 'border', 'shadowOffset', 'tilt', 'lifted', 'content'},
        'Sticker': {'text', 'tone', 'tilt'},
        'CutButton': {'text', 'icon', 'tone', 'active', 'enabled', 'clicked'},
        'Tape': {'color', 'tilt'},
        'Slice': {'color', 'angle'},
        'Halftone': {'color', 'spacing', 'dot'},
    }

    THEME_TOKENS = {
        'radius',
        'border',
        'shadowOffset',
        'motionFast',
        'motionBase',
        'animations',
        'fontDisplay',
        'fontMono',
        'ink',
        'tone',
    }

    def test_primitives_registered_in_qmldir(self):
        manifest = QMLDIR.read_text().splitlines()
        registered = {
            fields[0]: fields[-1]
            for line in manifest
            if (fields := line.partition('#')[0].split())
        }
        for name in self.PRIMITIVES:
            self.assertIn(name, registered, f"{name} must be registered in qmldir")
            self.assertEqual(registered[name], f"{name}.qml")

    def test_primitive_property_apis(self):
        for name, expected_props in self.PRIMITIVES.items():
            source = (RACCON_QML / f"{name}.qml").read_text()
            declared_props = set(re.findall(r'\b(?:property\s+\w+|signal|alias)\s+(\w+)', source))
            for prop in expected_props:
                self.assertIn(
                    prop,
                    declared_props,
                    f"Component {name}.qml missing expected API property or signal: {prop}",
                )

    def test_theme_collage_tokens_present(self):
        source = (RACCON_QML / 'Theme.qml').read_text()
        declared_tokens = set(re.findall(r'\b(?:property\s+\w+|function)\s+(\w+)', source))
        for token in self.THEME_TOKENS:
            self.assertIn(
                token,
                declared_tokens,
                f"Theme.qml missing expected token or function: {token}",
            )

    def test_component_file_line_limits(self):
        for name in list(self.PRIMITIVES.keys()) + ['Theme']:
            path = RACCON_QML / f"{name}.qml"
            line_count = len(path.read_text().splitlines())
            self.assertLessEqual(
                line_count,
                150,
                f"{name}.qml exceeds 150 lines: {line_count}",
            )


if __name__ == '__main__':
    unittest.main()
