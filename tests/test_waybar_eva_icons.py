"""Eva glyphs are available to Waybar without relying on Nerd Fonts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WAYBAR = ROOT / 'modules/waybar/files/.config/waybar'
ICON_ACTIONS = ROOT / 'modules/desktop/files/.config/raccon-menu/assets/icons/hicolor/scalable/actions'
sys.path.insert(0, str(ROOT / 'modules/desktop/files/.local/lib'))
sys.path.insert(0, str(ROOT / 'modules/base/files/.local/lib'))
import raccon_music_status


class WaybarEvaIconTests(unittest.TestCase):
    def test_status_icons_use_the_eva_outline_font(self):
        config = json.loads((WAYBAR / 'config.jsonc').read_text())
        expected = {
            'custom/hardware-toggle': ('exec', '\ueb91'),
            'custom/workspace-base': ('exec', '\ueb31'),
            'wireplumber': ('format-muted', '\uebe2'),
            'network': ('format-wifi', '\uebea'),
            'cpu': ('format', '\uea02'),
            'memory': ('format', '\ueaf1'),
            'custom/power': ('format', '\ueb70'),
            'temperature': ('format', '\uebc0'),
            'disk#root': ('format', '\ueaf1'),
            'disk#home': ('format', '\ueaf9'),
            'custom/updates': ('format', '\ueab0'),
            'bluetooth': ('format', '\uea48'),
            'custom/launcher': ('format', '\ueaef'),
        }
        for module, (key, glyph) in expected.items():
            with self.subTest(module=module):
                self.assertIn(glyph, config[module][key])
        self.assertEqual(config['wireplumber']['format-icons'], ['\uebe0', '\uebe0', '\uebe6'])
        self.assertEqual(config['network']['format-disconnected'], '\uebe9')
        self.assertEqual(config['backlight']['format-icons'], ['\uebb6'] * 3)
        self.assertEqual(config['idle_inhibitor']['format-icons'], {
            'activated': '\uebb6', 'deactivated': '\ueb33'})
        self.assertTrue(all(0xE000 <= ord(glyph) <= 0xF8FF for glyph in config['custom/desktop-mode']['format-icons'].values() if glyph))

    def test_shared_music_provider_emits_eva_glyphs(self):
        playing = raccon_music_status.snapshot('Playing', False)
        paused = raccon_music_status.snapshot('Paused', False)
        self.assertEqual(playing['open']['text'], '\ueb3b')
        self.assertEqual(playing['prev']['text'], '\ueba4')
        self.assertEqual(playing['play']['text'], '\ueb4b')
        self.assertEqual(playing['next']['text'], '\ueba6')
        self.assertEqual(paused['play']['text'], '\ueb68')

    def test_tiling_toggle_emits_eva_glyphs_for_both_modes(self):
        script = ROOT / 'modules/wayfire/files/.local/bin/wf-tile-mode'
        with tempfile.TemporaryDirectory() as home:
            state = Path(home) / 'floating.json'
            env = {**os.environ, 'HOME': home, 'XDG_CACHE_HOME': str(Path(home) / 'cache'),
                   'WF_TILE_FLOAT_STATE': str(state)}
            run = lambda: json.loads(subprocess.check_output(
                [sys.executable, str(script), 'status'], env=env, text=True))
            self.assertEqual(run()['text'], '\ueb06')
            state.write_text('["1:0:0"]')
            self.assertEqual(run()['text'], '\ueb19')

    def test_font_is_bundled_and_preferred_for_private_use_glyphs(self):
        font = ROOT / 'modules/waybar/files/.local/share/fonts/Eva-Icons.ttf'
        self.assertTrue(font.is_file())
        self.assertTrue(font.read_bytes().startswith(b'\x00\x01\x00\x00'))
        css = (WAYBAR / 'style.css').read_text()
        self.assertIn('"Eva-Icons"', css)

    def test_widget_control_assets_come_from_eva_outline(self):
        assets = list(ICON_ACTIONS.glob('raccon-*-symbolic.svg'))
        self.assertGreater(len(assets), 0)
        for asset in assets:
            with self.subTest(icon=asset.name):
                svg = asset.read_text()
                self.assertIn('Eva Icons', svg)
                self.assertIn('fill="currentColor"', svg)
                self.assertNotIn('stroke="#2e3436"', svg)


if __name__ == '__main__':
    unittest.main()
