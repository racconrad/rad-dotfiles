use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use crate::menu::panels::listen::{read_cached_kind, run_cmd, selected_row, wake};
use crate::menu::panels::present::presentation;
use crate::util::atomic::write_atomic;
use crate::util::hash::token;

pub fn dbus_val(v: &serde_json::Value) -> &serde_json::Value {
    v.get("data").unwrap_or(v)
}

pub fn bluetooth_snapshot() -> Result<serde_json::Value, String> {
    let raw = run_cmd(
        &["busctl", "--json=short", "call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"],
        None,
    )?;
    let parsed: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let Some(objects) = parsed.get("data").and_then(|d| d.as_array()).and_then(|a| a.first()).and_then(|v| v.as_object()) else {
        return Err("Invalid BlueZ reply".into());
    };
    let mut adapters = Vec::new();
    let mut devices = Vec::new();
    for (path, ifaces) in objects {
        if let Some(ap) = ifaces.get("org.bluez.Adapter1").and_then(|v| v.as_object()) {
            let enabled = ap.get("Powered").and_then(|v| dbus_val(v).as_bool()).unwrap_or(false);
            let scanning = ap.get("Discovering").and_then(|v| dbus_val(v).as_bool()).unwrap_or(false);
            adapters.push(serde_json::json!({
                "path": path, "token": token(path), "enabled": enabled, "scanning": scanning
            }));
        }
        if let Some(dp) = ifaces.get("org.bluez.Device1").and_then(|v| v.as_object()) {
            let alias = dp.get("Alias").and_then(|v| dbus_val(v).as_str()).filter(|s| !s.is_empty());
            let addr = dp.get("Address").and_then(|v| dbus_val(v).as_str()).unwrap_or("");
            let title = alias.unwrap_or(if addr.is_empty() { "Device" } else { addr });
            let connected = dp.get("Connected").and_then(|v| dbus_val(v).as_bool()).unwrap_or(false);
            let paired = dp.get("Paired").and_then(|v| dbus_val(v).as_bool()).unwrap_or(false);
            let trusted = dp.get("Trusted").and_then(|v| dbus_val(v).as_bool()).unwrap_or(false);
            let icon = dp.get("Icon").and_then(|v| dbus_val(v).as_str()).unwrap_or("bluetooth-symbolic");
            let kind = match icon {
                "audio-headset" | "audio-headphones" => "Headphones",
                "audio-card" => "Audio",
                "input-keyboard" => "Keyboard",
                "input-mouse" => "Mouse",
                "input-gaming" => "Controller",
                "phone" => "Phone",
                "computer" => "Computer",
                _ => "Device",
            };
            let bat_pct = ifaces
                .get("org.bluez.Battery1")
                .and_then(|b| b.get("Percentage"))
                .and_then(|v| dbus_val(v).as_u64())
                .filter(|&p| p <= 100);
            let battery = bat_pct.map(|p| format!("{p}%")).unwrap_or_default();
            let rssi = dp.get("RSSI").and_then(|v| dbus_val(v).as_i64());
            let signal = rssi.map(|r| format!("{r} dBm")).unwrap_or_else(|| "No data".into());
            devices.push(serde_json::json!({
                "path": path, "token": token(path), "title": title,
                "connected": connected, "paired": paired, "battery": battery,
                "address": addr, "trusted": trusted, "kind": kind, "icon": icon, "signal": signal
            }));
        }
    }
    devices.sort_by(|a, b| {
        let ac = a["connected"].as_bool().unwrap_or(false);
        let bc = b["connected"].as_bool().unwrap_or(false);
        let ap = a["paired"].as_bool().unwrap_or(false);
        let bp = b["paired"].as_bool().unwrap_or(false);
        bc.cmp(&ac).then_with(|| bp.cmp(&ap)).then_with(|| {
            a["title"].as_str().unwrap_or("").to_lowercase().cmp(&b["title"].as_str().unwrap_or("").to_lowercase())
        })
    });
    let enabled = adapters.iter().any(|a| a["enabled"].as_bool() == Some(true));
    let scanning = adapters.iter().any(|a| a["scanning"].as_bool() == Some(true));
    let title = devices
        .iter()
        .find(|d| d["connected"].as_bool() == Some(true))
        .and_then(|d| d["title"].as_str())
        .map(str::to_string)
        .unwrap_or_else(|| if enabled { "Disconnected".into() } else { "Off".into() });
    let err = if adapters.is_empty() { "No Bluetooth adapter found." } else { "" };
    Ok(serde_json::json!({
        "ready": true, "available": !adapters.is_empty(), "title": title,
        "enabled": enabled, "scanning": scanning, "adapters": adapters,
        "empty": devices.is_empty(), "devices": devices, "error": err
    }))
}

