use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fs;
use std::io::Read;
use std::path::Path;
use std::process::Command;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use crate::util::atomic::write_atomic;
use crate::util::hash::token;
use crate::util::paths::{home_dir, runtime_dir, share_dir};
use crate::util::watch::{emit_line, DirWatch, FileLock};

const MONTHS: [&str; 12] = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarEvent {
    pub id: String,
    pub date: String,
    pub title: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TaskRow {
    token: String,
    title: String,
    done: bool,
    id: serde_json::Value,
}

pub fn today_ymd() -> (i32, u32, u32) {
    unsafe {
        let mut t: libc::time_t = 0;
        libc::time(&mut t);
        let mut tm: libc::tm = std::mem::zeroed();
        libc::localtime_r(&t, &mut tm);
        (tm.tm_year + 1900, (tm.tm_mon + 1) as u32, tm.tm_mday as u32)
    }
}

pub fn get_today_iso() -> String {
    let (y, m, d) = today_ymd();
    format!("{:04}-{:02}-{:02}", y, m, d)
}

fn is_leap(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

pub fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => if is_leap(year) { 29 } else { 28 },
        _ => 30,
    }
}

pub fn parse_iso(iso: &str) -> Option<(i32, u32, u32)> {
    let parts: Vec<&str> = iso.trim().split('-').collect();
    if parts.len() != 3 || parts[0].len() != 4 || parts[1].len() != 2 || parts[2].len() != 2 {
        return None;
    }
    let y: i32 = parts[0].parse().ok()?;
    let m: u32 = parts[1].parse().ok()?;
    let d: u32 = parts[2].parse().ok()?;
    if !(1..=12).contains(&m) || d == 0 || d > days_in_month(y, m) {
        return None;
    }
    Some((y, m, d))
}

fn format_iso(y: i32, m: u32, d: u32) -> String {
    format!("{:04}-{:02}-{:02}", y, m, d)
}

// Howard Hinnant's civil-from/to-days algorithm (Monday = 0 .. Sunday = 6).
fn days_from_civil(y: i32, m: u32, d: u32) -> i64 {
    let y = y as i64 - if m <= 2 { 1 } else { 0 };
    let era = y.div_euclid(400);
    let yoe = y.rem_euclid(400);
    let m = m as i64;
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d as i64 - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

fn civil_from_days(z: i64) -> (i32, u32, u32) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = y + if m <= 2 { 1 } else { 0 };
    (y as i32, m as u32, d as u32)
}

fn weekday_mon0(y: i32, m: u32, d: u32) -> i64 {
    (days_from_civil(y, m, d) + 3).rem_euclid(7)
}

pub fn read_selected_date(runtime: &Path) -> String {
    let date_file = runtime.join("calendar-date.json");
    if let Ok(content) = fs::read_to_string(&date_file) {
        if let Ok(date_str) = serde_json::from_str::<String>(&content) {
            if parse_iso(&date_str).is_some() {
                return date_str;
            }
        }
    }
    get_today_iso()
}

pub fn set_selected_date(runtime: &Path, iso_date: &str) -> Result<(), String> {
    if parse_iso(iso_date).is_none() {
        return Err("Invalid date format.".into());
    }
    let content = serde_json::to_vec(&iso_date).map_err(|e| e.to_string())?;
    write_atomic(&runtime.join("calendar-date.json"), &content).map_err(|e| e.to_string())
}

pub fn move_month(runtime: &Path, offset: i32) -> Result<(), String> {
    if offset != -1 && offset != 1 {
        return Err("Invalid month change.".into());
    }
    let current = read_selected_date(runtime);
    let (y, m, d) = parse_iso(&current).unwrap_or_else(today_ymd);
    let idx = y * 12 + (m as i32 - 1) + offset;
    let ny = idx.div_euclid(12);
    let nm = (idx.rem_euclid(12) + 1) as u32;
    let nd = d.min(days_in_month(ny, nm));
    set_selected_date(runtime, &format_iso(ny, nm, nd))
}

fn events_path() -> std::path::PathBuf {
    share_dir().join("events.json")
}

fn load_events() -> Result<Vec<CalendarEvent>, String> {
    let path = events_path();
    let content = match fs::read_to_string(&path) {
        Ok(c) => c,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(_) => return Err("Could not read the agenda. Your events file was preserved.".into()),
    };
    let rows: Vec<CalendarEvent> = serde_json::from_str(&content)
        .map_err(|_| "Could not read the agenda. Your events file was preserved.".to_string())?;
    for row in &rows {
        if parse_iso(&row.date).is_none() {
            return Err("An event has an invalid date. Your events file was preserved.".into());
        }
    }
    Ok(rows)
}

