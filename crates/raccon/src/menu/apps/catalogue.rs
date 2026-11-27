use std::collections::BTreeMap;
use std::path::Path;

use crate::menu::apps::entry::{cached_applications, normalize, AppEntry};
use crate::menu::{home_apps, recent_apps};
use crate::util::hash::sha256_hex;

pub const SEARCH_TARGETS: &[(&str, &str, &str, &str, &str, &str, &str)] = &[
    ("audio", "Audio settings", "audio-volume-high-symbolic", "Setting", "tab", "audio", "sound volume microphone sonido volumen microfono"),
    ("connections", "Network settings", "network-wireless-symbolic", "Setting", "tab", "connections", "wifi internet redes conexiones"),
    ("bluetooth", "Bluetooth settings", "bluetooth-symbolic", "Setting", "tab", "bluetooth", "devices dispositivos"),
    ("calendar", "Calendar", "x-office-calendar-symbolic", "Setting", "tab", "calendar", "date calendario fecha"),
    ("modes", "Power modes", "preferences-system-symbolic", "Setting", "tab", "modes", "battery performance energia bateria rendimiento"),
    ("shortcuts", "Keyboard shortcuts", "input-keyboard-symbolic", "Setting", "tab", "shortcuts", "keys hotkeys teclado atajos"),
    ("wallpaper", "Wallpapers", "preferences-desktop-wallpaper-symbolic", "Action", "shortcut", "wallpaper", "wallpaper background fondos pantalla imagen"),
    ("notifications", "Notifications", "preferences-system-notifications-symbolic", "Action", "shortcut", "notifications", "notificaciones avisos"),
    ("lock", "Lock screen", "system-lock-screen-symbolic", "Action", "shortcut", "lock", "bloquear pantalla"),
];

pub fn shortcut_meta(key: &str) -> Option<(&'static str, &'static str, &'static str, &'static str)> {
    match key {
        "shortcut:browser" => Some(("Browser", "web-browser", "shortcut", "browser")),
        "shortcut:files" => Some(("Files", "system-file-manager", "shortcut", "files")),
        "shortcut:terminal" => Some(("Terminal", "utilities-terminal", "shortcut", "terminal")),
        _ => None,
    }
}

