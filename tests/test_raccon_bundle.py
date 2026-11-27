"""The exported desktop/quickshell bundle installs standalone without Eww dependencies."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bundle_installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class RacconBundleTests(unittest.TestCase):
    def test_portable_desktop_bundle_installs_quickshell_without_eww_packages(self):
        choices={key:item['default'] for key,item in installer.CATALOG['choices'].items()}
        with tempfile.TemporaryDirectory(prefix='raccon bundle ') as tmp:
            home=Path(tmp)/'other home'
            modules=installer.resolve_modules(['desktop','desktop-styles'],choices)
            plan=installer.file_plan(home,modules,choices)
            self.assertIn('quickshell',modules)
            self.assertIn('wallpaper',modules)
            self.assertIn('.config/quickshell/raccon/shell.qml',plan)
            pkgs=set(installer.packages_for(modules))
            self.assertIn('quickshell',pkgs)
            self.assertNotIn('eww',pkgs)
            self.assertNotIn('gtk-layer-shell',pkgs)
            self.assertIn('.config/quickshell/raccon/Bar.qml',plan)
            for rel,(raw,_) in plan.items():
                if rel.endswith(('.png','.ttf')):continue
                self.assertNotIn(str(Path.home()),raw.decode(),rel)

if __name__=='__main__':unittest.main()
