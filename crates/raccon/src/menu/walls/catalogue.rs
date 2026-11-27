use std::fs;
use std::path::{Path, PathBuf};

use crate::util::paths::{cache_dir, home_dir};

pub fn kind_of(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?.to_ascii_lowercase();
    let trimmed = ext.trim_end_matches('\'');
    match trimmed {
        "jpg" | "jpeg" | "png" | "webp" | "gif" => Some("images"),
        "mp4" | "webm" | "mkv" | "mov" => Some("videos"),
        _ => None,
    }
}

pub fn expand_tilde(raw: &str, home: &Path) -> PathBuf {
    if let Some(rest) = raw.strip_prefix("~/") {
        home.join(rest)
    } else if raw == "~" {
        home.to_path_buf()
    } else {
        PathBuf::from(raw)
    }
}

pub fn dir_has_entries(path: &Path) -> bool {
    path.is_dir() && fs::read_dir(path).map(|mut d| d.next().is_some()).unwrap_or(false)
}

pub fn resolve_wallpaper_dir() -> PathBuf {
    let home = home_dir();
    if let Ok(line) = fs::read_to_string(home.join(".config/raccon/wallpaper-dir")) {
        let p = expand_tilde(line.trim(), &home);
        if p.is_dir() {
            return p;
        }
    }
    if let Ok(env_dir) = std::env::var("WALLPAPER_DIR") {
        let p = expand_tilde(env_dir.trim(), &home);
        if p.is_dir() {
            return p;
        }
    }
    let default_dir = home.join("Pictures/Wallpapers");
    if dir_has_entries(&default_dir) {
        return default_dir;
    }
    if let Ok(text) = fs::read_to_string(home.join(".config/waypaper/config.ini")) {
        for line in text.lines() {
            if let Some(rest) = line.trim().strip_prefix("folder") {
                if let Some((_, val)) = rest.split_once('=') {
                    let p = expand_tilde(val.trim(), &home);
                    if dir_has_entries(&p) {
                        return p;
                    }
                }
            }
        }
    }
    for cand in [home.join("Pictures/Wallpapers"), home.join("Pictures"), home.join(".local/share/wallpapers/raccon")] {
        if dir_has_entries(&cand) {
            return cand;
        }
    }
    default_dir
}

pub fn catalogue() -> (PathBuf, Vec<PathBuf>, Vec<PathBuf>) {
    let target = resolve_wallpaper_dir();
    let mut files = Vec::new();
    if let Ok(entries) = fs::read_dir(&target) {
        for entry in entries.flatten() {
            let p = entry.path();
            if p.is_file() && kind_of(&p).is_some() {
                files.push(p);
            }
        }
    }
    files.sort();
    let images: Vec<PathBuf> = files.iter().filter(|p| kind_of(p) == Some("images")).cloned().collect();
    let videos: Vec<PathBuf> = files.iter().filter(|p| kind_of(p) == Some("videos")).cloned().collect();
    (target, images, videos)
}

pub fn current_wallpaper() -> String {
    fs::read_to_string(cache_dir().join("current-wallpaper"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .and_then(|s| fs::canonicalize(s).ok())
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default()
}
