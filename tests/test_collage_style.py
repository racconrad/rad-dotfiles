"""Maximalist Vocaloid/UTAU collage style palette, CSS, and preview checks."""
import colorsys
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import appearance, main


def source_colors():
    css = (ROOT / 'modules/desktop/files/.config/wlogout/colors.css').read_text()
    return dict(re.findall(r'@define-color (\w+) (#[0-9a-f]{6});', css))


class CollageStyleTests(unittest.TestCase):
    def test_aliases_and_multi_hue_collage_palette_contrast(self):
        self.assertIn('collage', main.PROFILES)
        self.assertEqual(main.PROFILES['collage']['name'], 'Collage')
        for alias in ('vocaloid', 'utau', 'utauloid', 'maximalist', 'papel mache'):
            self.assertEqual(main.normalize_style(alias), 'collage')

        for surface in ('#101010', '#fafafa'):
            for seed in ('#e5485d', '#38d9d2', '#ffaa00', '#000000', '#ffffff', '#808080'):
                source = source_colors()
                source.update(surface=surface, primary=seed, secondary=seed, tertiary=seed)
                original = dict(source)
                colors, swatches = main.palette('collage', source)
                self.assertEqual(source, original)
                self.assertEqual(len(swatches), 5)
                pairs = [
                    ('surface', 'on_surface'),
                    ('surface_container_highest', 'on_surface'),
                    ('surface_container', 'on_surface_variant'),
                ]
                for role in ('primary', 'secondary', 'tertiary', 'error'):
                    pairs.extend(((role, 'on_' + role), (role + '_container', 'on_' + role + '_container'),
                                  ('surface_container', role)))
                for bg, fg in pairs:
                    with self.subTest(surface=surface, seed=seed, bg=bg, fg=fg):
                        self.assertGreaterEqual(main.contrast_ratio(colors[bg], colors[fg]), 4.5)
                h1 = colorsys.rgb_to_hls(*main.rgb(colors['primary']))[0]
                h2 = colorsys.rgb_to_hls(*main.rgb(colors['secondary']))[0]
                diff = abs(h1 - h2) % 1.0
                self.assertGreaterEqual(min(diff, 1.0 - diff), .14)

    def test_all_adapters_parse_cleanly_and_keep_cutout_tokens(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        colors, _ = main.palette('collage', source_colors())
        output = appearance.build('collage', main.PROFILES['collage'], colors)
        for key in ('raccon', 'waybar', 'widgets', 'panels', 'selector', 'swaync', 'swayosd',
                    'widget_editor', 'wlogout', 'gtklock'):
            with self.subTest(key=key):
                Gtk.CssProvider().load_from_data(output[key].encode())
                self.assertIn(colors['primary'], output[key])
        self.assertIn('box-shadow: 4px 4px 0', output['raccon'])
        self.assertNotIn('-gtk-icon-transform: rotate(-8deg)', output['raccon'])
        self.assertIn('.popup.style-collage.motion', output['raccon'])
        self.assertIn('.popup.still', output['raccon'])
        for selector in ('.app-launch', '.mode-row', '.session-choice', '.shortcut-row'):
            self.assertIn(selector, output['raccon'])
        for chip in ('#custom-canvas-mode', '#custom-tiling', '#custom-desktop-mode',
                     '#custom-updates', '#battery', '#backlight', '#bluetooth', '#idle_inhibitor'):
            self.assertIn(chip, output['waybar'])
        self.assertIn('.notification .notification-default-action:hover', output['swaync'])
        self.assertNotIn('infinite', ''.join(output.values()))
        self.assertNotIn('transition: all', ''.join(output.values()))

    def test_macxp_aliases_palette_css_and_preview(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        self.assertIn('macxp', main.PROFILES)
        self.assertEqual(main.PROFILES['macxp']['name'], 'Vintage')
        for alias in ('vintage', 'mac', 'macintosh', 'windows xp', 'xp', 'luna', 'platinum'):
            self.assertEqual(main.normalize_style(alias), 'macxp')

        colors, swatches = main.palette('macxp', source_colors())
        self.assertEqual(len(swatches), 5)
        self.assertNotIn('#3b82f6', ''.join(swatches))
        for role in ('surface_container', 'primary', 'secondary', 'tertiary'):
            r, g, b = (int(colors[role][i:i+2], 16) for i in (1, 3, 5))
            self.assertEqual((r, g, b), (r, r, r))
        pairs = [('surface', 'on_surface'), ('surface_container_highest', 'on_surface'),
                 ('surface_container', 'on_surface_variant')]
        for role in ('primary', 'secondary', 'tertiary', 'error'):
            pairs.extend(((role, 'on_' + role), (role + '_container', 'on_' + role + '_container'),
                          ('surface_container', role)))
        for bg, fg in pairs:
            with self.subTest(bg=bg, fg=fg):
                self.assertGreaterEqual(main.contrast_ratio(colors[bg], colors[fg]), 4.5)

        output = appearance.build('macxp', main.PROFILES['macxp'], colors)
        for key in ('raccon', 'waybar', 'widgets', 'panels', 'selector', 'swaync', 'swayosd',
                    'widget_editor', 'wlogout', 'gtklock'):
            with self.subTest(key=key):
                Gtk.CssProvider().load_from_data(output[key].encode())
        self.assertIn('linear-gradient', output['raccon'])
        self.assertIn('linear-gradient', output['waybar'])
        shipped = ROOT / 'modules/desktop-styles/files/.config/desktop-style'
        for ext in ('.png', '.svg', '-colors.svg'):
            self.assertTrue((shipped / 'previews' / ('macxp' + ext)).is_file())

    def test_wlogout_contrast_in_light_and_dark_palettes(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            self.skipTest('GTK display required for offscreen computed styles')
        for surface in ('#101010', '#fafafa'):
            source = dict(primary='#e5485d', secondary='#47e5da', tertiary='#ffd166',
                          surface=surface, error='#ffb4ab')
            colors, _ = main.palette('collage', source)
            output = appearance.build('collage', main.PROFILES['collage'], colors)
            provider = Gtk.CssProvider()
            provider.load_from_data(output['wlogout'].encode())
            window = Gtk.OffscreenWindow()
            button = Gtk.Button(label='Lock')
            window.add(button)
            Gtk.StyleContext.add_provider_for_screen(window.get_screen(), provider, 600)
            try:
                for name in ('lock', 'shutdown'):
                    button.set_name(name)
                    for state in (Gtk.StateFlags.NORMAL, Gtk.StateFlags.PRELIGHT, Gtk.StateFlags.FOCUSED):
                        button.set_state_flags(state, True)
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore', DeprecationWarning)
                            bg_val = button.get_style_context().get_background_color(state)
                        background = main.hexcolor((bg_val.red, bg_val.green, bg_val.blue))
                        self.assertGreaterEqual(main.contrast_ratio(background, '#d4bff9'), 3)
                        fg_val = button.get_child().get_style_context().get_color(state)
                        foreground = main.hexcolor((fg_val.red, fg_val.green, fg_val.blue))
                        self.assertGreaterEqual(main.contrast_ratio(background, foreground), 4.5)
            finally:
                Gtk.StyleContext.remove_provider_for_screen(window.get_screen(), provider)
                window.destroy()

    def test_shipped_preview_catalog_and_regeneration(self):
        shipped = ROOT / 'modules/desktop-styles/files/.config/desktop-style'
        yuck = (shipped / 'eww.yuck').read_text()
        initial = json.loads(json.loads(re.search(r'\(deflisten ui :initial ("(?:[^"\\]|\\.)*")', yuck)[1]))
        self.assertEqual(initial['catalog']['collage']['name'], 'Collage')
        for ext in ('.png', '.svg', '-colors.svg'):
            self.assertTrue((shipped / 'previews' / ('collage' + ext)).is_file())
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'CONFIG', Path(directory)):
            main.save(main.CONFIG / 'waybar.json', dict(position='top', layout='islands'))
            row = main.preview('collage', source_colors())
            self.assertEqual(Path(row['preview']).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            tree = ET.parse(main.CONFIG / 'previews/collage.svg')
            self.assertEqual(tree.getroot().attrib['viewBox'], '0 0 440 280')

    def test_collage_adapts_to_distinct_wallpaper_palettes_and_menu_style_class(self):
        warm = dict(
            source_colors(),
            surface='#1c1210',
            primary='#ff8a65',
            secondary='#ffd54f',
            tertiary='#a5d6a7',
            wallpaper_dominant='#8d2b14',
        )
        cool = dict(
            source_colors(),
            surface='#0e1722',
            primary='#4fc3f7',
            secondary='#ba68c8',
            tertiary='#80cbc4',
            wallpaper_dominant='#0c4a6e',
        )
        warm_colors, _ = main.palette('collage', warm)
        cool_colors, _ = main.palette('collage', cool)

        for key in ('surface', 'secondary_container', 'primary', 'secondary', 'tertiary'):
            self.assertNotEqual(warm_colors[key], cool_colors[key], key)

        # Distinct chromatic secondary/tertiary from matugen must keep their hues instead of collapsing.
        def hue(c):
            return colorsys.rgb_to_hls(*main.rgb(c))[0]

        for name, src, out in (('warm', warm, warm_colors), ('cool', cool, cool_colors)):
            for role in ('primary', 'secondary', 'tertiary'):
                diff = abs(hue(src[role]) - hue(out[role])) % 1.0
                self.assertLess(min(diff, 1.0 - diff), 0.05, (name, role, src[role], out[role]))
            # secondary_container must reflect secondary hue, not fixed cream #eae6e1.
            sc_hue, _, sc_sat = colorsys.rgb_to_hls(*main.rgb(out['secondary_container']))
            self.assertGreater(sc_sat, 0.35, (name, out['secondary_container']))
            sc_diff = abs(sc_hue - hue(out['secondary'])) % 1.0
            self.assertLess(min(sc_diff, 1.0 - sc_diff), 0.06, (name, out['secondary_container'], out['secondary']))

        yuck = (ROOT / 'modules/desktop/files/.config/raccon-menu/eww.yuck').read_text()
        self.assertIn('style-${desktop.style', yuck)

    def test_collage_prefers_real_wallpaper_accents_and_refined_containers(self):
        red_mono = dict(
            source_colors(),
            surface='#1a1111',
            primary='#ffb3b1',
            secondary='#e6bdbb',
            tertiary='#ffdeab',
            wallpaper_dominant='#3b1819',
            wallpaper_accent_1='#da494e',
        )
        colors, _ = main.palette('collage', red_mono)

        def hue(c):
            return colorsys.rgb_to_hls(*main.rgb(c))[0]

        def lightness(c):
            return colorsys.rgb_to_hls(*main.rgb(c))[1]

        # Monochromatic/warm wallpaper must not invent unrelated cyan (+0.44) hues.
        for role in ('primary', 'secondary', 'tertiary'):
            diff = abs(hue(colors[role]) - hue('#da494e')) % 1.0
            self.assertLess(min(diff, 1.0 - diff), 0.15, (role, colors[role]))
            self.assertGreaterEqual(main.contrast_ratio(colors[role + '_container'], colors['on_' + role + '_container']), 4.8)
            self.assertLessEqual(lightness(colors[role + '_container']), 0.26)
            self.assertGreaterEqual(lightness(colors[role + '_container']), 0.17)

        # When a second real wallpaper accent exists, secondary adopts it.
        two_tone = dict(red_mono, wallpaper_accent_2='#38a3d1')
        two_colors, _ = main.palette('collage', two_tone)
        diff = abs(hue(two_colors['secondary']) - hue('#38a3d1')) % 1.0
        self.assertLess(min(diff, 1.0 - diff), 0.05, two_colors['secondary'])


if __name__ == '__main__':
    unittest.main()
