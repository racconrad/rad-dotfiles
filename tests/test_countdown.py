"""Unit tests for the countdown engine and time parser."""
from datetime import datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'modules/desktop/files/.local/lib'))

from raccon_countdown.engine import CountdownEngine, format_remaining, parse_time_spec


class TestCountdownEngine(unittest.TestCase):
    def test_parse_duration_units(self):
        self.assertEqual(parse_time_spec("45s"), 45)
        self.assertEqual(parse_time_spec("25m"), 1500)
        self.assertEqual(parse_time_spec("1h"), 3600)
        self.assertEqual(parse_time_spec("1h30m"), 5400)
        self.assertEqual(parse_time_spec("1h30m10s"), 5410)
        self.assertEqual(parse_time_spec("90"), 90)

    def test_parse_target_time(self):
        now = datetime(2026, 11, 14, 18, 0, 0)
        # Target in the future today
        self.assertEqual(parse_time_spec("18:30", now=now), 1800)
        self.assertEqual(parse_time_spec("18:30:15", now=now), 1815)
        # Target in the past today -> targets tomorrow (10:00 is 16 hours ahead)
        self.assertEqual(parse_time_spec("10:00", now=now), 16 * 3600)
        # 12-hour format with am/pm
        self.assertEqual(parse_time_spec("7pm", now=now), 3600)
        self.assertEqual(parse_time_spec("7:30pm", now=now), 5400)
        self.assertEqual(parse_time_spec("6am", now=now), 12 * 3600)

    def test_parse_invalid(self):
        with self.assertRaises(ValueError):
            parse_time_spec("invalid")
        with self.assertRaises(ValueError):
            parse_time_spec("12x")
        with self.assertRaises(ValueError):
            parse_time_spec("")
        with self.assertRaises(ValueError):
            parse_time_spec("25:99")

    def test_format_remaining(self):
        self.assertEqual(format_remaining(0), "00:00")
        self.assertEqual(format_remaining(65), "01:05")
        self.assertEqual(format_remaining(3665), "01:01:05")
        self.assertEqual(format_remaining(-10), "00:00")

    def test_engine_state_and_toggle(self):
        start_t = 1000.0
        engine = CountdownEngine(duration=100, now=start_t)
        self.assertEqual(engine.state, "running")
        self.assertEqual(engine.remaining_seconds, 100)

        # 30 seconds pass
        remaining, ended = engine.tick(now=start_t + 30)
        self.assertEqual(remaining, 70)
        self.assertFalse(ended)
        self.assertEqual(engine.state, "running")

        # Pause
        engine.pause(now=start_t + 30)
        self.assertEqual(engine.state, "paused")

        # Time passes while paused
        remaining, ended = engine.tick(now=start_t + 50)
        self.assertEqual(remaining, 70)
        self.assertFalse(ended)

        # Resume
        engine.resume(now=start_t + 50)
        self.assertEqual(engine.state, "running")

        # Another 60 seconds pass
        remaining, ended = engine.tick(now=start_t + 110)
        self.assertEqual(remaining, 10)
        self.assertFalse(ended)

        # Time expires
        remaining, ended = engine.tick(now=start_t + 130)
        self.assertEqual(remaining, 0)
        self.assertTrue(ended)
        self.assertEqual(engine.state, "ended")

        # Second tick after ended does not re-trigger ended flag
        remaining, ended = engine.tick(now=start_t + 135)
        self.assertEqual(remaining, 0)
        self.assertFalse(ended)
        self.assertEqual(engine.state, "ended")

    def test_engine_serialization(self):
        engine = CountdownEngine(duration=120, label="Focus", now=1000.0)
        data = engine.to_dict()
        self.assertEqual(data["state"], "running")
        self.assertEqual(data["duration_seconds"], 120)
        self.assertEqual(data["remaining_seconds"], 120)
        self.assertEqual(data["time_formatted"], "02:00")
        self.assertEqual(data["label"], "Focus")
        self.assertEqual(data["percent"], 0)

    def test_cli_controller_flow(self):
        import tempfile
        from raccon_countdown.cli import CountdownController

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            controller = CountdownController(state_file=state_file)

            # Initially idle
            status = controller.get_status()
            self.assertEqual(status["state"], "idle")

            # Initialize timer
            controller.start_timer("25m", label="Study", start_supervisor=False)
            status = controller.get_status()
            self.assertEqual(status["state"], "running")
            self.assertEqual(status["duration_seconds"], 1500)
            self.assertEqual(status["label"], "Study")

            # Pause
            controller.pause()
            status = controller.get_status()
            self.assertEqual(status["state"], "paused")

            # Resume
            controller.resume()
            status = controller.get_status()
            self.assertEqual(status["state"], "running")

            # Toggle -> paused
            controller.toggle()
            status = controller.get_status()
            self.assertEqual(status["state"], "paused")

            # Pause again while already paused is idempotent
            controller.pause()
            status = controller.get_status()
            self.assertEqual(status["state"], "paused")

            # Concurrency: starting new timer replaces the old one
            controller.start_timer("10m", label="Quick", start_supervisor=False)
            status = controller.get_status()
            self.assertEqual(status["state"], "running")
            self.assertEqual(status["duration_seconds"], 600)
            self.assertEqual(status["label"], "Quick")

            # Stop
            controller.stop(close_ui=False)
            status = controller.get_status()
            self.assertEqual(status["state"], "idle")




if __name__ == '__main__':
    unittest.main()
