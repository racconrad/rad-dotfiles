use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShortcutRow {
    pub keys: String,
    pub action: String,
    pub search: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShortcutSection {
    pub title: String,
    pub rows: Vec<ShortcutRow>,
}

fn wrap_text(text: &str, max_width: usize) -> String {
    let mut result = String::new();
    let mut line_len = 0;

    for word in text.split_whitespace() {
        if line_len == 0 {
            result.push_str(word);
            line_len = word.len();
        } else if line_len + 1 + word.len() <= max_width {
            result.push(' ');
            result.push_str(word);
            line_len += 1 + word.len();
        } else {
            result.push('\n');
            result.push_str(word);
            line_len = word.len();
        }
    }
    result
}

fn normalize(text: &str) -> String {
    text.to_lowercase()
        .chars()
        .filter(|c| c.is_alphanumeric() || c.is_whitespace() || *c == '+' || *c == '.' || *c == '/' || *c == '-' || *c == '(' || *c == ')')
        .collect()
}

pub fn parse_markdown(content: &str) -> Vec<(String, Vec<(String, String)>)> {
    let mut sections = Vec::new();
    let mut current_title: Option<String> = None;
    let mut current_rows = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if let Some(title) = trimmed.strip_prefix("## ") {
            if let Some(t) = current_title.take() {
                if !current_rows.is_empty() {
                    sections.push((t, std::mem::take(&mut current_rows)));
                }
            }
            current_title = Some(title.trim().to_string());
        } else if current_title.is_some() && trimmed.starts_with('|') {
            if trimmed.contains("---") {
                continue;
            }
            let cells: Vec<&str> = trimmed
                .trim_matches('|')
                .split('|')
                .map(|c| c.trim().trim_matches('`'))
                .collect();
            if cells.is_empty() || cells[0].eq_ignore_ascii_case("shortcut") {
                continue;
            }
            let keys = cells[0].to_string();
            let extra: Vec<&str> = cells[1..]
                .iter()
                .copied()
                .filter(|c| !c.is_empty() && *c != "—" && *c != "-" && *c != "same")
                .collect();
            let action = extra.join(" · ");
            current_rows.push((keys, action));
        } else if current_title.is_some() && trimmed.starts_with("- **") {
            if let Some(rest) = trimmed.strip_prefix("- **") {
                if let Some((k, v)) = rest.split_once("**") {
                    let action = v.trim_start_matches(':').trim().replace('`', "");
                    current_rows.push((k.trim().to_string(), action));
                }
            }
        }
    }

    if let Some(t) = current_title {
        if !current_rows.is_empty() {
            sections.push((t, current_rows));
        }
    }

    sections
}

pub fn load_shortcuts(home: &Path) -> Vec<ShortcutSection> {
    let default_menu = (
        "Raccon Menu".to_string(),
        vec![
            (
                "Ctrl+1…9".to_string(),
                "Home, Apps, Power, Session, Audio, Wi-Fi, Bluetooth, Calendar, Shortcuts".to_string(),
            ),
            ("Ctrl+F / Ctrl+L".to_string(), "Search apps".to_string()),
            ("Alt+1…9".to_string(), "Launch a Home app".to_string()),
            ("Esc".to_string(), "Back, clear search, then close".to_string()),
            ("Ctrl+W".to_string(), "Close the menu".to_string()),
        ],
    );

    let doc_path = home.join(".config").join("wayfire-keys.md");
    let mut raw_sections = vec![default_menu];

    if let Ok(content) = fs::read_to_string(&doc_path) {
        raw_sections.extend(parse_markdown(&content));
    }

    raw_sections
        .into_iter()
        .map(|(title, rows)| {
            let section_rows = rows
                .into_iter()
                .map(|(k, a)| {
                    let action = wrap_text(&a, 36);
                    let search = normalize(&format!("{} {} {}", k, a, title));
                    ShortcutRow { keys: k, action, search }
                })
                .collect();
            ShortcutSection { title, rows: section_rows }
        })
        .collect()
}

pub fn shortcuts_json(home: &Path) -> String {
    let sections = load_shortcuts(home);
    serde_json::to_string(&sections).unwrap_or_else(|_| "[]".to_string())
}
