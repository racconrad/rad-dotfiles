use std::collections::HashMap;
use std::fs;
use std::os::unix::io::AsRawFd;
use std::path::Path;
use std::process::{Child, Command, Stdio};

use crate::menu::cava;
use crate::util::hash::sha1_hex;
use crate::util::paths::{cache_dir, runtime_root};
use crate::util::watch::{emit_line, set_nonblocking, DirWatch};

const META_FORMAT: &str = "{{playerName}}\x1f{{status}}\x1f{{title}}\x1f{{artist}}\x1f{{album}}\x1f{{mpris:artUrl}}\x1f{{position}}\x1f{{mpris:length}}";
const VIZ_BARS: usize = 12;
const VIZ_MAX: usize = 24;
const BASE_PX: usize = 4;

fn empty_music() -> serde_json::Value {
    serde_json::json!({
        "visible": false, "playing": false, "title": "", "artist": "",
        "album": "", "player": "", "art": "", "has_art": false,
        "time": "", "percent": 0
    })
}

fn idle_viz() -> serde_json::Value {
    let mut map = serde_json::Map::new();
    map.insert("active".into(), serde_json::json!(false));
    map.insert("level".into(), serde_json::json!(0));
    for i in 0..VIZ_BARS {
        map.insert(format!("b{i}"), serde_json::json!(BASE_PX));
    }
    serde_json::Value::Object(map)
}

fn clock(micro: u64) -> String {
    let seconds = micro / 1_000_000;
    let hours = seconds / 3600;
    let rest = seconds % 3600;
    if hours > 0 {
        format!("{}:{:02}:{:02}", hours, rest / 60, rest % 60)
    } else {
        format!("{}:{:02}", rest / 60, rest % 60)
    }
}

