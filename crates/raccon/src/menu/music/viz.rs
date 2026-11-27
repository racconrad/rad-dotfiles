use std::os::unix::io::AsRawFd;
use std::process::{Child, Command, Stdio};

use crate::menu::cava;
use crate::menu::music::io::read_nonblocking;
use crate::util::paths::runtime_root;
use crate::util::watch::{emit_line, set_nonblocking};

pub const VIZ_BARS: usize = 12;
pub const VIZ_MAX: usize = 24;
pub const BASE_PX: usize = 4;

pub fn idle_viz() -> serde_json::Value {
    let mut map = serde_json::Map::new();
    map.insert("active".into(), serde_json::json!(false));
    map.insert("level".into(), serde_json::json!(0));
    for i in 0..VIZ_BARS {
        map.insert(format!("b{i}"), serde_json::json!(BASE_PX));
    }
    serde_json::Value::Object(map)
}

pub fn watch_viz() {
    let runtime = runtime_root();
    let conf = runtime.join("raccon-music-cava.conf");
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
                    std::thread::sleep(std::time::Duration::from_secs(5));
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
            libc::pollfd { fd: s_fd, events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: c_fd, events: libc::POLLIN, revents: 0 },
        ];
        if s_fd < 0 && c_fd < 0 {
            std::thread::sleep(std::time::Duration::from_secs(2));
            continue;
        }
        unsafe { libc::poll(pfds.as_mut_ptr(), 2, -1); }
        if s_fd >= 0 && (pfds[0].revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR)) != 0 {
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
                    std::thread::sleep(std::time::Duration::from_secs(2));
                }
            }
        }
        if c_fd >= 0 && (pfds[1].revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR)) != 0 {
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
