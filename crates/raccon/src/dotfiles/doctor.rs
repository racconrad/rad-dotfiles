use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use crate::dotfiles::installer::sha256_digest;
use crate::dotfiles::receipt::read_receipt;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticCheck {
    pub category: String,
    pub name: String,
    pub status: String, // "ok", "warn", "fail"
    pub detail: String,
    pub hint: String,
}

pub fn observe_processes() -> (HashSet<String>, bool) {
    let mut observed = HashSet::new();
    let mut incomplete = false;
    let proc_path = Path::new("/proc");

    let entries = match fs::read_dir(proc_path) {
        Ok(e) => e,
        Err(_) => return (observed, true),
    };

    let uid = unsafe { libc::getuid() };

    for entry in entries.filter_map(|e| e.ok()) {
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if !name_str.chars().all(|c| c.is_ascii_digit()) {
            continue;
        }

        let pid_path = entry.path();
        if let Ok(meta) = fs::metadata(&pid_path) {
            use std::os::unix::fs::MetadataExt;
            if meta.uid() == uid {
                let comm_path = pid_path.join("comm");
                if let Ok(comm) = fs::read_to_string(comm_path) {
                    observed.insert(comm.trim().to_string());
                }
            }
        } else {
            incomplete = true;
        }
    }

    (observed, incomplete)
}

pub fn which(executable: &str) -> bool {
    if let Ok(path_var) = std::env::var("PATH") {
        for dir in path_var.split(':') {
            let candidate = Path::new(dir).join(executable);
            if candidate.is_file() {
                if let Ok(meta) = candidate.metadata() {
                    if (meta.permissions().mode() & 0o111) != 0 {
                        return true;
                    }
                }
            }
        }
    }
    false
}

pub fn check_qs_raccon_process(proc_path: &Path, uid: u32) -> bool {
    let entries = match fs::read_dir(proc_path) {
        Ok(e) => e,
        Err(_) => return false,
    };

    for entry in entries.filter_map(|e| e.ok()) {
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if !name_str.chars().all(|c| c.is_ascii_digit()) {
            continue;
        }

        let pid_path = entry.path();
        if let Ok(meta) = fs::metadata(&pid_path) {
            use std::os::unix::fs::MetadataExt;
            if meta.uid() == uid {
                let cmdline_path = pid_path.join("cmdline");
                if let Ok(bytes) = fs::read(cmdline_path) {
                    let args: Vec<&str> = bytes
                        .split(|&b| b == 0)
                        .filter(|s| !s.is_empty())
                        .filter_map(|s| std::str::from_utf8(s).ok())
                        .collect();
                    if args
                        .first()
                        .is_some_and(|a| Path::new(a).file_name().is_some_and(|f| f == "qs"))
                        && args.windows(2).any(|w| w[0] == "-c" && w[1] == "raccon")
                    {
                        return true;
                    }
                }
            }
        }
    }
    false
}

pub fn is_qs_raccon_running() -> bool {
    let uid = unsafe { libc::getuid() };
    check_qs_raccon_process(Path::new("/proc"), uid)
}

pub fn check_qs_executable() -> DiagnosticCheck {
    let found = which("qs");
    DiagnosticCheck {
        category: "Executables".into(),
        name: "qs".into(),
        status: if found { "ok".into() } else { "warn".into() },
        detail: if found {
            "Available in PATH".into()
        } else {
            "Missing in PATH".into()
        },
        hint: if found {
            String::new()
        } else {
            "Install package providing qs".into()
        },
    }
}

pub fn check_qs_process() -> DiagnosticCheck {
    let running = is_qs_raccon_running();
    DiagnosticCheck {
        category: "Runtime".into(),
        name: "qs -c raccon".into(),
        status: if running { "ok".into() } else { "warn".into() },
        detail: if running {
            "Running".into()
        } else {
            "Not running in active user session".into()
        },
        hint: if running {
            String::new()
        } else {
            "Start quickshell with: qs -c raccon".into()
        },
    }
}

