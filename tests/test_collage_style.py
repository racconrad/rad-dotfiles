"""Maximalist Vocaloid/UTAU collage style palette, CSS, and preview checks."""
import colorsys
from pathlib import Path
import re
import sys
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import appearance, main


def source_colors():
    css = (ROOT / 'modules/desktop/files/.config/wlogout/colors.css').read_text()
    return dict(re.findall(r'@define-color (\w+) (#[0-9a-f]{6});', css))


def _dist(a, b):
    diff = abs(a - b) % 1.0
    return min(diff, 1.0 - diff)


class CollageStyleTests(unittest.TestCase):
    def test_aliases_and_triadic_collage_palette_contrast(self):
        self.assertIn('collage', main.PROFILES)
        self.assertEqual(main.PROFILES['collage']['name'], 'Collage')
        for alias in ('vocaloid', 'utau', 'utauloid', 'maximalist', 'papel mache'):
            self.assertEqual(main.normalize_style(alias), 'collage')

        for surface in ('#101010', '#fafafa'):
            for seed in ('#e5485d', '#38d9d2', '#ffaa00', '#000000', '#ffffff', '#808080', '#f6af8d'):
                source = source_colors()
                source.update(surface=surface, primary=seed, secondary=seed, tertiary=seed)
                colors, swatches = main.palette('collage', source)
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

                h1, _, s1 = colorsys.rgb_to_hls(*main.rgb(colors['primary']))
                h2, _, s2 = colorsys.rgb_to_hls(*main.rgb(colors['secondary']))
                h3, _, s3 = colorsys.rgb_to_hls(*main.rgb(colors['tertiary']))
                self.assertGreaterEqual(_dist(h1, h2), 0.08)
                self.assertGreaterEqual(_dist(h1, h3), 0.08)
                self.assertGreaterEqual(_dist(h2, h3), 0.08)
                for role_sat in (s1, s2, s3):
                    self.assertGreaterEqual(role_sat, 0.38)

    def test_all_adapters_parse_cleanly_and_keep_cutout_tokens(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        colors, _ = main.palette('collage', source_colors())
        output = appearance.build('collage', main.PROFILES['collage'], colors)
        for key in ('raccon', 'widgets', 'panels', 'swaync', 'swayosd',
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
        self.assertIn('.notification .notification-default-action:hover', output['swaync'])
        self.assertNotIn('infinite', ''.join(output.values()))
        self.assertNotIn('transition: all', ''.join(output.values()))

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


if __name__ == '__main__':
    unittest.main()
