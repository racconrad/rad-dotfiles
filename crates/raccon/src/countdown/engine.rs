use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CountdownData {
    #[serde(default)]
    pub pid: Option<u32>,
    pub state: String, // "running", "paused", "ended", "idle"
    pub duration_seconds: u64,
    pub remaining_seconds: u64,
    #[serde(default)]
    pub target_timestamp: Option<f64>,
    #[serde(default)]
    pub paused_remaining: Option<f64>,
    pub time_formatted: String,
    pub percent: u32,
    pub label: String,
}

impl Default for CountdownData {
    fn default() -> Self {
        Self {
            pid: None,
            state: "idle".to_string(),
            duration_seconds: 0,
            remaining_seconds: 0,
            target_timestamp: None,
            paused_remaining: None,
            time_formatted: "--:--".to_string(),
            percent: 0,
            label: String::new(),
        }
    }
}

pub fn format_remaining(seconds: u64) -> String {
    if seconds == 0 {
        return "00:00".to_string();
    }
    let h = seconds / 3600;
    let m = (seconds % 3600) / 60;
    let s = seconds % 60;
    if h > 0 {
        format!("{:02}:{:02}:{:02}", h, m, s)
    } else {
        format!("{:02}:{:02}", m, s)
    }
}

pub fn parse_time_spec(spec: &str, now_unix: Option<f64>) -> Result<u64, String> {
    let s = spec.trim().to_lowercase();
    if s.is_empty() {
        return Err("Empty time specification".into());
    }

    // Plain seconds: "90"
    if let Ok(sec) = s.parse::<u64>() {
        if sec == 0 {
            return Err("Duration must be greater than zero".into());
        }
        return Ok(sec);
    }

    // Compound duration: e.g. "1h30m", "25m", "45s", "1h30m10s"
    if s.chars().all(|c| c.is_ascii_digit() || c == 'h' || c == 'm' || c == 's') {
        let mut total = 0u64;
        let mut cur_num = String::new();
        let mut matched_any = false;

        for c in s.chars() {
            if c.is_ascii_digit() {
                cur_num.push(c);
            } else if c == 'h' {
                let n: u64 = cur_num.parse().unwrap_or(0);
                total += n * 3600;
                cur_num.clear();
                matched_any = true;
            } else if c == 'm' {
                let n: u64 = cur_num.parse().unwrap_or(0);
                total += n * 60;
                cur_num.clear();
                matched_any = true;
            } else if c == 's' {
                let n: u64 = cur_num.parse().unwrap_or(0);
                total += n;
                cur_num.clear();
                matched_any = true;
            }
        }

        if matched_any && cur_num.is_empty() && total > 0 {
            return Ok(total);
        }
    }

    // 12-hour (e.g. "7pm", "7:30pm", "6am") or 24-hour (e.g. "18:30", "18:30:15")
    let is_pm = s.ends_with("pm");
    let is_am = s.ends_with("am");
    let clean = s.trim_end_matches("pm").trim_end_matches("am").trim();

    let parts: Vec<&str> = clean.split(':').collect();
    if (1..=3).contains(&parts.len()) {
        if let Ok(mut hour) = parts[0].parse::<u32>() {
            let minute = if parts.len() > 1 {
                parts[1].parse::<u32>().map_err(|_| "Invalid minute")?
            } else {
                0
            };
            let second = if parts.len() > 2 {
                parts[2].parse::<u32>().map_err(|_| "Invalid second")?
            } else {
                0
            };

            if is_pm || is_am {
                if hour < 1 || hour > 12 || minute > 59 || second > 59 {
                    return Err(format!("Invalid 12-hour time: {}", spec));
                }
                if is_pm && hour != 12 {
                    hour += 12;
                } else if is_am && hour == 12 {
                    hour = 0;
                }
            } else {
                if hour > 23 || minute > 59 || second > 59 {
                    return Err(format!("Invalid 24-hour time: {}", spec));
                }
            }

            // Calculate duration until that time of day
            let now_t = now_unix.unwrap_or_else(|| {
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs_f64()
            });

            // Seconds since midnight in local time
            let sec_today = (now_t as u64) % 86400; // rough UTC or use system time
            // To get accurate local time, calculate target seconds
            let target_sec_of_day = (hour * 3600 + minute * 60 + second) as u64;

            // System local second of day
            let local_sec_of_day = {
                let out = std::process::Command::new("date")
                    .arg("+%H %M %S")
                    .output();
                if let Ok(o) = out {
                    let parts: Vec<u64> = String::from_utf8_lossy(&o.stdout)
                        .split_whitespace()
                        .filter_map(|s| s.parse().ok())
                        .collect();
                    if parts.len() == 3 {
                        parts[0] * 3600 + parts[1] * 60 + parts[2]
                    } else {
                        sec_today
                    }
                } else {
                    sec_today
                }
            };

            let diff = if target_sec_of_day > local_sec_of_day {
                target_sec_of_day - local_sec_of_day
            } else {
                86400 + target_sec_of_day - local_sec_of_day
            };

            return Ok(diff);
        }
    }

    Err(format!(
        "Unrecognized time format: '{}'. Use '25m', '1h30m', '45s', '18:30' or '5pm'.",
        spec
    ))
}

