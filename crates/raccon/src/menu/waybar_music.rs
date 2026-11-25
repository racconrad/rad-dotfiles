use std::collections::BTreeMap;
use std::ffi::CString;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::os::unix::io::{AsRawFd, FromRawFd, RawFd};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use crate::menu::{cava, music::read_nonblocking};
use crate::util::paths::runtime_root;
use crate::util::watch::{set_nonblocking, DirWatch, FileLock};

const IDLE_BARS: &str = "▁▁▁▁▁▁▁▁";
const TRACK_WIDTH: usize = 22;
const META_FORMAT: &str = "{{status}}\x1f{{title}}\x1f{{artist}}\x1f{{album}}\x1f{{playerName}}";

fn tip_for(mode: &str) -> Option<&'static str> {
    match mode {
        "open" => Some("Show music player"),
        "viz" => Some("Live audio visualizer · click for player · scroll for volume"),
        "track" => Some("Now playing · click for player · middle: play/pause · right: raise app"),
        "prev" => Some("Previous"),
        "play" => Some("Play / Pause"),
        "next" => Some("Next"),
        _ => None,
    }
}

fn format_track(title: &str, artist: &str) -> String {
    let t = title.trim();
    let a = artist.trim();
    if !t.is_empty() && !a.is_empty() {
        format!("{t} · {a}")
    } else if !t.is_empty() {
        t.to_string()
    } else {
        a.to_string()
    }
}

fn marquee(text: &str, step: usize) -> String {
    let chars: Vec<char> = text.chars().collect();
    if chars.is_empty() || chars.len() <= TRACK_WIDTH {
        return text.to_string();
    }
    if step <= 3 {
        return chars[..TRACK_WIDTH].iter().collect();
    }
    let mut loop_chars = chars;
    loop_chars.extend("   ·   ".chars());
    let len = loop_chars.len();
    let start = (step - 3) % len;
    (0..TRACK_WIDTH).map(|i| loop_chars[(start + i) % len]).collect()
}

fn format_tooltip(status: &str, title: &str, artist: &str, album: &str, player: &str) -> String {
    let mut lines = Vec::new();
    if !title.is_empty() {
        lines.push(title.to_string());
    }
    let meta = [artist, album].iter().filter(|s| !s.is_empty()).copied().collect::<Vec<_>>().join(" · ");
    if !meta.is_empty() {
        lines.push(meta);
    }
    let state_label = if !player.is_empty() { format!("{status} · {player}") } else { status.to_string() };
    if !state_label.is_empty() {
        lines.push(state_label);
    }
    lines.push("Click: player · Middle: play/pause · Right: raise app".to_string());
    lines.join("\n")
}

fn snapshot(status: &str, card_open: bool, track: &str, bars: &str, level: usize, tooltip: &str) -> serde_json::Value {
    let active = matches!(status, "Playing" | "Paused") && !card_open;
    if !active {
        return serde_json::json!({
            "open": {"text": ""}, "prev": {"text": ""}, "play": {"text": ""},
            "next": {"text": ""}, "viz": {"text": ""}, "track": {"text": ""},
        });
    }
    let play_icon = if status == "Playing" { "\u{eb4b}" } else { "\u{eb68}" };
    let base = status.to_lowercase();
    let lvl = level.min(3);
    let reactive = if status == "Playing" {
        serde_json::json!([base, format!("level-{lvl}")])
    } else {
        serde_json::json!([base])
    };
    let viz_text = if status == "Playing" && !bars.is_empty() { bars } else { IDLE_BARS };
    let viz_tip = if tooltip.is_empty() { tip_for("viz").unwrap_or("") } else { tooltip };
    let track_tip = if tooltip.is_empty() { tip_for("track").unwrap_or("") } else { tooltip };
    let track_val = if track.is_empty() {
        serde_json::json!({"text": ""})
    } else {
        serde_json::json!({"text": track, "tooltip": track_tip, "class": reactive})
    };
    serde_json::json!({
        "open": {"text": "\u{eb3b}", "tooltip": tip_for("open").unwrap(), "class": base},
        "prev": {"text": "\u{eba4}", "tooltip": tip_for("prev").unwrap(), "class": base},
        "play": {"text": play_icon, "tooltip": tip_for("play").unwrap(), "class": base},
        "next": {"text": "\u{eba6}", "tooltip": tip_for("next").unwrap(), "class": base},
        "viz": {"text": viz_text, "tooltip": viz_tip, "class": reactive},
        "track": track_val,
    })
}

