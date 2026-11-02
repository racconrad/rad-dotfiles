"""The new profile stays reversible and uses the guarded wallpaper path."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'modules/desktop-styles/files'
spec = importlib.util.spec_from_file_location('ascii_style', BASE/'.local/lib/desktop_style/main.py')
styles = importlib.util.module_from_spec(spec); spec.loader.exec_module(styles)


class AsciiThemeTests(unittest.TestCase):
    def test_curated_palette_preserves_source_and_has_readable_color_pairs(self):
        source = {'primary': '#112233', 'surface': '#eeeeee'}
        before = source.copy()
        colors, _ = styles.palette('ascii', source)
        self.assertEqual(source, before)
        for bg, fg in [('surface_container','on_surface'), ('surface_container','on_surface_variant'),
                       ('surface_container','secondary'), ('primary','on_primary'),
                       ('secondary','on_secondary'), ('error','on_error')]:
            self.assertGreaterEqual(styles.contrast_ratio(colors[bg], colors[fg]), 4.5)

    def test_companion_is_optional_and_never_bypasses_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(styles, 'HOME', Path(tmp)), patch.object(styles, 'update'), patch.object(styles.subprocess, 'run') as run:
            with self.assertRaises(ValueError): styles.companion_wallpaper('ascii')
            run.assert_not_called()
            image = Path(tmp)/'.local/share/wallpapers/raccon/ascii-bloom.png'
            image.parent.mkdir(parents=True); image.touch()
            styles.companion_wallpaper('ascii')
            self.assertEqual(run.call_args.args[0], [str(styles.BIN/'wallpaper-set'), str(image)])
            with self.assertRaises(ValueError): styles.companion_wallpaper('unknown')
            self.assertEqual(run.call_count, 1)

    def test_contract_includes_ascii_without_forcing_per_instance_frames(self):
        spec = importlib.util.spec_from_file_location('ascii_appearance', BASE/'.local/lib/desktop_style/appearance.py')
        appearance = importlib.util.module_from_spec(spec); spec.loader.exec_module(appearance)
        colors, _ = styles.palette('ascii', {})
        output = appearance.build('ascii', styles.PROFILES['ascii'], colors)
        tokens = json.loads(output['tokens'])
        self.assertTrue(tokens['strict'])
        self.assertFalse(tokens['continuous'])
        self.assertEqual(tokens['widgets'], dict(skin='ascii', frame='ascii', fx='none', background='surface'))
        self.assertNotIn('.rw-window-titlebar {', output['widgets'])
