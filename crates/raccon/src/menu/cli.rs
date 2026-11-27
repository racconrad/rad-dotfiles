use std::fs;
use std::path::Path;

use crate::menu::qs::{qs_ensure, qs_ipc};
use crate::menu::{
    apps, calendar, home_apps, modes, music, panels, recent_apps, runtime, shortcuts, transport,
    walls,
};
use crate::util::paths;

fn read_json_value(path: &Path) -> Option<serde_json::Value> {
    fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
}

pub fn appearance_state(home: &Path, state_root: &Path) -> String {
    let tokens = read_json_value(&home.join(".config/desktop-style/current/tokens.json"));
    let tokens_obj = tokens.as_ref().filter(|v| v.is_object());
    let style = tokens_obj
        .and_then(|t| t.get("style"))
        .and_then(|v| v.as_str())
        .filter(|s| {
            !s.is_empty()
                && s.bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
        })
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

pub fn run(args: Vec<String>) -> Result<(), String> {
    let runtime = paths::runtime_dir();
    let state = paths::state_dir();
    let home = paths::home_dir();

    if args.is_empty() {
        return runtime::widget("toggle", "menu");
    }

    let command = &args[0];
    match command.as_str() {
        "prepare" => qs_ensure(),
        "ipc" => {
            let function = args.get(1).ok_or("Missing IPC function.")?;
            if matches!(function.as_str(), "open" | "toggle" | "openMenu") {
                qs_ensure()?;
            }
            let params: Vec<_> = args[2..].iter().map(String::as_str).collect();
            let output = qs_ipc(function, &params)?;
            if !output.is_empty() {
                println!("{output}");
            }
            Ok(())
        }
        "listen" => {
            runtime::listen_desktop();
            Ok(())
        }
        "diagnose" => {
            runtime::diagnose();
            Ok(())
        }
        "catalogue" => {
            crate::util::watch::emit_line(
                &apps::catalogue_value(&state, &apps::cached_applications()).to_string(),
            );
            Ok(())
        }
        "watch-catalogue" => {
            apps::watch_catalogue();
            Ok(())
        }
        "query" => runtime::filter_query(args.get(1).map(|s| s.as_str()).unwrap_or(""), false),
        "launch-first" => {
            runtime::filter_query(args.get(1).map(|s| s.as_str()).unwrap_or(""), true)
        }
        "launch" => {
            let tok = args.get(1).ok_or("Missing app token")?;
            apps::launch_app(tok)?;
            let _ = runtime::close_menu();
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
                runtime::open_menu(Some(val))
            }
        }
        "apply" => runtime::apply_mode(args.get(1).ok_or("Missing mode.")?),
        "modes-data" => {
            crate::util::watch::emit_line(&modes::modes_json());
            Ok(())
        }
        "shortcuts-data" => {
            crate::util::watch::emit_line(&shortcuts::shortcuts_json(&home));
            Ok(())
        }
        "favorite" => {
            home_apps::edit(&state, &args[1..])?;
            Ok(())
        }
        "recent" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("clear");
            let key = args.get(2).map(|s| s.as_str());
            recent_apps::edit(&state, action, key)?;
            Ok(())
        }
        "calendar" => calendar::execute(&runtime, &args[1..]),
        "calendar-watch" => {
            calendar::watch(&runtime);
            Ok(())
        }
        "panel" | "control-action" => panels::execute(&args[1..]),
        "panel-watch" => {
            let kind = args.get(1).ok_or("Missing panel kind")?;
            panels::listen(kind)
        }
        "music-viz" => {
            music::watch_viz();
            Ok(())
        }
        "walls" => walls::execute(&args[1..]),
        "session-action" => {
            let action = args.get(1).map(String::as_str).unwrap_or("cancel");
            runtime::session_action(action)
        }
        "shortcut" => {
            let action = args.get(1).map(String::as_str).unwrap_or("");
            runtime::shortcut(action)
        }
        "open" => runtime::open_menu(args.get(1).map(String::as_str)),
        "tab" => runtime::open_menu(Some(args.get(1).ok_or("Invalid section.")?)),
        "close" => runtime::close_menu(),
        "toggle" => runtime::widget("toggle", "menu"),
        _ if transport::page_index(command).is_some() => runtime::open_menu(Some(command)),
        _ => Err(format!("Unknown menu command: {command}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::time::SystemTime;

    struct TempRoot(PathBuf);
    impl Drop for TempRoot {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn appearance_state_tracks_style_and_power() {
        let nanos = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = TempRoot(
            std::env::temp_dir().join(format!("raccon-cli-{}-{nanos}", std::process::id())),
        );
        let home = dir.0.as_path();
        let state_root = home.join(".local/state");
        let style_dir = home.join(".config/desktop-style/current");
        let power_dir = state_root.join("desktop-power");
        fs::create_dir_all(&style_dir).unwrap();
        fs::create_dir_all(&power_dir).unwrap();
        fs::write(style_dir.join("tokens.json"), r#"{"style":"collage"}"#).unwrap();
        fs::write(
            power_dir.join("status.json"),
            r#"{"policy":{"animation_factor":0.5}}"#,
        )
        .unwrap();

        let state: serde_json::Value =
            serde_json::from_str(&appearance_state(home, &state_root)).unwrap();
        assert_eq!(state["style"], "collage");
        assert_eq!(state["ascii"], false);
        assert_eq!(state["motion"], true);
        assert_eq!(state["duration"], "144ms");

        fs::write(style_dir.join("tokens.json"), r#"{"style":"ascii"}"#).unwrap();
        let state: serde_json::Value =
            serde_json::from_str(&appearance_state(home, &state_root)).unwrap();
        assert_eq!(state["style"], "ascii");
        assert_eq!(state["strict"], true);
    }
}
