"""Verify compact button paddings and responsive geometry across all Raccon menus."""
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import appearance, main as style_main


class MenuResponsiveTests(unittest.TestCase):
    def test_native_c_modules_compile_cleanly(self):
        if not shutil.which('cc') or not shutil.which('pkg-config'):
            self.skipTest('C/GTK toolchain unavailable')
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True))
        raccon_lib = ROOT / 'modules/desktop/files/.local/lib/raccon_menu'
        style_lib = ROOT / 'modules/desktop-styles/files/.local/lib/desktop_style'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for name, src, includes in (
                ('input', raccon_lib / 'input.c', [raccon_lib]),
                ('float', raccon_lib / 'float_input.c', [raccon_lib]),
                ('selector', style_lib / 'selector_input.c', [style_lib, raccon_lib]),
            ):
                with self.subTest(module=name):
                    cmd = ['cc', '-shared', '-fPIC', str(src), *(f'-I{inc}' for inc in includes),
                           '-o', str(out / f'{name}.so'), *flags, '-lm']
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, res.stderr)

    def test_compact_button_padding_beats_desktop_style_override(self):
        compiler = shutil.which('widgetctl')
        if not compiler:
            self.skipTest('widgetctl SCSS compiler required')
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            self.skipTest('GTK display required')

        source = dict(re.findall(r'\$(\w+):\s*(#[\da-fA-F]{6});',
            (ROOT / 'modules/desktop-styles/files/.config/desktop-style/_palette.scss').read_text()))
        colors, _ = style_main.palette('modern', source)
        output = appearance.build('modern', style_main.PROFILES['modern'], colors)
        palette = ''.join(f'${k}: {v};\n' for k, v in colors.items())
        palette += '$island_background: $surface_container;\n$island_outline: $outline_variant;\n'
        tokens = '$radius: 14px; $control_radius: 10px; $border: 0px; $opacity: 1; $font: "Inter"; $panel_padding: 16px; $control_padding: 6px;'

        cases = [
            ('raccon-menu', ('popup',), ('app-launch',), 5),
            ('raccon-menu', ('popup',), ('mode-row',), 6),
            ('raccon-menu', ('popup',), ('daily-app',), 6),
            ('raccon-float', ('popup', 'float-popup'), ('float-close',), 6),
            ('raccon-music', ('popup', 'music-popup'), ('music-hide',), 5),
            ('raccon-countdown', ('popup', 'countdown-popup'), ('countdown-btn',), 5),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compiled = {}
            for app in ('raccon-menu', 'raccon-float', 'raccon-music', 'raccon-countdown'):
                folder = root / app
                shutil.copytree(ROOT / 'modules/desktop/files/.config' / app, folder)
                (folder / '_palette.scss').write_text(palette)
                (folder / '_desktop-style.scss').write_text(output['raccon'])
                (folder / '_tokens.scss').write_text(tokens)
                css = folder / 'compiled.css'
                res = subprocess.run([compiler, 'compile-css', folder / 'eww.scss', css],
                                     cwd=folder, capture_output=True, text=True, timeout=15)
                self.assertEqual(res.returncode, 0, res.stderr)
                compiled[app] = css

            for app, parent_classes, btn_classes, max_top_pad in cases:
                with self.subTest(app=app, btn=btn_classes):
                    provider = Gtk.CssProvider()
                    provider.load_from_path(str(compiled[app]))
                    win = Gtk.OffscreenWindow()
                    box = Gtk.Box()
                    for cls in parent_classes:
                        box.get_style_context().add_class(cls)
                    btn = Gtk.Button(label='X')
                    for cls in btn_classes:
                        btn.get_style_context().add_class(cls)
                    box.add(btn)
                    win.add(box)
                    Gtk.StyleContext.add_provider_for_screen(win.get_screen(), provider, 600)
                    try:
                        pad = btn.get_style_context().get_padding(Gtk.StateFlags.NORMAL)
                        self.assertLessEqual(pad.top, max_top_pad)
                    finally:
                        Gtk.StyleContext.remove_provider_for_screen(win.get_screen(), provider)
                        win.destroy()

    def test_raccon_menu_has_bounded_side_scroll_and_float_bounds(self):
        yuck = (ROOT / 'modules/desktop/files/.config/raccon-menu/eww.yuck').read_text()
        self.assertNotIn('scroll :class "side-scroll"', yuck)
        controls = (ROOT / 'modules/desktop/files/.config/raccon-menu/controls.yuck').read_text()
        self.assertNotIn('(scroll :height 80', controls)
        shortcuts = (ROOT / 'modules/desktop/files/.config/raccon-menu/shortcuts.yuck').read_text()
        self.assertNotIn(':vexpand true\n      (box :class "keys-list"', shortcuts)
        input_c = (ROOT / 'modules/desktop/files/.local/lib/raccon_menu/input.c').read_text()
        self.assertIn('clamp_side_panel', input_c)
        self.assertIn('find(widget, "initial-page")', input_c)
        self.assertIn('"tab-layout"', input_c)
        self.assertIn('(menu-layout)', yuck)
        float_c = (ROOT / 'modules/desktop/files/.local/lib/raccon_menu/float_input.c').read_text()
        self.assertIn('popup_geometry_bind(w,344,178)', float_c)
        self.assertIn('countdown_animate(w, 1.0, 200)', float_c)
        self.assertIn('popup_geometry_bind(w,720,232)', float_c)
        self.assertIn('card_drag_motion', float_c)
        music_yuck = (ROOT / 'modules/desktop/files/.config/raccon-music/eww.yuck').read_text()
        self.assertIn('music-drag-surface', music_yuck)
        self.assertIn('music-backdrop', music_yuck)
        countdown_yuck = (ROOT / 'modules/desktop/files/.config/raccon-countdown/eww.yuck').read_text()
        self.assertIn('card-drag-surface', countdown_yuck)
        self.assertIn('countdown-card', countdown_yuck)
        bar = (ROOT / 'modules/waybar/files/.config/waybar/config.jsonc').read_text()
        import json
        bar_data = json.loads(bar)
        self.assertNotIn('exec-if', bar_data['custom/workspace-base'])
        self.assertIn('\ueb0e', bar_data['custom/canvas-mode']['format'])


if __name__ == '__main__':
    unittest.main()
