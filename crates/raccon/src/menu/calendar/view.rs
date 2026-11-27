use std::collections::BTreeSet;
use std::path::Path;

use crate::menu::calendar::date::{
    civil_from_days, days_from_civil, format_iso, get_today_iso, parse_iso, read_selected_date,
    today_ymd, weekday_mon0, MONTHS,
};
use crate::menu::calendar::events::{load_events, CalendarEvent, TaskRow};
use crate::util::hash::token;

pub fn calendar_grid(y: i32, m: u32, sel_iso: &str, today_iso: &str, rows: &[CalendarEvent]) -> serde_json::Value {
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

pub fn snapshot(runtime: &Path, task_rows: &[TaskRow], rows_override: Option<&[CalendarEvent]>, error: &str) -> serde_json::Value {
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::menu::calendar::date::{move_month, set_selected_date};
    use std::fs;

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
