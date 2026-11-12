"""Motion feedback must not change control allocation or hide keyboard actions."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'modules/desktop/files/.config'


class MotionRhythmTests(unittest.TestCase):
    def test_floating_hover_does_not_animate_layout(self):
        css = (CONFIG / 'raccon-float/eww.scss').read_text()
        self.assertNotRegex(css, r'transition:[^;]*(?:min-width|padding)')
        for selectors, declarations in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            if all(':hover' in part or '.expanded-row' in part for part in selectors.split(',')):
                self.assertNotRegex(declarations, r'(?:min-width|padding):')

    def test_session_confirmation_keeps_label_and_icon_slots(self):
        source = (CONFIG / 'raccon-float/eww.yuck').read_text()
        self.assertNotIn(':visible {armed == action}', source)
        self.assertIn(':style {armed == action ? "opacity: 1;" : "opacity: 0;"}', source)
        self.assertNotIn('180 + order * 35', source)

    def test_music_actions_do_not_depend_on_hover(self):
        source = (CONFIG / 'raccon-music/eww.yuck').read_text()
        self.assertNotIn('(revealer :reveal music_open', source)
        self.assertNotIn(':onhover ', source)
        self.assertIn(':tip "Previous"', source)
        self.assertIn(':tip "Next"', source)

    def test_dock_hover_keeps_hit_target_allocation(self):
        css = (ROOT / 'modules/waybar/files/.config/waybar/style.css').read_text()
        for selectors, declarations in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            if '#taskbar button' in selectors and ':hover' in selectors:
                self.assertNotRegex(declarations, r'(?:margin|padding):')

    def test_music_feedback_is_after_theme_and_respects_reduced_motion(self):
        css = (CONFIG / 'raccon-music/eww.scss').read_text()
        self.assertGreater(css.index('.popup.music-popup.motion button'), css.index('@import "desktop-style"'))
        self.assertIn('.popup.music-popup.still', css)
        self.assertIn('160ms', css)
