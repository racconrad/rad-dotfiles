"""Tests for collage palette contrast on dark surfaces."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))
from desktop_style import collage, main


class CollageContrastTests(unittest.TestCase):
    def test_dark_surface_contrast_thresholds(self):
        samples = [
            {'surface': '#121212', 'primary': '#526d7a'},
            {'surface': '#101014', 'primary': '#a9b1d6'},
            {'surface': '#0e1015', 'primary': '#70a7c2'},
        ]

        # With and without wallpaper accents; a fixed list keeps the test independent of the real wallpaper.
        wallpapers = ([], ['#e0457b'], ['#e0457b', '#f2c744', '#3fb8af'])
        for sample, accents in ((s, a) for s in samples for a in wallpapers):
            with self.subTest(sample=sample, accents=accents):
                colors, _ = collage.palette(sample, accents=accents)

                # 1. on_surface and on_surface_variant >= 7.0 vs containers
                for text_role in ('on_surface', 'on_surface_variant'):
                    for surf_role in ('surface_container_highest', 'surface_container'):
                        cr = main.contrast_ratio(colors[surf_role], colors[text_role])
                        self.assertGreaterEqual(
                            cr, 7.0,
                            f"{text_role} vs {surf_role} contrast {cr:.2f} < 7.0"
                        )

                # 2. each *_container text (on_*_container) >= 7.0 vs container
                container_roles = [
                    k for k in colors
                    if k.endswith('_container') and not k.startswith('on_') and not k.startswith('surface_')
                ]
                for container in container_roles:
                    on_container = f'on_{container}'
                    if on_container in colors:
                        cr = main.contrast_ratio(colors[container], colors[on_container])
                        self.assertGreaterEqual(
                            cr, 7.0,
                            f"{on_container} vs {container} contrast {cr:.2f} < 7.0"
                        )

                # 3. each accent (primary, secondary, tertiary) >= 6.0 vs surface_container_highest
                for accent in ('primary', 'secondary', 'tertiary'):
                    cr = main.contrast_ratio(colors['surface_container_highest'], colors[accent])
                    self.assertGreaterEqual(
                        cr, 6.0,
                        f"{accent} vs surface_container_highest contrast {cr:.2f} < 6.0"
                    )

    def test_wallpaper_accents_set_distinct_role_hues(self):
        colors, _ = collage.palette({'surface': '#121212', 'primary': '#526d7a'}, accents=['#e0457b', '#f2c744', '#3fb8af'])
        hues = [collage.colorsys.rgb_to_hls(*collage.rgb(colors[r]))[0] for r in ('primary', 'secondary', 'tertiary')]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertGreaterEqual(collage._hue_distance(hues[i], hues[j]), .07)


if __name__ == '__main__':
    unittest.main()
