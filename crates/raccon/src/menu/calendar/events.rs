use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::process::Command;

use crate::menu::calendar::date::parse_iso;
use crate::util::hash::token;
use crate::util::paths::{home_dir, share_dir};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarEvent {
    pub id: String,
    pub date: String,
    pub title: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskRow {
    pub token: String,
    pub title: String,
    pub done: bool,
    pub id: serde_json::Value,
}

pub fn events_path() -> PathBuf {
    share_dir().join("events.json")
}

pub fn load_events() -> Result<Vec<CalendarEvent>, String> {
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

pub fn planner_tasks() -> Result<Vec<TaskRow>, String> {
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
