use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, SystemTime};

use crate::menu::{home_apps, recent_apps};
use crate::util::atomic::write_atomic;
use crate::util::hash::sha256_hex;
use crate::util::paths::{config_dir, home_dir, state_dir};
use crate::util::watch::{emit_line, DirWatch};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppEntry {
    pub id: String,
    pub token: String,
    pub name: String,
    pub icon: String,
    pub file: String,
    pub has_file: bool,
    pub search: String,
    #[serde(default)]
    pub desktop_path: String,
}

pub const SEARCH_TARGETS: &[(&str, &str, &str, &str, &str, &str, &str)] = &[
    ("audio", "Audio settings", "audio-volume-high-symbolic", "Setting", "tab", "audio", "sound volume microphone sonido volumen microfono"),
    ("connections", "Network settings", "network-wireless-symbolic", "Setting", "tab", "connections", "wifi internet redes conexiones"),
    ("bluetooth", "Bluetooth settings", "bluetooth-symbolic", "Setting", "tab", "bluetooth", "devices dispositivos"),
    ("calendar", "Calendar", "x-office-calendar-symbolic", "Setting", "tab", "calendar", "date calendario fecha"),
    ("modes", "Power modes", "preferences-system-symbolic", "Setting", "tab", "modes", "battery performance energia bateria rendimiento"),
    ("shortcuts", "Keyboard shortcuts", "input-keyboard-symbolic", "Setting", "tab", "shortcuts", "keys hotkeys teclado atajos"),
    ("layout", "Desktop layout", "preferences-system-windows-symbolic", "Setting", "tab", "layout", "canvas tiling layout modo escritorio"),
    ("wallpaper", "Wallpapers", "preferences-desktop-wallpaper-symbolic", "Action", "shortcut", "wallpaper", "wallpaper background fondos pantalla imagen"),
    ("notifications", "Notifications", "preferences-system-notifications-symbolic", "Action", "shortcut", "notifications", "notificaciones avisos"),
    ("lock", "Lock screen", "system-lock-screen-symbolic", "Action", "shortcut", "lock", "bloquear pantalla"),
];

pub fn normalize(text: &str) -> String {
    text.to_lowercase()
        .chars()
        .map(|c| match c {
            'á' | 'à' | 'ä' | 'â' => 'a',
            'é' | 'è' | 'ë' | 'ê' => 'e',
            'í' | 'ì' | 'ï' | 'î' => 'i',
            'ó' | 'ò' | 'ö' | 'ô' => 'o',
            'ú' | 'ù' | 'ü' | 'û' => 'u',
            'ñ' => 'n',
            other => other,
        })
        .collect()
}

pub fn app_dirs() -> Vec<PathBuf> {
    let home = home_dir();
    let mut dirs = Vec::new();
    let data_home = std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".local/share"));
    dirs.push(data_home.join("applications"));
    dirs.push(home.join(".local/share/flatpak/exports/share/applications"));
    if let Ok(xdg_dirs) = std::env::var("XDG_DATA_DIRS") {
        for base in xdg_dirs.split(':').filter(|s| !s.is_empty()) {
            dirs.push(PathBuf::from(base).join("applications"));
        }
    } else {
        dirs.push(PathBuf::from("/usr/local/share/applications"));
        dirs.push(PathBuf::from("/usr/share/applications"));
        dirs.push(PathBuf::from("/var/lib/flatpak/exports/share/applications"));
    }
    let mut seen = BTreeSet::new();
    dirs.into_iter().filter(|d| seen.insert(d.clone())).collect()
}

fn parse_desktop_file(path: &Path, id: &str, empty_svg: &str) -> Option<AppEntry> {
    let text = fs::read_to_string(path).ok()?;
    let mut in_entry = false;
    let mut app_type = String::new();
    let mut name = String::new();
    let mut name_en = String::new();
    let mut generic = String::new();
    let mut comment = String::new();
    let mut icon = String::new();
    let mut exec = String::new();
    let mut no_display = false;
    let mut hidden = false;

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            in_entry = line == "[Desktop Entry]";
            continue;
        }
        if !in_entry {
            continue;
        }
        let Some((k, v)) = line.split_once('=') else {
            continue;
        };
        let key = k.trim();
        let val = v.trim();
        match key {
            "Type" => app_type = val.to_string(),
            "NoDisplay" => no_display = val.eq_ignore_ascii_case("true"),
            "Hidden" => hidden = val.eq_ignore_ascii_case("true"),
            "Name" => name = val.to_string(),
            "Name[en]" | "Name[en_US]" => {
                if name_en.is_empty() {
                    name_en = val.to_string();
                }
            }
            "GenericName" => generic = val.to_string(),
            "Comment" => comment = val.to_string(),
            "Icon" => icon = val.to_string(),
            "Exec" => exec = val.to_string(),
            _ => {}
        }
    }

    if app_type != "Application" || no_display || hidden {
        return None;
    }
    let display = if !name_en.is_empty() { name_en } else { name };
    if display.is_empty() || exec.is_empty() {
        return None;
    }
    let has_file = !icon.is_empty() && Path::new(&icon).is_file();
    let file = if has_file { icon.clone() } else { empty_svg.to_string() };
    let theme_icon = if icon.is_empty() {
        "application-x-executable".to_string()
    } else {
        icon
    };
    let search = normalize(&format!("{display} {generic} {comment}"));
    Some(AppEntry {
        id: id.to_string(),
        token: sha256_hex(id),
        name: display,
        icon: theme_icon,
        file,
        has_file,
        search,
        desktop_path: path.to_string_lossy().into_owned(),
    })
}