fn percent_decode(input: &str) -> String {
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

fn artwork(url: &str) -> String {
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
fn thumbnail(source: String) -> String {
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

fn capitalize_first(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(c) => c.to_uppercase().collect::<String>() + chars.as_str(),
        None => String::new(),
    }
}

pub fn music_state(line: &str, art_cache: &mut HashMap<String, String>) -> serde_json::Value {
    let parts: Vec<&str> = line.trim_end_matches(['\r', '\n']).split('\x1f').collect();
    if parts.len() < 8 || parts[2].is_empty() {
        return empty_music();
    }
    let (player, status, title, artist, album, url) = (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]);
    let pos: u64 = parts[6].parse().unwrap_or(0);
    let len: u64 = parts[7].parse().unwrap_or(0);
    if !art_cache.contains_key(url) {
        art_cache.clear();
        let resolved = if url.is_empty() { String::new() } else { thumbnail(artwork(url)) };
        art_cache.insert(url.to_string(), resolved);
    }
    let art = art_cache.get(url).cloned().unwrap_or_default();
    let player_name = player.split('.').next().map(capitalize_first).unwrap_or_default();
    let time_str = if len > 0 { format!("{} / {}", clock(pos), clock(len)) } else { clock(pos) };
    let pct = if len > 0 { ((pos as f64 * 100.0 / len as f64).min(100.0) * 10.0).round() / 10.0 } else { 0.0 };
    serde_json::json!({
        "visible": true,
        "playing": status == "Playing",
        "title": title,
        "artist": if artist.is_empty() { &player_name } else { artist },
        "album": album,
        "player": if player_name.is_empty() { "Music" } else { &player_name },
        "art": art,
        "has_art": !art.is_empty(),
        "time": time_str,
        "percent": pct,
    })
}

pub fn read_nonblocking(fd: i32, buf: &mut Vec<u8>) -> Result<Vec<String>, ()> {
    let mut tmp = [0u8; 65536];
    let n = unsafe { libc::read(fd, tmp.as_mut_ptr() as *mut libc::c_void, tmp.len()) };
    if n < 0 {
        let err = std::io::Error::last_os_error();
        if err.kind() == std::io::ErrorKind::WouldBlock {
            return Ok(Vec::new());
        }
        return Err(());
    }
    if n == 0 {
        return Err(());
    }
    buf.extend_from_slice(&tmp[..n as usize]);
    if buf.len() > 65536 {
        buf.clear();
        return Ok(Vec::new());
    }
    let mut lines = Vec::new();
    while let Some(pos) = buf.iter().position(|&b| b == b'\n') {
        let line: Vec<u8> = buf.drain(..=pos).collect();
        lines.push(String::from_utf8_lossy(&line[..line.len() - 1]).into_owned());
    }
    Ok(lines)
}

pub fn watch_music() {
    let flag = runtime_root().join("raccon-music.open");
    let watcher = DirWatch::new(&[flag.clone()], &[]);
    let mut art_cache = HashMap::new();
    let mut follow: Option<Child> = None;
    let mut buf = Vec::new();
    let mut last = empty_music().to_string();
    if !emit_line(&last) { return; }

    loop {
        if !flag.exists() {
            // Stop playerctl while hidden (0% idle CPU), but keep the last emitted track in Eww
            // so reopening shows immediately on frame 1 while fresh metadata arrives.
            cava::stop(&mut follow);
            buf.clear();
            watcher.wait(-1);
            continue;
        }
        if follow.is_none() {
            match Command::new("playerctl")
                .args(["--follow", "metadata", "--format", META_FORMAT])
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
            {
                Ok(child) => {
                    if let Some(ref stdout) = child.stdout {
                        set_nonblocking(stdout.as_raw_fd());
                    }
                    buf.clear();
                    follow = Some(child);
                }
                Err(_) => {
                    watcher.wait(5000);
                    continue;
                }
            }
        }
        let f_fd = follow.as_ref().and_then(|c| c.stdout.as_ref()).map(|s| s.as_raw_fd()).unwrap_or(-1);
        let mut pfds = [
            libc::pollfd { fd: watcher.raw_fd(), events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: f_fd, events: libc::POLLIN, revents: 0 },
        ];
        let nfds = if f_fd >= 0 { 2 } else { 1 };
        unsafe { libc::poll(pfds.as_mut_ptr(), nfds, -1); }
        if pfds[0].revents & libc::POLLIN != 0 {
            watcher.drain();
            if !flag.exists() {
                continue;
            }
        }
        if f_fd >= 0 && (pfds[1].revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR)) != 0 {
            match read_nonblocking(f_fd, &mut buf) {
                Ok(lines) => {
                    for line in lines {
                        let value = music_state(&line, &mut art_cache).to_string();
                        if value != last {
                            if !emit_line(&value) { return; }
                            last = value;
                        }
                    }
                }
                Err(_) => {
                    cava::stop(&mut follow);
                    let empty = empty_music().to_string();
                    if last != empty {
                        if !emit_line(&empty) { return; }
                        last = empty;
                    }
                    watcher.wait(2000);
                }
            }
        }
    }
}