fn planner_tasks() -> Result<Vec<TaskRow>, String> {
    let planner = home_dir().join(".config/eww/scripts/planner");
    if !planner.is_file() {
        return Ok(Vec::new());
    }
    let out = Command::new(&planner)
        .args(["--once", "tasks"])
        .output()
        .map_err(|_| "Could not load tasks.".to_string())?;
    if !out.status.success() {
        return Err("Could not load tasks.".into());
    }
    let val: serde_json::Value = serde_json::from_slice(&out.stdout)
        .map_err(|_| "Could not parse tasks.".to_string())?;
    let mut rows = Vec::new();
    if let Some(groups) = val.get("groups").and_then(|g| g.as_array()) {
        for group in groups {
            if let Some(items) = group.get("items").and_then(|i| i.as_array()) {
                for item in items {
                    if let (Some(id), Some(text)) = (item.get("id"), item.get("text").and_then(|v| v.as_str())) {
                        let id_str = match id {
                            serde_json::Value::String(s) => s.clone(),
                            other => other.to_string(),
                        };
                        rows.push(TaskRow {
                            token: token(&id_str),
                            title: text.to_string(),
                            done: item.get("done").and_then(|v| v.as_bool()).unwrap_or(false),
                            id: id.clone(),
                        });
                    }
                }
            }
        }
    }
    Ok(rows)
}

fn calendar_grid(y: i32, m: u32, sel_iso: &str, today_iso: &str, rows: &[CalendarEvent]) -> serde_json::Value {
    let occupied: BTreeSet<&str> = rows.iter().map(|r| r.date.as_str()).collect();
    let first_days = days_from_civil(y, m, 1);
    let offset_start = weekday_mon0(y, m, 1);
    let mut weeks = Vec::with_capacity(6);
    for w in 0..6 {
        let mut week = Vec::with_capacity(7);
        for dow in 0..7 {
            let idx = (w * 7 + dow) as i64 - offset_start;
            let (cy, cm, cd) = civil_from_days(first_days + idx);
            let iso = format_iso(cy, cm, cd);
            let event = occupied.contains(iso.as_str());
            week.push(serde_json::json!({
                "day": cd.to_string(),
                "iso": iso,
                "selected": iso == sel_iso,
                "today": iso == today_iso,
                "other": cm != m,
                "event": event,
            }));
        }
        weeks.push(serde_json::Value::Array(week));
    }
    serde_json::Value::Array(weeks)
}

fn snapshot(runtime: &Path, task_rows: &[TaskRow], rows_override: Option<&[CalendarEvent]>, error: &str) -> serde_json::Value {
    let sel_iso = read_selected_date(runtime);
    let (y, m, d) = parse_iso(&sel_iso).unwrap_or_else(today_ymd);
    let today_iso = get_today_iso();
    let owned_rows;
    let rows = match rows_override {
        Some(r) => r,
        None => {
            owned_rows = load_events().unwrap_or_default();
            &owned_rows
        }
    };
    let present: Vec<serde_json::Value> = rows
        .iter()
        .filter(|r| r.date == sel_iso)
        .map(|r| serde_json::json!({"token": token(&r.id), "title": r.title}))
        .collect();
    let mut upcoming_rows: Vec<&CalendarEvent> = rows.iter().filter(|r| r.date.as_str() > sel_iso.as_str()).collect();
    upcoming_rows.sort_by(|a, b| a.date.cmp(&b.date));
    let upcoming: Vec<serde_json::Value> = upcoming_rows
        .into_iter()
        .take(3)
        .map(|r| serde_json::json!({"title": r.title, "date": r.date}))
        .collect();
    let tasks_json: Vec<&TaskRow> = if sel_iso == today_iso { task_rows.iter().collect() } else { Vec::new() };
    serde_json::json!({
        "day": d,
        "month": m,
        "year": y,
        "date": format!("{:02}/{:02}/{:04}", d, m, y),
        "iso": sel_iso,
        "month_title": format!("{} {}", MONTHS[(m - 1) as usize], y),
        "weekdays": ["M", "T", "W", "T", "F", "S", "S"],
        "weeks": calendar_grid(y, m, &sel_iso, &today_iso, rows),
        "events": present,
        "upcoming": upcoming,
        "tasks": tasks_json,
        "error": error,
    })
}

