use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use crate::countdown::engine::{CountdownData, CountdownEngine, format_remaining, parse_time_spec};
use crate::menu::runtime;
use crate::util::atomic::write_atomic;
use crate::util::paths;

pub fn state_file() -> PathBuf {
    if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
        PathBuf::from(runtime).join("raccon-countdown.json")
    } else {
        let uid = unsafe { libc::getuid() };
        PathBuf::from(format!("/tmp/raccon-countdown-{}.json", uid))
    }
}

pub fn read_status() -> CountdownData {
    let path = state_file();
    if let Ok(content) = fs::read_to_string(&path) {
        if let Ok(data) = serde_json::from_str::<CountdownData>(&content) {
            return data;
        }
    }
    CountdownData::default()
}

pub fn write_status(data: &CountdownData) -> std::io::Result<()> {
    let path = state_file();
    let content = serde_json::to_vec(data)?;
    write_atomic(&path, &content)
}

pub fn open_ui() -> Result<(), String> {
    runtime::widget("open", "countdown")
}

pub fn dock_ui() -> Result<(), String> {
    let path = paths::state_root().join("raccon-countdown/pos");
    match fs::remove_file(path) {
        Ok(()) => (),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => (),
        Err(err) => return Err(err.to_string()),
    }
    close_ui();
    open_ui()
}

fn close_ui() {
    let _ = runtime::widget("close", "countdown");
}

pub fn stop() -> Result<(), String> {
    let status = read_status();
    if let Some(pid) = status.pid {
        unsafe {
            libc::kill(pid as i32, libc::SIGTERM);
        }
    }

    let idle = CountdownData::default();
    let _ = write_status(&idle);
    close_ui();
    Ok(())
}

pub fn start(spec: &str, label: &str) -> Result<u64, String> {
    let duration = parse_time_spec(spec, None)?;
    let prev = read_status();
    if prev.state != "idle" && !prev.state.is_empty() {
        let _ = stop();
    }

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();

    let initial = CountdownData {
        pid: None,
        state: "running".to_string(),
        duration_seconds: duration,
        remaining_seconds: duration,
        target_timestamp: Some(now + duration as f64),
        paused_remaining: None,
        time_formatted: format_remaining(duration),
        percent: 0,
        label: label.to_string(),
    };

    let exe = std::env::current_exe().map_err(|err| err.to_string())?;
    let mut command = Command::new(&exe);
    if exe
        .file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.starts_with("raccon"))
    {
        command.arg("countdown");
    }
    write_status(&initial).map_err(|e| e.to_string())?;
    let child = command
        .arg("--supervisor")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| {
            let _ = write_status(&CountdownData::default());
            error.to_string()
        })?;
    let mut with_pid = initial;
    with_pid.pid = Some(child.id());
    write_status(&with_pid).map_err(|err| err.to_string())?;

    if let Err(error) = open_ui() {
        eprintln!("countdown: timer started, but the widget could not open: {error}");
    }
    Ok(duration)
}

pub fn pause() -> Result<(), String> {
    let mut status = read_status();
    if status.state != "running" {
        return Ok(());
    }

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();

    let target = status.target_timestamp.unwrap_or(now);
    let rem = (target - now).max(0.0);
    status.remaining_seconds = rem.round() as u64;
    status.paused_remaining = Some(rem);
    status.time_formatted = format_remaining(status.remaining_seconds);
    status.state = "paused".to_string();

    write_status(&status).map_err(|e| e.to_string())
}

pub fn resume() -> Result<(), String> {
    let mut status = read_status();
    if status.state != "paused" {
        return Ok(());
    }

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();

    let rem = status
        .paused_remaining
        .unwrap_or(status.remaining_seconds as f64);
    status.target_timestamp = Some(now + rem);
    status.paused_remaining = None;
    status.state = "running".to_string();

    write_status(&status).map_err(|e| e.to_string())
}

pub fn toggle() -> Result<(), String> {
    let status = read_status();
    if status.state == "running" {
        pause()
    } else if status.state == "paused" {
        resume()
    } else if status.state == "ended" {
        stop()
    } else {
        Ok(())
    }
}

pub fn run_supervisor() {
    let pid = std::process::id();
    let status = read_status();
    if status.state != "running" {
        return;
    }

    let mut engine = CountdownEngine::new(
        status.duration_seconds,
        status.label.clone(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64(),
    );

    loop {
        thread::sleep(Duration::from_millis(250));

        // Read state in case pause/resume happened externally
        let current_state = read_status();
        if current_state.state == "idle" || current_state.state.is_empty() {
            break;
        }

        if current_state.state == "paused" {
            if engine.state == "running" {
                engine.pause(
                    SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs_f64(),
                );
            }
            continue;
        } else if current_state.state == "running" && engine.state == "paused" {
            engine.resume(
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs_f64(),
            );
        }

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let (remaining, ended) = engine.tick(now);
        let updated = engine.to_data(Some(pid));
        let _ = write_status(&updated);

        if ended {
            // Trigger visual alert / system notification
            let title = if updated.label.is_empty() {
                "Countdown Finished".to_string()
            } else {
                format!("Countdown: {}", updated.label)
            };
            let _ = Command::new("notify-send")
                .args([
                    "-u",
                    "critical",
                    "-a",
                    "Countdown",
                    "-i",
                    "alarm-symbolic",
                    &title,
                    "Time has expired!",
                ])
                .spawn();

            // Keep attention animation for 10 seconds before auto-closing
            thread::sleep(Duration::from_secs(10));
            close_ui();
            let _ = write_status(&CountdownData::default());
            break;
        }

        if remaining == 0 {
            break;
        }
    }
}

pub fn run_listen() {
    let mut last_output = String::new();
    loop {
        let status = read_status();
        let json_line = serde_json::to_string(&status).unwrap_or_default();
        if json_line != last_output {
            println!("{}", json_line);
            last_output = json_line;
        }
        thread::sleep(Duration::from_millis(200));
    }
}
