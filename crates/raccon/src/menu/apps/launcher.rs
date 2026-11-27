use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::SystemTime;

use crate::menu::apps::catalogue::catalogue_value;
use crate::menu::apps::entry::{app_dirs, cached_applications, scan_applications, AppEntry};
use crate::menu::recent_apps;
use crate::util::paths::state_dir;
use crate::util::watch::{emit_line, DirWatch};

pub fn watch_catalogue() {
    let state = state_dir();
    let _ = fs::create_dir_all(&state);
    let pref_files = [
        state.join("home-apps.json"),
        state.join("favorites.json"),
        state.join("recent-apps.json"),
    ];
    let existing_app_dirs: Vec<PathBuf> = app_dirs().into_iter().filter(|d| d.is_dir()).collect();
    let apps_watcher = DirWatch::new(&[], &existing_app_dirs);
    let state_watcher = DirWatch::new(&pref_files, &[]);

    let mut previous = String::new();
    let emit = |cat: &[AppEntry], prev: &mut String| -> bool {
        let val = catalogue_value(&state, cat).to_string();
        if &val != prev {
            if !emit_line(&val) {
                return false;
            }
            *prev = val;
        }
        true
    };
    let mut current = cached_applications();
    if !emit(&current, &mut previous) { return; }
    current = scan_applications();
    if !emit(&current, &mut previous) { return; }
    state_watcher.drain();

    let pref_stamps = || -> Vec<Option<SystemTime>> {
        pref_files.iter().map(|p| fs::metadata(p).and_then(|m| m.modified()).ok()).collect()
    };
    let mut last_prefs = pref_stamps();

    loop {
        let mut pfds = [
            libc::pollfd { fd: apps_watcher.raw_fd(), events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: state_watcher.raw_fd(), events: libc::POLLIN, revents: 0 },
        ];
        unsafe { libc::poll(pfds.as_mut_ptr(), 2, -1); }
        if pfds[0].revents & libc::POLLIN != 0 && apps_watcher.drain() {
            current = scan_applications();
            state_watcher.drain();
            if !emit(&current, &mut previous) { break; }
        }
        if pfds[1].revents & libc::POLLIN != 0 && state_watcher.drain() {
            let now_prefs = pref_stamps();
            if now_prefs != last_prefs {
                last_prefs = now_prefs;
                if !emit(&current, &mut previous) { break; }
            }
        }
    }
}

pub fn launch_app(token_str: &str) -> Result<String, String> {
    if token_str.len() != 64 || !token_str.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("Invalid application.".into());
    }
    let catalog = cached_applications();
    let app = catalog
        .into_iter()
        .find(|a| a.token == token_str)
        .ok_or("App is no longer available. Reopen the menu.")?;
    let desktop_path = if !app.desktop_path.is_empty() && Path::new(&app.desktop_path).is_file() {
        app.desktop_path.clone()
    } else {
        let fresh = scan_applications();
        fresh
            .into_iter()
            .find(|a| a.id == app.id)
            .map(|a| a.desktop_path)
            .filter(|p| !p.is_empty())
            .ok_or("App is no longer installed.")?
    };

    let launched = Command::new("gio")
        .args(["launch", &desktop_path])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map(|_| true)
        .unwrap_or(false);
    if !launched {
        return Err("Failed to launch application.".into());
    }
    let _ = recent_apps::edit(&state_dir(), "record", Some(&app.id));
    Ok(app.id)
}
