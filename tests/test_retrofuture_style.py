import json
import re
import tempfile
from unittest.mock import patch
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import appearance, main


class RetrofutureStyleTests(unittest.TestCase):
    def colors(self):
        names = ('surface surface_container surface_container_highest on_surface on_surface_variant primary on_primary secondary tertiary outline_variant outline error on_error background on_background').split()
        return {name: '#776655' for name in names}

    def test_profile_is_selectable_without_replacing_existing_styles(self):
        self.assertEqual(main.PROFILES['retrofuture']['name'], 'Raccon Retrofuture')
        self.assertEqual(main.PROFILES['retrofuture']['widget_frame'], 'future')
        self.assertTrue({'modern', 'glass', 'terminal', 'monochrome', 'retro', 'ascii'} <= set(main.PROFILES))

    def test_palette_keeps_text_and_selection_readable(self):
        source = self.colors()
        for seed in ('#111111', '#ffffff', '#ff0000', '#00ff00', '#0000ff'):
            source['primary'] = seed
            colors, _ = main.palette('retrofuture', source)
            self.assertGreaterEqual(main.contrast_ratio(colors['surface_container_highest'], colors['on_surface']), 4.5)
            self.assertGreaterEqual(main.contrast_ratio(colors['primary'], colors['on_primary']), 4.5)
            self.assertGreaterEqual(main.contrast_ratio(colors['surface_container'], colors['on_surface_variant']), 4.5)
        self.assertEqual(source['surface'], '#776655')

    def test_adapter_covers_surfaces_and_reduced_motion(self):
        colors, _ = main.palette('retrofuture', self.colors())
        output = appearance.build('retrofuture', main.PROFILES['retrofuture'], colors)
        tokens = json.loads(output['tokens'])
        self.assertEqual(tokens['style'], 'retrofuture')
        self.assertFalse(tokens['strict'])
        self.assertIn('linear-gradient', output['raccon'])
        self.assertIn('linear-gradient', output['waybar'])
        self.assertIn('.still', output['raccon'])
        self.assertIn('box-shadow', output['swaync'])
        self.assertTrue(all(value.strip() == 'none' for value in re.findall(r'animation:([^;]+);', output['raccon'])))

    def test_gtk_css_is_valid(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        colors, _ = main.palette('retrofuture', self.colors())
        output = appearance.build('retrofuture', main.PROFILES['retrofuture'], colors)
        for key in ('raccon', 'waybar', 'widgets', 'panels', 'selector', 'swaync', 'swayosd', 'widget_editor'):
            with self.subTest(key=key):
                Gtk.CssProvider().load_from_data(output[key].encode())

    def test_dock_icon_size_is_reversible_without_losing_custom_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            bar = home / '.config/waybar/config.jsonc'
            bar.parent.mkdir(parents=True)
            bar.write_text(json.dumps({'position':'bottom','margin-top':0,'margin-left':0,
                'margin-right':0,'margin-bottom':8,'wlr/taskbar':{'icon-size':19,'on-click':'custom-action'}}))
            ini = home / '.config/wayfire.ini'
            ini.write_text('[pixdecor]\nrounded_corner_radius = 14\nborder_size = 0\nshadow_radius = 0\ntitle_font = Inter 10\n')
            state = home / 'state'
            state.mkdir()
            with patch.object(main, 'HOME', home), patch.object(main, 'STATE', state):
                original = main.managed_settings()
                (state / 'geometry.json').write_text(json.dumps(original))
                main.configure_windows('retrofuture')
                current = json.loads(bar.read_text())
                self.assertEqual(current['wlr/taskbar']['icon-size'], 32)
                self.assertEqual(current['wlr/taskbar']['on-click'], 'custom-action')
                main.configure_windows('modern')
                self.assertEqual(json.loads(bar.read_text())['wlr/taskbar']['icon-size'], 19)
