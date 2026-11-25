use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::menu::{runtime, transport};
use crate::util::atomic::write_atomic;
use crate::util::hash::token;
use crate::util::paths::{config_dir, home_dir, runtime_dir, state_root};
use crate::util::watch::{emit_line, DirWatch};

const PAGE_SIZE: usize = 4;

fn panel_state_dir() -> std::path::PathBuf {
    state_root().join("desktop-panel")
}

fn service_page(kind: &str) -> Option<&'static str> {
    match kind {
        "audio" => Some("4"),
        "connections" => Some("5"),
        "bluetooth" => Some("6"),
        "calendar" => Some("7"),
        _ => None,
    }
}

fn run_cmd(argv: &[&str], stdin_data: Option<&str>) -> Result<String, String> {
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

fn defaults(kind: &str) -> serde_json::Value {
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

fn extract_volume_pct(vol_obj: Option<&serde_json::Value>) -> i64 {
    let Some(map) = vol_obj.and_then(|v| v.as_object()) else {
        return 0;
    };
    let mut total = 0i64;
    let mut count = 0i64;
    for ch in map.values() {
        if let Some(vp) = ch.get("value_percent").and_then(|v| v.as_str()) {
            let digits: String = vp.chars().take_while(|c| c.is_ascii_digit()).collect();
            if let Ok(n) = digits.parse::<i64>() {
                total += n;
                count += 1;
            }
        }
    }
    if count == 0 {
        0
    } else {
        ((total as f64 / count as f64).round() as i64).clamp(0, 100)
    }
}

pub fn audio_snapshot() -> Result<serde_json::Value, String> {
    let info_s = run_cmd(&["pactl", "-f", "json", "info"], None)?;
    let sinks_s = run_cmd(&["pactl", "-f", "json", "list", "sinks"], None)?;
    let sources_s = run_cmd(&["pactl", "-f", "json", "list", "sources"], None)?;
    let info: serde_json::Value = serde_json::from_str(&info_s).map_err(|e| e.to_string())?;
    let sinks: Vec<serde_json::Value> = serde_json::from_str(&sinks_s).map_err(|e| e.to_string())?;
    let sources: Vec<serde_json::Value> = serde_json::from_str(&sources_s).map_err(|e| e.to_string())?;

    let def_sink = info
        .get("default_sink_name")
        .or_else(|| info.get("default_sink"))
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let def_src = info
        .get("default_source_name")
        .or_else(|| info.get("default_source"))
        .and_then(|v| v.as_str())
        .unwrap_or("");

    let map_devices = |list: &[serde_json::Value], def_name: &str, filter_monitor: bool| -> (Vec<serde_json::Value>, serde_json::Value) {
        let mut rows = Vec::new();
        for dev in list {
            let name = dev.get("name").and_then(|v| v.as_str()).unwrap_or("");
            if filter_monitor && name.ends_with(".monitor") {
                continue;
            }
            let title = dev
                .get("description")
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .unwrap_or(name);
            let mute = dev.get("mute").and_then(|v| v.as_bool()).unwrap_or(false);
            let vol = extract_volume_pct(dev.get("volume"));
            rows.push(serde_json::json!({
                "name": name,
                "token": token(name),
                "title": title,
                "mute": mute,
                "volume": vol,
                "active": !def_name.is_empty() && name == def_name,
            }));
        }
        let chosen = rows
            .iter()
            .find(|r| r.get("active").and_then(|v| v.as_bool()) == Some(true))
            .cloned()
            .or_else(|| rows.first().cloned())
            .unwrap_or_else(|| serde_json::json!({"name": "", "title": "No device", "token": "", "volume": 0, "mute": false}));
        (rows, chosen)
    };

    let (outputs, output) = map_devices(&sinks, def_sink, false);
    let (inputs, input) = map_devices(&sources, def_src, true);
    Ok(serde_json::json!({
        "available": true,
        "ready": true,
        "error": "",
        "title": "Audio",
        "outputs": outputs,
        "inputs": inputs,
        "output": output,
        "input": input,
    }))
}

fn split_nmcli_fields(line: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut cur = String::new();
    let mut esc = false;
    for c in line.chars() {
        if esc {
            cur.push(c);
            esc = false;
        } else if c == '\\' {
            esc = true;
        } else if c == ':' {
            result.push(std::mem::take(&mut cur));
        } else {
            cur.push(c);
        }
    }
    result.push(cur);
    result
}

pub fn wifi_snapshot() -> Result<serde_json::Value, String> {
    let radio = run_cmd(&["nmcli", "radio", "wifi"], None)?;
    let list = run_cmd(
        &["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,SIGNAL,SECURITY,DEVICE", "device", "wifi", "list", "--rescan", "no"],
        None,
    )?;
    let mut by_ssid: BTreeMap<String, serde_json::Value> = BTreeMap::new();
    for line in list.lines() {
        let parts = split_nmcli_fields(line);
        if parts.len() != 6 || parts[1].is_empty() {
            continue;
        }
        let (act, ssid, bssid, sig_s, sec, dev) = (&parts[0], &parts[1], &parts[2], &parts[3], &parts[4], &parts[5]);
        let active = act == "*";
        let signal: i64 = sig_s.parse().unwrap_or(0);
        let secured = !sec.is_empty() && sec != "--";
        let item = serde_json::json!({
            "active": active,
            "title": ssid,
            "bssid": bssid,
            "device": dev,
            "token": token(&format!("{bssid}|{dev}")),
            "signal": signal,
            "secured": secured,
            "security": if secured { sec.as_str() } else { "Open" },
        });
        let replace = match by_ssid.get(ssid) {
            None => true,
            Some(old) => {
                let old_active = old["active"].as_bool().unwrap_or(false);
                let old_sig = old["signal"].as_i64().unwrap_or(0);
                active || (!old_active && signal > old_sig)
            }
        };
        if replace {
            by_ssid.insert(ssid.clone(), item);
        }
    }
    let mut networks: Vec<serde_json::Value> = by_ssid.into_values().collect();
    networks.sort_by(|a, b| {
        let aa = a["active"].as_bool().unwrap_or(false);
        let ba = b["active"].as_bool().unwrap_or(false);
        ba.cmp(&aa).then_with(|| {
            b["signal"].as_i64().unwrap_or(0).cmp(&a["signal"].as_i64().unwrap_or(0))
        })
    });
    let is_enabled = radio.trim() == "enabled";
    let title = networks
        .iter()
        .find(|n| n["active"].as_bool() == Some(true))
        .and_then(|n| n["title"].as_str())
        .map(str::to_string)
        .unwrap_or_else(|| if is_enabled { "Disconnected".into() } else { "Off".into() });
    Ok(serde_json::json!({
        "available": true,
        "ready": true,
        "error": "",
        "title": title,
        "enabled": is_enabled,
        "empty": networks.is_empty(),
        "networks": networks,
    }))
}

fn dbus_val(v: &serde_json::Value) -> &serde_json::Value {
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

pub fn refresh_kind(kind: &str) -> serde_json::Value {
    let res = match kind {
        "audio" => audio_snapshot(),
        "connections" => wifi_snapshot(),
        _ => bluetooth_snapshot(),
    };
    let data = match res {
        Ok(val) => val,
        Err(_) => {
            let mut d = defaults(kind);
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
    let _ = write_atomic(&panel_state_dir().join(format!("{kind}.json")), data.to_string().as_bytes());
    data
}

fn empty_wifi() -> serde_json::Value {
    serde_json::json!({"token": "", "title": "", "secured": false, "active": false, "signal": 0, "security": ""})
}

fn default_device_info() -> serde_json::Value {
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

fn read_cached_kind(kind: &str) -> serde_json::Value {
    let mut base = defaults(kind);
    if let Ok(text) = fs::read_to_string(panel_state_dir().join(format!("{kind}.json"))) {
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

fn wake(runtime: &Path, kind: &str) {
    let ns = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos().to_string();
    let _ = write_atomic(&runtime.join(format!("refresh-{kind}")), ns.as_bytes());
}

fn is_active(runtime: &Path, kind: &str) -> bool {
    let vis = fs::read_to_string(runtime.join("visible")).unwrap_or_default();
    let page = fs::read_to_string(runtime.join("page")).unwrap_or_default();
    vis.trim() == "1" && service_page(kind) == Some(page.trim())
}

pub fn listen(kind: &str) -> Result<(), String> {
    if service_page(kind).is_none() {
        return Err("Unknown panel kind".into());
    }
    let runtime = runtime_dir();
    let _ = fs::create_dir_all(&runtime);
    let watcher = DirWatch::new(&[], &[runtime.clone()]);
    let mut data = read_cached_kind(kind);
    let mut shown = presentation(kind, &data, &runtime).to_string();
    if !emit_line(&shown) { return Ok(()); }

    let mut deadline = Instant::now();
    let mut previous_marker = String::new();
    let mut was_active = false;
    let mut discovery: BTreeSet<String> = BTreeSet::new();

    loop {
        let current = is_active(&runtime, kind);
        let marker = fs::read_to_string(runtime.join(format!("refresh-{kind}"))).unwrap_or_default();
        if current || marker != previous_marker {
            let now = Instant::now();
            if (current && (!was_active || now >= deadline)) || marker != previous_marker {
                if current && kind == "bluetooth" {
                    let now_secs = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64();
                    let scanning = fs::read_to_string(runtime.join("scan-until"))
                        .ok()
                        .and_then(|s| s.trim().parse::<f64>().ok())
                        .map(|t| t > now_secs)
                        .unwrap_or(false);
                    if !scanning {
                        for path in discovery.clone() {
                            let _ = run_cmd(&["busctl", "call", "org.bluez", &path, "org.bluez.Adapter1", "StopDiscovery"], None);
                            discovery.remove(&path);
                        }
                    } else if let Some(adapters) = data.get("adapters").and_then(|v| v.as_array()) {
                        for ad in adapters {
                            let en = ad.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
                            if let Some(p) = ad.get("path").and_then(|v| v.as_str()) {
                                if en && !discovery.contains(p) {
                                    let _ = run_cmd(&["busctl", "call", "org.bluez", p, "org.bluez.Adapter1", "StartDiscovery"], None);
                                    discovery.insert(p.to_string());
                                }
                            }
                        }
                    }
                }
                let fresh = refresh_kind(kind);
                let frame = presentation(kind, &fresh, &runtime).to_string();
                if frame != shown {
                    if !emit_line(&frame) { return Ok(()); }
                    shown = frame;
                }
                data = fresh;
                previous_marker = marker;
                deadline = now + Duration::from_secs(if kind == "audio" { 1 } else { 2 });
            }
            if current {
                let frame = presentation(kind, &data, &runtime).to_string();
                if frame != shown {
                    if !emit_line(&frame) { return Ok(()); }
                    shown = frame;
                }
            }
        } else if !discovery.is_empty() {
            for path in discovery.clone() {
                let _ = run_cmd(&["busctl", "call", "org.bluez", &path, "org.bluez.Adapter1", "StopDiscovery"], None);
            }
            discovery.clear();
        }
        was_active = current;
        watcher.wait(if current { 250 } else { 5000 });
    }
}

fn selected_row(kind: &str, tok: &str, group: &str) -> Result<serde_json::Value, String> {
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

fn eww_update(pairs: &[(&str, String)]) {
    let args: Vec<String> = std::iter::once("update".to_string())
        .chain(pairs.iter().map(|(k, v)| format!("{k}={v}")))
        .collect();
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let _ = runtime::eww_cmd(&refs);
}

pub fn sync_appearance() {
    let menu_cfg = config_dir();
    let eww_cfg = home_dir().join(".config/raccon-menu");
    for filename in ["_palette.scss", "_desktop-style.scss"] {
        let src = eww_cfg.join(filename);
        let dst = menu_cfg.join(filename);
        let text = fs::read_to_string(&src).unwrap_or_else(|_| "/* No global override */\n".into());
        if fs::read_to_string(&dst).ok().as_deref() != Some(text.as_str()) {
            let _ = write_atomic(&dst, text.as_bytes());
        }
    }
}

pub fn preload() {
    std::thread::scope(|s| {
        s.spawn(|| { refresh_kind("audio"); });
        s.spawn(|| { refresh_kind("connections"); });
        s.spawn(|| { refresh_kind("bluetooth"); });
    });
}

pub fn execute(args: &[String]) -> Result<(), String> {
    let runtime = runtime_dir();
    let _ = fs::create_dir_all(&runtime);
    if args.is_empty() {
        return runtime::show(Some("audio"), false);
    }
    let op = args[0].as_str();
    if let Some(_) = service_page(op) {
        return runtime::show(Some(op), false);
    }
    if op == "tab" {
        if let Some(p) = args.get(1) {
            if let Some(idx) = service_page(p) {
                if !transport::send(&format!("service {idx}"), &runtime) {
                    return runtime::show(Some(p), false);
                }
                return Ok(());
            }
        }
        return Err("Invalid section.".into());
    }
    if op == "close" {
        return runtime::close(false);
    }
    if op == "preload" {
        preload();
        return Ok(());
    }
    if op == "listen" {
        let kind = args.get(1).ok_or("Missing panel kind")?;
        return listen(kind);
    }
    if op == "retry" {
        let kind = args.get(1).ok_or("Missing panel kind")?;
        if !matches!(kind.as_str(), "audio" | "connections" | "bluetooth") {
            return Err("Invalid panel.".into());
        }
        refresh_kind(kind);
        wake(&runtime, kind);
        return Ok(());
    }

    match op {
        "wifi-page" | "bt-page" => {
            let kind = if op == "wifi-page" { "connections" } else { "bluetooth" };
            let dir = args.get(1).map(|s| s.as_str()).unwrap_or("");
            if !matches!(dir, "next" | "previous") {
                return Err("Invalid page.".into());
            }
            let frame = presentation(kind, &read_cached_kind(kind), &runtime);
            let cur = frame["list_page"].as_i64().unwrap_or(0);
            let count = frame["page_count"].as_i64().unwrap_or(1);
            let next = (cur + if dir == "next" { 1 } else { -1 }).clamp(0, count - 1);
            write_atomic(&runtime.join(format!("list-page-{kind}")), next.to_string().as_bytes())
                .map_err(|e| e.to_string())?;
        }
        "bt-select" => {
            let tok = args.get(1).ok_or("Missing token")?;
            let row = selected_row("bluetooth", tok, "devices")?;
            let t = row["token"].as_str().unwrap_or("");
            write_atomic(&runtime.join("bt-selected"), t.as_bytes()).map_err(|e| e.to_string())?;
            wake(&runtime, "bluetooth");
        }
        "bt-back" => {
            write_atomic(&runtime.join("bt-selected"), b"").map_err(|e| e.to_string())?;
            wake(&runtime, "bluetooth");
        }
        "wifi-select" => {
            let tok = args.get(1).ok_or("Missing token")?;
            let row = selected_row("connections", tok, "networks")?;
            let payload = serde_json::json!({
                "token": row["token"], "title": row["title"], "secured": row["secured"],
                "active": row["active"], "signal": row["signal"], "security": row["security"]
            });
            eww_update(&[("wifi_selected", payload.to_string())]);
        }
        "wifi-connect" => {
            let raw = runtime::eww_cmd(&["get", "wifi_selected"])?;
            let sel: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
            let tok = sel.get("token").and_then(|v| v.as_str()).unwrap_or("");
            let row = selected_row("connections", tok, "networks")?;
            let mut buf = Vec::new();
            std::io::stdin().take(1025).read_to_end(&mut buf).map_err(|e| e.to_string())?;
            let secret = String::from_utf8_lossy(&buf).into_owned();
            if secret.len() > 1024 || secret.contains('\n') || secret.contains('\r') {
                return Err("Invalid password.".into());
            }
            let title = row["title"].as_str().unwrap_or("");
            let bssid = row["bssid"].as_str().unwrap_or("");
            let dev = row["device"].as_str().unwrap_or("");
            eww_update(&[
                ("wifi_busy", "true".into()),
                ("wifi_action", format!("Connecting to {title}…")),
                ("error", String::new()),
            ]);
            let mut res = Ok(());
            let mut connected = false;
            if secret.is_empty() {
                if let Ok(saved) = run_cmd(&["nmcli", "-t", "-f", "NAME", "connection", "show"], None) {
                    if saved.lines().any(|l| l == title) {
                        if run_cmd(&["nmcli", "--wait", "20", "connection", "up", "id", title], None).is_ok() {
                            connected = true;
                        }
                    }
                }
            }
            if !connected {
                let mut argv = vec!["nmcli", "--wait", "20"];
                if !secret.is_empty() {
                    argv.push("--ask");
                }
                argv.extend(["device", "wifi", "connect", bssid, "ifname", dev]);
                let stdin_str = if secret.is_empty() { None } else { Some(format!("{secret}\n")) };
                if let Err(e) = run_cmd(&argv, stdin_str.as_deref()) {
                    res = Err(e);
                }
            }
            if res.is_ok() {
                eww_update(&[("wifi_selected", empty_wifi().to_string())]);
            }
            eww_update(&[("wifi_action", String::new()), ("wifi_busy", "false".into())]);
            wake(&runtime, "connections");
            res?;
        }
        "wifi-disconnect" => {
            let tok = args.get(1).ok_or("Missing token")?;
            let row = selected_row("connections", tok, "networks")?;
            if row["active"].as_bool() != Some(true) {
                return Err("Network is already disconnected.".into());
            }
            let title = row["title"].as_str().unwrap_or("");
            let dev = row["device"].as_str().unwrap_or("");
            eww_update(&[
                ("wifi_busy", "true".into()),
                ("wifi_action", format!("Disconnecting {title}…")),
                ("error", String::new()),
            ]);
            let r = run_cmd(&["nmcli", "--wait", "8", "device", "disconnect", dev], None);
            if r.is_ok() {
                eww_update(&[("wifi_selected", empty_wifi().to_string())]);
            }
            eww_update(&[("wifi_action", String::new()), ("wifi_busy", "false".into())]);
            wake(&runtime, "connections");
            r?;
        }
        "wifi-power" => {
            let state = args.get(1).map(|s| s.as_str()).unwrap_or("");
            if !matches!(state, "on" | "off") {
                return Err("Invalid Wi-Fi state.".into());
            }
            eww_update(&[
                ("wifi_busy", "true".into()),
                ("wifi_action", format!("Turning Wi-Fi {state}…")),
                ("error", String::new()),
            ]);
            let r = run_cmd(&["nmcli", "radio", "wifi", state], None);
            if r.is_ok() && state == "off" {
                eww_update(&[("wifi_selected", empty_wifi().to_string())]);
            }
            eww_update(&[("wifi_action", String::new()), ("wifi_busy", "false".into())]);
            wake(&runtime, "connections");
            r?;
        }
        "wifi-scan" => {
            eww_update(&[
                ("wifi_busy", "true".into()),
                ("wifi_action", "Scanning nearby Wi-Fi networks…".into()),
                ("error", String::new()),
            ]);
            if let Err(e) = run_cmd(&["nmcli", "--wait", "10", "device", "wifi", "rescan"], None) {
                let low = e.to_lowercase();
                if !low.contains("not allowed") && !low.contains("in progress") {
                    eww_update(&[("wifi_action", String::new()), ("wifi_busy", "false".into())]);
                    wake(&runtime, "connections");
                    return Err(e);
                }
            }
            eww_update(&[("wifi_action", String::new()), ("wifi_busy", "false".into())]);
            wake(&runtime, "connections");
        }
        "audio-device" | "audio-mute" => {
            let kind = args.get(1).map(|s| s.as_str()).unwrap_or("");
            if !matches!(kind, "output" | "input") {
                return Err("Invalid audio device.".into());
            }
            let tok = args.get(2).ok_or("Missing token")?;
            let row = selected_row("audio", tok, &format!("{kind}s"))?;
            let name = row["name"].as_str().unwrap_or("");
            let target = if kind == "output" { "sink" } else { "source" };
            if op == "audio-device" {
                run_cmd(&["pactl", &format!("set-default-{target}"), name], None)?;
                let var = if kind == "output" { "outputs_open" } else { "inputs_open" };
                eww_update(&[(var, "false".into())]);
            } else {
                run_cmd(&["pactl", &format!("set-{target}-mute"), name, "toggle"], None)?;
            }
            wake(&runtime, "audio");
        }
        "bt-power" => {
            let state = args.get(1).map(|s| s.as_str()).unwrap_or("");
            if !matches!(state, "on" | "off") {
                return Err("Invalid Bluetooth state.".into());
            }
            eww_update(&[
                ("bt_busy", "true".into()),
                ("bt_action", format!("Turning Bluetooth {state}…")),
                ("error", String::new()),
            ]);
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
            eww_update(&[("bt_action", String::new()), ("bt_busy", "false".into())]);
            wake(&runtime, "bluetooth");
            r?;
        }
        "bt-scan" => {
            eww_update(&[
                ("bt_busy", "true".into()),
                ("bt_action", "Starting Bluetooth scan…".into()),
                ("error", String::new()),
            ]);
            let data = bluetooth_snapshot().unwrap_or_else(|_| read_cached_kind("bluetooth"));
            let powered = data
                .get("adapters")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().any(|a| a.get("enabled").and_then(|v| v.as_bool()) == Some(true)))
                .unwrap_or(false);
            if !powered {
                eww_update(&[("bt_action", String::new()), ("bt_busy", "false".into())]);
                return Err("Turn on Bluetooth first.".into());
            }
            let until = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64() + 20.0;
            let _ = write_atomic(&runtime.join("scan-until"), until.to_string().as_bytes());
            eww_update(&[("bt_action", String::new()), ("bt_busy", "false".into())]);
            wake(&runtime, "bluetooth");
        }
        "bt-device" => {
            let tok = args.get(1).ok_or("Missing token")?;
            let row = selected_row("bluetooth", tok, "devices")?;
            let path = row["path"].as_str().unwrap_or("");
            let addr = row["address"].as_str().unwrap_or("");
            let title = row["title"].as_str().unwrap_or("");
            if !path.starts_with("/org/bluez/hci") {
                return Err("Invalid device.".into());
            }
            eww_update(&[
                ("bt_busy", "true".into()),
                ("bt_action", format!("Checking {title}…")),
                ("error", String::new()),
            ]);
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
                eww_update(&[("bt_action", format!("Pairing {title}…"))]);
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
                eww_update(&[(
                    "bt_action",
                    format!("{} {title}…", if connected { "Disconnecting" } else { "Connecting to" }),
                )]);
                if let Err(e) = run_cmd(&["busctl", "call", "org.bluez", path, "org.bluez.Device1", method], None) {
                    let low = e.to_lowercase();
                    if method == "Connect" && just_paired && (low.contains("failed") || low.contains("abort") || low.contains("temporarily")) {
                        eww_update(&[("bt_action", format!("Retrying connection to {title}…"))]);
                        std::thread::sleep(Duration::from_millis(400));
                        res = run_cmd(&["busctl", "call", "org.bluez", path, "org.bluez.Device1", "Connect"], None).map(|_| ());
                    } else {
                        res = Err(e);
                    }
                }
            }
            eww_update(&[("bt_action", String::new()), ("bt_busy", "false".into())]);
            wake(&runtime, "bluetooth");
            res?;
        }
        "advanced" => {
            if args.get(1).map(|s| s.as_str()) != Some("audio") {
                return Err("Invalid panel.".into());
            }
            let mixer = ["pavucontrol", "pwvucontrol", "pavucontrol-qt"]
                .into_iter()
                .find(|m| Command::new("sh").args(["-c", &format!("command -v {m} >/dev/null")]).status().map(|s| s.success()).unwrap_or(false))
                .ok_or("No audio mixer application found.")?;
            let _ = runtime::close(false);
            let _ = Command::new(mixer)
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn();
        }
        "cancel-wifi" => {
            eww_update(&[("wifi_selected", empty_wifi().to_string())]);
        }
        _ => return Err("Invalid action.".into()),
    }
    Ok(())
}
