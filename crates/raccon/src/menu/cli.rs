use std::process::Command;

use crate::menu::{calendar, float, home_apps, modes, recent_apps, session, shortcuts, transport};
use crate::util::paths;

pub fn run(args: Vec<String>) -> Result<(), String> {
    let runtime = paths::runtime_dir();
    let state = paths::state_dir();
    let home = paths::home_dir();

    // Fast path: if args match transport request and FIFO is available, send immediately
    if let Some(cmd) = transport::parse_request(&args) {
        if transport::send(&cmd, &runtime) {
            return Ok(());
        }
    }

    if args.is_empty() {
        if transport::send("toggle", &runtime) {
            return Ok(());
        }
        // Fallback: spawn eww or show
        return Err("Menu not mapped; unable to toggle".into());
    }

    let command = &args[0];

    match command.as_str() {
        "modes-data" => {
            println!("{}", modes::modes_json());
            Ok(())
        }
        "shortcuts-data" => {
            println!("{}", shortcuts::shortcuts_json(&home));
            Ok(())
        }
        "palette" => {
            let config_dir = home.join(".config");
            let menu_cfg = config_dir.join("raccon-menu");
            let palette_src = menu_cfg.join("_palette.scss");
            let style_src = menu_cfg.join("_desktop-style.scss");

            let palette_content = std::fs::read_to_string(&palette_src).unwrap_or_default();
            let style_content = std::fs::read_to_string(&style_src).unwrap_or_else(|_| "/* Original appearance */\n".into());

            for name in ["raccon-float", "raccon-music", "raccon-countdown"] {
                let target_dir = config_dir.join(name);
                if target_dir.is_dir() {
                    let _ = std::fs::write(target_dir.join("_palette.scss"), &palette_content);
                    let _ = std::fs::write(target_dir.join("_desktop-style.scss"), &style_content);
                }
            }
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
            let tokens_file = home.join(".config").join("desktop-style").join("current").join("tokens.json");
            let style = if let Ok(content) = std::fs::read_to_string(&tokens_file) {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                    val.get("style").and_then(|s| s.as_str()).unwrap_or("original").to_string()
                } else {
                    "original".to_string()
                }
            } else {
                "original".to_string()
            };
            println!(r#"{{"style":"{}","motion":true,"duration":"240ms"}}"#, style);
            loop {
                std::thread::sleep(std::time::Duration::from_secs(5));
            }
        }
        "favorite" => {
            home_apps::edit(&state, &args[1..])?;
            let _ = transport::send("update-catalogue", &runtime);
            Ok(())
        }
        "recent" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("clear");
            let key = args.get(2).map(|s| s.as_str());
            recent_apps::edit(&state, action, key)?;
            let _ = transport::send("update-catalogue", &runtime);
            Ok(())
        }
        "calendar" => {
            calendar::execute(&runtime, &args[1..])?;
            let _ = transport::send("update-calendar", &runtime);
            Ok(())
        }
        "session-action" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("cancel");
            session::execute(action)
        }
        "shortcut" => {
            let action = args.get(1).map(|s| s.as_str()).unwrap_or("");
            match action {
                "lock" => {
                    let _ = Command::new("gtklock").spawn()
                        .or_else(|_| Command::new("swaylock").spawn());
                }
                "notifications" => {
                    let _ = Command::new("swaync-client").arg("-t").spawn();
                }
                _ => {}
            }
            Ok(())
        }
        "select" => {
            if let Some(mode) = args.get(1) {
                let _ = transport::send(&format!("select {}", mode), &runtime);
            }
            Ok(())
        }
        "confirm" => {
            if let Some(action) = args.get(1) {
                let _ = transport::send(&format!("confirm {}", action), &runtime);
            }
            Ok(())
        }
        "tab" => {
            if let Some(page) = args.get(1) {
                if let Some(idx) = transport::page_index(page) {
                    let _ = transport::send(&format!("tab {}", idx), &runtime);
                }
            }
            Ok(())
        }
        "close" => {
            let super_key = args.get(1).map(|s| s.as_str()) == Some("super");
            let cmd = if super_key { "hide-super" } else { "hide" };
            let _ = transport::send(cmd, &runtime);
            Ok(())
        }
        _ => {
            // Check if argument is a page name
            if let Some(idx) = transport::page_index(command) {
                let _ = transport::send(&format!("show {}", idx), &runtime);
                return Ok(());
            }
            Err(format!("Unknown command: {}", command))
        }
    }
}
