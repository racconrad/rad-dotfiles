import configparser
import json
import os
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_wf_tile import FakeIPC, view

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / 'modules/wayfire/files'
loader = importlib.machinery.SourceFileLoader('raccon_ux_tile', str(FILES / '.local/bin/wf-tile'))
spec = importlib.util.spec_from_loader(loader.name, loader)
tile = importlib.util.module_from_spec(spec)
loader.exec_module(tile)


class RacconUXTests(unittest.TestCase):
    def setUp(self):
        self.config = configparser.ConfigParser(interpolation=None, strict=False)
        self.config.read(FILES / '.config/wayfire.ini')

    def test_floating_default_keeps_explicit_tiling_available(self):
        self.assertEqual(self.config['simple-tile']['tile_by_default'], 'false')
        self.assertIn('simple-tile', self.config['core']['plugins'].split())
        self.assertNotIn('snap-tiling', self.config['core']['plugins'].split())
        self.assertEqual(self.config['command']['command_window_tile'], '~/.local/bin/wf-tile-ctl toggle')

    def test_swipes_do_not_compete_with_three_finger_drag(self):
        self.assertEqual(self.config['input']['3fg_drag'], '3fg-drag')
        self.assertEqual(self.config['vswipe']['fingers'], '4')
        self.assertEqual(self.config['vswipe']['enable_vertical'], 'false')

    def test_floating_default_and_explicit_workspace_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'wayfire.ini'
            config.write_text('[simple-tile]\ntile_by_default = false\n')
            with patch.object(tile, 'INI', str(config)), patch.object(tile, 'FLOAT_STATE', str(Path(directory) / 'modes.json')):
                self.assertTrue(tile.workspace_floating('1:0:0'))
                tile.save_workspace_mode('1:0:0', False)
                self.assertFalse(tile.workspace_floating('1:0:0'))
                tile.save_workspace_mode('1:0:0', True)
                self.assertTrue(tile.workspace_floating('1:0:0'))
                tile.save_workspace_mode('1:0:0', False)
                self.assertTrue(tile.workspace_floating('1:1:0'))
                self.assertTrue(tile.workspace_floating('2:0:0'))

    def test_legacy_tiling_default_remains_compatible(self):
        with patch.object(tile, 'get_ini_option', return_value='true'), patch.object(tile, 'load_floating', return_value=set()):
            self.assertFalse(tile.workspace_floating('1:0:0'))
        with patch.object(tile, 'get_ini_option', return_value='false'), patch.object(tile, 'load_floating', return_value={'1:0:0'}):
            self.assertTrue(tile.workspace_floating('1:0:0'))

    def test_workspace_toggle_tiles_explicitly_and_preserves_utilities(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'wayfire.ini'
            config.write_text('[simple-tile]\ntile_by_default = false\n')
            ipc = FakeIPC({'vertical-split': []}, [view(1, **{'tiled-edges': 0}),
                          view(2, **{'tiled-edges': 0, 'app-id': 'pavucontrol'})])
            with patch.object(tile, 'INI', str(config)), patch.object(tile, 'FLOAT_STATE', str(Path(directory) / 'modes.json')), \
                    patch.object(tile, 'notify'), patch.object(tile, 'remember_geometry'):
                tile.cmd_mode(ipc, 'toggle')
                self.assertEqual([vid for vid, _ in tile.leaves(ipc.layout)], [1])
                self.assertFalse(tile.workspace_floating('1:0:0'))
                tile.cmd_mode(ipc, 'toggle')
                self.assertEqual(list(tile.leaves(ipc.layout)), [])
                self.assertTrue(tile.workspace_floating('1:0:0'))

    def test_waybar_status_reflects_floating_default_without_daemon(self):
        loader = importlib.machinery.SourceFileLoader('raccon_ux_status', str(FILES / '.local/bin/wf-tile-mode'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        status = importlib.util.module_from_spec(spec)
        loader.exec_module(status)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / 'wayfire.ini'
            config.write_text('[simple-tile]\ntile_by_default = false\n')
            modes = home / 'modes.json'
            with patch.dict(os.environ, {'HOME': directory, 'XDG_CACHE_HOME': str(home / 'cache'),
                                         'WAYFIRE_CONFIG_FILE': str(config), 'WF_TILE_FLOAT_STATE': str(modes)}):
                self.assertEqual(status.get_tile_status()['alt'], 'float')
                modes.write_text(json.dumps(['tile:1:0:0']))
                self.assertEqual(status.get_tile_status()['alt'], 'tile')
