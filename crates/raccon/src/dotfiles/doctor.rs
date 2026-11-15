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

    checks
}
