from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import capture


class CapturePrivacyTests(unittest.TestCase):
    def test_wallpaper_names_and_folder_never_leave_the_machine(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / '.config/waypaper').mkdir(parents=True)
            (home / '.config/waypaper/config.ini').write_text('[Settings]\nfolder = /media/disk/walls\n')
            text = capture.sanitize('x', (f'url("{home}/Pictures/Wallpapers/me.jpeg") /media/disk/walls/a.png\n'
                                          f'{home}/.local/share/wallpapers/raccon/b.png\nWALL=/media/disk/walls\n'), home)
        for private in ('me.jpeg', 'a.png', 'b.png', '/media/disk', tmp):
            self.assertNotIn(private, text)
        self.assertEqual(text.count(capture.PUBLIC_WALLPAPER), 3)
        self.assertIn('WALL=@RDOT_HOME@/Pictures/Wallpapers\n', text)

    def test_gtklock_background_image_becomes_a_color(self):
        css = 'window {\n  background-image: url("/x/y.png");\n  background-size: cover;\n  background-position: center;\n}\n'
        out = capture.sanitize('.config/gtklock/style.css', css, Path('/nonexistent'))
        self.assertEqual(out, 'window {\n  background-color: @surface;\n}\n')

    def test_owner_real_name_is_replaced_but_runtime_ids_stay(self):
        with patch.object(capture, 'real_name', return_value='Ana'):
            out = capture.sanitize('x', 'Ana · menu\nBanana ~/.local/lib/ana-widgets\n', Path('/nonexistent'))
        self.assertEqual(out, 'Raccon · menu\nBanana ~/.local/lib/ana-widgets\n')


if __name__ == '__main__':
    unittest.main()
