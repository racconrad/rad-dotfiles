use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

use crate::menu::{
    apps, calendar, float, home_apps, modes, music, panels, recent_apps, runtime, session,
    shortcuts, transport, walls, waybar_music,
};
use crate::util::{atomic, paths};

fn is_hex_color(value: &str) -> bool {
    value.len() == 7 && value.starts_with('#') && value[1..].bytes().all(|b| b.is_ascii_hexdigit())
}

fn is_ident(value: &str) -> bool {
    !value.is_empty() && value.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
}

fn parse_scss_vars(text: &str, colors: &mut BTreeMap<String, String>) {
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix('$') {
            if let Some((k, v)) = rest.split_once(':') {
                let key = k.trim();
                let val = v.trim().trim_end_matches(';').trim();
                if is_ident(key) && is_hex_color(val) {
                    colors.insert(key.to_string(), val.to_string());
                }
            }
        }
    }
}

fn parse_css_define_colors(text: &str, colors: &mut BTreeMap<String, String>) {
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("@define-color") {
            let mut parts = rest.split_whitespace();
            if let (Some(key), Some(raw_val)) = (parts.next(), parts.next()) {
                let val = raw_val.trim_end_matches(';');
                if is_ident(key) && is_hex_color(val) {
                    colors.insert(key.to_string(), val.to_string());
                }
            }
        }
    }
}

fn read_json_value(path: &Path) -> Option<serde_json::Value> {
    fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
}

fn parse_power_appearance(path: &Path) -> BTreeMap<String, String> {
    let mut map = BTreeMap::new();
    let Ok(text) = fs::read_to_string(path) else {
        return map;
    };
    let mut in_appearance = false;
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            in_appearance = trimmed == "[appearance]";
            continue;
        }
        if !in_appearance || trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = trimmed.split_once('=') {
            let val = v.trim().trim_matches('"').trim_matches('\'');
            if is_ident(k.trim()) && is_ident(val) {
                map.insert(k.trim().to_string(), val.to_string());
            }
        }
    }
    map
}

fn write_if_changed(path: &Path, content: &str) {
    if fs::read_to_string(path).ok().as_deref() != Some(content) {
        let _ = atomic::write_atomic(path, content.as_bytes());
    }
}

fn token_number(tokens: Option<&serde_json::Value>, key: &str, default: f64) -> String {
    if let Some(v) = tokens.and_then(|t| t.get(key)).and_then(|v| v.as_f64()) {
        if (0.0..=100.0).contains(&v) {
            return if (v.fract()).abs() < f64::EPSILON {
                format!("{}", v as i64)
            } else {
                format!("{}", v)
            };
        }
    }
    if (default.fract()).abs() < f64::EPSILON {
        format!("{}", default as i64)
    } else {
        format!("{}", default)
    }
}

