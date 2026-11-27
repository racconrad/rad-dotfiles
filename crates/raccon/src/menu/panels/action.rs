use std::fs;

use crate::menu::panels::{audio, bluetooth, listen, present, wifi};
use crate::menu::runtime;
use crate::util::paths::runtime_dir;

pub fn execute(args: &[String]) -> Result<(), String> {
    let runtime = runtime_dir();
    let _ = fs::create_dir_all(&runtime);
    let op = args.first().map(String::as_str).unwrap_or("audio");
    if present::service_page(op).is_some() {
        return runtime::open_menu(Some(op));
    }
    if op == "tab" {
        let page = args.get(1).filter(|p| present::service_page(p).is_some()).ok_or("Invalid section.")?;
        return runtime::open_menu(Some(page));
    }
    if op == "close" {
        return runtime::close_menu();
    }
    if op == "preload" {
        listen::preload();
        return Ok(());
    }
    if op == "listen" {
        let kind = args.get(1).ok_or("Missing panel kind")?;
        return listen::listen(kind);
    }
    if op == "retry" {
        let kind = args.get(1).ok_or("Missing panel kind")?;
        if !matches!(kind.as_str(), "audio" | "connections" | "bluetooth") {
            return Err("Invalid panel.".into());
        }
        listen::refresh_kind(kind);
        listen::wake(&runtime, kind);
        return Ok(());
    }

    match op {
        "wifi-page" => wifi::handle_wifi_page(args, &runtime),
        "bt-page" => bluetooth::handle_bt_page(args, &runtime),
        "bt-select" => bluetooth::handle_bt_select(args, &runtime),
        "bt-back" => bluetooth::handle_bt_back(&runtime),
        "wifi-connect" => wifi::handle_wifi_connect(args, &runtime),
        "wifi-disconnect" => wifi::handle_wifi_disconnect(args, &runtime),
        "wifi-power" => wifi::handle_wifi_power(args, &runtime),
        "wifi-scan" => wifi::handle_wifi_scan(&runtime),
        "audio-device" | "audio-mute" => audio::handle_audio_action(op, args, &runtime),
        "bt-power" => bluetooth::handle_bt_power(args, &runtime),
        "bt-scan" => bluetooth::handle_bt_scan(&runtime),
        "bt-device" => bluetooth::handle_bt_device(args, &runtime),
        "advanced" => audio::handle_advanced_action(args),
        _ => Err("Invalid action.".into()),
    }
}