fn collect_desktop_files(base: &Path, current: &Path, out: &mut BTreeMap<String, PathBuf>) {
    let Ok(entries) = fs::read_dir(current) else {
        return;
    };
    for entry in entries.flatten() {
        let p = entry.path();
        if p.is_dir() {
            collect_desktop_files(base, &p, out);
        } else if p.extension().and_then(|s| s.to_str()) == Some("desktop") {
            if let Ok(rel) = p.strip_prefix(base) {
                let id = rel.to_string_lossy().replace('/', "-");
                out.entry(id).or_insert(p);
            }
        }
    }
}

pub fn scan_applications() -> Vec<AppEntry> {
    let empty_svg = config_dir().join("assets/empty.svg").to_string_lossy().into_owned();
    let mut files = BTreeMap::new();
    for dir in app_dirs() {
        if dir.is_dir() {
            collect_desktop_files(&dir, &dir, &mut files);
        }
    }
    let mut apps: Vec<AppEntry> = files
        .into_iter()
        .filter_map(|(id, path)| parse_desktop_file(&path, &id, &empty_svg))
        .collect();
    apps.sort_by(|a, b| normalize(&a.name).cmp(&normalize(&b.name)));
    if let Ok(bytes) = serde_json::to_vec(&apps) {
        let _ = write_atomic(&state_dir().join("apps.json"), &bytes);
    }
    apps
}

pub fn cached_applications() -> Vec<AppEntry> {
    let path = state_dir().join("apps.json");
    let empty_svg = config_dir().join("assets/empty.svg").to_string_lossy().into_owned();
    if let Ok(meta) = fs::metadata(&path) {
        if let Ok(modified) = meta.modified() {
            if SystemTime::now().duration_since(modified).unwrap_or(Duration::from_secs(999)) < Duration::from_secs(300) {
                if let Ok(text) = fs::read_to_string(&path) {
                    if let Ok(mut apps) = serde_json::from_str::<Vec<AppEntry>>(&text) {
                        for app in &mut apps {
                            if !app.has_file || !Path::new(&app.file).is_file() {
                                app.has_file = false;
                                app.file = empty_svg.clone();
                            }
                        }
                        return apps;
                    }
                }
            }
        }
    }
    scan_applications()
}

fn shortcut_meta(key: &str) -> Option<(&'static str, &'static str, &'static str, &'static str)> {
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

pub fn watch_catalogue() {
    let state = state_dir();
    let _ = fs::create_dir_all(&state);
    let pref_files = [
        state.join("home-apps.json"),
        state.join("favorites.json"),
        state.join("recent-apps.json"),
    ];
    let existing_app_dirs: Vec<PathBuf> = app_dirs().into_iter().filter(|d| d.is_dir()).collect();
    let apps_watcher = DirWatch::new(&[], &existing_app_dirs);
    let state_watcher = DirWatch::new(&pref_files, &[]);

    let mut previous = String::new();
    let emit = |cat: &[AppEntry], prev: &mut String| -> bool {
        let val = catalogue_value(&state, cat).to_string();
        if &val != prev {
            if !emit_line(&val) {
                return false;
            }
            *prev = val;
        }
        true
    };
    let mut current = cached_applications();
    if !emit(&current, &mut previous) { return; }
    current = scan_applications();
    if !emit(&current, &mut previous) { return; }
    // Drain any inotify event caused by our own apps.json atomic write above.
    state_watcher.drain();

    let pref_stamps = || -> Vec<Option<SystemTime>> {
        pref_files.iter().map(|p| fs::metadata(p).and_then(|m| m.modified()).ok()).collect()
    };
    let mut last_prefs = pref_stamps();

    loop {
        let mut pfds = [
            libc::pollfd { fd: apps_watcher.raw_fd(), events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: state_watcher.raw_fd(), events: libc::POLLIN, revents: 0 },
        ];
        unsafe { libc::poll(pfds.as_mut_ptr(), 2, -1); }
        if pfds[0].revents & libc::POLLIN != 0 && apps_watcher.drain() {
            current = scan_applications();
            state_watcher.drain();
            if !emit(&current, &mut previous) { break; }
        }
        if pfds[1].revents & libc::POLLIN != 0 && state_watcher.drain() {
            let now_prefs = pref_stamps();
            if now_prefs != last_prefs {
                last_prefs = now_prefs;
                if !emit(&current, &mut previous) { break; }
            }
        }
    }
}

pub fn launch_app(token_str: &str) -> Result<String, String> {
    if token_str.len() != 64 || !token_str.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("Invalid application.".into());
    }
    let catalog = cached_applications();
    let app = catalog
        .into_iter()
        .find(|a| a.token == token_str)
        .ok_or("App is no longer available. Reopen the menu.")?;
    let desktop_path = if !app.desktop_path.is_empty() && Path::new(&app.desktop_path).is_file() {
        app.desktop_path.clone()
    } else {
        let fresh = scan_applications();
        fresh
            .into_iter()
            .find(|a| a.id == app.id)
            .map(|a| a.desktop_path)
            .filter(|p| !p.is_empty())
            .ok_or("App is no longer installed.")?
    };

    let launched = Command::new("gio")
        .args(["launch", &desktop_path])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map(|_| true)
        .unwrap_or(false);
    if !launched {
        return Err("Failed to launch application.".into());
    }
    let _ = recent_apps::edit(&state_dir(), "record", Some(&app.id));
    Ok(app.id)
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