pub fn watch_viz() {
    let runtime = runtime_root();
    let flag = runtime.join("raccon-music.open");
    let conf = runtime.join("raccon-music-cava.conf");
    let watcher = DirWatch::new(&[flag.clone()], &[]);
    let mut status_proc: Option<Child> = None;
    let mut cava_proc: Option<Child> = None;
    let mut status_buf = Vec::new();
    let mut cava_buf = Vec::new();
    let mut playing = false;
    let mut last = String::new();

    let emit = |val: &serde_json::Value, last: &mut String| -> bool {
        let s = val.to_string();
        if &s != last {
            if !emit_line(&s) { return false; }
            *last = s;
        }
        true
    };
    if !emit(&idle_viz(), &mut last) { return; }

    loop {
        if !flag.exists() {
            cava::stop(&mut cava_proc);
            cava::stop(&mut status_proc);
            playing = false;
            status_buf.clear();
            cava_buf.clear();
            emit(&idle_viz(), &mut last);
            watcher.wait(-1);
            continue;
        }
        if status_proc.is_none() {
            match Command::new("playerctl")
                .args(["--follow", "status"])
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
            {
                Ok(c) => {
                    if let Some(ref stdout) = c.stdout {
                        set_nonblocking(stdout.as_raw_fd());
                    }
                    status_buf.clear();
                    status_proc = Some(c);
                }
                Err(_) => {
                    watcher.wait(5000);
                    continue;
                }
            }
        }
        if playing && cava_proc.is_none() {
            cava_buf.clear();
            cava_proc = cava::spawn(&conf, VIZ_BARS, 24, VIZ_MAX).ok();
        } else if !playing && cava_proc.is_some() {
            cava::stop(&mut cava_proc);
            cava_buf.clear();
            emit(&idle_viz(), &mut last);
        }

        let s_fd = status_proc.as_ref().and_then(|c| c.stdout.as_ref()).map(|s| s.as_raw_fd()).unwrap_or(-1);
        let c_fd = cava_proc.as_ref().and_then(|c| c.stdout.as_ref()).map(|s| s.as_raw_fd()).unwrap_or(-1);
        let mut pfds = [
            libc::pollfd { fd: watcher.raw_fd(), events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: s_fd, events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: c_fd, events: libc::POLLIN, revents: 0 },
        ];
        let nfds = if c_fd >= 0 { 3 } else if s_fd >= 0 { 2 } else { 1 };
        unsafe { libc::poll(pfds.as_mut_ptr(), nfds, -1); }
        if pfds[0].revents & libc::POLLIN != 0 {
            watcher.drain();
            if !flag.exists() { continue; }
        }
        if s_fd >= 0 && (pfds[1].revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR)) != 0 {
            match read_nonblocking(s_fd, &mut status_buf) {
                Ok(lines) => {
                    for line in lines {
                        playing = line.trim() == "Playing";
                    }
                    if !playing {
                        cava::stop(&mut cava_proc);
                        emit(&idle_viz(), &mut last);
                    }
                }
                Err(_) => {
                    cava::stop(&mut status_proc);
                    cava::stop(&mut cava_proc);
                    playing = false;
                    emit(&idle_viz(), &mut last);
                    watcher.wait(2000);
                }
            }
        }
        if c_fd >= 0 && (pfds[2].revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR)) != 0 {
            match read_nonblocking(c_fd, &mut cava_buf) {
                Ok(lines) => {
                    for raw in lines.iter().rev() {
                        if let Some(vals) = cava::parse_line(raw, VIZ_BARS, VIZ_MAX) {
                            let mut obj = serde_json::Map::new();
                            obj.insert("active".into(), serde_json::json!(true));
                            obj.insert("level".into(), serde_json::json!(cava::energy_level(&vals, VIZ_MAX)));
                            for (i, v) in vals.iter().enumerate() {
                                obj.insert(format!("b{i}"), serde_json::json!(BASE_PX + v));
                            }
                            emit(&serde_json::Value::Object(obj), &mut last);
                            break;
                        }
                    }
                }
                Err(_) => {
                    cava::stop(&mut cava_proc);
                    emit(&idle_viz(), &mut last);
                }
            }
        }
    }
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

    #[test]
    fn test_music_state_formatting() {
        let mut cache = HashMap::new();
        let line = "spotify\x1fPlaying\x1fSong\x1f\x1fAlbum\x1f\x1f61000000\x1f183000000";
        let out = music_state(line, &mut cache);
        assert_eq!(out["time"], "1:01 / 3:03");
        assert_eq!(out["artist"], "Spotify");
        assert_eq!(out["playing"], true);
        assert_eq!(music_state("\x1f\x1f\x1f\x1f\x1f\x1f\x1f", &mut cache), empty_music());
        assert_eq!(clock(3_723_000_000), "1:02:03");
    }
}
