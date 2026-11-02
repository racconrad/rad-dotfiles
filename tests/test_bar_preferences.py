"""Bar layout preferences survive theme changes, including rollback on failure."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'modules/desktop-styles/files/.local/lib'
sys.path.insert(0,str(LIB))
from desktop_style import main as styles
from desktop_style.appearance import build
from desktop_style.waybar import Document, compact


class BarPreferencesTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);home=Path(temp.name)
        for key,value in [('HOME',home),('CONFIG',home/'.config/desktop-style'),
                          ('CURRENT',home/'.config/desktop-style/current'),('STATE',home/'state')]:
            p=patch.object(styles,key,value);p.start();self.addCleanup(p.stop)
        self.bar=home/'.config/waybar/config.jsonc';self.bar.parent.mkdir(parents=True)
        self.bar.write_text('{"position":"top","margin-top":0,"margin-bottom":0,"margin-left":0,"margin-right":0}')

    def test_all_profiles_default_to_bottom_islands_and_keep_explicit_overrides(self):
        for prefs in (None,dict(position='top',layout='continuous'),dict(position='bottom',layout='islands')):
            if prefs:styles.save(styles.CONFIG/'waybar.json',prefs)
            expected=prefs or dict(position='bottom',layout='islands')
            for name in styles.PROFILES:
                styles.configure_bar(name)
                bar=json.loads(self.bar.read_text())
                self.assertEqual(bar['position'],expected['position'])
                self.assertEqual(styles.bar_profile(name)['continuous'],expected['layout']=='continuous')
                self.assertEqual(bar['margin-top'],10 if expected==dict(position='top',layout='islands') else 0)
                self.assertEqual(bar['margin-bottom'],10 if expected==dict(position='bottom',layout='islands') else 0)

    def test_partial_or_invalid_preferences_fall_back_per_field(self):
        for value,expected in [(dict(position='top'),dict(position='top',layout='islands')),
                                (['bad'],dict(position='bottom',layout='islands')),
                                (dict(position='oops',layout='continuous'),dict(position='bottom',layout='continuous'))]:
            styles.save(styles.CONFIG/'waybar.json',value)
            self.assertEqual(styles.bar_preferences(),expected)

    def test_failed_bar_restart_restores_files_and_preferences(self):
        previous=self.bar.read_bytes()
        with patch.object(styles,'source_palette',return_value={}),patch.object(styles,'palette',return_value=({},[])),\
             patch('desktop_style.appearance.build',return_value={'waybar':'new css'}),\
             patch.object(styles,'reload_bar_style'),patch.object(styles,'restart_bar',side_effect=OSError('Cannot connect')):
            with self.assertRaises(OSError):styles.set_bar('position','bottom')
        self.assertEqual(self.bar.read_bytes(),previous)
        self.assertFalse((styles.CONFIG/'waybar.json').exists())

    def test_side_positions_use_vertical_dimensions_groups_and_correct_margins(self):
        self.bar.write_text('// keep this comment\n' + json.dumps({
            'position': 'bottom', 'height': 58, 'margin-top': 0, 'margin-bottom': 10,
            'margin-left': 14, 'margin-right': 14,
            'group/workspaces': {'orientation': 'horizontal', 'modules': ['custom/ws1']},
            'clock': {'format': '{:%H:%M}', 'on-click': 'calendar'},
            'wireplumber': {'format': '{icon} {volume}%', 'on-scroll-up': 'volume-up'}}))
        for edge in ('left', 'right'):
            for layout in ('islands', 'continuous'):
                styles.save(styles.CONFIG/'waybar.json', dict(position=edge, layout=layout))
                for name in styles.PROFILES:
                    styles.configure_bar(name)
                    bar = Document(self.bar.read_text()).data
                    self.assertEqual((bar['position'], bar['width'], bar['height']), (edge, 64, 0))
                    self.assertEqual(bar['group/workspaces']['orientation'], 'vertical')
                    self.assertEqual(bar['clock']['format'], '{:%H\n%M}')
                    self.assertEqual(bar['clock']['on-click'], 'calendar')
                    self.assertEqual(bar['wireplumber']['on-scroll-up'], 'volume-up')
                    for side in ('left', 'right', 'top', 'bottom'):
                        self.assertEqual(bar['margin-'+side], 0 if layout == 'continuous' else
                                         14 if side in ('top','bottom') else 10 if side == edge else 0)
        styles.save(styles.CONFIG/'waybar.json', dict(position='top', layout='islands'))
        styles.configure_bar('retro')
        restored = Document(self.bar.read_text()).data
        self.assertEqual(restored['height'], 58)
        self.assertNotIn('width', restored)
        self.assertEqual(restored['clock'], {'format': '{:%H:%M}', 'on-click': 'calendar'})
        self.assertEqual(restored['wireplumber']['format'], '{icon} {volume}%')
        self.assertEqual(restored['group/workspaces']['orientation'], 'horizontal')
        self.assertIn('// keep this comment', self.bar.read_text())
        self.assertFalse((styles.STATE/'waybar-horizontal.json').exists())

    def test_jsonc_patch_preserves_comments_urls_trailing_commas_and_actions(self):
        text = '''// Header
{
  "height": 62, // User height
  "position": "bottom",
  "clock": {"format": "{:%T}", /* preserve */ "on-click": "echo https://test/",},
  "custom/mine": {"exec": "echo \\\"/* not a comment */\\\"",},
}'''
        side, saved = compact(text, True, [])
        self.assertIn('/* preserve */', side)
        self.assertIn('// User height', side)
        restored, saved = compact(side, False, saved)
        self.assertEqual(Document(restored).data, Document(text).data)
        self.assertEqual(saved, [])

    def test_side_restart_failure_also_restores_horizontal_snapshot(self):
        before = self.bar.read_text()
        with patch.object(styles,'source_palette',return_value={}),patch.object(styles,'palette',return_value=({},[])),\
             patch('desktop_style.appearance.build',return_value={'waybar':'new css'}),\
             patch.object(styles,'reload_bar_style'),patch.object(styles,'restart_bar',side_effect=OSError('No display')):
            with self.assertRaises(OSError): styles.set_bar('position','left')
        self.assertEqual(self.bar.read_text(), before)
        self.assertFalse((styles.STATE/'waybar-horizontal.json').exists())

    def test_changing_side_never_overwrites_original_horizontal_formats(self):
        initial = '{"height": 70, "width": 1200, "clock": {"format": "user format"}}'
        first, saved = compact(initial, True, [])
        second, saved = compact(first, True, saved)
        restored, _ = compact(second, False, saved)
        self.assertEqual(Document(restored).data, Document(initial).data)


if __name__=='__main__':unittest.main()
