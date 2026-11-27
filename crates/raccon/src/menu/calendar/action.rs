use std::fs;
use std::io::Read;
use std::path::Path;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::menu::calendar::date::{format_iso, get_today_iso, move_month, parse_iso, read_selected_date, set_selected_date};
use crate::menu::calendar::events::{events_path, load_events, planner_tasks, CalendarEvent};
use crate::menu::calendar::watch::watch;
use crate::util::atomic::write_atomic;
use crate::util::hash::token;
use crate::util::paths::{home_dir, runtime_dir};
use crate::util::watch::FileLock;

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
