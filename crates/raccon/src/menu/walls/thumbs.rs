use std::fs;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::menu::walls::catalogue::kind_of;
use crate::util::hash::sha1_hex;

pub fn mtime_le(src: &Path, dst: &Path) -> bool {
    let Ok(s) = fs::metadata(src) else { return false; };
    let Ok(d) = fs::metadata(dst) else { return false; };
    d.len() > 0 && s.modified().ok() <= d.modified().ok()
}

pub fn cached_thumb(src: &Path, thumbs_dir: &Path) -> String {
    let out = thumbs_dir.join(format!("{}.png", sha1_hex(&src.to_string_lossy())));
    if mtime_le(src, &out) {
        out.to_string_lossy().into_owned()
    } else {
        String::new()
    }
}

pub fn generate_thumb(src: &Path, thumbs_dir: &Path) -> String {
    let out = thumbs_dir.join(format!("{}.png", sha1_hex(&src.to_string_lossy())));
    if mtime_le(src, &out) {
        return out.to_string_lossy().into_owned();
    }
    let _ = fs::create_dir_all(thumbs_dir);
    let temp = thumbs_dir.join(format!(".thumb-{}-{}.png", std::process::id(), sha1_hex(&src.to_string_lossy())));
    let vf = "scale=480:300:force_original_aspect_ratio=increase,crop=480:300";
    let seeks: &[&[&str]] = if kind_of(src) == Some("videos") { &[&["-ss", "1"], &[]] } else { &[&[]] };
    for seek in seeks {
        let ok = Command::new("ffmpeg")
            .args(["-nostdin", "-loglevel", "error", "-y", "-threads", "1"])
            .args(*seek)
            .arg("-i")
            .arg(src)
            .args(["-filter_threads", "1", "-frames:v", "1", "-vf", vf, "-threads", "1"])
            .arg(&temp)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if ok && temp.metadata().map(|m| m.len() > 0).unwrap_or(false) && fs::rename(&temp, &out).is_ok() {
            return out.to_string_lossy().into_owned();
        }
    }
    let _ = fs::remove_file(&temp);
    String::new()
}

pub fn css_url(path: &str) -> String {
    path.replace('\\', "\\\\").replace('"', "\\\"")
}
