use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::util::atomic::write_atomic_with_mode;

#[derive(Debug, Default, Clone)]
pub struct IniSection {
    pub order: Vec<String>,
    pub entries: HashMap<String, String>,
}

#[derive(Debug, Default, Clone)]
pub struct IniConfig {
    pub section_order: Vec<String>,
    pub sections: HashMap<String, IniSection>,
}

impl IniConfig {
    pub fn parse(content: &str) -> Self {
        let mut config = IniConfig::default();
        let mut current_section: Option<String> = None;

        for line in content.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('#') || trimmed.starts_with(';') {
                continue;
            }

            if trimmed.starts_with('[') && trimmed.ends_with(']') {
                let sec_name = trimmed[1..trimmed.len() - 1].trim().to_string();
                if !config.sections.contains_key(&sec_name) {
                    config.section_order.push(sec_name.clone());
                    config.sections.insert(sec_name.clone(), IniSection::default());
                }
                current_section = Some(sec_name);
            } else if let Some(ref sec_name) = current_section {
                if let Some((k, v)) = line.split_once('=') {
                    let key = k.trim().to_string();
                    let value = v.trim().to_string();
                    if let Some(sec) = config.sections.get_mut(sec_name) {
                        if !sec.entries.contains_key(&key) {
                            sec.order.push(key.clone());
                        }
                        sec.entries.insert(key, value);
                    }
                }
            }
        }

        config
    }
}

pub fn merge_ini(base_str: &str, user_str: &str) -> String {
    let user_cfg = IniConfig::parse(user_str);
    let mut pending_user = user_cfg.clone();

    let mut output = String::new();
    let mut current_section: Option<String> = None;

    for line in base_str.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            // Append any pending user keys from the previous section
            if let Some(ref sec_name) = current_section {
                if let Some(sec) = pending_user.sections.get_mut(sec_name) {
                    for key in &sec.order {
                        if let Some(val) = sec.entries.remove(key) {
                            output.push_str(&format!("{} = {}\n", key, val));
                        }
                    }
                }
            }

            let sec_name = trimmed[1..trimmed.len() - 1].trim().to_string();
            current_section = Some(sec_name);
            output.push_str(line);
            output.push('\n');
        } else if let Some((k, _)) = line.split_once('=') {
            let key = k.trim();
            if let Some(ref sec_name) = current_section {
                if let Some(user_val) = user_cfg
                    .sections
                    .get(sec_name)
                    .and_then(|s| s.entries.get(key))
                {
                    // Overridden by user
                    output.push_str(&format!("{} = {}\n", key, user_val));
                    if let Some(sec) = pending_user.sections.get_mut(sec_name) {
                        sec.entries.remove(key);
                    }
                    continue;
                }
            }
            output.push_str(line);
            output.push('\n');
        } else {
            output.push_str(line);
            output.push('\n');
        }
    }

    // Append remaining keys in the last section
    if let Some(ref sec_name) = current_section {
        if let Some(sec) = pending_user.sections.get_mut(sec_name) {
            for key in &sec.order {
                if let Some(val) = sec.entries.remove(key) {
                    output.push_str(&format!("{} = {}\n", key, val));
                }
            }
        }
    }

    // Append any completely new sections from user config
    for sec_name in &user_cfg.section_order {
        if let Some(sec) = pending_user.sections.get(sec_name) {
            let remaining_entries: Vec<(&String, &String)> = sec
                .order
                .iter()
                .filter_map(|k| sec.entries.get(k).map(|v| (k, v)))
                .collect();
            if !remaining_entries.is_empty() {
                output.push_str(&format!("\n[{}]\n", sec_name));
                for (k, v) in remaining_entries {
                    output.push_str(&format!("{} = {}\n", k, v));
                }
            }
        }
    }

    output
}

pub fn sync_wayfire(config_dir: &Path) -> std::io::Result<bool> {
    let layers_dir = config_dir.join("wayfire");
    let base_path = layers_dir.join("raccon.ini");
    let user_path = layers_dir.join("user.ini");
    let target_path = config_dir.join("wayfire.ini");

    if !base_path.exists() {
        return Ok(false);
    }

    let base_content = fs::read_to_string(&base_path)?;
    let user_content = if user_path.exists() {
        fs::read_to_string(&user_path)?
    } else {
        String::new()
    };

    let merged = merge_ini(&base_content, &user_content);
    if target_path.exists() {
        if let Ok(current) = fs::read_to_string(&target_path) {
            if current == merged {
                return Ok(false);
            }
        }
    }

    write_atomic_with_mode(&target_path, merged.as_bytes(), 0o600)?;
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merge_ini() {
        let base = "[core]\nclose_top = <super> KEY_Q\n[shell]\nbar = true\n";
        let user = "[core]\nclose_top = <super> KEY_C\n[custom]\nmy_key = 123\n";

        let merged = merge_ini(base, user);
        assert!(merged.contains("close_top = <super> KEY_C"));
        assert!(merged.contains("bar = true"));
        assert!(merged.contains("[custom]"));
        assert!(merged.contains("my_key = 123"));
    }
}
