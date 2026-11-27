use std::fs;
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::menu::panels::{audio, bluetooth, present, wifi};
use crate::util::atomic::write_atomic;
use crate::util::paths::runtime_dir;
use crate::util::watch::{emit_line, DirWatch};

pub fn run_cmd(argv: &[&str], stdin_data: Option<&str>) -> Result<String, String> {
    let mut cmd = Command::new(argv[0]);
    cmd.args(&argv[1..]).env("LC_ALL", "C");
    if stdin_data.is_some() {
        cmd.stdin(Stdio::piped());
    } else {
        cmd.stdin(Stdio::null());
    }
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = cmd.spawn().map_err(|e| e.to_string())?;
    if let Some(data) = stdin_data {
        if let Some(mut sin) = child.stdin.take() {
            let _ = sin.write_all(data.as_bytes());
        }
    }
    let out = child.wait_with_output().map_err(|e| e.to_string())?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr).trim().to_string();
        return Err(if err.is_empty() {
            "Could not complete the operation.".into()
        } else {
            err
        });
    }
    Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
}

pub fn wake(runtime: &Path, kind: &str) {
    let ns = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos().to_string();
    let _ = write_atomic(&runtime.join(format!("refresh-{kind}")), ns.as_bytes());
}

pub fn read_cached_kind(kind: &str) -> serde_json::Value {
    let mut base = present::defaults(kind);
    if let Ok(text) = fs::read_to_string(present::panel_state_dir().join(format!("{kind}.json"))) {
        if let Ok(serde_json::Value::Object(extra)) = serde_json::from_str::<serde_json::Value>(&text) {
            if let Some(map) = base.as_object_mut() {
                for (k, v) in extra {
                    map.insert(k, v);
                }
            }
        }
    }
    base
}

pub fn selected_row(kind: &str, tok: &str, group: &str) -> Result<serde_json::Value, String> {
    if tok.len() != 24 || !tok.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("Invalid selection.".into());
    }
    let data = read_cached_kind(kind);
    data.get(group)
        .and_then(|v| v.as_array())
        .and_then(|arr| arr.iter().find(|r| r.get("token").and_then(|t| t.as_str()) == Some(tok)))
        .cloned()
        .ok_or_else(|| "Device changed. Refresh the list.".to_string())
}

pub fn refresh_kind(kind: &str) -> serde_json::Value {
    let res = match kind {
        "audio" => audio::audio_snapshot(),
        "connections" => wifi::wifi_snapshot(),
        _ => bluetooth::bluetooth_snapshot(),
    };
    let data = match res {
        Ok(val) => val,
        Err(_) => {
            let mut d = present::defaults(kind);
            if let Some(obj) = d.as_object_mut() {
                obj.insert("ready".into(), serde_json::json!(true));
                obj.insert("title".into(), serde_json::json!("Unavailable"));
                let msg = match kind {
                    "audio" => "Audio service is not responding.",
                    "connections" => "Could not query NetworkManager.",
                    _ => "Bluetooth is unavailable.",
                };
                obj.insert("error".into(), serde_json::json!(msg));
            }
            d
        }
    };
    let _ = write_atomic(&present::panel_state_dir().join(format!("{kind}.json")), data.to_string().as_bytes());
    data
}

pub fn listen(kind: &str) -> Result<(), String> {
    if present::service_page(kind).is_none() {
        return Err("Unknown panel kind".into());
    }
    let runtime = runtime_dir();
    let _ = fs::create_dir_all(&runtime);
    let watcher = DirWatch::new(&[], &[runtime.clone()]);
    let mut data = read_cached_kind(kind);
    let mut shown = present::presentation(kind, &data, &runtime).to_string();
    if !emit_line(&shown) { return Ok(()); }

    let mut deadline = Instant::now();
    let mut previous_marker = String::new();
    let mut discovery: Option<std::process::Child> = None;

    loop {
        let marker = fs::read_to_string(runtime.join(format!("refresh-{kind}"))).unwrap_or_default();
        let now = Instant::now();
        if now >= deadline || marker != previous_marker {
            if kind == "bluetooth" {
                let now_secs = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64();
                let scanning = fs::read_to_string(runtime.join("scan-until"))
                    .ok()
                    .and_then(|s| s.trim().parse::<f64>().ok())
                    .map(|t| t > now_secs)
                    .unwrap_or(false);
                if !scanning {
                    if let Some(mut child) = discovery.take() {
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                } else if discovery.as_mut().map_or(true, |c| c.try_wait().map_or(true, |s| s.is_some())) {
                    discovery = Command::new("bluetoothctl")
                        .args(["--timeout", "20", "scan", "on"])
                        .stdin(Stdio::null())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn()
                        .ok();
                }
            }
            data = refresh_kind(kind);
            previous_marker = marker;
            deadline = now + Duration::from_secs(if kind == "audio" { 1 } else { 2 });
        }
        let frame = present::presentation(kind, &data, &runtime).to_string();
        if frame != shown {
            if !emit_line(&frame) { return Ok(()); }
            shown = frame;
        }
        watcher.wait(deadline.saturating_duration_since(Instant::now()).as_millis().clamp(1, 2000) as i32);
    }
}

pub fn preload() {
    std::thread::scope(|s| {
        s.spawn(|| { refresh_kind("audio"); });
        s.spawn(|| { refresh_kind("connections"); });
        s.spawn(|| { refresh_kind("bluetooth"); });
    });
}