pub fn sync_palette(home: &Path, state_root: &Path) {
    let config_dir = home.join(".config");
    let menu_cfg = config_dir.join("raccon-menu");

    let mut colors: BTreeMap<String, String> = [
        ("primary", "#a6c8ff"),
        ("on_primary", "#02315f"),
        ("secondary", "#bdc7dc"),
        ("tertiary", "#dabde2"),
        ("surface", "#111318"),
        ("surface_container", "#1d2024"),
        ("surface_container_high", "#282a2f"),
        ("surface_container_highest", "#32353a"),
        ("on_surface", "#e1e2e9"),
        ("on_surface_variant", "#c4c6cf"),
        ("outline_variant", "#43474e"),
        ("shadow", "#000000"),
        ("error", "#ffb4ab"),
    ]
    .into_iter()
    .map(|(k, v)| (k.to_string(), v.to_string()))
    .collect();

    if let Ok(scss) = fs::read_to_string(config_dir.join("eww/_colors.scss")) {
        parse_scss_vars(&scss, &mut colors);
    }
    if let Ok(css) = fs::read_to_string(config_dir.join("waybar/colors.css")) {
        parse_css_define_colors(&css, &mut colors);
    }

    let tokens = read_json_value(&config_dir.join("desktop-style/current/tokens.json"));
    if let Some(resolved) = tokens.as_ref().and_then(|t| t.get("colors")).and_then(|c| c.as_object()) {
        for (k, v) in resolved {
            if is_ident(k) {
                if let Some(s) = v.as_str() {
                    if is_hex_color(s) {
                        colors.insert(k.clone(), s.to_string());
                    }
                }
            }
        }
    }

    let mut text = String::from("// Generated from active desktop tokens, with Waybar/Matugen fallback.\n");
    for (k, v) in &colors {
        text.push_str(&format!("${}: {};\n", k, v));
    }

    let status = read_json_value(&state_root.join("desktop-power/status.json"));
    let level = status
        .as_ref()
        .and_then(|s| s.get("level"))
        .and_then(|v| v.as_str())
        .unwrap_or("normal");
    let appearance_cfg = parse_power_appearance(&config_dir.join("desktop-power/config.toml"));
    let default_role = match level {
        "high" => "primary",
        "warning" => "tertiary",
        "critical" => "error",
        _ => "on_surface",
    };
    let mut role = appearance_cfg.get(level).map(String::as_str).unwrap_or(default_role);
    if !colors.contains_key(role) {
        role = "on_surface";
    }
    if matches!(level, "high" | "warning" | "critical") {
        text.push_str(&format!("$island_background: rgba(mix(${}, $surface_container, 12%), .97);\n", role));
        text.push_str(&format!("$island_outline: rgba(${}, .6);\n", role));
    } else {
        text.push_str("$island_background: rgba($surface_container, .97);\n$island_outline: rgba($outline_variant, .45);\n");
    }

    if menu_cfg.is_dir() {
        write_if_changed(&menu_cfg.join("_palette.scss"), &text);
    }

    let style_content = fs::read_to_string(menu_cfg.join("_desktop-style.scss"))
        .unwrap_or_else(|_| "/* Original appearance */\n".into());
    for name in ["raccon-float", "raccon-music", "raccon-countdown"] {
        let target_dir = config_dir.join(name);
        if target_dir.is_dir() {
            write_if_changed(&target_dir.join("_palette.scss"), &text);
            write_if_changed(&target_dir.join("_desktop-style.scss"), &style_content);
        }
    }

    let tokens_obj = tokens.as_ref().filter(|v| v.is_object());
    let font = tokens_obj
        .and_then(|t| t.get("font"))
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .unwrap_or("Inter")
        .replace(['"', '\\', '\n'], "");
    let opacity_num = tokens_obj
        .and_then(|t| t.get("opacity"))
        .and_then(|v| v.as_f64())
        .filter(|v| (0.0..=100.0).contains(v))
        .unwrap_or(1.0)
        .min(1.0);
    let opacity = if (opacity_num.fract()).abs() < f64::EPSILON {
        format!("{}", opacity_num as i64)
    } else {
        format!("{}", opacity_num)
    };
    let tokens_scss = format!(
        "$radius: {}px;\n$control_radius: {}px;\n$border: {}px;\n$opacity: {};\n$font: \"{}\";\n$panel_padding: {}px;\n$control_padding: {}px;\n",
        token_number(tokens_obj, "radius", 20.0),
        token_number(tokens_obj, "control_radius", 12.0),
        token_number(tokens_obj, "border", 0.0),
        opacity,
        font,
        token_number(tokens_obj, "panel_padding", 16.0),
        token_number(tokens_obj, "control_padding", 8.0),
    );
    for name in ["raccon-float", "raccon-countdown"] {
        let target_dir = config_dir.join(name);
        if target_dir.is_dir() {
            write_if_changed(&target_dir.join("_tokens.scss"), &tokens_scss);
        }
    }
}

