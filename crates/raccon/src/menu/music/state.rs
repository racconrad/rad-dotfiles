use std::collections::HashMap;

use crate::menu::music::art::{artwork, thumbnail};

pub fn empty_music() -> serde_json::Value {
    serde_json::json!({
        "visible": false, "playing": false, "title": "", "artist": "",
        "album": "", "player": "", "art": "", "has_art": false,
        "time": "", "percent": 0
    })
}

pub fn clock(micro: u64) -> String {
    let seconds = micro / 1_000_000;
    let hours = seconds / 3600;
    let rest = seconds % 3600;
    if hours > 0 {
        format!("{}:{:02}:{:02}", hours, rest / 60, rest % 60)
    } else {
        format!("{}:{:02}", rest / 60, rest % 60)
    }
}

pub fn capitalize_first(s: &str) -> String {
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

#[cfg(test)]
mod tests {
    use super::*;

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
