import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rdot_install_zsh', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
BASE = (ROOT / 'modules/zsh/files/.zshrc').read_bytes()
CHOICES = {key: info['default'] for key, info in installer.CATALOG['choices'].items()}


class ZshPersonalBlockTests(unittest.TestCase):
    def render(self, home):
        return installer.render('.zshrc', BASE, home, {'zsh'}, CHOICES).decode()

    def test_base_replaces_old_config_but_keeps_personal_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / '.zshrc').write_text('alias old=1\n' + installer.ZSH_PERSONAL + '\nexport JAVA_HOME=/x\n')
            text = self.render(home)
        self.assertNotIn('alias old=1', text)
        self.assertTrue(text.endswith(installer.ZSH_PERSONAL + '\nexport JAVA_HOME=/x\n'))
        self.assertEqual(text.count(installer.ZSH_PERSONAL), 1)

    def test_fresh_install_is_the_base_with_an_empty_personal_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.render(Path(tmp))
        self.assertTrue(text.rstrip().endswith(installer.ZSH_PERSONAL))
        for personal in ('ANDROID', 'JAVA_HOME', 'supabase', 'NVM_DIR', 'GOPATH', 'love'):
            self.assertNotIn(personal, text)


if __name__ == '__main__':
    unittest.main()
