use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::menu::{apps, cli, modes, positioning, recent_apps, transport};
use crate::util::atomic::write_atomic;
use crate::util::paths::{cache_dir, config_dir, home_dir, runtime_dir, state_dir, state_root};
use crate::util::watch::{emit_line, DirWatch, FileLock};

const WINDOW: &str = "raccon-menu";

fn eww_bin_args(args: &[&str], env_extra: Option<&[(&str, String)]>) -> Result<String, String> {
    let cfg = config_dir();
    let idempotent = args.first().is_some_and(|a| matches!(*a, "update" | "get" | "active-windows" | "ping"));
    let attempts = if idempotent { 5 } else { 1 };
    for attempt in 0..attempts {
        let mut cmd = Command::new("eww");
        cmd.args(["-c", &cfg.to_string_lossy(), "--no-daemonize"]).args(args);
        if let Some(pairs) = env_extra {
            for (k, v) in pairs {
                cmd.env(k, v);
            }
        }
        let out = cmd.output().map_err(|e| format!("Eww did not start: {e}"))?;
        if out.status.success() {
            return Ok(String::from_utf8_lossy(&out.stdout).trim().to_string());
        }
        let err = String::from_utf8_lossy(&out.stderr).trim().to_string();
        let msg = if err.is_empty() {
            String::from_utf8_lossy(&out.stdout).trim().to_string()
        } else {
            err
        };
        let transient = msg.contains("Resource temporarily unavailable") || msg.contains("channel closed");
        if attempt + 1 == attempts || !transient {
            return Err(if msg.is_empty() { "Eww did not respond.".into() } else { msg });
        }
        std::thread::sleep(Duration::from_millis(80 * (attempt as u64 + 1)));
    }
    Err("Eww did not respond.".into())
}

pub fn eww_cmd(args: &[&str]) -> Result<String, String> {
    eww_bin_args(args, None)
}

fn source_revision(path: &Path) -> String {
    fs::metadata(path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_nanos().to_string())
        .unwrap_or_else(|| "0".into())
}

fn lib_menu_dir() -> PathBuf {
    let installed = home_dir().join(".local/lib/raccon_menu");
    if installed.join("input.c").is_file() {
        return installed;
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(repo) = exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent()) {
            let cand = repo.join("modules/desktop/files/.local/lib/raccon_menu");
            if cand.join("input.c").is_file() {
                return cand;
            }
        }
    }
    installed
}

pub fn build_input_module() -> Result<PathBuf, String> {
    let lib_dir = lib_menu_dir();
    let source = lib_dir.join("input.c");
    let target = cache_dir().join("raccon-menu/input.so");
    let _ = fs::create_dir_all(target.parent().unwrap());
    let _lock = FileLock::lock(&target.with_file_name("build.lock"));
    let src_rev: u128 = source_revision(&source).parse().unwrap_or(0);
    let dst_rev: u128 = source_revision(&target).parse().unwrap_or(0);
    if !target.exists() || dst_rev < src_rev {
        let pkg = Command::new("pkg-config")
            .args(["--cflags", "--libs", "gtk+-3.0"])
            .output()
            .map_err(|e| format!("pkg-config failed: {e}"))?;
        if !pkg.status.success() {
            return Err("pkg-config gtk+-3.0 failed".into());
        }
        let flags_s = String::from_utf8_lossy(&pkg.stdout);
        let flags: Vec<&str> = flags_s.split_whitespace().collect();
        let temp = target.with_file_name(format!(".input-{}.so", std::process::id()));
        let out = Command::new("cc")
            .args([
                "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Wno-unused-parameter",
                &source.to_string_lossy(), "-o", &temp.to_string_lossy(),
            ])
            .args(&flags)
            .output()
            .map_err(|e| format!("cc failed: {e}"))?;
        if !out.status.success() {
            let _ = fs::remove_file(&temp);
            return Err(format!("Failed to compile input.c: {}", String::from_utf8_lossy(&out.stderr)));
        }
        fs::rename(&temp, &target).map_err(|e| e.to_string())?;
    }
    Ok(target)
}

