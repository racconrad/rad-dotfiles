import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'modules/wallpaper/files/.local/bin/wayfire-theme-apply'
STYLE = ROOT / 'modules/desktop-styles/files/.local/lib/desktop_style/main.py'


class LayerWriterTests(unittest.TestCase):
    def theme_home(self, home):
        root = home / '.config'
        (root / 'wayfire').mkdir(parents=True)
        (root / 'matugen/out').mkdir(parents=True)
        (root / 'matugen/out/wayfire-colors.sh').write_text('\n'.join(
            f'WF_{key}=112233' for key in ('PRIMARY', 'ON_PRIMARY', 'SURFACE', 'SURFACE_CONTAINER',
                                          'ON_SURFACE', 'ON_SURFACE_VARIANT', 'OUTLINE_VARIANT')))
        (root / 'wayfire.ini').write_text('[core]\nbackground_color = old\n')
        (root / 'wayfire/raccon.ini').write_text('[core]\nbackground_color = base\n')
        bin_dir = home / '.local/bin'
        bin_dir.mkdir(parents=True)
        sync = bin_dir / 'wayfire-config'
        sync.write_text('#!/bin/sh\nprintf sync > "$HOME/synced"\n')
        sync.chmod(0o755)
        return root

    def test_theme_updates_base_not_effective(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = self.theme_home(home)
            subprocess.run(['bash', str(THEME)], env={**os.environ, 'HOME': str(home),
                'WAYFIRE_CONFIG_FILE': str(root / 'wayfire.ini')}, check=True)
            self.assertIn('112233', (root / 'wayfire/raccon.ini').read_text())
            self.assertIn('old', (root / 'wayfire.ini').read_text())
            self.assertTrue((home / 'synced').exists())

    def test_theme_explicit_custom_config_is_not_redirected(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = self.theme_home(home)
            custom = home / 'nested.ini'
            custom.write_text('[core]\nbackground_color = custom\n')
            subprocess.run(['bash', str(THEME)], env={**os.environ, 'HOME': str(home),
                'WAYFIRE_CONFIG_FILE': str(custom)}, check=True)
            self.assertIn('112233', custom.read_text())
            self.assertIn('base', (root / 'wayfire/raccon.ini').read_text())
            self.assertFalse((home / 'synced').exists())

    def test_style_writes_user_options_in_layered_mode(self):
        spec = importlib.util.spec_from_file_location('layer_style', STYLE)
        style = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(style)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / '.config/wayfire').mkdir(parents=True)
            (home / '.config/wayfire/raccon.ini').write_text('[pixdecor]\nborder_size = 1\n')
            (home / '.config/waybar').mkdir()
            (home / '.config/waybar/config.jsonc').write_text('{"position":"top"}')
            api = Mock()
            with patch.object(style, 'HOME', home), patch.dict('sys.modules', {'wayfire_config': api}):
                style.set_managed({'bar': {'position': 'bottom'}, 'window': {'border_size': 2}})
            api.set_options.assert_called_once_with(home / '.config', 'pixdecor', {'border_size': 2})

    def test_display_layers_preserve_unrelated_options_without_duplicate_outputs(self):
        import configparser
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = self.theme_home(home)
            user = root / 'wayfire/user.ini'
            user.write_text('[input]\nnatural_scroll = false\n[output:eDP-1]\nscale = 2\nmode = old\n')
            drm = home / 'drm'
            connector = drm / 'card0-eDP-1'
            connector.mkdir(parents=True)
            (connector / 'status').write_text('connected\n')
            (connector / 'modes').write_text('1920x1080\n')
            source = (ROOT / 'modules/wayfire/files/.local/bin/display-mode').read_text()
            script = home / 'display-mode'
            script.write_text(source.replace('/sys/class/drm', str(drm)))
            subprocess.run(['bash', str(script), 'laptop'], env={**os.environ,
                'HOME': str(home), 'WAYFIRE_CONFIG_FILE': str(root / 'wayfire.ini'),
                'PYTHONPATH': str(ROOT / 'modules/wayfire/files/.local/lib')}, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            parsed = configparser.ConfigParser(interpolation=None)
            parsed.read(user)
            self.assertEqual(parsed['input']['natural_scroll'], 'false')
            self.assertEqual(parsed['output:eDP-1']['mode'], 'auto')
            self.assertEqual(parsed['output:eDP-1']['scale'], '2')
