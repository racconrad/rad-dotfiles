import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / 'modules/hyprland/files/.config/hypr/conf'


class RacconUXTests(unittest.TestCase):
    def test_windows_can_switch_between_floating_and_tiled(self):
        binds = (CONF / 'binds/windows.lua').read_text()
        self.assertRegex(
            binds,
            r'hl\.bind\(mod\s*\.\.\s*" \+ T",\s*hl\.dsp\.window\.float\(\{\s*action\s*=\s*"toggle"\s*\}\)\)',
        )

    def test_volume_control_stays_floating(self):
        rules = (CONF / 'rules.lua').read_text()
        utilities = re.search(r'hl\.window_rule\(\{\s*name\s*=\s*"float-utilities",(?P<rule>.*?)\}\)',
                              rules, re.DOTALL)
        self.assertIsNotNone(utilities)
        rule = utilities['rule']
        classes = re.search(r'\bclass\s*=\s*"([^"]+)"', rule)
        self.assertIsNotNone(classes)
        self.assertRegex('pavucontrol', classes[1].replace(r'\\', '\\'))
        self.assertRegex(rule, r'\bfloat\s*=\s*true\b')

    def test_workspace_swipes_are_horizontal(self):
        inputs = (CONF / 'input.lua').read_text()
        gestures = re.findall(r'hl\.gesture\(\{([^}]+)\}\)', inputs)
        workspace_swipes = [gesture for gesture in gestures if re.search(r'action\s*=\s*"workspace"', gesture)]
        self.assertTrue(workspace_swipes)
        for gesture in workspace_swipes:
            self.assertRegex(gesture, r'direction\s*=\s*"horizontal"')
