"""Core time parsing and state machine for raccon-countdown."""
from datetime import datetime, timedelta
import json
import re
import time


def parse_time_spec(spec: str, now: datetime | None = None) -> int:
    """Parse a time string as relative duration or target hour of day into seconds."""
    s = spec.strip().lower()
    if not s:
        raise ValueError("Empty time specification")

    # Plain seconds: e.g. "90"
    if s.isdigit():
        sec = int(s)
        if sec <= 0:
            raise ValueError("Duration must be greater than zero")
        return sec

    # Compound duration: e.g. "1h30m", "25m", "45s", "1h30m10s"
    duration_match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", s)
    if duration_match and any(duration_match.groups()):
        h = int(duration_match.group(1) or 0)
        m = int(duration_match.group(2) or 0)
        sec = int(duration_match.group(3) or 0)
        total = h * 3600 + m * 60 + sec
        if total <= 0:
            raise ValueError("Duration must be greater than zero")
        return total

    # 12-hour or 24-hour target hour format
    # e.g. "18:30", "18:30:15", "7pm", "7:30pm", "6am"
    ref_now = now or datetime.now()

    # 12-hour: (\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?(am|pm)
    m12 = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?\s*(am|pm)", s)
    if m12:
        hour = int(m12.group(1))
        minute = int(m12.group(2) or 0)
        second = int(m12.group(3) or 0)
        meridiem = m12.group(4)
        if not (1 <= hour <= 12 and 0 <= minute <= 59 and 0 <= second <= 59):
            raise ValueError(f"Invalid 12-hour time: {spec}")
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        target = ref_now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if target <= ref_now:
            target += timedelta(days=1)
        return int((target - ref_now).total_seconds())

    # 24-hour: (\d{1,2}):(\d{1,2})(?::(\d{1,2}))?
    m24 = re.fullmatch(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", s)
    if m24:
        hour = int(m24.group(1))
        minute = int(m24.group(2))
        second = int(m24.group(3) or 0)
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            raise ValueError(f"Invalid 24-hour time: {spec}")
        target = ref_now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if target <= ref_now:
            target += timedelta(days=1)
        return int((target - ref_now).total_seconds())

    raise ValueError(f"Unrecognized time format: '{spec}'. Use '25m', '1h30m', '45s', '18:30' or '5pm'.")


def format_remaining(seconds: int) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds <= 0:
        return "00:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class CountdownEngine:
    """State machine managing a single countdown timer."""

    def __init__(self, duration: int, label: str = "", now: float | None = None):
        current_t = time.time() if now is None else now
        self.duration_seconds = max(1, duration)
        self.remaining_seconds = self.duration_seconds
        self.target_timestamp = current_t + self.duration_seconds
        self.paused_remaining: float | None = None
        self.state = "running"  # "running", "paused", "ended", "idle"
        self.label = label
        self._notified_ended = False

    def pause(self, now: float | None = None) -> None:
        """Pause running countdown."""
        if self.state != "running":
            return
        current_t = time.time() if now is None else now
        self.remaining_seconds = max(0, int(round(self.target_timestamp - current_t)))
        self.paused_remaining = max(0.0, self.target_timestamp - current_t)
        self.state = "paused"

    def resume(self, now: float | None = None) -> None:
        """Resume paused countdown."""
        if self.state != "paused":
            return
        current_t = time.time() if now is None else now
        rem = self.paused_remaining if self.paused_remaining is not None else float(self.remaining_seconds)
        self.target_timestamp = current_t + rem
        self.paused_remaining = None
        self.state = "running"

    def toggle(self, now: float | None = None) -> None:
        """Toggle between running and paused."""
        if self.state == "running":
            self.pause(now)
        elif self.state == "paused":
            self.resume(now)

    def tick(self, now: float | None = None) -> tuple[int, bool]:
        """Advance time and return (remaining_seconds, just_ended)."""
        current_t = time.time() if now is None else now

        if self.state == "paused":
            return self.remaining_seconds, False

        if self.state == "ended":
            return 0, False

        rem = max(0, int(round(self.target_timestamp - current_t)))
        self.remaining_seconds = rem

        if rem <= 0:
            self.state = "ended"
            if not self._notified_ended:
                self._notified_ended = True
                return 0, True
            return 0, False

        return rem, False

    def to_dict(self) -> dict:
        """Produce dictionary suitable for JSON serialization."""
        elapsed = self.duration_seconds - self.remaining_seconds
        pct = 100 if self.duration_seconds <= 0 else min(100, max(0, int((elapsed / self.duration_seconds) * 100)))
        return {
            "state": self.state,
            "duration_seconds": self.duration_seconds,
            "remaining_seconds": self.remaining_seconds,
            "time_formatted": format_remaining(self.remaining_seconds),
            "percent": pct,
            "label": self.label,
        }

    def to_json(self) -> str:
        """Serialize state to JSON string."""
        return json.dumps(self.to_dict())
