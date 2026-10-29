"""Widget/media/editor contracts for every desktop profile, without a display."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'modules/desktop-styles/files/.local/lib/desktop_style'
def load(name):
    spec=importlib.util.spec_from_file_location('widget_theme_'+name, BASE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
appearance=load('appearance');styles=load('main')
chrome='.rw-motion-space .rw-window-frame:not(.rw-frame-none)'

class WidgetThemeTests(unittest.TestCase):
    def setUp(self):
        self.source=styles.read(styles.STATE/'source.json')

    def test_all_profiles_have_complete_widget_contracts(self):
        for name,profile in styles.PROFILES.items():
            colors,_=styles.palette(name,self.source)
            output=appearance.build(name,profile,colors)
            tokens=json.loads(output['tokens'])
            self.assertIn(tokens['widgets']['frame'], ('none','monochrome','terminal','retro','glass','modern','gnome','windows'))
            self.assertEqual(tokens['widgets']['fx'], 'none' if tokens['strict'] else 'focus')
            self.assertIn(profile['font'], output['widget_editor'])
            self.assertNotIn(chrome+' .rw-window-titlebar {', output['widgets'])
            self.assertIn(colors['on_primary'], output['widgets'])

    def test_media_does_not_receive_text_card_padding_or_background_reset(self):
        for name,profile in styles.PROFILES.items():
            colors,_=styles.palette(name,self.source)
            css=appearance.build(name,profile,colors)['widgets']
            rules=[(selector,body) for selector,body in re.findall(r'([^{}]+)\{([^{}]*)\}',css) if '.photo-frame' in selector or '.image-frame' in selector]
            self.assertTrue(rules)
            for selector,body in rules:
                self.assertNotRegex(body,r'\bbackground\s*:')
                self.assertNotIn('background-image',body)
                self.assertNotIn('background-size',body)
                self.assertIn('padding: 0',body)
                self.assertIn('border-width: 0',body)

    def test_editor_selection_has_matching_contrast_pair(self):
        for name,profile in styles.PROFILES.items():
            colors,_=styles.palette(name,self.source)
            css=appearance.build(name,profile,colors)['widget_editor']
            self.assertIn('.wcard:hover label',css)
            self.assertIn('color: '+colors['on_primary'],css)
            self.assertIn('font-family: "'+profile['font']+'"',css)

if __name__=='__main__':unittest.main()
