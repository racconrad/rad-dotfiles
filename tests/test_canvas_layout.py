import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "modules/wayfire/files/.local/bin/raccon-canvas-mode"
BAR = ROOT / "modules/waybar/files/.config/waybar/config.jsonc"


class CanvasLayoutTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.home = Path(scratch.name)
        self.state = self.home / "mode"
        self.state.write_text("normal\n")
        self.log = self.home / "events"
        self.env = {
            **os.environ,
            "HOME": scratch.name,
            "PATH": f"{scratch.name}:/usr/bin:/bin",
        }
        self.stub("eww", 'printf "eww %s\\n" "$*" >> "$HOME/events"')
        self.stub("pkill", 'printf "signal %s\\n" "$1" >> "$HOME/events"')
        self.stub("wf-canvas-mode", """
case "$1" in
    status) cat "$HOME/mode";;
    on) printf 'canvas\\n' > "$HOME/mode";;
    off) printf 'recover\\n' > "$HOME/mode"; printf 'restore failed\\n' >&2; exit 1;;
esac
""")

    def stub(self, name, code):
        program = self.home / name
        program.write_text(f"#!/bin/sh\n{code}\n")
        program.chmod(0o755)

    def invoke(self, action):
        return subprocess.run([WRAPPER, action], env=self.env, capture_output=True, text=True)

    def test_session_path_without_local_bin_still_hides_workspaces(self):
        target = self.home / ".local/bin/wf-canvas-mode"
        target.parent.mkdir(parents=True)
        (self.home / "wf-canvas-mode").rename(target)
        self.env["PATH"] = "/usr/bin:/bin"
        self.state.write_text("canvas\n")
        self.assertEqual(self.invoke("normal").returncode, 1)
        self.assertEqual(self.invoke("label").stdout.strip(), "Canvas")

    def test_bar_opens_layout_selection_without_switching(self):
        self.stub("desktop-menu", 'printf "desktop-menu %s\\n" "$*" >> "$HOME/events"')
        self.assertEqual(self.invoke("menu").returncode, 0)
        self.assertEqual(self.state.read_text().strip(), "normal")
        events = self.log.read_text()
        self.assertIn("layout_status=normal", events)
        self.assertIn("desktop-menu layout", events)
        self.assertNotIn("signal ", events)

    def test_completion_updates_menu_before_sending_bar_signals(self):
        self.assertEqual(self.invoke("on").returncode, 0)
        events = self.log.read_text()
        self.assertLess(events.index("layout_status=changing"), events.index("layout_status=canvas"))
        self.assertLess(events.index("layout_status=canvas"), events.index("signal -RTMIN+8"))
        self.assertEqual(self.invoke("label").stdout.strip(), "Canvas")
        self.assertEqual(self.invoke("normal").returncode, 1)

    def test_failed_restore_never_reports_tiling(self):
        result = self.invoke("off")
        self.assertEqual(result.returncode, 1)
        self.assertIn("layout_status=recover layout_error=restore failed", self.log.read_text())
        self.assertEqual(self.invoke("label").stdout.strip(), "Recovery needed")
        self.assertEqual(self.invoke("normal").returncode, 1)

    def test_layout_and_workspace_modules_refresh_by_signal(self):
        source = BAR.read_text()
        config = json.loads("\n".join(line for line in source.splitlines()
                                      if not line.lstrip().startswith("//")))
        for name in ["canvas-mode", "tiling", "workspace-base"] + [f"ws{i}" for i in range(1, 11)]:
            module = config[f"custom/{name}"]
            self.assertIn("signal", module)
            self.assertNotIn("interval", module)
        self.assertNotIn("wayfire/workspaces", config)
        self.assertNotIn("Workspaces", config["custom/workspace-base"].get("tooltip-format", ""))
        canvas_mod = config["custom/canvas-mode"]
        self.assertEqual(canvas_mod["on-click-right"], "~/.local/bin/canvasctl select")
        self.assertEqual(canvas_mod["on-click-middle"], "~/.local/bin/canvasctl fit")
        self.assertEqual(
            canvas_mod["tooltip-format"],
            "Desktop layout (Tiling / Canvas)\nClick: switch · Right-click: jump window · Middle-click: fit all",
        )

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

    def test_canvas_mode_filters_shortcuts_and_blocks_tinywidgets(self):
        import importlib.util
        import sys
        from unittest.mock import patch

        shortcuts_path = ROOT / "modules/desktop/files/.local/lib/raccon_menu/shortcuts.py"
        spec = importlib.util.spec_from_file_location("test_canvas_shortcuts", shortcuts_path)
        shortcuts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shortcuts)

        real_doc = ROOT / "modules/wayfire/files/.config/wayfire-keys.md"
        doc = self.home / ".config/wayfire-keys.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(
            real_doc.read_text()
            + "\n## Extras\n| Shortcut | Action |\n|---|---|\n| Super+Alt+M | Open TinyWidgets editor |\n"
        )
        bin_dir = self.home / ".local/bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (self.home / "wf-canvas-mode").replace(bin_dir / "wf-canvas-mode")
        self.state.write_text("canvas\n")
        with patch.dict(os.environ, {"HOME": str(self.home)}), patch.object(shortcuts, "DOC", doc):
            canvas_payload = shortcuts.payload()
            titles_canvas = [item["title"] for item in canvas_payload]
            self.assertIn("Canvas", titles_canvas)
            self.assertIn("Window switching and gestures", titles_canvas)
            self.assertNotIn("Focus, move, resize (wf-tile)", titles_canvas)
            self.assertNotIn("Advanced tiling", titles_canvas)
            self.assertNotIn("Snapping (grid) — floating windows", titles_canvas)
            self.assertNotIn("Workspaces", titles_canvas)
            self.assertNotIn("Workspaces and overview", titles_canvas)
            self.assertNotIn("Extras", titles_canvas)
            for item in canvas_payload:
                self.assertNotIn("workspace", item["title"].lower())
                for row in item["rows"]:
                    self.assertNotIn("workspace", row["keys"].lower())
                    self.assertNotIn("workspace", row["action"].lower())
            canvas_section = next(item for item in canvas_payload if item["title"] == "Canvas")
            canvas_keys = [r["keys"] for r in canvas_section["rows"]]
            self.assertIn("Super+M", canvas_keys)
            self.assertIn("Super+Backspace", canvas_keys)
            self.assertIn("Super+Ctrl+Arrows", canvas_keys)
            win_state = next(item for item in canvas_payload if item["title"] == "Window state (wm-actions, core)")
            win_keys = [r["keys"] for r in win_state["rows"]]
            self.assertIn("Super+F", win_keys)
            self.assertNotIn("Super+M", win_keys)
            self.assertNotIn("Super+Shift+D", win_keys)
            self.assertNotIn("Super+Shift+O", win_keys)
            switching = next(item for item in canvas_payload if item["title"] == "Window switching and gestures")
            self.assertEqual(
                [r["keys"] for r in switching["rows"]],
                ["Super+`", "Alt+Tab / Alt+Shift+Tab", "3-finger drag"],
            )

        self.state.write_text("normal\n")
        with patch.dict(os.environ, {"HOME": str(self.home)}), patch.object(shortcuts, "DOC", doc):
            titles_normal = [item["title"] for item in shortcuts.payload()]
            self.assertNotIn("Canvas", titles_normal)
            self.assertIn("Focus, move, resize (wf-tile)", titles_normal)
            self.assertIn("Workspaces", titles_normal)
            self.assertIn("Snapping (grid) — floating windows", titles_normal)
            self.assertIn("Extras", titles_normal)

        sys.path.insert(0, str(ROOT / "modules/power/files/.local/lib"))
        sys.path.insert(0, str(ROOT / "modules/desktop-styles/files/.local/lib"))
        from desktop_power import effects
        from desktop_style import main as style_main

        widgetctl = bin_dir / "widgetctl"
        widgetctl.write_text("#!/bin/sh\necho \"$*\" >> \"$HOME/widgetctl.log\"\n")
        widgetctl.chmod(0o755)
        self.state.write_text("canvas\n")
        with patch.dict(os.environ, {"HOME": str(self.home)}), \
             patch.object(effects, "HOME", self.home), patch.object(effects, "STATE", self.home / "power-state"), \
             patch.object(effects, "run") as power_run:
            effects.widgets({"widgets": True})
            power_run.assert_called_once()
            self.assertEqual(power_run.call_args.args[0][-1], "stop")
        with patch.dict(os.environ, {"HOME": str(self.home)}), patch.object(style_main, "BIN", bin_dir):
            self.assertFalse(style_main.widgets_available())
