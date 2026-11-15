use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

use crate::dotfiles::receipt::{write_receipt, Receipt, ReceiptFileEntry};
use crate::util::atomic::write_atomic_with_mode;

pub fn sha256_digest(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();
    result.iter().map(|b| format!("{:02x}", b)).collect()
}

pub fn render(
    relative: &str,
    content: &[u8],
    home: &Path,
    choices: &HashMap<String, String>,
) -> Vec<u8> {
    let text = match std::str::from_utf8(content) {
        Ok(t) => t,
        Err(_) => return content.to_vec(),
    };

    let home_str = home.to_string_lossy();
    let terminal = choices.get("terminal").map(|s| s.as_str()).unwrap_or("kitty");

    let mut rendered = text
        .replace("@RDOT_HOME@", &home_str)
        .replace("@RDOT_TERMINAL@", terminal);

    if relative == ".zshrc" {
        let personal_tag = "# >>> personal (kept on reinstall, never captured)";
        let existing = fs::read_to_string(home.join(".zshrc")).unwrap_or_default();
        if existing.contains(personal_tag) && rendered.contains(personal_tag) {
            if let Some((_, user_part)) = existing.split_once(personal_tag) {
                if let Some((template_part, _)) = rendered.split_once(personal_tag) {
                    rendered = format!("{}{}{}", template_part, personal_tag, user_part);
                }
            }
        }
    }

    rendered.into_bytes()
}

pub fn build_plan(
    root: &Path,
    home: &Path,
    modules: &[String],
    choices: &HashMap<String, String>,
) -> Result<HashMap<String, (Vec<u8>, u32)>, String> {
    let mut plan = HashMap::new();

    for module in modules {
        let base = root.join("modules").join(module).join("files");
        if !base.is_dir() {
            continue;
        }

        for entry in WalkDir::new(&base).into_iter().filter_map(|e| e.ok()) {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }

            let rel_path = match path.strip_prefix(&base) {
                Ok(p) => p.to_string_lossy().to_string(),
                Err(_) => continue,
            };

            if rel_path.contains("__pycache__") || rel_path.ends_with(".pyc") {
                continue;
            }

            let metadata = fs::metadata(path).map_err(|e| e.to_string())?;
            let mode = metadata.permissions().mode() & 0o777;
            let raw_content = fs::read(path).map_err(|e| e.to_string())?;
            let rendered = render(&rel_path, &raw_content, home, choices);

            plan.insert(rel_path, (rendered, mode));
        }
    }

    Ok(plan)
}

pub fn apply_plan(
    home: &Path,
    plan: &HashMap<String, (Vec<u8>, u32)>,
    modules: &[String],
    choices: &HashMap<String, String>,
    dry_run: bool,
) -> Result<Option<PathBuf>, String> {
    let mut changes = Vec::new();

    for (rel, (data, mode)) in plan {
        let target = home.join(rel);
        let needs_write = match fs::read(&target) {
            Ok(existing) => {
                if let Ok(meta) = fs::metadata(&target) {
                    existing != *data || (meta.permissions().mode() & 0o777) != *mode
                } else {
                    true
                }
            }
            Err(_) => true,
        };

        if needs_write {
            changes.push((rel.clone(), data.clone(), *mode));
        }
    }

    if dry_run {
        println!("Dry-run: {} files to write/update. Preview only.", changes.len());
        for (rel, _, _) in &changes {
            println!("  [dry-run] {}", rel);
        }
        return Ok(None);
    }

    if changes.is_empty() {
        println!("All files are up to date.");
        return Ok(None);
    }

    let timestamp = format!(
        "backup-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    );
    let backup_dir = home
        .join(".local")
        .join("state")
        .join("raccon-dots")
        .join("backups")
        .join(&timestamp);

    fs::create_dir_all(&backup_dir).map_err(|e| e.to_string())?;

    for (rel, data, mode) in &changes {
        let target = home.join(rel);
        if target.exists() {
            let backup_file = backup_dir.join(rel);
            if let Some(parent) = backup_file.parent() {
                let _ = fs::create_dir_all(parent);
            }
            let _ = fs::copy(&target, &backup_file);
        }

        write_atomic_with_mode(&target, data, *mode).map_err(|e| {
            format!("Failed to write {}: {}", rel, e)
        })?;
    }

    let mut receipt_files = HashMap::new();
    for (rel, (data, mode)) in plan {
        receipt_files.insert(
            rel.clone(),
            ReceiptFileEntry {
                sha256: sha256_digest(data),
                mode: *mode,
            },
        );
    }

    let receipt = Receipt {
        schema: 1,
        name: "raccon-dots".to_string(),
        version: "0.3.0".to_string(),
        modules: modules.to_vec(),
        choices: choices.clone(),
        files: receipt_files,
        installed_at: Some(chrono_like_now()),
    };

    write_receipt(home, &receipt).map_err(|e| e.to_string())?;

    println!(
        "Successfully installed {} files. Backup created at: {}",
        changes.len(),
        backup_dir.display()
    );

    Ok(Some(backup_dir))
}

fn chrono_like_now() -> String {
    let output = std::process::Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output();
    if let Ok(out) = output {
        let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if !s.is_empty() {
            return s;
        }
    }
    "2026-11-14T00:00:00Z".to_string()
}
