use serde::{Deserialize, Serialize};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::Command;

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

const CANVAS_OMIT_SECTIONS: &[&str] = &[
    "Focus, move, resize (wf-tile)",
    "Advanced tiling",
    "Snapping (grid) — floating windows",
    "Workspaces",
    "Workspaces and overview",
    "Explicit Dwindle layout",
    "Experimental native Snap Tiling",
];
const NORMAL_OMIT_SECTIONS: &[&str] = &["Canvas"];
const CANVAS_OMIT_KEYS: &[&str] = &[
    "Super+M",
    "Super+Shift+D",
    "Super+Shift+O",
    "Super+1..9, Super+0",
    "Super+Shift+1..9, Super+Shift+0",
    "Super+Ctrl+Arrows",
    "Super+Ctrl+Shift+Arrows",
    "Super+Backspace",
    "Super+S",
    "Super+Ctrl+Tab",
    "Super+Ctrl+LeftDrag, Super+MiddleDrag",
    "Super+MiddleDrag",
    "4-finger horizontal swipe",
];

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
                .map(|c| {
                    let s = c.trim();
                    s.strip_prefix('`').and_then(|x| x.strip_suffix('`')).unwrap_or(s)
                })
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

fn is_executable(path: &Path) -> bool {
    path.is_file()
        && fs::metadata(path)
            .map(|m| (m.permissions().mode() & 0o111) != 0)
            .unwrap_or(false)
}

fn is_canvas_mode(home: &Path) -> bool {
    let raccon_tool = home.join(".local/bin/raccon-canvas-mode");
    let wf_tool = home.join(".local/bin/wf-canvas-mode");
    let tool = if is_executable(&raccon_tool) {
        raccon_tool
    } else if is_executable(&wf_tool) {
        wf_tool
    } else {
        return false;
    };

    let mut cmd = Command::new(tool);
    cmd.arg("status");
    let user_ini = home.join(".config/wayfire/user.ini");
    if user_ini.is_file() && std::env::var_os("WF_CANVAS_INI").is_none() {
        cmd.env("WF_CANVAS_INI", user_ini);
    }

    cmd.output()
        .map(|out| out.status.success() && String::from_utf8_lossy(&out.stdout).trim() == "canvas")
        .unwrap_or(false)
}

pub fn filter_sections(
    sections: Vec<(String, Vec<(String, String)>)>,
    is_canvas: bool,
) -> Vec<(String, Vec<(String, String)>)> {
    if !is_canvas {
        return sections
            .into_iter()
            .filter(|(title, _)| !NORMAL_OMIT_SECTIONS.contains(&title.as_str()))
            .collect();
    }

    sections
        .into_iter()
        .filter(|(title, _)| {
            !CANVAS_OMIT_SECTIONS.contains(&title.as_str())
                && !normalize(title).contains("workspace")
        })
        .filter_map(|(title, rows)| {
            let filtered: Vec<(String, String)> = rows
                .into_iter()
                .filter(|(keys, action)| {
                    if title != "Canvas" && CANVAS_OMIT_KEYS.contains(&keys.as_str()) {
                        return false;
                    }
                    let combined = normalize(&format!("{} {}", keys, action));
                    !combined.contains("tinywidgets")
                        && !combined.contains("widgetctl")
                        && !combined.contains("workspace")
                })
                .collect();
            if filtered.is_empty() {
                None
            } else {
                Some((title, filtered))
            }
        })
        .collect()
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
    let mut parsed_sections = Vec::new();
    if let Ok(content) = fs::read_to_string(&doc_path) {
        parsed_sections = filter_sections(parse_markdown(&content), is_canvas_mode(home));
    }

    let mut raw_sections = vec![default_menu];
    raw_sections.extend(parsed_sections);

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_filter_sections_by_mode() {
        let sections = vec![
            (
                "Canvas".into(),
                vec![
                    ("Super+R".into(), "Origin".into()),
                    ("Super+M".into(), "Toggle workarea fill on focused window".into()),
                    ("Super+Backspace".into(), "Previous camera position".into()),
                    ("Super+Ctrl+Arrows".into(), "Resize focused window".into()),
                ],
            ),
            (
                "Focus, move, resize (wf-tile)".into(),
                vec![("Super+J".into(), "Split".into())],
            ),
            (
                "Snapping (grid) — floating windows".into(),
                vec![("Super+Shift+Left".into(), "Left half".into())],
            ),
            (
                "Window state (wm-actions, core)".into(),
                vec![
                    ("Super+F".into(), "Fullscreen".into()),
                    ("Super+M".into(), "Maximize".into()),
                    ("Super+Shift+O".into(), "Sticky (show on all workspaces)".into()),
                    ("Super+Shift+D".into(), "Show desktop".into()),
                ],
            ),
            (
                "Workspaces".into(),
                vec![
                    ("Super+1..9, Super+0".into(), "Go to workspace 1..10".into()),
                    ("Super+S".into(), "Expo (workspace overview)".into()),
                ],
            ),
            (
                "Window switching and gestures".into(),
                vec![
                    ("Super+`".into(), "Scale (visible windows)".into()),
                    ("Alt+Tab / Alt+Shift+Tab".into(), "Switcher next / previous".into()),
                    ("Super+W".into(), "Send to workspace".into()),
                ],
            ),
            (
                "Extras".into(),
                vec![("Super+Alt+M".into(), "TinyWidgets editor".into())],
            ),
        ];

        let canvas = filter_sections(sections.clone(), true);
        let canvas_titles: Vec<&str> = canvas.iter().map(|(t, _)| t.as_str()).collect();
        assert_eq!(
            canvas_titles,
            vec!["Canvas", "Window state (wm-actions, core)", "Window switching and gestures"]
        );
        assert_eq!(
            canvas[0].1,
            vec![
                ("Super+R".into(), "Origin".into()),
                ("Super+M".into(), "Toggle workarea fill on focused window".into()),
                ("Super+Backspace".into(), "Previous camera position".into()),
                ("Super+Ctrl+Arrows".into(), "Resize focused window".into()),
            ]
        );
        assert_eq!(canvas[1].1, vec![("Super+F".into(), "Fullscreen".into())]);
        assert_eq!(
            canvas[2].1,
            vec![
                ("Super+`".into(), "Scale (visible windows)".into()),
                ("Alt+Tab / Alt+Shift+Tab".into(), "Switcher next / previous".into()),
            ]
        );
        assert!(canvas.iter().all(|(t, rows)| {
            !t.to_lowercase().contains("workspace")
                && rows.iter().all(|(k, a)| {
                    !k.to_lowercase().contains("workspace") && !a.to_lowercase().contains("workspace")
                })
        }));

        let normal = filter_sections(sections, false);
        let normal_titles: Vec<&str> = normal.iter().map(|(t, _)| t.as_str()).collect();
        assert!(!normal_titles.contains(&"Canvas"));
        assert!(normal_titles.contains(&"Focus, move, resize (wf-tile)"));
        assert!(normal_titles.contains(&"Workspaces"));
        assert!(normal_titles.contains(&"Snapping (grid) — floating windows"));
    }
}
