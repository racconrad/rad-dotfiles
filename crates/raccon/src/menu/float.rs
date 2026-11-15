use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::thread;
use std::time::{Duration, Instant};

use crate::util::paths;

pub fn card_wait(name: &str, timeout_secs: u64) -> Result<(), String> {
    let base = std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| paths::home_dir().join(".cache"));
    let path = base.join(name);
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);

    while Instant::now() < deadline {
        if let Ok(content) = fs::read_to_string(&path) {
            if content.trim() == "1" {
                return Ok(());
            }
        }
        thread::sleep(Duration::from_millis(20));
    }

    if let Ok(content) = fs::read_to_string(&path) {
        if content.trim() == "1" {
            return Ok(());
        }
    }
    Err("Floating card did not finish its hidden warmup.".into())
}

pub fn keyboard_build() -> Result<PathBuf, String> {
    let home = paths::home_dir();
    let cache_dir = home.join(".cache").join("raccon-float");
    fs::create_dir_all(&cache_dir).map_err(|e| e.to_string())?;
    let out = cache_dir.join("keyboard.so");

    let mut src_dir = home.join(".local").join("lib").join("raccon_menu");
    if !src_dir.join("float_input.c").exists() {
        if let Ok(current_exe) = std::env::current_exe() {
            if let Some(repo_candidate) = current_exe
                .parent()
                .and_then(|p| p.parent())
                .and_then(|p| p.parent())
                .map(|p| p.join("modules/desktop/files/.local/lib/raccon_menu"))
            {
                if repo_candidate.join("float_input.c").exists() {
                    src_dir = repo_candidate;
                }
            }
        }
    }

    let source_names = [
        "float_input.c",
        "navigation.h",
        "thumbnail_playback.h",
        "float_resident.h",
        "resident_surface.h",
        "soft_icons.h",
        "popup_geometry.h",
    ];

    let mut needs_build = !out.exists();
    if !needs_build {
        if let Ok(out_meta) = fs::metadata(&out) {
            if let Ok(out_mtime) = out_meta.modified() {
                for name in &source_names {
                    let src_file = src_dir.join(name);
                    if let Ok(src_meta) = fs::metadata(&src_file) {
                        if let Ok(src_mtime) = src_meta.modified() {
                            if src_mtime > out_mtime {
                                needs_build = true;
                                break;
                            }
                        }
                    }
                }
            } else {
                needs_build = true;
            }
        } else {
            needs_build = true;
        }
    }

    if needs_build {
        let pkg_out = Command::new("pkg-config")
            .args(["--cflags", "--libs", "gtk+-3.0", "libjpeg"])
            .output()
            .map_err(|e| format!("Failed to run pkg-config: {}", e))?;
        if !pkg_out.status.success() {
            return Err("pkg-config failed for gtk+-3.0 libjpeg".into());
        }
        let flags_str = String::from_utf8_lossy(&pkg_out.stdout);
        let flags: Vec<&str> = flags_str.split_whitespace().collect();

        let temp_so = cache_dir.join(format!("keyboard-{}.so", std::process::id()));
        let mut cc_cmd = Command::new("cc");
        cc_cmd.args([
            "-shared",
            "-fPIC",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Wno-unused-parameter",
        ]);
        cc_cmd.arg(src_dir.join("float_input.c"));
        cc_cmd.arg("-o");
        cc_cmd.arg(&temp_so);
        cc_cmd.args(&flags);

        let status = cc_cmd.status().map_err(|e| format!("cc invocation failed: {}", e))?;
        if !status.success() {
            let _ = fs::remove_file(&temp_so);
            return Err("C compiler failed to compile keyboard.so".into());
        }

        fs::rename(&temp_so, &out).map_err(|e| {
            let _ = fs::remove_file(&temp_so);
            format!("Failed to rename keyboard.so: {}", e)
        })?;
    }

    Ok(out)
}
