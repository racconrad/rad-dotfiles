"""The exported cards must install standalone and build from a different HOME."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bundle_installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class RacconBundleTests(unittest.TestCase):
    def test_portable_card_keyboard_build_and_optional_theme_imports(self):
        choices={key:item['default'] for key,item in installer.CATALOG['choices'].items()}
        with tempfile.TemporaryDirectory(prefix='raccon bundle ') as tmp:
            home=Path(tmp)/'other home'
            for selection in (['desktop'],['desktop-styles']):
                modules=installer.resolve_modules(selection,choices)
                plan=installer.file_plan(home,modules,choices)
                self.assertIn('wallpaper',modules)
                self.assertIn('libjpeg-turbo',installer.CATALOG['modules']['desktop']['packages'])
                for name in ('raccon-menu','raccon-float','raccon-music'):
                    css=plan[f'.config/{name}/eww.scss'][0].decode()
                    import_line='@import "desktop-style";'
                    self.assertEqual(import_line in css,'desktop-styles' in modules)
                    if name=='raccon-menu' and 'desktop-styles' in modules:
                        self.assertLess(css.index(import_line),css.index('.popup.motion'))
                for path,(data,mode) in plan.items():
                    target=home/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(mode)
            build=home/'.local/lib/raccon_menu/keyboard_build.py'
            subprocess.run([sys.executable,str(build)],env={**os.environ,'HOME':str(home)},check=True,capture_output=True)
            self.assertTrue((home/'.cache/raccon-float/keyboard.so').exists())
            data=json.loads(plan['.config/waybar/config.jsonc'][0])
            self.assertEqual(data['custom/power']['on-click'],'~/.local/bin/raccon-float session')
            self.assertNotIn('on-click-release',data['custom/power'])
            self.assertNotIn(str(Path.home()),plan['.local/lib/raccon_menu/walls.py'][0].decode())

if __name__=='__main__':unittest.main()
