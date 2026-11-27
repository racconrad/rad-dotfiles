use std::collections::BTreeMap;
use std::io::Read;
use std::path::Path;

use crate::menu::panels::listen::{read_cached_kind, run_cmd, selected_row, wake};
use crate::menu::panels::present::presentation;
use crate::util::atomic::write_atomic;
use crate::util::hash::token;

pub fn split_nmcli_fields(line: &str) -> Vec<String> {
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

pub fn handle_wifi_page(args: &[String], runtime: &Path) -> Result<(), String> {
    let dir = args.get(1).map(|s| s.as_str()).unwrap_or("");
    if !matches!(dir, "next" | "previous") {
        return Err("Invalid page.".into());
    }
    let frame = presentation("connections", &read_cached_kind("connections"), runtime);
    let cur = frame["list_page"].as_i64().unwrap_or(0);
    let count = frame["page_count"].as_i64().unwrap_or(1);
    let next = (cur + if dir == "next" { 1 } else { -1 }).clamp(0, count - 1);
    write_atomic(&runtime.join("list-page-connections"), next.to_string().as_bytes())
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub fn handle_wifi_connect(args: &[String], runtime: &Path) -> Result<(), String> {
    let tok = args.get(1).ok_or("Missing token")?;
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
    wake(runtime, "connections");
    res
}

pub fn handle_wifi_disconnect(args: &[String], runtime: &Path) -> Result<(), String> {
    let tok = args.get(1).ok_or("Missing token")?;
    let row = selected_row("connections", tok, "networks")?;
    if row["active"].as_bool() != Some(true) {
        return Err("Network is already disconnected.".into());
    }
    let dev = row["device"].as_str().unwrap_or("");
    let r = run_cmd(&["nmcli", "--wait", "8", "device", "disconnect", dev], None);
    wake(runtime, "connections");
    r.map(|_| ())
}

pub fn handle_wifi_power(args: &[String], runtime: &Path) -> Result<(), String> {
    let state = args.get(1).map(|s| s.as_str()).unwrap_or("");
    if !matches!(state, "on" | "off") {
        return Err("Invalid Wi-Fi state.".into());
    }
    let r = run_cmd(&["nmcli", "radio", "wifi", state], None);
    wake(runtime, "connections");
    r.map(|_| ())
}

pub fn handle_wifi_scan(runtime: &Path) -> Result<(), String> {
    if let Err(e) = run_cmd(&["nmcli", "--wait", "10", "device", "wifi", "rescan"], None) {
        let low = e.to_lowercase();
        if !low.contains("not allowed") && !low.contains("in progress") {
            wake(runtime, "connections");
            return Err(e);
        }
    }
    wake(runtime, "connections");
    Ok(())
}
