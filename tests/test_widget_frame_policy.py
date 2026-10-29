"""Theme-specific frame policy, legacy migration and live token publication."""
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
from desktop_style.appearance import resolve
spec=importlib.util.spec_from_file_location('frame_style_engine',LIB/'desktop_style/main.py')
styles=importlib.util.module_from_spec(spec);spec.loader.exec_module(styles)

class FramePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name)/'state';self.state.mkdir()
        self.current=Path(self.tmp.name)/'current';self.current.mkdir()
        for key,value in (('STATE',self.state),('CURRENT',self.current)):
            p=patch.object(styles,key,value);p.start();self.addCleanup(p.stop)
        p=patch.object(styles,'update');p.start();self.addCleanup(p.stop)
        (self.state/'selection.json').write_text('{"style":"modern"}')
        self.tokens=self.current/'tokens.json'
        self.tokens.write_text(json.dumps({'style':'modern','colors':{},'widgets':{'frame':'modern'}}))

    def test_defaults_follow_style(self):
        for name in ('monochrome','glass','modern'):
            self.assertEqual(resolve(name,styles.PROFILES[name],{})['widgets']['frame'],'none')
        for name in ('terminal','retro','gnome','windows'):
            self.assertEqual(resolve(name,styles.PROFILES[name],{})['widgets']['frame'],name)

    def test_inactive_theme_edit_is_saved_without_changing_live_widgets(self):
        before=self.tokens.read_text()
        styles.set_widget_frame('none','windows')
        self.assertEqual(self.tokens.read_text(),before)
        self.assertEqual(styles.widget_frame('windows'),'none')
        self.assertEqual(styles.widget_frame('modern'),'auto')
        styles.set_widget_frame('retro','modern')
        self.assertEqual(json.loads(self.tokens.read_text())['widgets']['frame'],'retro')
        self.assertEqual(styles.widget_frame('windows'),'none')

    def test_auto_restores_active_theme_default(self):
        styles.set_widget_frame('retro','modern')
        styles.set_widget_frame('auto','modern')
        self.assertEqual(json.loads(self.tokens.read_text())['widgets']['frame'],'none')

    def test_legacy_global_choice_is_preserved_for_other_themes(self):
        (self.state/'widget-frame.json').write_text('{"frame":"glass"}')
        styles.set_widget_frame('none','modern')
        self.assertEqual(styles.widget_frame('modern'),'none')
        self.assertEqual(styles.widget_frame('windows'),'glass')
        data=json.loads((self.state/'widget-frame.json').read_text())
        self.assertEqual(data['version'],2)

    def test_apply_uses_target_theme_not_current_theme(self):
        styles.set_widget_frame('future','windows')
        data={'style':'windows','widgets':{'frame':'windows'}}
        self.assertEqual(json.loads(styles.with_widget_frame(json.dumps(data)))['widgets']['frame'],'future')
        self.assertEqual(styles.widget_frame('modern'),'auto')

    def test_bad_choices_are_not_written(self):
        for frame,style in (('unknown','modern'),('none','unknown')):
            with self.assertRaises(ValueError):styles.set_widget_frame(frame,style)
        self.assertFalse((self.state/'widget-frame.json').exists())

if __name__=='__main__':unittest.main()
