use std::fs;
use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, UNIX_EPOCH};

use crate::menu::transport;
use crate::util::atomic::write_atomic;
use crate::util::paths::{home_dir, runtime_root};

const GAP: i64 = 4;

fn strip_jsonc(text: &str) -> String {
    let bytes = text.as_bytes();
    let mut out = String::with_capacity(text.len());
    let mut i = 0;
    let mut quoted = false;
    while i < bytes.len() {
        let b = bytes[i];
        if quoted {
            out.push(b as char);
            if b == b'\\' && i + 1 < bytes.len() {
                i += 1;
                out.push(bytes[i] as char);
            } else if b == b'"' {
                quoted = false;
            }
            i += 1;
        } else if b == b'"' {
            quoted = true;
            out.push('"');
            i += 1;
        } else if i + 1 < bytes.len() && b == b'/' && bytes[i + 1] == b'/' {
            while i < bytes.len() && bytes[i] != b'\n' {
                i += 1;
            }
        } else if i + 1 < bytes.len() && b == b'/' && bytes[i + 1] == b'*' {
            i += 2;
            while i + 1 < bytes.len() && !(bytes[i] == b'*' && bytes[i + 1] == b'/') {
                i += 1;
            }
            i = (i + 2).min(bytes.len());
        } else {
            out.push(b as char);
            i += 1;
        }
    }
    out
}

fn bar_config(output: &str) -> serde_json::Value {
    let path = home_dir().join(".config/waybar/config.jsonc");
    let Ok(raw) = fs::read_to_string(path) else {
        return serde_json::json!({});
    };
    let clean = strip_jsonc(&raw);
    let Ok(val) = serde_json::from_str::<serde_json::Value>(&clean) else {
        return serde_json::json!({});
    };
    let bars = match val {
        serde_json::Value::Array(arr) => arr,
        other => vec![other],
    };
    bars.into_iter()
        .find(|bar| {
            if !bar.is_object() {
                return false;
            }
            match bar.get("output") {
                None => true,
                Some(serde_json::Value::String(s)) => output.is_empty() || s == output,
                Some(serde_json::Value::Array(arr)) => {
                    output.is_empty() || arr.iter().any(|v| v.as_str() == Some(output))
                }
                _ => true,
            }
        })
        .unwrap_or_else(|| serde_json::json!({}))
}

fn find_wayfire_socket() -> Option<PathBuf> {
    if let Ok(sock) = std::env::var("WAYFIRE_SOCKET") {
        if !sock.is_empty() {
            return Some(PathBuf::from(sock));
        }
    }
    let root = runtime_root();
    let entries = fs::read_dir(&root).ok()?;
    for e in entries.flatten() {
        let name = e.file_name();
        let s = name.to_string_lossy();
        if s.starts_with("wayfire") && s.ends_with(".socket") {
            return Some(e.path());
        }
    }
    None
}

fn wayfire_ipc(sock_path: &Path, method: &str) -> Result<serde_json::Value, String> {
    let mut stream = UnixStream::connect(sock_path).map_err(|e| e.to_string())?;
    let _ = stream.set_read_timeout(Some(Duration::from_millis(120)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(120)));
    let msg = serde_json::json!({"method": method, "data": {}}).to_string();
    let len = (msg.len() as u32).to_le_bytes();
    stream.write_all(&len).map_err(|e| e.to_string())?;
    stream.write_all(msg.as_bytes()).map_err(|e| e.to_string())?;
    let mut hdr = [0u8; 4];
    stream.read_exact(&mut hdr).map_err(|e| e.to_string())?;
    let rlen = u32::from_le_bytes(hdr) as usize;
    if rlen > 4 * 1024 * 1024 {
        return Err("Unexpected Wayfire response size".into());
    }
    let mut buf = vec![0u8; rlen];
    stream.read_exact(&mut buf).map_err(|e| e.to_string())?;
    serde_json::from_slice(&buf).map_err(|e| e.to_string())
}

fn num(v: Option<&serde_json::Value>, default: i64) -> i64 {
    v.and_then(|x| x.as_i64().or_else(|| x.as_f64().map(|f| f as i64)))
        .map(|x| x.max(0))
        .unwrap_or(default)
}

#[derive(Clone, Copy)]
struct DockLayout {
    edge: &'static str,
    inset: i64,
    start: i64,
    end: i64,
    ox: i64,
    oy: i64,
    ow: i64,
    oh: i64,
}