pub struct CountdownEngine {
    pub duration_seconds: u64,
    pub remaining_seconds: u64,
    pub target_timestamp: f64,
    pub paused_remaining: Option<f64>,
    pub state: String,
    pub label: String,
    pub notified_ended: bool,
}

impl CountdownEngine {
    pub fn new(duration: u64, label: String, now: f64) -> Self {
        let dur = duration.max(1);
        Self {
            duration_seconds: dur,
            remaining_seconds: dur,
            target_timestamp: now + dur as f64,
            paused_remaining: None,
            state: "running".to_string(),
            label,
            notified_ended: false,
        }
    }

    pub fn pause(&mut self, now: f64) {
        if self.state != "running" {
            return;
        }
        let rem = (self.target_timestamp - now).max(0.0);
        self.remaining_seconds = rem.round() as u64;
        self.paused_remaining = Some(rem);
        self.state = "paused".to_string();
    }

    pub fn resume(&mut self, now: f64) {
        if self.state != "paused" {
            return;
        }
        let rem = self.paused_remaining.unwrap_or(self.remaining_seconds as f64);
        self.target_timestamp = now + rem;
        self.paused_remaining = None;
        self.state = "running".to_string();
    }

    pub fn tick(&mut self, now: f64) -> (u64, bool) {
        if self.state != "running" {
            return (self.remaining_seconds, false);
        }

        let diff = self.target_timestamp - now;
        if diff <= 0.0 {
            self.remaining_seconds = 0;
            self.state = "ended".to_string();
            let just_ended = !self.notified_ended;
            self.notified_ended = true;
            return (0, just_ended);
        }

        self.remaining_seconds = diff.ceil() as u64;
        (self.remaining_seconds, false)
    }

    pub fn to_data(&self, pid: Option<u32>) -> CountdownData {
        let pct = if self.duration_seconds > 0 {
            let elapsed = self.duration_seconds.saturating_sub(self.remaining_seconds);
            ((elapsed as f64 / self.duration_seconds as f64) * 100.0).round() as u32
        } else {
            0
        };

        CountdownData {
            pid,
            state: self.state.clone(),
            duration_seconds: self.duration_seconds,
            remaining_seconds: self.remaining_seconds,
            target_timestamp: Some(self.target_timestamp),
            paused_remaining: self.paused_remaining,
            time_formatted: format_remaining(self.remaining_seconds),
            percent: pct,
            label: self.label.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_duration() {
        assert_eq!(parse_time_spec("45s", None).unwrap(), 45);
        assert_eq!(parse_time_spec("25m", None).unwrap(), 1500);
        assert_eq!(parse_time_spec("1h", None).unwrap(), 3600);
        assert_eq!(parse_time_spec("1h30m", None).unwrap(), 5400);
        assert_eq!(parse_time_spec("1h30m10s", None).unwrap(), 5410);
        assert_eq!(parse_time_spec("90", None).unwrap(), 90);
    }

    #[test]
    fn test_format_remaining() {
        assert_eq!(format_remaining(0), "00:00");
        assert_eq!(format_remaining(65), "01:05");
        assert_eq!(format_remaining(3665), "01:01:05");
    }

    #[test]
    fn test_engine_state_and_toggle() {
        let start = 1000.0;
        let mut engine = CountdownEngine::new(100, "Test".into(), start);
        assert_eq!(engine.state, "running");
        assert_eq!(engine.remaining_seconds, 100);

        let (rem, ended) = engine.tick(start + 30.0);
        assert_eq!(rem, 70);
        assert!(!ended);

        engine.pause(start + 30.0);
        assert_eq!(engine.state, "paused");

        let (rem2, _) = engine.tick(start + 50.0);
        assert_eq!(rem2, 70);

        engine.resume(start + 50.0);
        assert_eq!(engine.state, "running");

        let (rem3, ended3) = engine.tick(start + 125.0);
        assert_eq!(rem3, 0);
        assert!(ended3);
        assert_eq!(engine.state, "ended");
    }
}
