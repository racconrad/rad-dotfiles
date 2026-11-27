use std::fs;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::util::hash::sha1_hex;
use crate::util::paths::cache_dir;

pub fn percent_decode(input: &str) -> String {
    let bytes = input.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let (Some(h), Some(l)) = ((bytes[i + 1] as char).to_digit(16), (bytes[i + 2] as char).to_digit(16)) {
                out.push(((h << 4) | l) as u8);
                i += 3;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

pub fn artwork(url: &str) -> String {
    if let Some(rest) = url.strip_prefix("file://") {
        let path = percent_decode(rest);
        if Path::new(&path).is_file() && !path.contains('\'') && !path.contains('\\') {
            return path;
        }
        return String::new();
    }
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return String::new();
    }
    let cache = cache_dir().join("raccon-menu/art");
    let target = cache.join(sha1_hex(url));
    if target.is_file() {
        return target.to_string_lossy().into_owned();
    }
    if fs::create_dir_all(&cache).is_err() {
        return String::new();
    }
    let temp = cache.join(format!(".part-{}", std::process::id()));
    let ok = Command::new("curl")
        .args(["-fsSL", "--max-time", "3", "--max-filesize", "8388608", "-o"])
        .arg(&temp)
        .arg(url)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false);
    if ok && temp.metadata().map(|m| m.len() > 0).unwrap_or(false) && fs::rename(&temp, &target).is_ok() {
        return target.to_string_lossy().into_owned();
    }
    let _ = fs::remove_file(&temp);
    String::new()
}

/// GTK rescales a CSS background on every repaint, and dragging repaints each frame;
/// a card-sized copy keeps that cheap. Falls back to the original when magick fails.
pub fn thumbnail(source: String) -> String {
    if source.is_empty() {
        return source;
    }
    let stamp = fs::metadata(&source).and_then(|m| m.modified()).ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map(|d| d.as_secs()).unwrap_or(0);
    let cache = cache_dir().join("raccon-menu/art");
    let target = cache.join(format!("{}.thumb.jpg", sha1_hex(&format!("{source}:{stamp}"))));
    if target.is_file() {
        return target.to_string_lossy().into_owned();
    }
    let temp = cache.join(format!(".thumb-{}.jpg", std::process::id()));
    let ok = fs::create_dir_all(&cache).is_ok()
        && Command::new("magick")
            .arg(format!("{source}[0]"))
            .args(["-thumbnail", "360x360^", "-quality", "88"])
            .arg(&temp)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
        && fs::rename(&temp, &target).is_ok();
    if ok {
        return target.to_string_lossy().into_owned();
    }
    let _ = fs::remove_file(&temp);
    source
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thumbnail_downscales_and_falls_back() {
        assert_eq!(thumbnail(String::new()), "");
        assert_eq!(thumbnail("/nonexistent/art.png".into()), "/nonexistent/art.png");
        let src = std::env::temp_dir().join(format!("raccon-art-{}.png", std::process::id()));
        let made = Command::new("magick").args(["-size", "1200x1200", "xc:red"]).arg(&src).status();
        if !made.map(|s| s.success()).unwrap_or(false) {
            return; // magick missing: nothing to downscale with
        }
        let thumb = thumbnail(src.to_string_lossy().into_owned());
        assert!(thumb.ends_with(".thumb.jpg"), "{thumb}");
        let size = Command::new("magick").args(["identify", "-format", "%wx%h", &thumb]).output().unwrap();
        assert_eq!(String::from_utf8_lossy(&size.stdout), "360x360");
        let _ = fs::remove_file(&src);
        let _ = fs::remove_file(&thumb);
    }
}