fn mkfifo_private(path: &Path) -> Result<(), String> {
    let _ = fs::remove_file(path);
    let c = CString::new(path.as_os_str().as_bytes()).map_err(|_| "bad path")?;
    let rc = unsafe { libc::mkfifo(c.as_ptr(), 0o600) };
    if rc != 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    Ok(())
}

fn open_fd(path: &Path, flags: libc::c_int) -> Option<RawFd> {
    let c = CString::new(path.as_os_str().as_bytes()).ok()?;
    let fd = unsafe { libc::open(c.as_ptr(), flags) };
    if fd >= 0 { Some(fd) } else { None }
}

fn waybar_music_dir() -> Result<PathBuf, String> {
    let root = runtime_root().join("raccon-waybar-music");
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let _ = fs::set_permissions(&root, fs::Permissions::from_mode(0o700));
    Ok(root)
}

pub fn serve() -> Result<(), String> {
    let root = waybar_music_dir()?;
    let Some(_lock) = FileLock::try_lock(&root.join("provider.lock")) else {
        return Ok(());
    };
    let inbox_path = root.join("subscribe");
    mkfifo_private(&inbox_path)?;
    let inbox = open_fd(&inbox_path, libc::O_RDWR | libc::O_NONBLOCK | libc::O_CLOEXEC)
        .ok_or("failed to open subscribe fifo")?;
    let _ = fs::write(root.join("provider.pid"), std::process::id().to_string());

    let flag = runtime_root().join("raccon-music.open");
    let watcher = DirWatch::new(&[flag.clone()], &[]);
    let mut clients: BTreeMap<RawFd, String> = BTreeMap::new();
    let mut player_proc: Option<Child> = None;
    let mut cava_proc: Option<Child> = None;
    let mut status = String::new();
    let mut title = String::new();
    let mut artist = String::new();
    let mut album = String::new();
    let mut player = String::new();
    let mut bars = IDLE_BARS.to_string();
    let mut level = 0usize;
    let mut marquee_step = 0usize;
    let mut next_marquee: Option<Instant> = None;
    let mut player_buf = Vec::new();
    let mut cava_buf = Vec::new();
    let mut req_buf = Vec::new();
    let mut latest = String::new();
    let mut retry = Instant::now();
    let mut cava_retry = Instant::now();
    let mut idle_until = Instant::now() + Duration::from_secs(5);

    let uid = unsafe { libc::getuid() };

    let publish = |status: &str, title: &str, artist: &str, album: &str, player: &str, bars: &str, level: usize, step: usize, latest: &mut String, clients: &mut BTreeMap<RawFd, String>, idle_until: &mut Instant| {
        let full = format_track(title, artist);
        let vis_track = if status == "Playing" {
            marquee(&full, step)
        } else {
            full.chars().take(TRACK_WIDTH).collect()
        };
        let tip = if full.is_empty() { String::new() } else { format_tooltip(status, title, artist, album, player) };
        let payload = snapshot(status, flag.exists(), &vis_track, bars, level, &tip).to_string() + "\n";
        if &payload == latest {
            return;
        }
        *latest = payload;
        let dead: Vec<RawFd> = clients
            .keys()
            .copied()
            .filter(|&fd| {
                let bytes = latest.as_bytes();
                let n = unsafe { libc::write(fd, bytes.as_ptr() as *const libc::c_void, bytes.len()) };
                n < 0
            })
            .collect();
        for fd in dead {
            if let Some(name) = clients.remove(&fd) {
                unsafe { libc::close(fd); }
                let _ = fs::remove_file(root.join(name));
            }
            if clients.is_empty() {
                *idle_until = Instant::now() + Duration::from_secs(3);
            }
        }
    };

    publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);

    while !clients.is_empty() || Instant::now() < idle_until {
        let now = Instant::now();
        if player_proc.is_none() && now >= retry {
            if let Ok(c) = Command::new("playerctl")
                .args(["--follow", "metadata", "--format", META_FORMAT])
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
            {
                if let Some(ref s) = c.stdout {
                    set_nonblocking(s.as_raw_fd());
                }
                player_buf.clear();
                player_proc = Some(c);
            } else {
                retry = now + Duration::from_secs(2);
            }
        }

        let want_cava = !clients.is_empty() && status == "Playing" && !flag.exists();
        if want_cava && cava_proc.is_none() && now >= cava_retry {
            cava_buf.clear();
            match cava::spawn(&root.join("cava.conf"), 8, 22, 7) {
                Ok(c) => cava_proc = Some(c),
                Err(_) => cava_retry = now + Duration::from_secs(3),
            }
        } else if !want_cava && cava_proc.is_some() {
            cava::stop(&mut cava_proc);
            bars = IDLE_BARS.to_string();
            level = 0;
        }

        let full_len = format_track(&title, &artist).chars().count();
        let scrolling = !clients.is_empty() && status == "Playing" && !flag.exists() && full_len > TRACK_WIDTH;
        if scrolling {
            if let Some(t) = next_marquee {
                if now >= t {
                    marquee_step += 1;
                    publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);
                    next_marquee = Some(now + Duration::from_millis(420));
                }
            } else {
                next_marquee = Some(now + Duration::from_millis(420));
            }
        } else {
            next_marquee = None;
        }

        let mut timeout_ms = 500i32;
        if let Some(t) = next_marquee {
            timeout_ms = timeout_ms.min(t.saturating_duration_since(now).as_millis() as i32);
        }
        if clients.is_empty() {
            timeout_ms = timeout_ms.min(idle_until.saturating_duration_since(now).as_millis() as i32);
        }

        let mut pfds = Vec::with_capacity(4 + clients.len());
        pfds.push(libc::pollfd { fd: inbox, events: libc::POLLIN, revents: 0 });
        pfds.push(libc::pollfd { fd: watcher.raw_fd(), events: libc::POLLIN, revents: 0 });
        let p_fd = player_proc.as_ref().and_then(|c| c.stdout.as_ref()).map(|s| s.as_raw_fd()).unwrap_or(-1);
        let c_fd = cava_proc.as_ref().and_then(|c| c.stdout.as_ref()).map(|s| s.as_raw_fd()).unwrap_or(-1);
        if p_fd >= 0 {
            pfds.push(libc::pollfd { fd: p_fd, events: libc::POLLIN, revents: 0 });
        }
        if c_fd >= 0 {
            pfds.push(libc::pollfd { fd: c_fd, events: libc::POLLIN, revents: 0 });
        }
        let client_start = pfds.len();
        let client_fds: Vec<RawFd> = clients.keys().copied().collect();
        for &fd in &client_fds {
            pfds.push(libc::pollfd { fd, events: libc::POLLERR | libc::POLLHUP, revents: 0 });
        }

        unsafe { libc::poll(pfds.as_mut_ptr(), pfds.len() as libc::nfds_t, timeout_ms.max(10)); }

        if pfds[0].revents & libc::POLLIN != 0 {
            if let Ok(lines) = read_nonblocking(inbox, &mut req_buf) {
                for name in lines {
                    if !name.starts_with("client-") || name.contains('/') || name.len() > 100 {
                        continue;
                    }
                    let cp = root.join(&name);
                    if let Ok(meta) = fs::symlink_metadata(&cp) {
                        if meta.uid() != uid { continue; }
                    }
                    if let Some(wfd) = open_fd(&cp, libc::O_WRONLY | libc::O_NONBLOCK | libc::O_CLOEXEC | libc::O_NOFOLLOW) {
                        clients.insert(wfd, name);
                        let bytes = latest.as_bytes();
                        let n = unsafe { libc::write(wfd, bytes.as_ptr() as *const libc::c_void, bytes.len()) };
                        if n < 0 {
                            if let Some(cname) = clients.remove(&wfd) {
                                unsafe { libc::close(wfd); }
                                let _ = fs::remove_file(root.join(cname));
                            }
                        }
                    }
                }
            }
        }
        if pfds[1].revents & libc::POLLIN != 0 && watcher.drain() {
            publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);
        }
        for (idx, &fd) in client_fds.iter().enumerate() {
            if pfds[client_start + idx].revents != 0 {
                if let Some(name) = clients.remove(&fd) {
                    unsafe { libc::close(fd); }
                    let _ = fs::remove_file(root.join(name));
                }
                if clients.is_empty() {
                    idle_until = Instant::now() + Duration::from_secs(3);
                }
            }
        }
        if p_fd >= 0 {
            let p_rev = pfds[2].revents;
            if p_rev & (libc::POLLIN | libc::POLLHUP | libc::POLLERR) != 0 {
                match read_nonblocking(p_fd, &mut player_buf) {
                    Ok(lines) => {
                        for line in lines {
                            let parts: Vec<&str> = line.trim_end_matches(['\r', '\n']).split('\x1f').collect();
                            let ns = parts.first().copied().unwrap_or("").trim().to_string();
                            let nt = parts.get(1).copied().unwrap_or("").to_string();
                            let na = parts.get(2).copied().unwrap_or("").to_string();
                            let nal = parts.get(3).copied().unwrap_or("").to_string();
                            let np = parts.get(4).copied().unwrap_or("").trim().to_string();
                            if (nt.as_str(), na.as_str()) != (title.as_str(), artist.as_str()) {
                                marquee_step = 0;
                                next_marquee = None;
                            }
                            status = ns;
                            title = nt;
                            artist = na;
                            album = nal;
                            player = np;
                        }
                        publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);
                    }
                    Err(_) => {
                        cava::stop(&mut player_proc);
                        cava::stop(&mut cava_proc);
                        status.clear(); title.clear(); artist.clear(); album.clear(); player.clear();
                        bars = IDLE_BARS.to_string(); level = 0; marquee_step = 0;
                        retry = Instant::now() + Duration::from_secs(2);
                        publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);
                    }
                }
            }
        }
        if c_fd >= 0 {
            let c_idx = if p_fd >= 0 { 3 } else { 2 };
            if pfds[c_idx].revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR) != 0 {
                match read_nonblocking(c_fd, &mut cava_buf) {
                    Ok(lines) => {
                        for raw in lines.iter().rev() {
                            if let Some(vals) = cava::parse_line(raw, 8, 7) {
                                bars = cava::bars_text(&vals);
                                level = cava::energy_level(&vals, 7);
                                publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);
                                break;
                            }
                        }
                    }
                    Err(_) => {
                        cava::stop(&mut cava_proc);
                        bars = IDLE_BARS.to_string(); level = 0;
                        cava_retry = Instant::now() + Duration::from_secs(2);
                        publish(&status, &title, &artist, &album, &player, &bars, level, marquee_step, &mut latest, &mut clients, &mut idle_until);
                    }
                }
            }
        }
    }

    cava::stop(&mut cava_proc);
    cava::stop(&mut player_proc);
    for (fd, name) in clients {
        unsafe { libc::close(fd); }
        let _ = fs::remove_file(root.join(name));
    }
    unsafe { libc::close(inbox); }
    let _ = fs::remove_file(&inbox_path);
    let _ = fs::remove_file(root.join("provider.pid"));
    Ok(())
}

