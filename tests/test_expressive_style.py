"""Wallpaper-driven expressive surfaces, without touching a running desktop."""
import colorsys
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import appearance, main


def source_colors():
    css = (ROOT / 'modules/desktop/files/.config/wlogout/colors.css').read_text()
    return dict(re.findall(r'@define-color (\w+) (#[0-9a-f]{6});', css))


class ExpressiveStyleTests(unittest.TestCase):
    def test_palette_follows_wallpaper_roles_without_mutating_source(self):
        self.assertNotIn('retrofuture', main.PROFILES)
        self.assertEqual(main.normalize_style('retrofuture'), 'modern')
        self.assertEqual(main.normalize_style('expressive'), 'dynamic')
        source = source_colors()
        original = dict(source)
        first, swatches = main.palette('dynamic', source)
        source.update(primary='#ffa060', secondary='#60e0b0', tertiary='#80a0ff')
        second, _ = main.palette('dynamic', source)
        for role in ('primary', 'secondary', 'tertiary'):
            self.assertNotEqual(first[role], second[role])
            hue = colorsys.rgb_to_hls(*main.rgb(second[role]))[0]
            expected = colorsys.rgb_to_hls(*main.rgb(source[role]))[0]
            self.assertLess(abs(hue - expected), .01)
        self.assertEqual(first['error'], original['error'])
        self.assertNotEqual(first['primary_container'], original['primary_container'])
        self.assertEqual(first['source_color'] if 'source_color' in first else None, original.get('source_color'))
        self.assertEqual(swatches, [first[k] for k in ('surface', 'primary', 'secondary', 'tertiary', 'on_surface')])
        self.assertEqual(original, source_colors())

    def test_dark_light_neutral_and_extreme_seeds_have_readable_pairs(self):
        for surface in ('#101010', '#fafafa'):
            for seed in ('#000000', '#ffffff', '#ff0000', '#00ff00', '#0000ff', '#808080'):
                source = source_colors()
                source.update(surface=surface, primary=seed, secondary=seed, tertiary=seed)
                original = dict(source)
                colors, _ = main.palette('dynamic', source)
                self.assertEqual(source, original)
                self.assertEqual(main.luminance(colors['surface']) < .5, surface == '#101010')
                if seed in ('#000000', '#ffffff', '#808080'):
                    for role in ('surface', 'surface_container', 'on_surface', 'primary_container'):
                        self.assertLessEqual(max(main.rgb(colors[role])) - min(main.rgb(colors[role])), .005)
                pairs = [('surface', 'on_surface'), ('surface_container_highest', 'on_surface'),
                         ('surface_container', 'on_surface_variant')]
                for role in ('primary', 'secondary', 'tertiary', 'error'):
                    pairs.extend(((role, 'on_' + role), (role + '_container', 'on_' + role + '_container'),
                                  ('surface_container', role)))
                for bg, fg in pairs:
                    with self.subTest(surface=surface, seed=seed, bg=bg, fg=fg):
                        self.assertGreaterEqual(main.contrast_ratio(colors[bg], colors[fg]), 4.5)

    def test_every_native_adapter_parses_and_retains_motion_policy(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        colors, _ = main.palette('dynamic', source_colors())
        output = appearance.build('dynamic', main.PROFILES['dynamic'], colors)
        for key in ('raccon', 'waybar', 'widgets', 'panels', 'selector', 'swaync', 'swayosd',
                    'widget_editor', 'wlogout', 'gtklock'):
            with self.subTest(key=key):
                Gtk.CssProvider().load_from_data(output[key].encode())
                self.assertIn(colors['primary'], output[key])
        self.assertIn('border-radius: 32px 12px 32px 12px', output['raccon'])
        self.assertIn('.popup.motion', output['raccon'])
        self.assertIn('.popup.still', output['raccon'])
        self.assertIn('.style-selector.reduce-motion', output['selector'])
        self.assertNotIn('infinite', ''.join(output.values()))
        self.assertNotIn('transition: all', ''.join(output.values()))
        tokens = json.loads(output['tokens'])
        self.assertEqual(tokens['widgets']['frame'], 'none')
        self.assertEqual(tokens['opacity'], 1)
        self.assertFalse(tokens['strict'])

    def test_bar_layout_and_position_remain_user_preferences(self):
        colors, _ = main.palette('dynamic', source_colors())
        for position in ('top', 'bottom', 'left', 'right'):
            for continuous in (False, True):
                profile = dict(main.PROFILES['dynamic'], position=position, continuous=continuous)
                output = appearance.build('dynamic', profile, colors)
                tokens = json.loads(output['tokens'])
                self.assertEqual(tokens['position'], position)
                self.assertEqual(tokens['continuous'], continuous)
                self.assertNotIn('min-width: 44px', output['waybar'])

    def test_preview_is_available_on_fresh_install_and_regenerates(self):
        shipped = ROOT / 'modules/desktop-styles/files/.config/desktop-style'
        yuck = (shipped / 'eww.yuck').read_text()
        initial = json.loads(json.loads(re.search(r'\(deflisten ui :initial ("(?:[^"\\]|\\.)*")', yuck)[1]))
        row = initial['catalog']['dynamic']
        self.assertEqual(row['name'], 'Dynamic')
        for extension in ('.png', '.svg', '-colors.svg'):
            self.assertTrue((shipped / 'previews' / ('dynamic' + extension)).is_file())
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'CONFIG', Path(directory)):
            main.save(main.CONFIG / 'waybar.json', dict(position='left', layout='continuous'))
            row = main.preview('dynamic', source_colors())
            self.assertEqual(Path(row['preview']).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            tree = ET.parse(main.CONFIG / 'previews/dynamic.svg')
            self.assertEqual(tree.getroot().attrib['viewBox'], '0 0 440 280')
            from PIL import Image
            colors, _ = main.palette('dynamic', source_colors())
            with Image.open(row['preview']) as image:
                self.assertEqual(image.convert('RGB').getpixel((24, 225)), tuple(round(v * 255) for v in main.rgb(colors['primary'])))


if __name__ == '__main__':
    unittest.main()
