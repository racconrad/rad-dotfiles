use std::fs;
use std::path::Path;
use std::time::Instant;

use crate::menu::calendar::events::{events_path, load_events, planner_tasks, TaskRow};
use crate::menu::calendar::view::snapshot;
use crate::util::watch::{emit_line, DirWatch};

pub fn watch(runtime: &Path) {
    let ev_path = events_path();
    let task_changes = runtime.join("calendar-tasks.json");
    let tracked = [runtime.join("calendar-date.json"), task_changes.clone(), ev_path];
    let watcher = DirWatch::new(&tracked, &[]);
    let mut previous = String::new();
    let mut task_rows: Vec<TaskRow> = Vec::new();
    let mut task_error = String::new();
    let mut next_refresh = Instant::now();
    loop {
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
        let timeout_ms = next_refresh.saturating_duration_since(Instant::now()).as_millis() as i32;
        let prev_tasks = fs::metadata(&task_changes).and_then(|m| m.modified()).ok();
        watcher.wait(timeout_ms);
        if fs::metadata(&task_changes).and_then(|m| m.modified()).ok() != prev_tasks {
            next_refresh = Instant::now();
        }
    }
}
