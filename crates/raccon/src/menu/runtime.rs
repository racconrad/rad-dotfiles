use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};

use crate::menu::qs::{qs_ensure, qs_ipc};
use crate::menu::{apps, cli, modes, recent_apps, transport};
use crate::util::paths::{home_dir, runtime_dir, state_dir, state_root};
use crate::util::watch::{DirWatch, FileLock, emit_line};

pub fn widget(function: &str, name: &str) -> Result<(), String> {
    if matches!(function, "open" | "toggle") {
        qs_ensure()?;
    }
    qs_ipc(function, &[name]).map(|_| ())
}

pub fn open_menu(page: Option<&str>) -> Result<(), String> {
    let Some(page) = page else {
        return widget("open", "menu");
    };
    let index = transport::page_index(page).ok_or("Invalid menu page.")?;
    qs_ensure()?;
    qs_ipc("openMenu", &[index]).map(|_| ())
}

pub fn close_menu() -> Result<(), String> {
    widget("close", "menu")
}

pub fn diagnose() {
    println!("Raccon Quickshell diagnostics");
    for function in ["ping", "list"] {
        match qs_ipc(function, &[]) {
            Ok(out) => println!("{function}: {out}"),
            Err(error) => println!("{function}: {error}"),
        }
    }
}

fn read_preference_mode() -> String {
    let path = state_root().join("desktop-power/preference.json");
    fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v.get("mode").and_then(|m| m.as_str()).map(str::to_string))
        .filter(|m| modes::MODES.iter().any(|x| x.id == m))
        .unwrap_or_else(|| "auto".into())
}

fn identity() -> (String, String, bool) {
    let home = home_dir();
    let uid = unsafe { libc::getuid() };
    let mut user = std::env::var("USER").unwrap_or_else(|_| "user".into());
    unsafe {
        let pw = libc::getpwuid(uid);
        if !pw.is_null() {
            if !(*pw).pw_gecos.is_null() {
                let gecos = std::ffi::CStr::from_ptr((*pw).pw_gecos).to_string_lossy();
                let first = gecos.split(',').next().unwrap_or("").trim();
                if !first.is_empty() {
                    user = first.to_string();
                }
            }
            if user.is_empty() && !(*pw).pw_name.is_null() {
                user = std::ffi::CStr::from_ptr((*pw).pw_name)
                    .to_string_lossy()
                    .into_owned();
            }
        }
    }
    let uname = std::env::var("USER").unwrap_or_default();
    let candidates = [
        home.join(".face"),
        home.join(".face.icon"),
        PathBuf::from("/var/lib/AccountsService/icons").join(&uname),
    ];
    let avatar = candidates
        .iter()
        .find(|p| p.is_file())
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default();
    let has_avatar = !avatar.is_empty();
    (user, avatar, has_avatar)
}

fn local_clock_date() -> (String, String) {
    let (clock_s, date_s) = unsafe {
        let mut t: libc::time_t = 0;
        libc::time(&mut t);
        let mut tm: libc::tm = std::mem::zeroed();
        libc::localtime_r(&t, &mut tm);
        let mut cbuf = [0u8; 32];
        let fmt_c = b"%I:%M %p\0";
        let cn = libc::strftime(
            cbuf.as_mut_ptr() as *mut libc::c_char,
            cbuf.len(),
            fmt_c.as_ptr() as *const libc::c_char,
            &tm,
        );
        let clock = if cn > 0 {
            String::from_utf8_lossy(&cbuf[..cn]).into_owned()
        } else {
            "00:00".into()
        };
        let mut dbuf = [0u8; 64];
        let fmt_d = b"%A, %B %d\0";
        let dn = libc::strftime(
            dbuf.as_mut_ptr() as *mut libc::c_char,
            dbuf.len(),
            fmt_d.as_ptr() as *const libc::c_char,
            &tm,
        );
        let date = if dn > 0 {
            String::from_utf8_lossy(&dbuf[..dn]).into_owned()
        } else {
            String::new()
        };
        (clock, date)
    };
    (clock_s, date_s)
}