pub fn appearance_state(home: &Path, state_root: &Path) -> String {
    let tokens = read_json_value(&home.join(".config/desktop-style/current/tokens.json"));
    let tokens_obj = tokens.as_ref().filter(|v| v.is_object());
    let style = tokens_obj
        .and_then(|t| t.get("style"))
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty() && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-'))
        .unwrap_or("original");
    let strict = tokens_obj
        .and_then(|t| t.get("strict"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
        || matches!(style, "ascii" | "monochrome" | "terminal" | "retro");

    let status = read_json_value(&state_root.join("desktop-power/status.json"));
    let factor = status
        .as_ref()
        .and_then(|s| s.get("policy"))
        .and_then(|p| p.get("animation_factor"))
        .and_then(|v| v.as_f64())
        .unwrap_or(1.0)
        .clamp(0.6, 1.0);
    let duration = format!("{}ms", (240.0 * factor).round() as i64);

    serde_json::json!({
        "style": style,
        "ascii": style == "ascii",
        "strict": strict,
        "motion": factor > 0.0,
        "duration": duration,
    })
    .to_string()
}

fn watch_stamps(paths: &[PathBuf]) -> Vec<Option<(SystemTime, u64)>> {
    paths
        .iter()
        .map(|p| {
            fs::metadata(p)
                .ok()
                .and_then(|m| m.modified().ok().map(|t| (t, m.len())))
        })
        .collect()
}

pub fn run(args: Vec<String>) -> Result<(), String> {
    let runtime = paths::runtime_dir();
    let state = paths::state_dir();
    let home = paths::home_dir();
    let state_root = state.parent().unwrap_or(&state).to_path_buf();

    // Fast path: if args match transport request and FIFO is available, send immediately
    if let Some(cmd) = transport::parse_request(&args) {
        if transport::send(&cmd, &runtime) {
            return Ok(());
        }
    }

    if args.is_empty() {
        return runtime::show(None, false);
    }

    let command = &args[0];

    let result = match command.as_str() {
        "prepare" => runtime::prepare(),
        "listen" => {
            runtime::listen_desktop();
            Ok(())
        }
        "opened" => {
            runtime::opened();
            Ok(())
        }
        "diagnose" => {
            runtime::diagnose();
            Ok(())
        }
        "catalogue" => {
            crate::util::watch::emit_line(&apps::catalogue_value(&state, &apps::cached_applications()).to_string());
            Ok(())
        }
        "watch-catalogue" => {
            apps::watch_catalogue();
            Ok(())
        }
        "query" => runtime::filter_query(args.get(1).map(|s| s.as_str()).unwrap_or(""), false),
        "launch-first" => runtime::filter_query(args.get(1).map(|s| s.as_str()).unwrap_or(""), true),
        "launch" => {
            let tok = args.get(1).ok_or("Missing app token")?;
            apps::launch_app(tok)?;
            let _ = runtime::close(false);
            Ok(())
        }
        "search-action" => {
            if args.len() != 2 {
                return Err("Invalid search action.".into());
            }
            let (cmd, val) = apps::resolve_search_action(&args[1])?;
            if cmd == "shortcut" {
                runtime::shortcut(val)
            } else {
                runtime::show(Some(val), false)
            }
        }
        "apply" => runtime::apply_mode(),
        "modes-data" => {
            crate::util::watch::emit_line(&modes::modes_json());
            Ok(())
        }
        "shortcuts-data" => {
            crate::util::watch::emit_line(&shortcuts::shortcuts_json(&home));
            Ok(())
        }
        "palette" => {
            sync_palette(&home, &state_root);
            Ok(())
        }
        "card-wait" => {
            let target = args.get(1).map(|s| s.as_str()).unwrap_or("ready");
            let timeout = args.get(2).and_then(|s| s.parse::<u64>().ok()).unwrap_or(3);
            float::card_wait(target, timeout)
        }
        "keyboard-build" => {
            let out = float::keyboard_build()?;
            println!("{}", out.display());
            Ok(())
        }
        "listen-appearance" => {
            let watched = vec![
                home.join(".config/desktop-style/current/tokens.json"),
                state_root.join("desktop-power/status.json"),
                home.join(".config/waybar/colors.css"),
                home.join(".config/eww/_colors.scss"),
                home.join(".config/raccon-menu/_desktop-style.scss"),
            ];
            let mut last_stamps: Option<Vec<Option<(SystemTime, u64)>>> = None;
            let mut prev_state: Option<String> = None;
            loop {
                let stamps = watch_stamps(&watched);
                if last_stamps.as_ref() != Some(&stamps) {
                    sync_palette(&home, &state_root);
                    let line = appearance_state(&home, &state_root);
                    if prev_state.as_ref() != Some(&line) {
                        if !crate::util::watch::emit_line(&line) {
                            return Ok(());
                        }
                        prev_state = Some(line);
                    }
                    last_stamps = Some(stamps);
                }
                std::thread::sleep(Duration::from_millis(150));
            }
        }
        "favorite" => {
            home_apps::edit(&state, &args[1..])?;
            let _ = transport::send("update-catalogue", &runtime);
            runtime::update_catalogue_now();
            Ok(())
        }
        "recent" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("clear");
            let key = args.get(2).map(|s| s.as_str());
            recent_apps::edit(&state, action, key)?;
            let _ = transport::send("update-catalogue", &runtime);
            runtime::update_catalogue_now();
            Ok(())
        }
        "calendar" => {
            let res = calendar::execute(&runtime, &args[1..]);
            if res.is_ok() && args.get(1).map(|s| s.as_str()) != Some("watch") {
                let _ = transport::send("update-calendar", &runtime);
            }
            res
        }
        "calendar-watch" => {
            calendar::watch(&runtime);
            Ok(())
        }
        "panel" | "control-action" => panels::execute(&args[1..]),
        "panel-watch" => {
            let kind = args.get(1).ok_or("Missing panel kind")?;
            panels::listen(kind)
        }
        "music-watch" => {
            music::watch_music();
            Ok(())
        }
        "music-viz" => {
            music::watch_viz();
            Ok(())
        }
        "waybar-music" => {
            let mode = args.get(1).map(|s| s.as_str()).unwrap_or("");
            waybar_music::listen(mode)
        }
        "waybar-music-serve" => waybar_music::serve(),
        "walls" => walls::execute(&args[1..]),
        "wall-preview-watch" => {
            walls::watch_preview();
            Ok(())
        }
        "session-action" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("cancel");
            if runtime::eww_cmd(&["ping"]).is_ok() {
                runtime::session_action_checked(action)
            } else {
                session::execute(action)
            }
        }
        "shortcut" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("");
            runtime::shortcut(action)
        }
        "select" => {
            let mode = args.get(1).ok_or("Missing mode")?;
            if !modes::MODES.iter().any(|m| m.id == mode) {
                return Err("Invalid mode.".into());
            }
            runtime::eww_cmd(&["update", &format!("selected={mode}"), "error="]).map(|_| ())
        }
        "confirm" => {
            let act = args.get(1).map(|s| s.as_str()).unwrap_or("cancel");
            if !matches!(act, "suspend" | "reboot" | "poweroff" | "logout" | "cancel") {
                return Err("Invalid action.".into());
            }
            let val = if act == "cancel" { "" } else { act };
            runtime::eww_cmd(&["update", &format!("confirmation={val}")]).map(|_| ())
        }
        "tab" => {
            let page = args.get(1).ok_or("Invalid section.")?;
            let idx = transport::page_index(page).ok_or("Invalid section.")?;
            if !transport::send(&format!("tab {}", idx), &runtime) {
                runtime::eww_cmd(&["update", &format!("page={idx}"), "confirmation=", "error="]).map(|_| ())
            } else {
                Ok(())
            }
        }
        "close" => {
            let super_key = args.get(1).map(|s| s.as_str()) == Some("super");
            runtime::close(super_key)
        }
        "toggle" => runtime::show(None, false),
        _ => {
            if let Some(idx) = transport::page_index(command) {
                if transport::send(&format!("show {}", idx), &runtime) {
                    return Ok(());
                }
                return runtime::show(Some(command), false);
            }
            Err(format!("Unknown menu command: {}", command))
        }
    };
    if let Err(ref msg) = result {
        runtime::eww_error(msg);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    struct TempRoot(PathBuf);
    impl Drop for TempRoot {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn test_sync_palette_and_appearance_state_track_token_and_power_updates() {
        let nanos = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = TempRoot(std::env::temp_dir().join(format!("raccon-cli-{}-{}", std::process::id(), nanos)));
        let home = dir.0.as_path();
        let state_root = home.join(".local/state");
        for sub in [
            ".config/raccon-menu",
            ".config/raccon-float",
            ".config/raccon-music",
            ".config/desktop-style/current",
            ".config/waybar",
            ".local/state/desktop-power",
        ] {
            fs::create_dir_all(home.join(sub)).unwrap();
        }
        fs::write(home.join(".config/waybar/colors.css"), "@define-color primary #ee1133;\n").unwrap();
        fs::write(home.join(".config/raccon-menu/_desktop-style.scss"), "/* modern */\n").unwrap();
        fs::write(
            home.join(".config/desktop-style/current/tokens.json"),
            r##"{"style":"collage","font":"Inter Display","radius":0,"control_radius":0,"border":3,"opacity":1,"panel_padding":16,"control_padding":6,"colors":{"primary":"#ff5577","surface_container":"#221118","outline_variant":"#664455"}}"##,
        )
        .unwrap();
        fs::write(
            state_root.join("desktop-power/status.json"),
            r#"{"level":"warning","policy":{"animation_factor":0.5}}"#,
        )
        .unwrap();

        sync_palette(home, &state_root);
        let menu_palette = fs::read_to_string(home.join(".config/raccon-menu/_palette.scss")).unwrap();
        assert!(menu_palette.contains("$primary: #ff5577;"));
        assert!(menu_palette.contains("$island_outline: rgba($tertiary, .6);"));
        assert_eq!(
            fs::read_to_string(home.join(".config/raccon-float/_palette.scss")).unwrap(),
            menu_palette
        );
        let float_tokens = fs::read_to_string(home.join(".config/raccon-float/_tokens.scss")).unwrap();
        assert!(float_tokens.contains("$radius: 0px;"));
        assert!(float_tokens.contains("$font: \"Inter Display\";"));

        let state: serde_json::Value = serde_json::from_str(&appearance_state(home, &state_root)).unwrap();
        assert_eq!(state["style"], "collage");
        assert_eq!(state["ascii"], false);
        assert_eq!(state["strict"], false);
        assert_eq!(state["motion"], true);
        assert_eq!(state["duration"], "144ms");

        fs::write(
            home.join(".config/desktop-style/current/tokens.json"),
            r##"{"style":"ascii","colors":{"primary":"#ff9b91"}}"##,
        )
        .unwrap();
        sync_palette(home, &state_root);
        let updated_palette = fs::read_to_string(home.join(".config/raccon-music/_palette.scss")).unwrap();
        assert!(updated_palette.contains("$primary: #ff9b91;"));
        let state2: serde_json::Value = serde_json::from_str(&appearance_state(home, &state_root)).unwrap();
        assert_eq!(state2["style"], "ascii");
        assert_eq!(state2["ascii"], true);
        assert_eq!(state2["strict"], true);
    }
}
