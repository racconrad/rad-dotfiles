"""Progressive loading and startup checks for Collage desktop style."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))


class StyleTests(unittest.TestCase):
    def test_collage_profile_is_available_without_rendering(self):
        from desktop_style import main as s
        self.assertIn('collage', s.PROFILES)
        self.assertEqual(s.normalize_style('modern'), 'collage')
        self.assertEqual(s.PROFILES['collage']['name'], 'Collage')


if __name__ == '__main__':
    unittest.main()
