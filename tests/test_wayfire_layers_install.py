import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('layers_install', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class LayerInstallTests(unittest.TestCase):
    def plan(self, home):
        choices = {key: value['default'] for key, value in installer.CATALOG['choices'].items()}
        return installer.file_plan(home, ['wayfire'], choices)

    def test_new_install_has_base_user_and_effective(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.plan(Path(directory))
            self.assertIn('.config/wayfire/raccon.ini', plan)
            self.assertIn('.config/wayfire/user.ini', plan)
            self.assertIn('.config/wayfire.ini', plan)

    def test_preserves_existing_user_and_applies_override(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            user = home / '.config/wayfire/user.ini'
            user.parent.mkdir(parents=True)
            user.write_text('[input]\nnatural_scroll = false\n')
            plan = self.plan(home)
            self.assertNotIn('.config/wayfire/user.ini', plan)
            self.assertIn('natural_scroll = false', plan['.config/wayfire.ini'][0].decode())
            self.assertIn('natural_scroll = true', plan['.config/wayfire/raccon.ini'][0].decode())

    def test_migrates_legacy_custom_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            current = home / '.config/wayfire.ini'
            current.parent.mkdir()
            current.write_text('[orbit]\nspeed = 40\n')
            plan = self.plan(home)
            self.assertIn('speed = 40', plan['.config/wayfire/user.ini'][0].decode())

    def test_receipt_excludes_user_and_generated_output(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            plan = self.plan(home)
            choices = {key: value['default'] for key, value in installer.CATALOG['choices'].items()}
            installer.apply_plan(home, plan, ['wayfire'], choices)
            receipt = installer.read_receipt(home)
            self.assertNotIn('.config/wayfire/user.ini', receipt['files'])
            self.assertNotIn('.config/wayfire.ini', receipt['files'])
            self.assertIn('.config/wayfire/raccon.ini', receipt['files'])

    def test_update_accepts_generated_user_overrides(self):
        from module_update import inspect_plan
        from wayfire_config import sync
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            plan = self.plan(home)
            for relative, (data, mode) in plan.items():
                target = home / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(mode)
            (home / '.config/wayfire/user.ini').write_text('[input]\nnatural_scroll = false\n')
            sync(home / '.config')
            _, conflicts = inspect_plan(home, self.plan(home), {'files': {}})
            self.assertNotIn('.config/wayfire.ini', conflicts)
