import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RACCON_QML = ROOT / 'modules/quickshell/files/.config/quickshell/raccon'
QMLDIR = RACCON_QML / 'qmldir'


class CollagePrimitivesV2Tests(unittest.TestCase):
    PRIMITIVES = {
        'Backdrop': {'seed', 'slices', 'animated'},
        'Tag': {'text', 'tone', 'tilt'},
        'AccentBar': {'tone', 'grow'},
        'Zigzag': {'color', 'edge', 'teeth', 'depth'},
        'Burst': {'color', 'count', 'fire'},
        'Spark': {'color', 'size', 'spin'},
    }

    THEME_TOKENS = {
        'motionSlap',
        'overshoot',
        'toneAt',
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
            declared = set(re.findall(r'\b(?:property\s+\w+|signal|alias|function)\s+(\w+)', source))
            for prop in expected_props:
                self.assertIn(
                    prop,
                    declared,
                    f"Component {name}.qml missing expected API property or signal: {prop}",
                )

    def test_theme_collage_tokens_v2_present(self):
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
