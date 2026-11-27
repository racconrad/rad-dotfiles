use std::fs;
use std::path::Path;

use crate::util::atomic::write_atomic;

pub const MONTHS: [&str; 12] = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
];

pub fn today_ymd() -> (i32, u32, u32) {
    unsafe {
        let mut t: libc::time_t = 0;
        libc::time(&mut t);
        let mut tm: libc::tm = std::mem::zeroed();
        libc::localtime_r(&mut t, &mut tm);
        (tm.tm_year + 1900, (tm.tm_mon + 1) as u32, tm.tm_mday as u32)
    }
}

pub fn get_today_iso() -> String {
    let (y, m, d) = today_ymd();
    format!("{:04}-{:02}-{:02}", y, m, d)
}

pub fn is_leap(year: i32) -> bool {
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

pub fn format_iso(y: i32, m: u32, d: u32) -> String {
    format!("{:04}-{:02}-{:02}", y, m, d)
}

pub fn days_from_civil(y: i32, m: u32, d: u32) -> i64 {
    let y = y as i64 - if m <= 2 { 1 } else { 0 };
    let era = y.div_euclid(400);
    let yoe = y.rem_euclid(400);
    let m = m as i64;
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d as i64 - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

pub fn civil_from_days(z: i64) -> (i32, u32, u32) {
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

pub fn weekday_mon0(y: i32, m: u32, d: u32) -> i64 {
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
