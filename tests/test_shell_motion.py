"""Interaction motion and removed terminal controls remain consistent."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BAR = ROOT / 'modules/waybar/files/.config/waybar'
SOURCE = ROOT / 'modules/desktop/files/.local/lib/raccon_menu/backend.py'
spec = importlib.util.spec_from_file_location('shell_motion_menu', SOURCE)
menu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(menu)


class ShellMotionTests(unittest.TestCase):
    def test_visual_style_does_not_disable_interaction_motion(self):
        for style in ('ascii', 'terminal', 'monochrome', 'retro', 'modern'):
            with self.subTest(style=style), patch.object(menu, 'appearance_tokens',
                    return_value=dict(style=style, strict=True)), patch.object(menu, 'motion', return_value=.6):
                self.assertTrue(menu.appearance_state({})['motion'])
        with patch.object(menu, 'motion', return_value=0):
            self.assertFalse(menu.appearance_state({})['motion'])

    def test_desktop_entry_uses_unlocalized_name(self):
        from gi.repository import Gio
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'files.desktop'
            path.write_text('[Desktop Entry]\nType=Application\nName=Archivos\nName[en]=Files\nName[es]=Archivos\nExec=true\n')
            app = Gio.DesktopAppInfo.new_from_filename(str(path))
            with patch.object(Gio.AppInfo, 'get_all', return_value=[app]), \
                    patch.object(menu, 'write'), patch.object(Gio.DesktopAppInfo, 'get_display_name', return_value='Archivos'):
                result = menu.applications()[0]
                self.assertEqual(result['name'], 'Files')
                self.assertIn('files', result['search'])
                self.assertIn('archivos', result['search'])

    def test_quick_terminal_has_no_remaining_module_configuration(self):
        for path in (ROOT / 'modules').rglob('*'):
            if path.is_file() and path.suffix in ('.css', '.jsonc', '.yuck', '.ini'):
                self.assertNotIn('quick-terminal', path.read_text(), str(path))

    def test_theme_font_preserves_eva_before_nerd_font(self):
        source = ROOT / 'modules/desktop-styles/files/.local/lib/desktop_style/appearance.py'
        self.assertIn('"{font}", "Eva-Icons", "JetBrainsMono Nerd Font Propo"', source.read_text())

    def test_waybar_motion_override_follows_theme(self):
        css = (BAR / 'style.css').read_text()
        self.assertIn('@import "motion.css";', css)
        self.assertGreater(css.index('@import "motion.css";'), css.index('/current/waybar.css'))
        motion = (BAR / 'motion.css').read_text()
        self.assertIn('transition:', motion)
        self.assertNotIn('infinite', motion)

    def test_remaining_waybar_launcher_icons_and_tooltips(self):
        config = json.loads((BAR / 'config.jsonc').read_text())
        self.assertIn('\ueb91', config['custom/hardware-toggle']['exec'])
        self.assertIn('\ueb31', config['custom/workspace-base']['exec'])
        self.assertNotIn('usados', config['disk#home']['tooltip-format'])
        for name in ('temperature', 'backlight', 'bluetooth'):
            self.assertTrue(config[name]['tooltip'])
            self.assertTrue(config[name]['tooltip-format'])