pub fn watch(runtime: &Path) {
    let ev_path = events_path();
    let tracked = [
        runtime.join("calendar-date.json"),
        runtime.join("calendar-tasks.json"),
        ev_path.clone(),
        runtime.join("page"),
        runtime.join("visible"),
    ];
    let watcher = DirWatch::new(&tracked, &[]);
    let mut previous = String::new();
    let mut task_rows: Vec<TaskRow> = Vec::new();
    let mut task_error = String::new();
    let mut next_refresh = Instant::now();
    loop {
        let page = fs::read_to_string(runtime.join("page")).unwrap_or_default();
        let vis = fs::read_to_string(runtime.join("visible")).unwrap_or_default();
        let active = page.trim() == "7" && vis.trim() == "1";
        if active || previous.is_empty() {
            let now = Instant::now();
            if now >= next_refresh {
                match planner_tasks() {
                    Ok(t) => {
                        task_rows = t;
                        task_error.clear();
                    }
                    Err(_) => {
                        task_rows.clear();
                        task_error = "Could not load tasks. Reopen the calendar to retry.".into();
                    }
                }
                next_refresh = now + std::time::Duration::from_secs(15);
            }
            let frame = match load_events() {
                Ok(ev) => snapshot(runtime, &task_rows, Some(&ev), &task_error),
                Err(err) => snapshot(runtime, &task_rows, Some(&[]), &err),
            };
            let line = frame.to_string();
            if line != previous {
                if !emit_line(&line) { return; }
                previous = line;
            }
        }
        let timeout_ms = if active {
            next_refresh.saturating_duration_since(Instant::now()).as_millis().min(15_000) as i32
        } else {
            -1
        };
        let prev_tasks = fs::metadata(runtime.join("calendar-tasks.json")).and_then(|m| m.modified()).ok();
        let prev_page = fs::metadata(runtime.join("page")).and_then(|m| m.modified()).ok();
        let prev_vis = fs::metadata(runtime.join("visible")).and_then(|m| m.modified()).ok();
        watcher.wait(timeout_ms);
        if fs::metadata(runtime.join("calendar-tasks.json")).and_then(|m| m.modified()).ok() != prev_tasks
            || fs::metadata(runtime.join("page")).and_then(|m| m.modified()).ok() != prev_page
            || fs::metadata(runtime.join("visible")).and_then(|m| m.modified()).ok() != prev_vis
        {
            next_refresh = Instant::now();
        }
    }
}

pub fn execute(runtime: &Path, args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Err("Missing calendar action".into());
    }
    let _ = fs::create_dir_all(runtime);
    match args[0].as_str() {
        "today" => set_selected_date(runtime, &get_today_iso()),
        "select" => {
            if args.len() == 2 {
                set_selected_date(runtime, &args[1])
            } else if args.len() >= 4 {
                let d: u32 = args[1].parse().map_err(|_| "Invalid day")?;
                let m: u32 = args[2].parse().map_err(|_| "Invalid month")?;
                let y: i32 = args[3].parse().map_err(|_| "Invalid year")?;
                set_selected_date(runtime, &format_iso(y, m, d))
            } else {
                Err("Missing date argument".into())
            }
        }
        "move" => {
            let offset: i32 = args.get(1).ok_or("Missing month offset")?.parse().map_err(|_| "Invalid offset")?;
            move_month(runtime, offset)
        }
        "task" => {
            let tok = args.get(1).ok_or("Missing task token")?;
            let planner = home_dir().join(".config/eww/scripts/planner");
            let rows = planner_tasks()?;
            let row = rows.into_iter().find(|r| &r.token == tok).ok_or("Task not found.")?;
            let id_str = match row.id {
                serde_json::Value::String(s) => s,
                other => other.to_string(),
            };
            let status = Command::new(planner).args(["task", &id_str]).status().map_err(|e| e.to_string())?;
            if !status.success() {
                return Err("Could not update task.".into());
            }
            let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos().to_string();
            write_atomic(&runtime.join("calendar-tasks.json"), stamp.as_bytes()).map_err(|e| e.to_string())
        }
        "add" | "remove" => {
            let path = events_path();
            let _lock = FileLock::lock(&path.with_extension("lock"));
            let mut rows = load_events()?;
            if args[0] == "add" {
                let mut buf = Vec::new();
                std::io::stdin().take(501).read_to_end(&mut buf).map_err(|e| e.to_string())?;
                let title = String::from_utf8_lossy(&buf).trim().to_string();
                if title.is_empty() || title.chars().count() > 500 {
                    return Err("Enter an event with up to 500 characters.".into());
                }
                let date = match args.get(1) {
                    Some(d) => {
                        if parse_iso(d).is_none() { return Err("Invalid date.".into()); }
                        d.clone()
                    }
                    None => read_selected_date(runtime),
                };
                let id = format!(
                    "{:x}-{}",
                    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos(),
                    std::process::id()
                );
                rows.push(CalendarEvent { id, date, title });
            } else {
                let tok = args.get(1).ok_or("Missing event token")?;
                rows.retain(|r| &token(&r.id) != tok);
            }
            let json = serde_json::to_vec(&rows).map_err(|e| e.to_string())?;
            write_atomic(&path, &json).map_err(|e| e.to_string())
        }
        "watch" => {
            watch(&runtime_dir());
            Ok(())
        }
        _ => Err(format!("Unknown calendar action: {}", args[0])),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calendar_move_month_and_grid() {
        let temp_dir = std::env::temp_dir().join(format!("raccon_test_cal_{}", std::process::id()));
        let _ = fs::remove_dir_all(&temp_dir);
        fs::create_dir_all(&temp_dir).unwrap();
        set_selected_date(&temp_dir, "2026-01-31").unwrap();
        move_month(&temp_dir, 1).unwrap();
        assert_eq!(read_selected_date(&temp_dir), "2026-02-28");
        let snap = snapshot(&temp_dir, &[], Some(&[]), "");
        assert_eq!(snap["month_title"], "February 2026");
        assert_eq!(snap["weeks"].as_array().unwrap().len(), 6);
        let _ = fs::remove_dir_all(&temp_dir);
    }
}