pub fn listen(mode: &str) -> Result<(), String> {
    if tip_for(mode).is_none() {
        return Err("Usage: waybar-music open|viz|track|prev|play|next".into());
    }
    let root = waybar_music_dir()?;
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let mut previous = String::new();
    let mut seq = 0u64;
    loop {
        seq += 1;
        let name = format!("client-{}-{}", std::process::id(), seq);
        let client_path = root.join(&name);
        if mkfifo_private(&client_path).is_ok() {
            let reader = open_fd(&client_path, libc::O_RDONLY | libc::O_NONBLOCK | libc::O_CLOEXEC);
            let keeper = open_fd(&client_path, libc::O_WRONLY | libc::O_NONBLOCK | libc::O_CLOEXEC);
            if let (Some(rfd), Some(kfd)) = (reader, keeper) {
                let mut subscribed = false;
                {
                    let _lock = FileLock::lock(&root.join("start.lock"));
                    let mut launched = false;
                    for _ in 0..60 {
                        if let Some(ifd) = open_fd(&root.join("subscribe"), libc::O_WRONLY | libc::O_NONBLOCK | libc::O_CLOEXEC) {
                            let msg = format!("{name}\n");
                            unsafe {
                                libc::write(ifd, msg.as_ptr() as *const libc::c_void, msg.len());
                                libc::close(ifd);
                            }
                            subscribed = true;
                            break;
                        }
                        if !launched {
                            let _ = Command::new(&exe)
                                .args(["waybar-music-serve"])
                                .stdin(Stdio::null())
                                .stdout(Stdio::null())
                                .stderr(Stdio::null())
                                .spawn();
                            launched = true;
                        }
                        std::thread::sleep(Duration::from_millis(25));
                    }
                }
                if subscribed {
                    let mut pfd = libc::pollfd { fd: rfd, events: libc::POLLIN, revents: 0 };
                    let ready = unsafe { libc::poll(&mut pfd, 1, 2000) };
                    unsafe { libc::close(kfd); }
                    if ready > 0 {
                        let flags = unsafe { libc::fcntl(rfd, libc::F_GETFL, 0) };
                        if flags >= 0 {
                            unsafe { libc::fcntl(rfd, libc::F_SETFL, flags & !libc::O_NONBLOCK); }
                        }
                        let file = unsafe { fs::File::from_raw_fd(rfd) };
                        let reader = BufReader::new(file);
                        for line in reader.lines().map_while(Result::ok) {
                            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&line) {
                                if let Some(val) = parsed.get(mode) {
                                    let out = val.to_string();
                                    if out != previous {
                                        if writeln!(std::io::stdout(), "{}", out).is_err() {
                                            let _ = fs::remove_file(&client_path);
                                            return Ok(());
                                        }
                                        let _ = std::io::stdout().flush();
                                        previous = out;
                                    }
                                }
                            }
                        }
                    } else {
                        unsafe { libc::close(rfd); }
                    }
                } else {
                    unsafe {
                        libc::close(kfd);
                        libc::close(rfd);
                    }
                }
            } else {
                if let Some(fd) = reader { unsafe { libc::close(fd); } }
                if let Some(fd) = keeper { unsafe { libc::close(fd); } }
            }
            let _ = fs::remove_file(&client_path);
        }
        let empty = "{\"text\":\"\"}";
        if previous != empty {
            if writeln!(std::io::stdout(), "{}", empty).is_err() {
                return Ok(());
            }
            let _ = std::io::stdout().flush();
            previous = empty.to_string();
        }
        std::thread::sleep(Duration::from_secs(1));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_marquee_and_snapshot() {
        assert_eq!(marquee("Short", 5), "Short");
        assert_eq!(marquee("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 0).chars().count(), TRACK_WIDTH);
        let idle = snapshot("", false, "", "", 0, "");
        assert_eq!(idle["play"]["text"], "");
        let playing = snapshot("Playing", false, "Song", "▁▂▃", 2, "Tip");
        assert_eq!(playing["viz"]["text"], "▁▂▃");
        assert_eq!(playing["play"]["text"], "\u{eb4b}");
    }
}
