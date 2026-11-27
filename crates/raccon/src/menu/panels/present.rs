use std::fs;
use std::path::{Path, PathBuf};

use crate::util::paths::state_root;

pub const PAGE_SIZE: usize = 4;

pub fn panel_state_dir() -> PathBuf {
    state_root().join("desktop-panel")
}

pub fn service_page(kind: &str) -> Option<&'static str> {
    match kind {
        "audio" => Some("4"),
        "connections" => Some("5"),
        "bluetooth" => Some("6"),
        "calendar" => Some("7"),
        _ => None,
    }
}

pub fn defaults(kind: &str) -> serde_json::Value {
    match kind {
        "audio" => {
            let dev = serde_json::json!({"name": "", "title": "No device", "token": "", "volume": 0, "mute": false});
            serde_json::json!({
                "available": false, "ready": false, "error": "", "title": "Loading…",
                "outputs": [], "inputs": [], "output": dev, "input": dev
            })
        }
        "connections" => serde_json::json!({
            "available": false, "ready": false, "error": "", "title": "Loading…",
            "enabled": false, "networks": [], "empty": true
        }),
        _ => serde_json::json!({
            "available": false, "ready": false, "error": "", "title": "Loading…",
            "enabled": false, "scanning": false, "adapters": [], "devices": [], "empty": true
        }),
    }
}

pub fn default_device_info() -> serde_json::Value {
    serde_json::json!({
        "token": "", "title": "", "icon": "bluetooth-symbolic", "connected": false,
        "paired": false, "battery": "", "address": "", "trusted": false, "kind": "Device", "signal": "No data"
    })
}

pub fn presentation(kind: &str, data: &serde_json::Value, runtime: &Path) -> serde_json::Value {
    let mut out = data.clone();
    let ready = data.get("ready").and_then(|v| v.as_bool()).unwrap_or(false);
    let err = data.get("error").and_then(|v| v.as_str()).unwrap_or("");
    let available = data.get("available").and_then(|v| v.as_bool()).unwrap_or(false);
    let enabled = data.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
    let scanning = data.get("scanning").and_then(|v| v.as_bool()).unwrap_or(false);

    let (status, message): (&str, String) = if !ready {
        ("loading", match kind {
            "audio" => "Loading audio devices…",
            "connections" => "Loading networks…",
            _ => "Loading Bluetooth devices…",
        }.to_string())
    } else if !err.is_empty() || !available {
        ("error", if err.is_empty() { "Service unavailable. Retry to check again.".into() } else { err.to_string() })
    } else if kind == "audio" {
        let has_out = data.get("outputs").and_then(|v| v.as_array()).map(|a| !a.is_empty()).unwrap_or(false);
        let has_in = data.get("inputs").and_then(|v| v.as_array()).map(|a| !a.is_empty()).unwrap_or(false);
        if has_out || has_in { ("ready", String::new()) } else { ("empty", "No audio devices found.".into()) }
    } else if !enabled {
        ("off", if kind == "connections" { "Turn on Wi-Fi to see networks." } else { "Turn on Bluetooth to connect." }.into())
    } else if kind == "bluetooth" && scanning {
        let found = data.get("devices").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
        ("loading", if found > 0 { format!("Scanning for Bluetooth devices… ({found} found)") } else { "Scanning nearby Bluetooth devices (20s)…".into() })
    } else {
        let group = if kind == "connections" { "networks" } else { "devices" };
        let rows = data.get(group).and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]);
        if rows.is_empty() {
            ("empty", if kind == "connections" { "No networks found. Scan again." } else { "No devices found. Scan to discover." }.into())
        } else {
            let active_key = if kind == "connections" { "active" } else { "connected" };
            if let Some(active_row) = rows.iter().find(|r| r.get(active_key).and_then(|v| v.as_bool()) == Some(true)) {
                let t = active_row.get("title").and_then(|v| v.as_str()).unwrap_or("");
                let msg = if kind == "connections" {
                    let sig = active_row.get("signal").and_then(|v| v.as_i64()).unwrap_or(0);
                    if t.is_empty() { "Connected".into() } else { format!("Connected · {t} ({sig}%)") }
                } else {
                    let bat = active_row.get("battery").and_then(|v| v.as_str()).unwrap_or("");
                    if t.is_empty() {
                        "Connected".into()
                    } else if bat.is_empty() {
                        format!("Connected · {t}")
                    } else {
                        format!("Connected · {t} ({bat})")
                    }
                };
                ("ready", msg)
            } else {
                let msg = if kind == "connections" {
                    format!("Disconnected · {} networks nearby", rows.len())
                } else {
                    format!("Disconnected · {} devices known", rows.len())
                };
                ("disconnected", msg)
            }
        }
    };

    if let Some(obj) = out.as_object_mut() {
        obj.insert("status".into(), serde_json::json!(status));
        obj.insert("message".into(), serde_json::json!(message));
        if kind != "audio" {
            let group = if kind == "connections" { "networks" } else { "devices" };
            let rows = data.get(group).and_then(|v| v.as_array()).cloned().unwrap_or_default();
            let count = ((rows.len() + PAGE_SIZE - 1) / PAGE_SIZE).max(1);
            let page = fs::read_to_string(runtime.join(format!("list-page-{kind}")))
                .ok()
                .and_then(|s| s.trim().parse::<usize>().ok())
                .unwrap_or(0)
                .min(count - 1);
            let start = page * PAGE_SIZE;
            let end = (start + PAGE_SIZE).min(rows.len());
            let page_rows = rows[start..end].to_vec();
            let chosen = fs::read_to_string(runtime.join("bt-selected")).unwrap_or_default().trim().to_string();
            let detail = if kind == "bluetooth" {
                rows.iter()
                    .find(|r| r.get("token").and_then(|v| v.as_str()) == Some(chosen.as_str()))
                    .cloned()
                    .unwrap_or_else(default_device_info)
            } else {
                default_device_info()
            };
            obj.insert("rows".into(), serde_json::json!(page_rows));
            obj.insert("list_page".into(), serde_json::json!(page));
            obj.insert("page_count".into(), serde_json::json!(count));
            obj.insert("total".into(), serde_json::json!(rows.len()));
            obj.insert("detail".into(), detail);
        }
    }
    out
}
