"""Command line controller and supervisor for raccon-countdown."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from .engine import CountdownEngine, format_remaining, parse_time_spec


def default_state_file() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "raccon-countdown.json"
    return Path("/tmp") / f"raccon-countdown-{os.getuid()}.json"


def default_eww_config() -> Path:
    return Path.home() / ".config" / "raccon-countdown"


class CountdownController:
    """Controls timer lifecycle, state persistence, and supervisor process."""

    def __init__(self, state_file: Path | None = None, eww_dir: Path | None = None):
        self.state_file = state_file or default_state_file()
        self.eww_dir = eww_dir or default_eww_config()

    def get_status(self) -> dict:
        """Read active status from state file or return idle state."""
        if not self.state_file.exists():
            return {
                "state": "idle",
                "duration_seconds": 0,
                "remaining_seconds": 0,
                "time_formatted": "--:--",
                "percent": 0,
                "label": "",
            }
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "state": "idle",
            "duration_seconds": 0,
            "remaining_seconds": 0,
            "time_formatted": "--:--",
            "percent": 0,
            "label": "",
        }

    def _write_state(self, state_dict: dict) -> None:
        """Write state atomically."""
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state_dict), encoding="utf-8")
        tmp.replace(self.state_file)

    def start_timer(self, spec: str, label: str = "", start_supervisor: bool = True) -> int:
        """Parse time spec, write initial state and optionally launch background supervisor."""
        duration = parse_time_spec(spec)
        self.stop(close_ui=False)

        now = time.time()
        initial_state = {
            "pid": os.getpid(),
            "state": "running",
            "duration_seconds": duration,
            "remaining_seconds": duration,
            "target_timestamp": now + duration,
            "paused_remaining": None,
            "time_formatted": format_remaining(duration),
            "percent": 0,
            "label": label,
        }
        self._write_state(initial_state)

        if start_supervisor:
            script = shutil.which("countdown") or str(Path.home() / ".local/bin/countdown")
            proc = subprocess.Popen(
                [sys.executable, script, "--supervisor"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            initial_state["pid"] = proc.pid
            self._write_state(initial_state)
            self.open_ui()

        return duration

    def pause(self) -> None:
        """Pause running countdown."""
        status = self.get_status()
        if status.get("state") != "running":
            return
        now = time.time()
        target_t = status.get("target_timestamp", now)
        rem = max(0.0, target_t - now)
        status["state"] = "paused"
        status["paused_remaining"] = rem
        status["remaining_seconds"] = int(round(rem))
        status["time_formatted"] = format_remaining(status["remaining_seconds"])
        self._write_state(status)

    def resume(self) -> None:
        """Resume paused countdown."""
        status = self.get_status()
        if status.get("state") != "paused":
            return
        now = time.time()
        rem = status.get("paused_remaining")
        if rem is None:
            rem = float(status.get("remaining_seconds", 0))
        status["state"] = "running"
        status["target_timestamp"] = now + rem
        status["paused_remaining"] = None
        self._write_state(status)

    def toggle(self) -> None:
        """Toggle between running and paused, or dismiss if ended."""
        status = self.get_status()
        curr_state = status.get("state")
        if curr_state == "running":
            self.pause()
        elif curr_state == "paused":
            self.resume()
        elif curr_state == "ended":
            self.stop()

    def stop(self, close_ui: bool = True) -> None:
        """Stop countdown, terminate supervisor process, and close Eww."""
        status = self.get_status()
        pid = status.get("pid")
        if pid and pid != os.getpid():
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        if self.state_file.exists():
            try:
                self.state_file.unlink()
            except OSError:
                pass

        if close_ui:
            self.close_ui()

    def open_ui(self) -> None:
        """Open the raccon-countdown floating pill in Eww."""
        if not shutil.which("eww") or not self.eww_dir.exists():
            return
        subprocess.Popen(
            ["eww", "-c", str(self.eww_dir), "open", "raccon-countdown"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def close_ui(self) -> None:
        """Close the raccon-countdown floating pill in Eww."""
        if not shutil.which("eww") or not self.eww_dir.exists():
            return
        subprocess.Popen(
            ["eww", "-c", str(self.eww_dir), "close", "raccon-countdown"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _play_alert(self, label: str, duration: int) -> None:
        """Send desktop notification and play chime on timer completion."""
        # 1. Desktop Notification
        title = "Countdown Finished!" if not label else f"Countdown: {label}"
        body = f"Time is up! ({format_remaining(duration)})"
        if shutil.which("notify-send"):
            try:
                subprocess.Popen([
                    "notify-send",
                    "-u", "critical",
                    "-a", "Countdown",
                    "-i", "alarm-symbolic",
                    title,
                    body
                ])
            except OSError:
                pass

        # 2. Sound notification
        sound_paths = [
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
            "/usr/share/sounds/freedesktop/stereo/bell.oga",
        ]
        sound_file = next((p for p in sound_paths if Path(p).exists()), None)
        if sound_file and shutil.which("paplay"):
            try:
                subprocess.Popen(["paplay", sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        elif shutil.which("canberra-gtk-play"):
            try:
                subprocess.Popen(["canberra-gtk-play", "-i", "complete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def run_supervisor(self) -> None:
        """Supervisor loop updating timer state each second."""
        status = self.get_status()
        if status.get("state") == "idle":
            return

        status["pid"] = os.getpid()
        self._write_state(status)

        duration = status.get("duration_seconds", 60)
        label = status.get("label", "")
        engine = CountdownEngine(duration=duration, label=label)

        def sig_handler(signum, frame):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, sig_handler)
        signal.signal(signal.SIGINT, sig_handler)

        while True:
            # Re-read status in case paused/resumed externally
            status = self.get_status()
            curr_state = status.get("state")
            if curr_state in ("idle", None):
                break

            now = time.time()
            if curr_state == "paused":
                time.sleep(0.5)
                continue

            target_t = status.get("target_timestamp", now)
            rem = max(0, int(round(target_t - now)))
            status["remaining_seconds"] = rem
            status["time_formatted"] = format_remaining(rem)
            elapsed = duration - rem
            status["percent"] = 100 if duration <= 0 else min(100, max(0, int((elapsed / duration) * 100)))

            if rem <= 0:
                status["state"] = "ended"
                self._write_state(status)
                self._play_alert(label, duration)
                # Keep alive in ended state so UI shows animation until stopped
                break

            self._write_state(status)
            time.sleep(0.5)

        # In ended state, wait up to 10 minutes or until stopped
        for _ in range(600):
            status = self.get_status()
            if status.get("state") != "ended":
                break
            time.sleep(1.0)

        self.stop()

    def stream_listen(self) -> None:
        """Stream JSON state line-by-line for Eww deflisten."""
        prev = None
        while True:
            st = self.get_status()
            line = json.dumps(st)
            if line != prev:
                print(line, flush=True)
                prev = line
            time.sleep(0.25)


def main():
    parser = argparse.ArgumentParser(description="Raccon countdown utility")
    parser.add_argument("time_or_cmd", nargs="?", help="Duration (25m, 1h30m, 45s), target time (18:30, 5pm), or command")
    parser.add_argument("--label", "-l", default="", help="Optional label for the timer")
    parser.add_argument("--supervisor", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--listen", action="store_true", help="Stream state JSON for deflisten")
    args = parser.parse_args()

    controller = CountdownController()

    if args.supervisor:
        controller.run_supervisor()
        return

    if args.listen:
        controller.stream_listen()
        return

    cmd = (args.time_or_cmd or "").strip().lower()

    if not cmd or cmd == "status":
        print(json.dumps(controller.get_status(), indent=2))
        return

    if cmd == "pause":
        controller.pause()
        return

    if cmd == "resume":
        controller.resume()
        return

    if cmd == "toggle":
        controller.toggle()
        return

    if cmd in ("stop", "cancel", "close", "dismiss"):
        controller.stop()
        return

    # Otherwise treated as duration or target time
    try:
        controller.start_timer(cmd, label=args.label)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
