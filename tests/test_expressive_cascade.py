"""Computed GTK styles after the real popup SCSS import order, without mapping."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import appearance, main


class ExpressiveCascadeTests(unittest.TestCase):
    def test_widget_clock_uses_the_emphasized_type_and_wallpaper_accent(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            self.skipTest('GTK display required for offscreen computed styles')
        colors, _ = main.palette('expressive', dict(primary='#a097f7', surface='#101010', error='#ffb4ab'))
        output = appearance.build('expressive', main.PROFILES['expressive'], colors)
        window = Gtk.OffscreenWindow()
        root = Gtk.Box()
        for name in ('rw-desktop', 'wroot', 'rw-clock'):
            root.get_style_context().add_class(name)
        window.add(root)
        clock = Gtk.Label(label='10:24')
        clock.get_style_context().add_class('clock')
        root.add(clock)
        provider = Gtk.CssProvider()
        provider.load_from_data(output['widgets'].encode())
        Gtk.StyleContext.add_provider_for_screen(window.get_screen(), provider, 600)
        try:
            context = clock.get_style_context()
            self.assertEqual(context.get_property('font-weight', 0), 800)
            value = context.get_color(0)
            self.assertEqual(main.hexcolor((value.red, value.green, value.blue)), colors['primary'])
        finally:
            Gtk.StyleContext.remove_provider_for_screen(window.get_screen(), provider)
            window.destroy()

    def test_logout_bitmap_icons_keep_contrast_in_light_and_dark_palettes(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            self.skipTest('GTK display required for offscreen computed styles')
        for surface in ('#101010', '#fafafa'):
            source = dict(primary='#a097f7', secondary='#b6cbee', tertiary='#ebbad0',
                          surface=surface, error='#ffb4ab')
            colors, _ = main.palette('expressive', source)
            output = appearance.build('expressive', main.PROFILES['expressive'], colors)
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
                            value = button.get_style_context().get_background_color(state)
                        background = main.hexcolor((value.red, value.green, value.blue))
                        # Existing wlogout PNG glyphs cannot inherit the CSS foreground.
                        self.assertGreaterEqual(main.contrast_ratio(background, '#d4bff9'), 3)
                        foreground = button.get_child().get_style_context().get_color(state)
                        self.assertGreaterEqual(main.contrast_ratio(background, main.hexcolor((foreground.red, foreground.green, foreground.blue))), 4.5)
            finally:
                Gtk.StyleContext.remove_provider_for_screen(window.get_screen(), provider)
                window.destroy()

    def test_real_popup_scss_preserves_emphasis_contrast_and_reduced_motion(self):
        compiler = shutil.which('widgetctl')
        if not compiler:
            self.skipTest('widgetctl SCSS compiler required')
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            self.skipTest('GTK display required for offscreen computed styles')
        source = dict(re.findall(r'\$(\w+):\s*(#[\da-fA-F]{6});',
            (ROOT / 'modules/desktop-styles/files/.config/desktop-style/_palette.scss').read_text()))
        colors, _ = main.palette('expressive', source)
        output = appearance.build('expressive', main.PROFILES['expressive'], colors)
        palette = ''.join(f'${key}: {value};\n' for key, value in colors.items())
        palette += '$island_background: $surface_container;\n$island_outline: $outline_variant;\n'
        settings = Gtk.Settings.get_default()
        animations = settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations', False)
        self.addCleanup(settings.set_property, 'gtk-enable-animations', animations)
        with tempfile.TemporaryDirectory() as directory, warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            for popup in ('raccon-menu', 'raccon-float', 'raccon-music'):
                with self.subTest(popup=popup):
                    folder = Path(directory) / popup
                    shutil.copytree(ROOT / 'modules/desktop/files/.config' / popup, folder)
                    (folder / '_palette.scss').write_text(palette)
                    (folder / '_desktop-style.scss').write_text(output['raccon'])
                    (folder / '_tokens.scss').write_text('$radius: 32px; $control_radius: 10px; $border: 0px; $opacity: 1; $font: "Inter"; $panel_padding: 20px; $control_padding: 10px;')
                    css = folder / 'compiled.css'
                    result = subprocess.run([compiler, 'compile-css', folder / 'eww.scss', css], cwd=folder, capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    provider = Gtk.CssProvider()
                    provider.load_from_path(str(css))
                    window = Gtk.OffscreenWindow()
                    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    for name in ('popup', 'style-expressive', 'still'):
                        root.get_style_context().add_class(name)
                    if popup != 'raccon-menu':
                        root.get_style_context().add_class('float-popup' if popup == 'raccon-float' else 'music-popup')
                    window.add(root)
                    title = Gtk.Label(label='Raccon')
                    title.get_style_context().add_class('float-title' if popup == 'raccon-float' else 'music-title' if popup == 'raccon-music' else 'title')
                    root.add(title)
                    button = Gtk.Button(label='Apps')
                    button.get_style_context().add_class('music-button' if popup == 'raccon-music' else 'daily-app')
                    root.add(button)
                    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), provider, 600)
                    try:
                        context = title.get_style_context()
                        self.assertEqual(context.get_property('font-size', 0), 16 if popup == 'raccon-music' else 28)
                        for state in (Gtk.StateFlags.NORMAL, Gtk.StateFlags.PRELIGHT, Gtk.StateFlags.FOCUSED):
                            button.set_state_flags(state, True)
                            context = button.get_style_context()
                            fg = button.get_child().get_style_context().get_color(state)
                            bg = context.get_background_color(state)
                            pair = [main.hexcolor((color.red, color.green, color.blue)) for color in (fg, bg)]
                            self.assertGreaterEqual(main.contrast_ratio(*pair), 4.5)
                    finally:
                        Gtk.StyleContext.remove_provider_for_screen(window.get_screen(), provider)
                        window.destroy()


if __name__ == '__main__':
    unittest.main()
