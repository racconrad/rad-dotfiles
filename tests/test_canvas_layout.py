import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CanvasLayoutTests(unittest.TestCase):

    def test_canvas_overlay_disables_widgets_workspaces_and_tiling_bindings(self):
        overlay = (ROOT / "crates/canvas-session/src/overlay.ini").read_text()
        for key in (
            "workspaces_state = /bin/true",
            "binding_widgets = disabled",
            "binding_widgets_menu = disabled",
            "binding_widgets_toggle = disabled",
            "binding_ws1 = disabled",
            "binding_sendws1 = disabled",
            "binding_tile_preselect = disabled",
            "binding_scratch_1_toggle = disabled",
            "with_win_left = disabled",
            "with_win_right = disabled",
            "with_win_up = disabled",
            "with_win_down = disabled",
            "toggle_sticky = disabled",
            "toggle_all = disabled",
            "toggle = disabled",
            "enable_horizontal = false",
            "open_animation = none",
            "close_animation = zoom",
            "duration = 220ms sigmoid",
            "zoom_duration = 220ms sigmoid",
        ):
            self.assertIn(key, overlay)