pub fn catalogue_value(state: &Path, catalog: &[AppEntry]) -> serde_json::Value {
    let keys = home_apps::load_items(state);
    let by_id: BTreeMap<&str, &AppEntry> = catalog.iter().map(|a| (a.id.as_str(), a)).collect();

    let mut fav_items = Vec::new();
    for (pos, key) in keys.iter().enumerate() {
        let mut item = if let Some((name, icon, action, val)) = shortcut_meta(key) {
            serde_json::json!({
                "name": name, "icon": icon, "action": action, "value": val,
                "has_file": false, "file": "", "available": true
            })
        } else if let Some(app) = by_id.get(key.as_str()) {
            serde_json::json!({
                "name": app.name, "icon": app.icon, "action": "launch", "value": app.token,
                "has_file": app.has_file, "file": app.file, "available": true
            })
        } else {
            serde_json::json!({
                "name": key.trim_end_matches(".desktop"),
                "icon": "application-x-executable",
                "action": "launch",
                "value": sha256_hex(key),
                "has_file": false,
                "file": "",
                "available": false
            })
        };
        let reference = if shortcut_meta(key).is_some() { key.clone() } else { sha256_hex(key) };
        if let Some(obj) = item.as_object_mut() {
            obj.insert("key".into(), serde_json::json!(key));
            obj.insert("ref".into(), serde_json::json!(reference));
            obj.insert("position".into(), serde_json::json!(pos));
            obj.insert("can_move_previous".into(), serde_json::json!(pos > 0));
            obj.insert("can_move_next".into(), serde_json::json!(pos + 1 < keys.len()));
        }
        fav_items.push(item);
    }

    let favorites: Vec<Vec<serde_json::Value>> = fav_items.chunks(3).map(|c| c.to_vec()).collect();
    let apps_json: Vec<serde_json::Value> = catalog
        .iter()
        .map(|app| {
            serde_json::json!({
                "id": app.id, "token": app.token, "name": app.name, "icon": app.icon,
                "file": app.file, "has_file": app.has_file, "search": app.search,
                "key": app.id, "ref": sha256_hex(&app.id),
                "pinned": keys.iter().any(|k| k == &app.id),
            })
        })
        .collect();

    let shortcuts: Vec<serde_json::Value> = home_apps::DEFAULT_SHORTCUTS
        .iter()
        .filter_map(|&k| {
            let (name, icon, action, val) = shortcut_meta(k)?;
            Some(serde_json::json!({
                "name": name, "icon": icon, "action": action, "value": val,
                "has_file": false, "file": "", "available": true,
                "key": k, "ref": k, "pinned": keys.iter().any(|item| item == k)
            }))
        })
        .collect();

    let mut search_rows: Vec<serde_json::Value> = apps_json
        .iter()
        .map(|app| {
            let mut row = app.clone();
            if let Some(obj) = row.as_object_mut() {
                obj.insert("category".into(), serde_json::json!("Application"));
                obj.insert("action".into(), serde_json::json!("launch"));
                obj.insert("value".into(), app["token"].clone());
                obj.insert("pinnable".into(), serde_json::json!(true));
            }
            row
        })
        .collect();
    for (key, name, icon, category, _cmd, _val, aliases) in SEARCH_TARGETS {
        search_rows.push(serde_json::json!({
            "name": name, "icon": icon, "category": category,
            "action": "search-action", "value": key,
            "search": format!("{name} {category} {aliases}").to_lowercase(),
            "has_file": false, "file": "", "pinned": false, "pinnable": false, "ref": key
        }));
    }

    let recent_data = recent_apps::load(state);
    let recent_items: Vec<serde_json::Value> = if recent_data.enabled {
        recent_data
            .items
            .iter()
            .filter_map(|k| {
                if let Some((name, icon, action, val)) = shortcut_meta(k) {
                    Some(serde_json::json!({"id": k, "name": name, "icon": icon, "action": action, "value": val, "has_file": false, "file": ""}))
                } else {
                    by_id.get(k.as_str()).map(|app| {
                        serde_json::json!({
                            "id": app.id, "token": app.token, "name": app.name, "icon": app.icon,
                            "file": app.file, "has_file": app.has_file, "search": app.search,
                            "action": "launch", "value": app.token
                        })
                    })
                }
            })
            .collect()
    } else {
        Vec::new()
    };

    serde_json::json!({
        "home_count": keys.len(),
        "home_limit": home_apps::LIMIT,
        "apps": apps_json,
        "favorites": favorites,
        "shortcuts": shortcuts,
        "search": search_rows,
        "recent_enabled": recent_data.enabled,
        "recent": recent_items,
    })
}

pub fn filter_search(state: &Path, query: &str) -> Vec<serde_json::Value> {
    let words: Vec<String> = normalize(query)
        .split_whitespace()
        .map(|s| s.to_string())
        .collect();
    let cat = catalogue_value(state, &cached_applications());
    let Some(rows) = cat.get("search").and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    rows.iter()
        .filter(|row| {
            let s = row.get("search").and_then(|v| v.as_str()).unwrap_or("");
            words.iter().all(|w| s.contains(w))
        })
        .cloned()
        .collect()
}

pub fn resolve_search_action(key: &str) -> Result<(&'static str, &'static str), String> {
    SEARCH_TARGETS
        .iter()
        .find(|(k, ..)| *k == key)
        .map(|(_, _, _, _, cmd, val, _)| (*cmd, *val))
        .ok_or_else(|| "Invalid search action.".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_search_targets() {
        assert_eq!(resolve_search_action("wallpaper").unwrap(), ("shortcut", "wallpaper"));
        assert_eq!(resolve_search_action("audio").unwrap(), ("tab", "audio"));
        assert!(resolve_search_action("invalid").is_err());
    }
}
