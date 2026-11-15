"""Tests for raccon-countdown Eww configuration and style integration."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_MODULE = ROOT / "modules/desktop/files"
EWW_DIR = DESKTOP_MODULE / ".config/raccon-countdown"
BACKEND_PY = DESKTOP_MODULE / ".local/lib/raccon_menu/backend.py"


class TestCountdownEww(unittest.TestCase):
    def test_eww_config_files_exist(self):
        yuck = EWW_DIR / "eww.yuck"
        scss = EWW_DIR / "eww.scss"
        self.assertTrue(yuck.exists(), f"Missing {yuck}")
        self.assertTrue(scss.exists(), f"Missing {scss}")

    def test_eww_yuck_structure(self):
        yuck_text = (EWW_DIR / "eww.yuck").read_text(encoding="utf-8")
        # Window definition
        self.assertIn("(defwindow raccon-countdown", yuck_text)
        self.assertIn(':anchor "top center"', yuck_text)
        self.assertIn(':stacking "overlay"', yuck_text)

        # Deflisten for countdown state
        self.assertIn("(deflisten countdown", yuck_text)

        # Actions
        self.assertIn("countdown toggle", yuck_text)
        self.assertIn("countdown stop", yuck_text)

    def test_eww_scss_imports_and_animation(self):
        scss_text = (EWW_DIR / "eww.scss").read_text(encoding="utf-8")
        # System theme imports
        self.assertIn('@import "palette";', scss_text)
        self.assertIn('@import "tokens";', scss_text)
        self.assertIn('@import "desktop-style";', scss_text)

        # End alert animation
        self.assertIn("@keyframes countdown-pulse", scss_text)
        self.assertIn(".state-ended", scss_text)

    def test_backend_sync_appearance_includes_countdown(self):
        backend_text = BACKEND_PY.read_text(encoding="utf-8")
        # Verify raccon-countdown is in sync_popup_appearance
        self.assertIn("'raccon-countdown'", backend_text)


if __name__ == "__main__":
    unittest.main()