fn ensure_daemon(runtime: &Path, revision: &str, module: &Path) -> Result<(), String> {
    let installed = fs::read_to_string(runtime.join("revision")).unwrap_or_default().trim().to_string();
    if eww_cmd(&["ping"]).is_ok() && (revision.is_empty() || revision == installed) {
        return Ok(());
    }
    let _ = eww_cmd(&["kill"]);
    std::thread::sleep(Duration::from_millis(100));

    let st = state_dir();
    let _ = fs::create_dir_all(&st);
    let log_path = st.join("daemon.log");
    let log_out = fs::OpenOptions::new().create(true).append(true).open(&log_path).ok();
    let log_err = log_out.as_ref().and_then(|f| f.try_clone().ok());

    let backend_bin = std::env::current_exe()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_else(|_| home_dir().join(".local/bin/desktop-menu").to_string_lossy().into_owned());

    let mut cmd = Command::new("eww");
    cmd.args(["-c", &config_dir().to_string_lossy(), "--no-daemonize", "daemon"])
        .env("LANGUAGE", "en_US:en")
        .env("LC_ALL", "C.UTF-8")
        .env("GTK_MODULES", module)
        .env("RACCON_MENU_CONFIG", config_dir())
        .env("RACCON_MENU_REVISION", revision)
        .env("RACCON_MENU_BACKEND", &backend_bin)
        .env("RACCON_MENU_RUNTIME", runtime.file_name().unwrap_or_default())
        .env("RACCON_MENU_SIMPLE_PAGES", "0")
        .stdin(Stdio::null());
    if let Some(f) = log_out { cmd.stdout(Stdio::from(f)); }
    if let Some(f) = log_err { cmd.stderr(Stdio::from(f)); }

    let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn eww daemon: {e}"))?;
    for _ in 0..30 {
        if eww_cmd(&["ping"]).is_ok() {
            let cur = fs::read_to_string(runtime.join("revision")).unwrap_or_default().trim().to_string();
            if revision.is_empty() || cur == revision {
                return Ok(());
            }
        }
        if child.try_wait().ok().flatten().is_some() {
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    Err(format!("Eww could not start. Check log: {}", log_path.display()))
}

fn monitor_geometry() -> (usize, i64, i64) {
    (0, 316, 224)
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

pub fn close(super_key: bool) -> Result<(), String> {
    let runtime = runtime_dir();
    if transport::send(if super_key { "hide-super" } else { "hide" }, &runtime) {
        return Ok(());
    }
    let _ = fs::create_dir_all(&runtime);
    if super_key {
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64();
        let _ = write_atomic(&runtime.join("closed"), now.to_string().as_bytes());
    }
    let _ = eww_cmd(&["update", "revealed=false"]);
    std::thread::sleep(Duration::from_millis(120));
    let _ = eww_cmd(&["close", WINDOW]);
    Ok(())
}

pub fn show(page: Option<&str>, prewarm: bool) -> Result<(), String> {
    let runtime = runtime_dir();
    let page_name = page.unwrap_or("home");
    if !prewarm {
        let cmd = match page {
            Some(p) => {
                let idx = transport::page_index(p).ok_or("Invalid menu page.")?;
                format!("show {idx}")
            }
            None => "toggle".to_string(),
        };
        if transport::send(&cmd, &runtime) {
            return Ok(());
        }
    }

    let _ = fs::create_dir_all(&runtime);
    let _lock = FileLock::lock(&runtime.join("toggle.lock"));
    if page.is_none() {
        if let Ok(raw) = fs::read_to_string(runtime.join("closed")) {
            if let Ok(stamp) = raw.trim().parse::<f64>() {
                let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64();
                if now >= stamp && (now - stamp) < 0.45 {
                    return Ok(());
                }
            }
        }
    }

    let mut last_dock = None;
    positioning::refresh(&runtime, true, &mut last_dock);
    let module = build_input_module()?;
    let home = home_dir();
    let sr = state_root();
    cli::sync_palette(&home, &sr);

    let input_c = lib_menu_dir().join("input.c");
    let revision = source_revision(&input_c);
    ensure_daemon(&runtime, &revision, &module)?;

    let active_wins = eww_cmd(&["active-windows"]).unwrap_or_default();
    let active = active_wins.contains(&format!("{WINDOW}:"));
    if active && prewarm {
        return Ok(());
    }
    if active && page.is_none() {
        if eww_cmd(&["get", "revealed"]).unwrap_or_default().trim_matches('"') != "true" {
            return eww_cmd(&["update", "revealed=true"]).map(|_| ());
        }
        return close(true);
    }

    let idx = transport::page_index(page_name).unwrap_or("0");
    let selected = read_preference_mode();
    let modes_json = modes::modes_json();
    let mut upd_args = vec![
        "update".to_string(),
        format!("page={idx}"),
        format!("selected={selected}"),
        "confirmation=".into(),
        "error=".into(),
        format!("modes={modes_json}"),
        "revealed=true".into(),
        format!("prewarm={prewarm}"),
    ];
    if let Ok(cached_desk) = fs::read_to_string(state_dir().join("desktop.json")) {
        if !cached_desk.trim().is_empty() {
            upd_args.push(format!("desktop={}", cached_desk.trim()));
        }
    }
    if !active {
        let cat = apps::catalogue_value(&state_dir(), &apps::cached_applications()).to_string();
        upd_args.push(format!("catalogue={cat}"));
        upd_args.push("apps_loading=false".into());
        upd_args.push("busy=false".into());
    }
    let refs: Vec<&str> = upd_args.iter().map(String::as_str).collect();
    eww_cmd(&refs)?;

    if !active {
        let (mon, w, h) = monitor_geometry();
        let _ = eww_cmd(&[
            "open", WINDOW, "--screen", &mon.to_string(),
            "--arg", &format!("panel_width={w}"), "--arg", &format!("content_height={h}"),
        ]);
        if prewarm {
            for _ in 0..60 {
                if transport::send("inspect", &runtime) {
                    return Ok(());
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            return Err("Could not prepare the resident window.".into());
        }
        let _ = eww_cmd(&["update", "revealed=true"]);
        for _ in 0..20 {
            if transport::send(&format!("show {idx}"), &runtime) {
                std::thread::sleep(Duration::from_millis(30));
                if fs::read_to_string(runtime.join("visible")).unwrap_or_default().trim() == "1" {
                    return Ok(());
                }
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        return Err("Eww did not confirm the menu is visible.".into());
    }
    Ok(())
}

pub fn prepare() -> Result<(), String> {
    let runtime = runtime_dir();
    let ready = runtime.join("ready");
    let watcher = DirWatch::new(&[ready.clone()], &[]);
    let mut last_err = None;
    for attempt in 0..3 {
        let is_ready = fs::read_to_string(&ready).unwrap_or_default().trim() == "1" && transport::send("inspect", &runtime);
        let res = if is_ready { Ok(()) } else { show(Some("home"), true) };
        match res {
            Ok(()) => {
                let deadline = Instant::now() + Duration::from_secs(3);
                loop {
                    if fs::read_to_string(&ready).unwrap_or_default().trim() == "1" {
                        let mut last_dock = None;
                        positioning::refresh(&runtime, true, &mut last_dock);
                        cli::sync_palette(&home_dir(), &state_root());
                        let rows = modes::modes_json();
                        let cache = runtime.join("modes.json");
                        if fs::read_to_string(&cache).ok().as_deref() != Some(rows.as_str()) {
                            let _ = eww_cmd(&["update", &format!("modes={rows}")]);
                            let _ = write_atomic(&cache, rows.as_bytes());
                        }
                        if let Ok(exe) = std::env::current_exe() {
                            let _ = Command::new(exe)
                                .args(["panel", "preload"])
                                .stdin(Stdio::null())
                                .stdout(Stdio::null())
                                .stderr(Stdio::null())
                                .spawn();
                        }
                        return Ok(());
                    }
                    let rem = deadline.saturating_duration_since(Instant::now());
                    if rem.is_zero() {
                        last_err = Some("Could not prepare the resident window before timeout.".to_string());
                        break;
                    }
                    watcher.wait(rem.as_millis() as i32);
                }
            }
            Err(e) => last_err = Some(e),
        }
        std::thread::sleep(Duration::from_millis(200 * (attempt as u64 + 1)));
    }
    Err(last_err.unwrap_or_else(|| "Failed to prepare menu".into()))
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
                user = std::ffi::CStr::from_ptr((*pw).pw_name).to_string_lossy().into_owned();
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
        let cn = libc::strftime(cbuf.as_mut_ptr() as *mut libc::c_char, cbuf.len(), fmt_c.as_ptr() as *const libc::c_char, &tm);
        let clock = if cn > 0 { String::from_utf8_lossy(&cbuf[..cn]).into_owned() } else { "00:00".into() };
        let mut dbuf = [0u8; 64];
        let fmt_d = b"%A, %B %d\0";
        let dn = libc::strftime(dbuf.as_mut_ptr() as *mut libc::c_char, dbuf.len(), fmt_d.as_ptr() as *const libc::c_char, &tm);
        let date = if dn > 0 { String::from_utf8_lossy(&dbuf[..dn]).into_owned() } else { String::new() };
        (clock, date)
    };
    (clock_s, date_s)
}

pub fn listen_desktop() {
    let runtime = runtime_dir();
    let _ = fs::create_dir_all(&runtime);
    let home = home_dir();
    let sr = state_root();
    let st = state_dir();
    let watcher = DirWatch::new(&[runtime.join("visible"), sr.join("desktop-power/status.json"), sr.join("desktop-power/preference.json")], &[]);
    let (user, avatar, has_avatar) = identity();
    let mut last_dock = None;
    let mut last_line = String::new();

    loop {
        let vis = fs::read_to_string(runtime.join("visible")).unwrap_or_else(|_| "1".into());
        if vis.trim() == "0" {
            watcher.wait(2000);
            continue;
        }
        positioning::refresh(&runtime, false, &mut last_dock);
        cli::sync_palette(&home, &sr);
        let app: serde_json::Value = serde_json::from_str(&cli::appearance_state(&home, &sr))
            .unwrap_or_else(|_| serde_json::json!({}));
        let power: serde_json::Value = fs::read_to_string(sr.join("desktop-power/status.json"))
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_else(|| serde_json::json!({}));
        let mode = power.get("mode").and_then(|v| v.as_str()).unwrap_or("");
        let source = power.get("source").and_then(|v| v.as_str()).unwrap_or("");
        let applying = power.get("transition").and_then(|v| v.as_bool()).unwrap_or(false);
        let errors_obj = power.get("errors").and_then(|v| v.as_object());
        let errors_str = errors_obj
            .map(|m| m.iter().map(|(k, v)| format!("{k}: {v}")).collect::<Vec<_>>().join(" · "))
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
            let _ = write_atomic(&st.join("desktop.json"), line.as_bytes());
            if !emit_line(&line) { return; }
            last_line = line;
        }
        watcher.wait(2000);
    }
}

pub fn opened() {
    let runtime = runtime_dir();
    let mut last_dock = None;
    positioning::refresh(&runtime, true, &mut last_dock);
    cli::sync_palette(&home_dir(), &state_root());
    let selected = read_preference_mode();
    let mut args = vec![
        "update".to_string(),
        format!("selected={selected}"),
        "confirmation=".into(),
        "error=".into(),
    ];
    let rows = modes::modes_json();
    let cache = runtime.join("modes.json");
    if fs::read_to_string(&cache).ok().as_deref() != Some(rows.as_str()) {
        args.push(format!("modes={rows}"));
        let _ = write_atomic(&cache, rows.as_bytes());
    }
    let canvas_tool = home_dir().join(".local/bin/raccon-canvas-mode");
    if canvas_tool.is_file() {
        if let Ok(out) = Command::new(&canvas_tool).arg("status").output() {
            let st = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !st.is_empty() {
                args.push(format!("layout_status={st}"));
                args.push("layout_error=".into());
            }
        }
    }
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let _ = eww_cmd(&refs);
}

pub fn apply_mode() -> Result<(), String> {
    let runtime = runtime_dir();
    let Some(_lock) = FileLock::try_lock(&runtime.join("apply.lock")) else {
        return Ok(());
    };
    let mode = eww_cmd(&["get", "selected"])?.trim_matches('"').to_string();
    if !modes::MODES.iter().any(|m| m.id == mode) {
        return Err("Select a valid mode.".into());
    }
    let _ = eww_cmd(&["update", "busy=true", "error="]);
    let res = Command::new(home_dir().join(".local/bin/desktop-power"))
        .args(["set", &mode])
        .output();
    let _ = eww_cmd(&["update", "busy=false"]);
    let out = res.map_err(|e| e.to_string())?;
    if !out.status.success() {
        let msg = String::from_utf8_lossy(&out.stderr).trim().to_string();
        return Err(if msg.is_empty() { "Could not set power mode.".into() } else { msg });
    }
    Ok(())
}

pub fn shortcut(name: &str) -> Result<(), String> {
    let runtime = runtime_dir();
    let home = home_dir();
    let spawn_detached = |prog: &str, args: &[&str]| {
        let _ = Command::new(prog)
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
    };
    let _ = close(false);
    match name {
        "files" => spawn_detached("dolphin", &[]),
        "browser" => spawn_detached("brave", &[]),
        "terminal" => spawn_detached("kitty", &[]),
        "audio" | "connections" | "calendar" => {
            let exe = std::env::current_exe().unwrap_or_else(|_| home.join(".local/bin/desktop-menu"));
            let exes = exe.to_string_lossy().into_owned();
            spawn_detached(&exes, &["panel", name]);
        }
        "wallpaper" => {
            let bin = home.join(".local/bin/raccon-float");
            spawn_detached(&bin.to_string_lossy(), &["wallpaper"]);
        }
        "notifications" => {
            let _ = transport::send("hide", &runtime);
            spawn_detached("swaync-client", &["-t", "-sw"]);
        }
        "lock" => {
            let bin = home.join(".local/bin/lock");
            if bin.is_file() {
                spawn_detached(&bin.to_string_lossy(), &[]);
            } else {
                spawn_detached("gtklock", &[]);
            }
        }
        _ => return Err("Invalid shortcut.".into()),
    }
    let key = format!("shortcut:{name}");
    if matches!(name, "browser" | "files" | "terminal") {
        let _ = recent_apps::edit(&state_dir(), "record", Some(&key));
        let _ = transport::send("update-catalogue", &runtime);
    }
    Ok(())
}

pub fn diagnose() {
    let runtime = runtime_dir();
    println!("{} · diagnostics", WINDOW);
    println!("Config: {}", config_dir().display());
    println!("Session: {}", std::env::var("XDG_SESSION_TYPE").unwrap_or_else(|_| "unknown".into()));
    println!("Wayland: {}", std::env::var("WAYLAND_DISPLAY").unwrap_or_else(|_| "unknown".into()));
    if transport::send("inspect", &runtime) {
        std::thread::sleep(Duration::from_millis(50));
        if let Ok(ins) = fs::read_to_string(runtime.join("inspect")) {
            println!("{}", ins.trim());
        }
    }
    if let Ok(vis) = fs::read_to_string(runtime.join("visible")) {
        println!("Resident window: {}", if vis.trim() == "1" { "visible" } else { "hidden" });
    }
    for args in [vec!["ping"], vec!["active-windows"], vec!["get", "revealed"], vec!["get", "page"]] {
        let label = args.join(" ");
        match eww_cmd(&args) {
            Ok(out) => println!("{label}: {}", if out.is_empty() { "(empty)" } else { &out }),
            Err(e) => println!("{label}: {e}"),
        }
    }
}

pub fn update_catalogue_now() {
    let st = state_dir();
    let cat = apps::catalogue_value(&st, &apps::cached_applications()).to_string();
    let _ = eww_cmd(&["update", &format!("catalogue={cat}"), "error="]);
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
    let arr = serde_json::Value::Array(results.clone()).to_string();
    let empty = if results.is_empty() { "true" } else { "false" };
    eww_cmd(&["update", &format!("apps={arr}"), &format!("query_empty={empty}")]).map(|_| ())
}

fn dispatch_subcommand(args: &[String]) -> Result<(), String> {
    if args.is_empty() {
        return Ok(());
    }
    match args[0].as_str() {
        "launch" => {
            let tok = args.get(1).ok_or("Missing app token")?;
            apps::launch_app(tok)?;
            let _ = close(false);
            Ok(())
        }
        "search-action" => {
            let key = args.get(1).ok_or("Missing search key")?;
            let (cmd, val) = apps::resolve_search_action(key)?;
            if cmd == "shortcut" {
                shortcut(val)
            } else {
                show(Some(val), false)
            }
        }
        "shortcut" => shortcut(args.get(1).map(|s| s.as_str()).unwrap_or("")),
        "tab" => show(args.get(1).map(|s| s.as_str()), false),
        _ => Ok(()),
    }
}

pub fn eww_error(msg: &str) {
    let val = serde_json::json!(msg).to_string();
    let _ = eww_cmd(&["update", &format!("error={val}"), "busy=false"]);
}

pub fn session_action_checked(action: &str) -> Result<(), String> {
    if !matches!(action, "suspend" | "reboot" | "poweroff" | "logout") {
        return Err("Invalid action.".into());
    }
    let confirmed = eww_cmd(&["get", "confirmation"]).unwrap_or_default().trim_matches('"').to_string();
    if confirmed != action {
        return Err("Select the action to confirm first.".into());
    }
    if action == "logout" {
        let sid = std::env::var("XDG_SESSION_ID").unwrap_or_default();
        if sid.is_empty() || !sid.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-') {
            return Err("Could not identify this session.".into());
        }
        let st = Command::new("loginctl").args(["terminate-session", &sid]).status().map_err(|e| e.to_string())?;
        if !st.success() { return Err("Could not terminate session.".into()); }
    } else {
        let st = Command::new("systemctl").arg(action).status().map_err(|e| e.to_string())?;
        if !st.success() { return Err("Could not run system action.".into()); }
    }
    let _ = close(false);
    Ok(())
}
