"""Geometry contracts for bar placement; no live desktop changes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'modules/desktop/files/.local/lib/raccon_menu/positioning.py'
spec=importlib.util.spec_from_file_location('shell_positioning',SOURCE)
position=importlib.util.module_from_spec(spec);spec.loader.exec_module(position)

class PlacementTests(unittest.TestCase):
    def test_bar_geometry_includes_margin_and_uses_four_pixel_gap(self):
        screen=dict(x=0,y=0,width=1920,height=1080)
        for edge,bar,inset in (
            ('bottom',dict(x=14,y=1010,width=1892,height=60),74),
            ('top',dict(x=14,y=10,width=1892,height=60),74),
            ('left',dict(x=10,y=14,width=60,height=1052),74),
            ('right',dict(x=1850,y=14,width=60,height=1052),74),
        ):
            with self.subTest(edge=edge):
                data=position.layout({'position':'bottom'},bar,screen)
                self.assertEqual(data['edge'],edge);self.assertEqual(data['inset'],inset)
                self.assertEqual(data['start'],14);self.assertEqual(data['end'],14)

    def test_fallback_supports_each_configured_edge(self):
        for edge in ('bottom','top','left','right'):
            bar={'position':edge,'height':40,'width':52,'margin-'+edge:6}
            data=position.layout(bar)
            self.assertEqual(data['edge'],edge)
            self.assertEqual(data['inset'],50 if edge in ('top','bottom') else 62)

    def test_jsonc_keeps_comments_inside_strings_and_selects_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config.jsonc'
            path.write_text('[/* header */ {"position":"top","output":"eDP-1","tooltip":"https://example.test/a//b"},\n// select second\n{"position":"left","output":["HDMI-A-1"]}]')
            with patch.object(position,'CONFIG',path):
                self.assertEqual(position.config('HDMI-A-1')['position'],'left')
                self.assertEqual(position.config('eDP-1')['tooltip'],'https://example.test/a//b')

    def test_actual_bar_position_overrides_stale_configuration(self):
        focus={'info':{'name':'DP-2','geometry':dict(x=1920,y=0,width=1280,height=720)}}
        views=[dict(mapped=True,**{'app-id':'waybar','output-name':'DP-2'},geometry=dict(x=0,y=4,width=1280,height=42))]
        with patch.object(position,'ipc',side_effect=[focus,views]),patch.object(position,'config',return_value={'position':'bottom'}):
            data=position.current()
        self.assertEqual(data['edge'],'top');self.assertEqual(data['inset'],50)
        self.assertEqual(data['ox'],1920)

    def test_invalid_compositor_response_falls_back_without_crashing(self):
        for responses in ([None],[{'info':None},{'error':'disabled'}],[{'info':{'name':'test'}},{'error':'disabled'}]):
            with patch.object(position,'ipc',side_effect=responses),patch.object(position,'config',return_value={'position':'left'}):
                self.assertEqual(position.current()['edge'],'left')

    def test_missing_compositor_uses_configuration(self):
        with patch.object(position,'ipc',side_effect=OSError),patch.object(position,'config',return_value={'position':'right','width':60}):
            data=position.current()
        self.assertEqual(data['edge'],'right');self.assertEqual(data['inset'],64)

if __name__=='__main__':unittest.main()
