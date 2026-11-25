"""Verify Cava audio visualizer helpers, Waybar music pills, and Eww music card CSS."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop/files/.local/lib'))
sys.path.insert(0, str(ROOT / 'modules/base/files/.local/lib'))
sys.path.insert(0, str(ROOT / 'modules/desktop-styles/files/.local/lib'))

import raccon_cava
import raccon_music_status
from raccon_menu import music_viz
from desktop_style import appearance, main as style_main
from desktop_style.waybar import Document, compact


class MusicVisualizerTests(unittest.TestCase):
    def test_cava_parse_energy_and_bars(self):
        vals = raccon_cava.parse_line('0;2;5;9;-1;3;7;1;', bars=8, max_range=7)
        self.assertEqual(vals, [0, 2, 5, 7, 0, 3, 7, 1])
        self.assertEqual(raccon_cava.bars_text(vals), '▁▃▆█▁▄█▂')
        self.assertEqual(raccon_cava.energy_level([0] * 8, max_range=7), 0)
        self.assertEqual(raccon_cava.energy_level([7] * 8, max_range=7), 3)
        self.assertIsNone(raccon_cava.parse_line('not;numbers', bars=4, max_range=7))

    def test_waybar_snapshot_includes_viz_track_and_clean_hide(self):
        playing = raccon_music_status.snapshot(
            'Playing', False, track='Machine Love', bars='▂▄▆█▆▄▂▁', level=2, tooltip='Tip'
        )
        self.assertEqual(playing['viz']['text'], '▂▄▆█▆▄▂▁')
        self.assertEqual(playing['viz']['class'], ['playing', 'level-2'])
        self.assertEqual(playing['track']['text'], 'Machine Love')
        self.assertEqual(playing['track']['class'], ['playing', 'level-2'])

        hidden = raccon_music_status.snapshot('Playing', True, track='Machine Love', bars='▂▄▆█▆▄▂▁', level=2)
        for key in ('open', 'viz', 'track', 'prev', 'play', 'next'):
            self.assertEqual(hidden[key]['text'], '')

    def test_marquee_scrolls_only_overflowing_titles(self):
        self.assertEqual(raccon_music_status.marquee('Short Song', 10, width=22), 'Short Song')
        long_title = 'A Very Long Track Name · Featured Artist'
        self.assertEqual(raccon_music_status.marquee(long_title, 0, width=16), long_title[:16])
        shifted = raccon_music_status.marquee(long_title, 8, width=16)
        self.assertEqual(len(shifted), 16)
        self.assertNotEqual(shifted, long_title[:16])

    def test_music_viz_payload_and_idle_isolation(self):
        payload = music_viz.frame_payload([0, 4, 8, 12, 16, 20, 24, 12, 8, 4, 2, 0])
        self.assertTrue(payload['active'])
        self.assertEqual(payload['b0'], 4)
        self.assertEqual(payload['b6'], 28)
        self.assertIn(payload['level'], (1, 2))

        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            bindir = home / 'bin'
            bindir.mkdir()
            log = home / 'calls'
            for name in ('playerctl', 'cava'):
                tool = bindir / name
                tool.write_text(f'#!/bin/sh\necho {name} >> "{log}"\nexit 0\n')
                tool.chmod(0o755)
            env = {**os.environ, 'HOME': str(home), 'XDG_RUNTIME_DIR': str(home),
                   'PATH': str(bindir) + os.pathsep + os.environ['PATH'],
                   'PYTHONPATH': str(ROOT / 'modules/base/files/.local/lib')}
            script = ROOT / 'modules/desktop/files/.local/lib/raccon_menu/music_viz.py'
            proc = subprocess.Popen([sys.executable, str(script)], env=env, stdout=subprocess.PIPE, text=True)
            try:
                first = json.loads(proc.stdout.readline())
                self.assertEqual(first, music_viz.IDLE)
                self.assertFalse(log.exists())
            finally:
                proc.terminate()
                proc.communicate(timeout=3)

    def test_vertical_waybar_compacts_without_music_track(self):
        text = (ROOT / 'modules/waybar/files/.config/waybar/config.jsonc').read_text()
        self.assertNotIn('custom/music-track', Document(text).data['group/music']['modules'])
        self.assertNotIn('custom/music-track', Document(text).data)
        self.assertNotIn('custom/music-open', Document(text).data['group/music']['modules'])
        self.assertNotIn('custom/music-open', Document(text).data)
        side, saved = compact(text, True, [])
        self.assertEqual(Document(side).data['group/music']['orientation'], 'vertical')
        self.assertNotIn('custom/music-track', Document(side).data['group/music']['modules'])
        self.assertNotIn('custom/music-open', Document(side).data['group/music']['modules'])
        restored, saved = compact(side, False, saved)
        self.assertEqual(Document(restored).data['group/music']['orientation'], 'horizontal')
        self.assertEqual(saved, [])

    def test_waybar_music_viz_has_no_bottom_border_or_open_icon(self):
        import re
        src_colors = dict(re.findall(r'\$(\w+):\s*(#[\da-fA-F]{6});', (ROOT/'modules/desktop-styles/files/.config/desktop-style/_palette.scss').read_text()))
        for style_name in ('modern', 'terminal', 'dynamic', 'collage', 'macxp'):
            colors, _ = style_main.palette(style_name, src_colors)
            css = appearance.build(style_name, style_main.PROFILES[style_name], colors)['waybar']
            self.assertNotIn('custom-music-open', css, style_name)
            for line in css.splitlines():
                if 'custom-music-viz' in line:
                    self.assertNotIn('border-bottom', line, f'{style_name}: {line}')

    def test_waybar_css_and_music_scss_compile_cleanly_in_gtk(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            self.skipTest('GTK display required')

        with tempfile.TemporaryDirectory() as root:
            tmp = Path(root)
            waybar_dir = tmp / 'waybar'
            shutil.copytree(ROOT / 'modules/waybar/files/.config/waybar', waybar_dir)
            style_file = waybar_dir / 'style.css'
            import re
            src_colors = dict(re.findall(r'\$(\w+):\s*(#[\da-fA-F]{6});', (ROOT/'modules/desktop-styles/files/.config/desktop-style/_palette.scss').read_text()))
            colors, _ = style_main.palette('terminal', src_colors)
            output = appearance.build('terminal', style_main.PROFILES['terminal'], colors)
            generated = tmp / 'generated-waybar.css'
            generated.write_text(output['waybar'])
            style_file.write_text(
                style_file.read_text().replace('@RDOT_HOME@/.config/desktop-style/current/waybar.css', str(generated))
            )
            provider = Gtk.CssProvider()
            provider.load_from_path(str(style_file))

            compiler = shutil.which('widgetctl')
            if compiler:
                music_dir = tmp / 'raccon-music'
                shutil.copytree(ROOT / 'modules/desktop/files/.config/raccon-music', music_dir)
                palette = ''.join(f'${k}: {v};\n' for k, v in colors.items())
                palette += '$island_background: $surface_container;\n$island_outline: $outline_variant;\n'
                (music_dir / '_palette.scss').write_text(palette)
                (music_dir / '_desktop-style.scss').write_text(output['raccon'])
                compiled = music_dir / 'compiled.css'
                res = subprocess.run([compiler, 'compile-css', music_dir / 'eww.scss', compiled],
                                     cwd=music_dir, capture_output=True, text=True, timeout=15)
                self.assertEqual(res.returncode, 0, res.stderr)
                Gtk.CssProvider().load_from_path(str(compiled))


if __name__ == '__main__':
    unittest.main()