pub fn handle_bt_page(args: &[String], runtime: &Path) -> Result<(), String> {
    let dir = args.get(1).map(|s| s.as_str()).unwrap_or("");
    if !matches!(dir, "next" | "previous") {
        return Err("Invalid page.".into());
    }
    let frame = presentation("bluetooth", &read_cached_kind("bluetooth"), runtime);
    let cur = frame["list_page"].as_i64().unwrap_or(0);
    let count = frame["page_count"].as_i64().unwrap_or(1);
    let next = (cur + if dir == "next" { 1 } else { -1 }).clamp(0, count - 1);
    write_atomic(&runtime.join("list-page-bluetooth"), next.to_string().as_bytes())
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub fn handle_bt_select(args: &[String], runtime: &Path) -> Result<(), String> {
    let tok = args.get(1).ok_or("Missing token")?;
    let row = selected_row("bluetooth", tok, "devices")?;
    let t = row["token"].as_str().unwrap_or("");
    write_atomic(&runtime.join("bt-selected"), t.as_bytes()).map_err(|e| e.to_string())?;
    wake(runtime, "bluetooth");
    Ok(())
}

pub fn handle_bt_back(runtime: &Path) -> Result<(), String> {
    write_atomic(&runtime.join("bt-selected"), b"").map_err(|e| e.to_string())?;
    wake(runtime, "bluetooth");
    Ok(())
}

pub fn handle_bt_power(args: &[String], runtime: &Path) -> Result<(), String> {
    let state = args.get(1).map(|s| s.as_str()).unwrap_or("");
    if !matches!(state, "on" | "off") {
        return Err("Invalid Bluetooth state.".into());
    }
    let data = bluetooth_snapshot().unwrap_or_else(|_| read_cached_kind("bluetooth"));
    let val = if state == "on" { "true" } else { "false" };
    let mut r = Ok(());
    if let Some(adapters) = data.get("adapters").and_then(|v| v.as_array()) {
        for ad in adapters {
            if let Some(path) = ad.get("path").and_then(|v| v.as_str()) {
                if path.starts_with("/org/bluez/hci") {
                    if let Err(e) = run_cmd(
                        &["busctl", "set-property", "org.bluez", path, "org.bluez.Adapter1", "Powered", "b", val],
                        None,
                    ) {
                        r = Err(e);
                    }
                }
            }
        }
    }
    if state == "off" {
        let _ = write_atomic(&runtime.join("scan-until"), b"0");
        let _ = write_atomic(&runtime.join("bt-selected"), b"");
    }
    wake(runtime, "bluetooth");
    r
}

pub fn handle_bt_scan(runtime: &Path) -> Result<(), String> {
    let data = bluetooth_snapshot().unwrap_or_else(|_| read_cached_kind("bluetooth"));
    let powered = data
        .get("adapters")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().any(|a| a.get("enabled").and_then(|v| v.as_bool()) == Some(true)))
        .unwrap_or(false);
    if !powered {
        return Err("Turn on Bluetooth first.".into());
    }
    let until = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64() + 20.0;
    let _ = write_atomic(&runtime.join("scan-until"), until.to_string().as_bytes());
    wake(runtime, "bluetooth");
    Ok(())
}

pub fn handle_bt_device(args: &[String], runtime: &Path) -> Result<(), String> {
    let tok = args.get(1).ok_or("Missing token")?;
    let row = selected_row("bluetooth", tok, "devices")?;
    let path = row["path"].as_str().unwrap_or("");
    let addr = row["address"].as_str().unwrap_or("");
    if !path.starts_with("/org/bluez/hci") {
        return Err("Invalid device.".into());
    }
    let mut paired = row["paired"].as_bool().unwrap_or(false);
    let mut trusted = row["trusted"].as_bool().unwrap_or(false);
    let mut connected = row["connected"].as_bool().unwrap_or(false);
    if let Ok(fresh) = bluetooth_snapshot() {
        if let Some(d) = fresh.get("devices").and_then(|v| v.as_array()).and_then(|arr| arr.iter().find(|x| x["path"].as_str() == Some(path))) {
            paired = d["paired"].as_bool().unwrap_or(paired);
            trusted = d["trusted"].as_bool().unwrap_or(trusted);
            connected = d["connected"].as_bool().unwrap_or(connected);
        }
    }
    let mut res = Ok(());
    let mut just_paired = false;
    if !paired && !addr.is_empty() {
        if let Err(e) = run_cmd(&["bluetoothctl", "--agent", "NoInputNoOutput", "--timeout", "20", "pair", addr], None) {
            res = Err(e);
        } else {
            just_paired = true;
        }
    }
    if res.is_ok() && !trusted {
        let _ = run_cmd(&["busctl", "set-property", "org.bluez", path, "org.bluez.Device1", "Trusted", "b", "true"], None);
    }
    if res.is_ok() {
        let method = if connected { "Disconnect" } else { "Connect" };
        if let Err(e) = run_cmd(&["busctl", "call", "org.bluez", path, "org.bluez.Device1", method], None) {
            let low = e.to_lowercase();
            if method == "Connect" && just_paired && (low.contains("failed") || low.contains("abort") || low.contains("temporarily")) {
                std::thread::sleep(Duration::from_millis(400));
                res = run_cmd(&["busctl", "call", "org.bluez", path, "org.bluez.Device1", "Connect"], None).map(|_| ());
            } else {
                res = Err(e);
            }
        }
    }
    wake(runtime, "bluetooth");
    res
}
