import re
import tomllib
import unittest
from collections import Counter
from pathlib import Path


MODULES = Path(__file__).resolve().parents[1] / 'modules'
QUICKSHELL = MODULES / 'quickshell'
SHELL = QUICKSHELL / 'files/.config/quickshell/raccon/shell.qml'
MATUGEN = MODULES / 'themes/files/.config/matugen'


class QuickshellModuleTests(unittest.TestCase):
    def test_qmldir_matches_component_files(self):
        declarations = Counter(
            manifest.parent / fields[-1]
            for manifest in QUICKSHELL.rglob('qmldir')
            for line in manifest.read_text().splitlines()
            if (fields := line.partition('#')[0].split()) and fields[-1].endswith('.qml')
        )
        components = Counter(path for path in QUICKSHELL.rglob('*.qml') if path.name != 'shell.qml')
        self.assertTrue(components)
        self.assertEqual(declarations, components)

    def test_lazy_loaders_are_addressable_over_ipc(self):
        source = SHELL.read_text()
        loaders = re.findall(r'\bLazyLoader\s*\{\s*id:\s*(\w+)', source)
        widgets = re.search(r'\bwidgets:\s*\(\{([^}]+)\}\)', source)
        self.assertTrue(loaders)
        self.assertIsNotNone(widgets)
        keys = {entry.split(':', 1)[0].strip() for entry in widgets[1].split(',')}
        self.assertLessEqual(set(loaders), keys)

    def test_matugen_quickshell_template_is_shipped(self):
        config = tomllib.loads((MATUGEN / 'config.toml').read_text())
        path = config['templates']['quickshell']['input_path'].removeprefix('~/.config/matugen/')
        self.assertTrue((MATUGEN / path).is_file())
