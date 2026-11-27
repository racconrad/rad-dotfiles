use std::path::Path;
use std::process::{Command, Stdio};

use crate::menu::panels::listen::{run_cmd, selected_row, wake};
use crate::menu::runtime;
use crate::util::hash::token;

pub fn extract_volume_pct(vol_obj: Option<&serde_json::Value>) -> i64 {
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

pub fn handle_audio_action(op: &str, args: &[String], runtime: &Path) -> Result<(), String> {
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
    } else {
        run_cmd(&["pactl", &format!("set-{target}-mute"), name, "toggle"], None)?;
    }
    wake(runtime, "audio");
    Ok(())
}

pub fn handle_advanced_action(args: &[String]) -> Result<(), String> {
    if args.get(1).map(|s| s.as_str()) != Some("audio") {
        return Err("Invalid panel.".into());
    }
    let mixer = ["pavucontrol", "pwvucontrol", "pavucontrol-qt"]
        .into_iter()
        .find(|m| Command::new("sh").args(["-c", &format!("command -v {m} >/dev/null")]).status().map(|s| s.success()).unwrap_or(false))
        .ok_or("No audio mixer application found.")?;
    let _ = runtime::close_menu();
    let _ = Command::new(mixer)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn();
    Ok(())
}
