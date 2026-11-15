use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

use crate::util::atomic::write_atomic;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarEvent {
    pub id: String,
    pub date: String,
    pub title: String,
}

pub fn get_today_iso() -> String {
    // Read from system time
    let output = std::process::Command::new("date")
        .arg("+%Y-%m-%d")
        .output();
    if let Ok(out) = output {
        let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if !s.is_empty() {
            return s;
        }
    }
    "2026-11-14".to_string()
}

pub fn read_selected_date(runtime_dir: &Path) -> String {
    let date_file = runtime_dir.join("calendar-date.json");
    if let Ok(content) = fs::read_to_string(&date_file) {
        if let Ok(date_str) = serde_json::from_str::<String>(&content) {
            return date_str;
        }
    }
    get_today_iso()
}

pub fn set_selected_date(runtime_dir: &Path, iso_date: &str) -> std::io::Result<()> {
    let date_file = runtime_dir.join("calendar-date.json");
    let content = serde_json::to_vec(&iso_date)?;
    write_atomic(&date_file, &content)
}

pub fn move_month(runtime_dir: &Path, offset: i32) -> std::io::Result<()> {
    let current = read_selected_date(runtime_dir);
    let parts: Vec<&str> = current.split('-').collect();
    if parts.len() != 3 {
        return set_selected_date(runtime_dir, &get_today_iso());
    }

    let mut year: i32 = parts[0].parse().unwrap_or(2026);
    let mut month: i32 = parts[1].parse().unwrap_or(11);
    let day: u32 = parts[2].parse().unwrap_or(1);

    month += offset;
    if month < 1 {
        month += 12;
        year -= 1;
    } else if month > 12 {
        month -= 12;
        year += 1;
    }

    let target_day = day.min(28); // Safe clamp
    let new_date = format!("{:04}-{:02}-{:02}", year, month, target_day);
    set_selected_date(runtime_dir, &new_date)
}

pub fn execute(runtime_dir: &Path, args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Err("Missing calendar action".into());
    }

    match args[0].as_str() {
        "today" => {
            set_selected_date(runtime_dir, &get_today_iso()).map_err(|e| e.to_string())
        }
        "select" => {
            let date = args.get(1).ok_or("Missing date argument")?;
            set_selected_date(runtime_dir, date).map_err(|e| e.to_string())
        }
        "move" => {
            let offset_str = args.get(1).ok_or("Missing month offset")?;
            let offset: i32 = offset_str.parse().map_err(|_| "Invalid offset")?;
            move_month(runtime_dir, offset).map_err(|e| e.to_string())
        }
        _ => Err(format!("Unknown calendar action: {}", args[0])),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calendar_move_month() {
        let temp_dir = std::env::temp_dir().join("raccon_test_calendar");
        let _ = fs::remove_dir_all(&temp_dir);
        fs::create_dir_all(&temp_dir).unwrap();

        set_selected_date(&temp_dir, "2026-11-14").unwrap();
        assert_eq!(read_selected_date(&temp_dir), "2026-11-14");

        // Move +1 month -> December
        move_month(&temp_dir, 1).unwrap();
        assert_eq!(read_selected_date(&temp_dir), "2026-12-14");

        // Move -1 month -> November
        move_month(&temp_dir, -1).unwrap();
        assert_eq!(read_selected_date(&temp_dir), "2026-11-14");

        let _ = fs::remove_dir_all(&temp_dir);
    }
}