pub fn listen_desktop() {
    let runtime = runtime_dir();
    let _ = fs::create_dir_all(&runtime);
    let home = home_dir();
    let sr = state_root();
    let watcher = DirWatch::new(
        &[
            sr.join("desktop-power/status.json"),
            sr.join("desktop-power/preference.json"),
        ],
        &[],
    );
    let (user, avatar, has_avatar) = identity();
    let mut last_line = String::new();

    loop {
        let app: serde_json::Value = serde_json::from_str(&cli::appearance_state(&home, &sr))
            .unwrap_or_else(|_| serde_json::json!({}));
        let power: serde_json::Value = fs::read_to_string(sr.join("desktop-power/status.json"))
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_else(|| serde_json::json!({}));
        let mode = power.get("mode").and_then(|v| v.as_str()).unwrap_or("");
        let source = power.get("source").and_then(|v| v.as_str()).unwrap_or("");
        let applying = power
            .get("transition")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let errors_obj = power.get("errors").and_then(|v| v.as_object());
        let errors_str = errors_obj
            .map(|m| {
                m.iter()
                    .map(|(k, v)| format!("{k}: {v}"))
                    .collect::<Vec<_>>()
                    .join(" · ")
            })
            .unwrap_or_default();
        let mode_name = modes::MODES
            .iter()
            .find(|m| m.id == mode)
            .map(|m| m.name)
            .unwrap_or("Loading mode");
        let (clock, date) = local_clock_date();
        let pref = read_preference_mode();
        let mut obj = serde_json::json!({
            "clock": clock, "date": date, "mode": mode, "source": source,
            "preference": pref, "mode_name": mode_name, "applying": applying,
            "has_errors": !errors_str.is_empty(), "errors": errors_str,
            "ready": !mode.is_empty(), "user": user, "avatar": avatar, "has_avatar": has_avatar
        });
        if let (Some(dst), Some(src)) = (obj.as_object_mut(), app.as_object()) {
            for (k, v) in src {
                dst.insert(k.clone(), v.clone());
            }
        }
        let line = obj.to_string();
        if line != last_line {
            if !emit_line(&line) {
                return;
            }
            last_line = line;
        }
        watcher.wait(2000);
    }
}

pub fn apply_mode(mode: &str) -> Result<(), String> {
    let runtime = runtime_dir();
    let Some(_lock) = FileLock::try_lock(&runtime.join("apply.lock")) else {
        return Ok(());
    };
    if !modes::MODES.iter().any(|m| m.id == mode) {
        return Err("Select a valid mode.".into());
    }
    let out = Command::new(home_dir().join(".local/bin/desktop-power"))
        .args(["set", mode])
        .output()
        .map_err(|e| e.to_string())?;
    if !out.status.success() {
        let msg = String::from_utf8_lossy(&out.stderr).trim().to_string();
        return Err(if msg.is_empty() {
            "Could not set power mode.".into()
        } else {
            msg
        });
    }
    Ok(())
}

pub fn shortcut(name: &str) -> Result<(), String> {
    let lock = home_dir().join(".local/bin/lock");
    let mut command = match name {
        "audio" | "connections" | "calendar" => return open_menu(Some(name)),
        "wallpaper" => {
            let _ = close_menu();
            return widget("open", "wallpaper");
        }
        "files" => Command::new("dolphin"),
        "browser" => Command::new("brave"),
        "terminal" => Command::new("kitty"),
        "notifications" => {
            let mut command = Command::new("swaync-client");
            command.args(["-t", "-sw"]);
            command
        }
        "lock" if lock.is_file() => Command::new(lock),
        "lock" => Command::new("gtklock"),
        _ => return Err("Invalid shortcut.".into()),
    };

    let _ = close_menu();
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| error.to_string())?;
    let key = format!("shortcut:{name}");
    if matches!(name, "browser" | "files" | "terminal") {
        let _ = recent_apps::edit(&state_dir(), "record", Some(&key));
    }
    Ok(())
}

pub fn filter_query(query: &str, launch_first: bool) -> Result<(), String> {
    let st = state_dir();
    let results = apps::filter_search(&st, query);
    if launch_first {
        if let Some(first) = results.first() {
            let act = first.get("action").and_then(|v| v.as_str()).unwrap_or("");
            let val = first.get("value").and_then(|v| v.as_str()).unwrap_or("");
            return dispatch_subcommand(&[act.to_string(), val.to_string()]);
        }
        return Ok(());
    }
    emit_line(&serde_json::Value::Array(results).to_string());
    Ok(())
}

fn dispatch_subcommand(args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Ok(());
    }
    match args[0].as_str() {
        "launch" => {
            let tok = args.get(1).ok_or("Missing app token")?;
            apps::launch_app(tok)?;
            let _ = close_menu();
            Ok(())
        }
        "search-action" => {
            let key = args.get(1).ok_or("Missing search key")?;
            let (cmd, val) = apps::resolve_search_action(key)?;
            if cmd == "shortcut" {
                shortcut(val)
            } else {
                open_menu(Some(val))
            }
        }
        "shortcut" => shortcut(args.get(1).map(|s| s.as_str()).unwrap_or("")),
        "tab" => open_menu(args.get(1).map(String::as_str)),
        _ => Ok(()),
    }
}

pub fn session_action(action: &str) -> Result<(), String> {
    if action == "cancel" {
        return Ok(());
    }
    if !matches!(action, "suspend" | "reboot" | "poweroff" | "logout") {
        return Err("Invalid action.".into());
    }
    if action == "logout" {
        let sid = std::env::var("XDG_SESSION_ID").unwrap_or_default();
        if sid.is_empty()
            || !sid
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
        {
            return Err("Could not identify this session.".into());
        }
        let st = Command::new("loginctl")
            .args(["terminate-session", &sid])
            .status()
            .map_err(|e| e.to_string())?;
        if !st.success() {
            return Err("Could not terminate session.".into());
        }
    } else {
        let st = Command::new("systemctl")
            .arg(action)
            .status()
            .map_err(|e| e.to_string())?;
        if !st.success() {
            return Err("Could not run system action.".into());
        }
    }
    let _ = close_menu();
    Ok(())
}
