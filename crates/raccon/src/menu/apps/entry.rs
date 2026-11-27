use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

use crate::util::atomic::write_atomic;
use crate::util::hash::sha256_hex;
use crate::util::paths::{config_dir, home_dir, state_dir};

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

pub fn parse_desktop_file(path: &Path, id: &str, empty_svg: &str) -> Option<AppEntry> {
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

pub fn collect_desktop_files(base: &Path, current: &Path, out: &mut BTreeMap<String, PathBuf>) {
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