pub fn check_hypr_canvas(home: &Path) -> DiagnosticCheck {
    let canvas_path = home.join(".local/bin/hypr-canvas");
    let found = canvas_path.is_file();
    DiagnosticCheck {
        category: "Executables".into(),
        name: "hypr-canvas".into(),
        status: if found { "ok".into() } else { "warn".into() },
        detail: if found {
            "Available in ~/.local/bin".into()
        } else {
            "Missing in ~/.local/bin".into()
        },
        hint: if found {
            String::new()
        } else {
            "Install hypr-canvas to ~/.local/bin".into()
        },
    }
}

pub fn check_quickshell_colors(home: &Path) -> DiagnosticCheck {
    let path = home.join(".config/quickshell/raccon/colors.json");
    if !path.exists() {
        DiagnosticCheck {
            category: "Files".into(),
            name: "quickshell colors.json".into(),
            status: "warn".into(),
            detail: "Missing ~/.config/quickshell/raccon/colors.json".into(),
            hint: "Generate palette with matugen / desktop-style".into(),
        }
    } else {
        match fs::read_to_string(&path) {
            Ok(content) => match serde_json::from_str::<serde_json::Value>(&content) {
                Ok(_) => DiagnosticCheck {
                    category: "Files".into(),
                    name: "quickshell colors.json".into(),
                    status: "ok".into(),
                    detail: "Valid JSON configuration".into(),
                    hint: String::new(),
                },
                Err(err) => DiagnosticCheck {
                    category: "Files".into(),
                    name: "quickshell colors.json".into(),
                    status: "warn".into(),
                    detail: format!("Invalid JSON: {}", err),
                    hint: "Regenerate colors.json with matugen".into(),
                },
            },
            Err(err) => DiagnosticCheck {
                category: "Files".into(),
                name: "quickshell colors.json".into(),
                status: "warn".into(),
                detail: format!("Could not read: {}", err),
                hint: "Check file permissions".into(),
            },
        }
    }
}

