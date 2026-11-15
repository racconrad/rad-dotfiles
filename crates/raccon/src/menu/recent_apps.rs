use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

use crate::util::atomic::write_atomic;

pub const LIMIT: usize = 6;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecentAppsData {
    pub version: u32,
    pub enabled: bool,
    pub items: Vec<String>,
}

impl Default for RecentAppsData {
    fn default() -> Self {
        Self {
            version: 1,
            enabled: false,
            items: Vec::new(),
        }
    }
}

pub fn load(state_dir: &Path) -> RecentAppsData {
    let path = state_dir.join("recent-apps.json");
    if let Ok(content) = fs::read_to_string(&path) {
        if let Ok(data) = serde_json::from_str::<RecentAppsData>(&content) {
            if data.version == 1 && data.items.len() <= LIMIT {
                return data;
            }
        }
    }
    RecentAppsData::default()
}

pub fn save(state_dir: &Path, data: &RecentAppsData) -> std::io::Result<()> {
    let content = serde_json::to_vec_pretty(data)?;
    write_atomic(&state_dir.join("recent-apps.json"), &content)
}

pub fn edit(state_dir: &Path, action: &str, key: Option<&str>) -> Result<(), String> {
    let mut data = load(state_dir);

    match action {
        "enable" => data.enabled = true,
        "disable" => data.enabled = false,
        "clear" => data.items.clear(),
        "record" => {
            if data.enabled {
                if let Some(k) = key {
                    data.items.retain(|item| item != k);
                    data.items.insert(0, k.to_string());
                    data.items.truncate(LIMIT);
                }
            }
        }
        _ => return Err(format!("Unknown recent action: {}", action)),
    }

    save(state_dir, &data).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_recent_apps_lifecycle() {
        let temp_dir = std::env::temp_dir().join("raccon_test_recent_apps");
        let _ = fs::remove_dir_all(&temp_dir);
        fs::create_dir_all(&temp_dir).unwrap();

        let initial = load(&temp_dir);
        assert!(!initial.enabled);
        assert!(initial.items.is_empty());

        // Enable
        edit(&temp_dir, "enable", None).unwrap();
        let enabled = load(&temp_dir);
        assert!(enabled.enabled);

        // Record
        edit(&temp_dir, "record", Some("app:one")).unwrap();
        edit(&temp_dir, "record", Some("app:two")).unwrap();
        let recorded = load(&temp_dir);
        assert_eq!(recorded.items, vec!["app:two", "app:one"]);

        // Clear
        edit(&temp_dir, "clear", None).unwrap();
        let cleared = load(&temp_dir);
        assert!(cleared.items.is_empty());

        let _ = fs::remove_dir_all(&temp_dir);
    }
}

