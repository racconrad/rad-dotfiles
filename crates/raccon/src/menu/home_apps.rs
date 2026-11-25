use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

use crate::util::atomic::write_atomic;

pub const LIMIT: usize = 6;
pub const DEFAULT_SHORTCUTS: &[&str] = &[
    "shortcut:browser",
    "shortcut:files",
    "shortcut:terminal",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HomeAppsData {
    pub version: u32,
    pub items: Vec<String>,
}

impl Default for HomeAppsData {
    fn default() -> Self {
        Self {
            version: 1,
            items: DEFAULT_SHORTCUTS.iter().map(|s| s.to_string()).collect(),
        }
    }
}

pub fn load_items(state_dir: &Path) -> Vec<String> {
    let path = state_dir.join("home-apps.json");
    if let Ok(content) = fs::read_to_string(&path) {
        if let Ok(data) = serde_json::from_str::<HomeAppsData>(&content) {
            if data.version == 1 && data.items.len() <= LIMIT {
                return data.items;
            }
        }
    }
    DEFAULT_SHORTCUTS.iter().map(|s| s.to_string()).collect()
}

pub fn save_items(state_dir: &Path, items: Vec<String>) -> std::io::Result<()> {
    let data = HomeAppsData {
        version: 1,
        items: items.into_iter().take(LIMIT).collect(),
    };
    let content = serde_json::to_vec_pretty(&data)?;
    write_atomic(&state_dir.join("home-apps.json"), &content)
}

pub fn edit(state_dir: &Path, args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Err("Missing favorite command".into());
    }

    let action = &args[0];
    let mut items = load_items(state_dir);

    let resolve_key = |raw: &str, items: &[String]| -> Option<String> {
        if DEFAULT_SHORTCUTS.contains(&raw) || items.iter().any(|i| i == raw) {
            return Some(raw.to_string());
        }
        for k in items {
            if crate::util::hash::sha256_hex(k) == raw {
                return Some(k.clone());
            }
        }
        for app in crate::menu::apps::cached_applications() {
            if app.id == raw || app.token == raw {
                return Some(app.id);
            }
        }
        if raw.len() != 64 || !raw.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Some(raw.to_string());
        }
        None
    };

    match action.as_str() {
        "reset" => {
            items = DEFAULT_SHORTCUTS.iter().map(|s| s.to_string()).collect();
        }
        "add" => {
            let raw = args.get(1).ok_or("Missing app to add")?;
            let key = resolve_key(raw, &items).ok_or("Application is no longer available.")?;
            if !items.contains(&key) && items.len() < LIMIT {
                items.push(key);
            }
        }
        "remove" => {
            let raw = args.get(1).ok_or("Missing app to remove")?;
            let key = resolve_key(raw, &items).ok_or("Shortcut is not in the main menu.")?;
            items.retain(|k| k != &key);
        }
        "move" => {
            let raw = args.get(1).ok_or("Missing app to move")?;
            let key = resolve_key(raw, &items).ok_or("Shortcut is not in the main menu.")?;
            let direction = args.get(2).map(|s| s.as_str()).unwrap_or("next");
            if let Some(idx) = items.iter().position(|k| k == &key) {
                if direction == "previous" && idx > 0 {
                    items.swap(idx, idx - 1);
                } else if direction == "next" && idx + 1 < items.len() {
                    items.swap(idx, idx + 1);
                }
            }
        }
        _ => return Err(format!("Unknown favorite action: {}", action)),
    }

    save_items(state_dir, items).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_defaults_when_empty() {
        let temp_dir = std::env::temp_dir().join("raccon_test_home_apps_empty");
        let _ = fs::remove_dir_all(&temp_dir);
        let items = load_items(&temp_dir);
        assert_eq!(items.len(), 3);
        assert_eq!(items[0], "shortcut:browser");
    }

    #[test]
    fn test_add_remove_move() {
        let temp_dir = std::env::temp_dir().join("raccon_test_home_apps_mut");
        let _ = fs::remove_dir_all(&temp_dir);
        fs::create_dir_all(&temp_dir).unwrap();

        // Add
        edit(&temp_dir, &["add".to_string(), "app:test".to_string()]).unwrap();
        let items = load_items(&temp_dir);
        assert_eq!(items.len(), 4);
        assert_eq!(items[3], "app:test");

        // Move previous
        edit(&temp_dir, &["move".to_string(), "app:test".to_string(), "previous".to_string()]).unwrap();
        let moved = load_items(&temp_dir);
        assert_eq!(moved[2], "app:test");

        // Remove
        edit(&temp_dir, &["remove".to_string(), "app:test".to_string()]).unwrap();
        let removed = load_items(&temp_dir);
        assert_eq!(removed.len(), 3);

        let _ = fs::remove_dir_all(&temp_dir);
    }
}