fn compute_layout(bar: &serde_json::Value, geo: Option<&serde_json::Value>, output: Option<&serde_json::Value>) -> DockLayout {
    let ow = output.map(|o| num(o.get("width"), 1920)).unwrap_or(1920);
    let oh = output.map(|o| num(o.get("height"), 1080)).unwrap_or(1080);
    let ox = output.and_then(|o| o.get("x")).and_then(|v| v.as_i64()).unwrap_or(0);
    let oy = output.and_then(|o| o.get("y")).and_then(|v| v.as_i64()).unwrap_or(0);
    let mut edge = match bar.get("position").and_then(|v| v.as_str()) {
        Some("top") => "top",
        Some("left") => "left",
        Some("right") => "right",
        _ => "bottom",
    };

    let (inset, start, end) = if let Some(g) = geo {
        let x = num(g.get("x"), 0);
        let y = num(g.get("y"), 0);
        let w = num(g.get("width"), 0);
        let h = num(g.get("height"), 0);
        edge = if w >= h {
            if (y as f64 + h as f64 / 2.0) < (oh as f64 / 2.0) { "top" } else { "bottom" }
        } else if (x as f64 + w as f64 / 2.0) < (ow as f64 / 2.0) {
            "left"
        } else {
            "right"
        };
        if matches!(edge, "top" | "bottom") {
            let ins = if edge == "top" { y + h + GAP } else { oh - y + GAP };
            (ins, x, (ow - x - w).max(0))
        } else {
            let ins = if edge == "left" { x + w + GAP } else { ow - x + GAP };
            (ins, y, (oh - y - h).max(0))
        }
    } else {
        let base = if matches!(edge, "top" | "bottom") {
            num(bar.get("height"), 32)
        } else {
            num(bar.get("width"), 48)
        };
        let ins = base + num(bar.get(&format!("margin-{edge}")), 0) + GAP;
        let s = num(bar.get(if matches!(edge, "top" | "bottom") { "margin-left" } else { "margin-top" }), 8);
        let e = num(bar.get(if matches!(edge, "top" | "bottom") { "margin-right" } else { "margin-bottom" }), 8);
        (ins, s, e)
    };
    DockLayout {
        edge,
        inset: inset.max(GAP),
        start: start.max(4),
        end: end.max(4),
        ox,
        oy,
        ow,
        oh,
    }
}

fn current_dock() -> (DockLayout, &'static str) {
    if let Some(sock) = find_wayfire_socket() {
        if let Ok(resp) = wayfire_ipc(&sock, "window-rules/get-focused-output") {
            let mut focus = resp.get("info").filter(|v| v.is_object() && !v.as_object().unwrap().is_empty()).cloned();
            if focus.is_none() {
                if let Ok(serde_json::Value::Array(outs)) = wayfire_ipc(&sock, "window-rules/list-outputs") {
                    focus = outs.into_iter().find(|v| v.is_object());
                }
            }
            if let Some(f) = focus {
                let out_name = f.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let views = wayfire_ipc(&sock, "window-rules/list-views").ok();
                let chosen = views.and_then(|v| {
                    v.as_array().and_then(|arr| {
                        arr.iter()
                            .filter(|item| {
                                item.get("mapped").and_then(|m| m.as_bool()) == Some(true)
                                    && item.get("app-id").and_then(|a| a.as_str()) == Some("waybar")
                                    && item.get("output-name").and_then(|o| o.as_str()) == Some(out_name)
                            })
                            .max_by_key(|item| {
                                let g = item.get("geometry");
                                let w = num(g.and_then(|x| x.get("width")), 0);
                                let h = num(g.and_then(|x| x.get("height")), 0);
                                w * h
                            })
                            .cloned()
                    })
                });
                let layout = compute_layout(&bar_config(out_name), chosen.as_ref().and_then(|c| c.get("geometry")), f.get("geometry"));
                let source = if chosen.is_some() { "wayfire" } else { "config" };
                return (layout, source);
            }
        }
    }
    (compute_layout(&bar_config(""), None, None), "config")
}

pub fn refresh(runtime: &Path, force: bool, last_run: &mut Option<Instant>) {
    if !force {
        if let Some(prev) = last_run {
            if prev.elapsed() < Duration::from_millis(500) {
                return;
            }
        }
    }
    *last_run = Some(Instant::now());
    let (d, source) = current_dock();
    let mtime = fs::metadata(home_dir().join(".config/waybar/config.jsonc"))
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|t| t.as_nanos())
        .unwrap_or(0);
    let text = format!(
        "[dock]\nedge = {}\ninset = {}\nstart = {}\nend = {}\nox = {}\noy = {}\now = {}\noh = {}\nsource = {}\nconfig_mtime = {}\n\n",
        d.edge, d.inset, d.start, d.end, d.ox, d.oy, d.ow, d.oh, source, mtime
    );
    let target = runtime.join("dock.ini");
    if let Ok(prev) = fs::read_to_string(&target) {
        if source == "config"
            && prev.contains("source = wayfire")
            && prev.contains(&format!("config_mtime = {mtime}"))
        {
            return;
        }
        if prev == text {
            return;
        }
    }
    if write_atomic(&target, text.as_bytes()).is_ok() {
        transport::send("dock", runtime);
    }
}