pub fn diagnose(home: &Path) -> Vec<DiagnosticCheck> {
    let mut checks = Vec::new();

    let receipt = match read_receipt(home) {
        Some(r) => r,
        None => {
            checks.push(DiagnosticCheck {
                category: "Installation".into(),
                name: "Installed components".into(),
                status: "warn".into(),
                detail: "Unknown: no installation receipt found (~/.rdot).".into(),
                hint: "Run 'raccon install' to install dotfiles and generate a receipt.".into(),
            });
            return checks;
        }
    };

    checks.push(DiagnosticCheck {
        category: "Installation".into(),
        name: "Receipt".into(),
        status: "ok".into(),
        detail: format!("Version {}; {} modules recorded.", receipt.version, receipt.modules.len()),
        hint: String::new(),
    });

    // Check files integrity
    let mut modified = 0;
    let mut missing = 0;

    for (rel, entry) in &receipt.files {
        let target = home.join(rel);
        if !target.exists() {
            missing += 1;
        } else if let Ok(data) = fs::read(&target) {
            let hash = sha256_digest(&data);
            if hash != entry.sha256 {
                modified += 1;
            }
        } else {
            modified += 1;
        }
    }

    if missing > 0 || modified > 0 {
        checks.push(DiagnosticCheck {
            category: "Files".into(),
            name: "Integrity".into(),
            status: "warn".into(),
            detail: format!("{} missing, {} modified locally.", missing, modified),
            hint: "Run 'raccon update' to refresh module files.".into(),
        });
    } else {
        checks.push(DiagnosticCheck {
            category: "Files".into(),
            name: "Integrity".into(),
            status: "ok".into(),
            detail: format!("All {} tracked files verified.", receipt.files.len()),
            hint: String::new(),
        });
    }

    // Process checks
    let (procs, _) = observe_processes();
    for proc_name in ["wayfire", "waybar"] {
        if receipt.modules.iter().any(|m| m == proc_name) {
            let running = procs.contains(proc_name);
            checks.push(DiagnosticCheck {
                category: "Runtime".into(),
                name: proc_name.into(),
                status: if running { "ok".into() } else { "warn".into() },
                detail: if running { "Running".into() } else { "Not running in active user session".into() },
                hint: if running { String::new() } else { "Inspect session logs".into() },
            });
        }
    }

    // Executables checks
    let exec_map: &[(&str, &[&str])] = &[
        ("wayfire", &["wayfire"]),
        ("waybar", &["waybar"]),
        ("desktop", &["eww"]),
        ("nvim", &["nvim"]),
        ("kitty", &["kitty"]),
    ];

    for (module, bins) in exec_map {
        if receipt.modules.iter().any(|m| m == *module) {
            for bin in *bins {
                let found = which(bin);
                checks.push(DiagnosticCheck {
                    category: "Executables".into(),
                    name: bin.to_string(),
                    status: if found { "ok".into() } else { "warn".into() },
                    detail: if found { "Available in PATH".into() } else { "Missing in PATH".into() },
                    hint: if found { String::new() } else { format!("Install package providing {}", bin) },
                });
            }
        }
    }

    // Quickshell and desktop runtime checks
    checks.push(check_qs_executable());
    checks.push(check_qs_process());
    checks.push(check_hypr_canvas(home));
    checks.push(check_quickshell_colors(home));

    checks
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    struct TempTestDir(PathBuf);
    impl TempTestDir {
        fn new(name: &str) -> Self {
            let p = std::env::temp_dir().join(format!(
                "raccon_doc_test_{}_{}_{}",
                name,
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            let _ = fs::remove_dir_all(&p);
            fs::create_dir_all(&p).unwrap();
            Self(p)
        }
        fn path(&self) -> &Path {
            &self.0
        }
    }
    impl Drop for TempTestDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn test_check_quickshell_colors_valid() {
        let dir = TempTestDir::new("colors_valid");
        let colors_dir = dir.path().join(".config/quickshell/raccon");
        fs::create_dir_all(&colors_dir).unwrap();
        fs::write(
            colors_dir.join("colors.json"),
            "{\"surface\": \"#121212\", \"primary\": \"#e5485d\"}",
        )
        .unwrap();

        let check = check_quickshell_colors(dir.path());
        assert_eq!(check.status, "ok");
        assert_eq!(check.detail, "Valid JSON configuration");
    }

    #[test]
    fn test_check_quickshell_colors_missing() {
        let dir = TempTestDir::new("colors_missing");
        let check = check_quickshell_colors(dir.path());
        assert_eq!(check.status, "warn");
        assert!(check.detail.contains("Missing"));
    }

    #[test]
    fn test_check_quickshell_colors_invalid_json() {
        let dir = TempTestDir::new("colors_invalid");
        let colors_dir = dir.path().join(".config/quickshell/raccon");
        fs::create_dir_all(&colors_dir).unwrap();
        fs::write(colors_dir.join("colors.json"), "{ invalid json").unwrap();

        let check = check_quickshell_colors(dir.path());
        assert_eq!(check.status, "warn");
        assert!(check.detail.contains("Invalid JSON"));
    }

    #[test]
    fn test_check_hypr_canvas() {
        let dir = TempTestDir::new("canvas");
        let check_missing = check_hypr_canvas(dir.path());
        assert_eq!(check_missing.status, "warn");

        let bin_dir = dir.path().join(".local/bin");
        fs::create_dir_all(&bin_dir).unwrap();
        fs::write(bin_dir.join("hypr-canvas"), "#!/bin/sh\n").unwrap();

        let check_found = check_hypr_canvas(dir.path());
        assert_eq!(check_found.status, "ok");
    }

    #[test]
    fn test_check_qs_raccon_process() {
        let dir = TempTestDir::new("qs_proc");
        let pid_dir = dir.path().join("99999");
        fs::create_dir_all(&pid_dir).unwrap();
        fs::write(pid_dir.join("cmdline"), b"qs\0-c\0raccon\0--no-duplicate\0").unwrap();

        let uid = unsafe { libc::getuid() };
        assert!(check_qs_raccon_process(dir.path(), uid));

        // Test non-matching process
        let other_dir = TempTestDir::new("qs_other");
        let other_pid = other_dir.path().join("99998");
        fs::create_dir_all(&other_pid).unwrap();
        fs::write(other_pid.join("cmdline"), b"bash\0-c\0echo hi\0").unwrap();
        assert!(!check_qs_raccon_process(other_dir.path(), uid));
    }
}
