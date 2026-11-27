use std::collections::HashMap;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use crate::util::atomic::write_atomic_with_mode;

pub fn contains_secret(text: &str) -> bool {
    let patterns = [
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "ghp_",
        "github_pat_",
        "AIzaSy",
        "AKIA",
        "Bearer ",
    ];

    for pattern in patterns {
        if text.contains(pattern) {
            return true;
        }
    }
    false
}

pub fn sanitize(relative: &str, text: &str, home: &Path) -> Result<String, String> {
    if contains_secret(text) {
        return Err(format!(
            "Secret/credential pattern detected in {}; capture aborted for security.",
            relative
        ));
    }

    let home_str = home.to_string_lossy();
    let mut sanitized = text.replace(&*home_str, "@RDOT_HOME@");

    // Replace wallpaper paths
    let wallpaper_placeholder = "@RDOT_HOME@/Pictures/Wallpapers/wallpaper.png";
    if sanitized.contains("@RDOT_HOME@/Pictures/Wallpapers/") {
        // Simple normalization for wallpapers
        let lines: Vec<String> = sanitized
            .lines()
            .map(|line| {
                if line.contains("@RDOT_HOME@/Pictures/Wallpapers/") && (line.contains("wallpaper") || line.contains("file")) {
                    if let Some((k, _)) = line.split_once('=') {
                        return format!("{} = {}", k.trim(), wallpaper_placeholder);
                    }
                }
                line.to_string()
            })
            .collect();
        sanitized = lines.join("\n") + "\n";
    }

    Ok(sanitized)
}

pub fn capture_file(
    source_home_path: &Path,
    dest_repo_path: &Path,
    relative: &str,
    home: &Path,
    dry_run: bool,
) -> Result<bool, String> {
    if !source_home_path.exists() {
        return Ok(false);
    }

    let raw = fs::read(source_home_path)
        .map_err(|e| format!("Could not read source file {}: {}", source_home_path.display(), e))?;

    let (content_to_write, mode) = match std::str::from_utf8(&raw) {
        Ok(text) => {
            let sanitized = sanitize(relative, text, home)?;
            let mode = fs::metadata(source_home_path)
                .map(|m| m.permissions().mode() & 0o777)
                .unwrap_or(0o644);
            (sanitized.into_bytes(), mode)
        }
        Err(_) => {
            // Binary file (copy as-is)
            let mode = fs::metadata(source_home_path)
                .map(|m| m.permissions().mode() & 0o777)
                .unwrap_or(0o644);
            (raw, mode)
        }
    };

    let needs_write = match fs::read(dest_repo_path) {
        Ok(existing) => existing != content_to_write,
        Err(_) => true,
    };

    if !needs_write {
        return Ok(false);
    }

    if dry_run {
        println!("  [dry-run capture] {} -> {}", source_home_path.display(), dest_repo_path.display());
        return Ok(true);
    }

    write_atomic_with_mode(dest_repo_path, &content_to_write, mode)
        .map_err(|e| format!("Failed to write captured file: {}", e))?;

    println!("  [captured] {}", relative);
    Ok(true)
}

pub fn capture_module_configs(
    root: &Path,
    home: &Path,
    modules: &[String],
    dry_run: bool,
) -> Result<usize, String> {
    let mut captured_count = 0;

    let config_targets: HashMap<&str, &[&str]> = HashMap::from([
        ("hyprland", &[
            ".config/hypr/conf/animations.lua",
            ".config/hypr/conf/autostart.lua",
            ".config/hypr/conf/binds/apps.lua",
            ".config/hypr/conf/binds/canvas.lua",
            ".config/hypr/conf/binds/media.lua",
            ".config/hypr/conf/binds/windows.lua",
            ".config/hypr/conf/binds/workspaces.lua",
            ".config/hypr/conf/environment.lua",
            ".config/hypr/conf/input.lua",
            ".config/hypr/conf/layouts.lua",
            ".config/hypr/conf/look.lua",
            ".config/hypr/conf/monitors.lua",
            ".config/hypr/conf/programs.lua",
            ".config/hypr/conf/rules.lua",
            ".config/hypr/conf/window-style.lua",
            ".config/hypr/hypridle.conf",
            ".config/hypr/hyprland.lua",
            ".config/hypr/shortcuts.md",
        ][..]),
        ("quickshell", &[".config/quickshell/raccon/shell.qml"][..]),
        ("power", &[".config/desktop-power/config.toml"][..]),
        ("themes", &[".config/matugen/config.toml"][..]),
        ("kitty", &[".config/kitty/kitty.conf"][..]),
        ("alacritty", &[".config/alacritty/alacritty.toml"][..]),
        ("fuzzel", &[".config/fuzzel/fuzzel.ini"][..]),
        ("swaync", &[".config/swaync/config.json", ".config/swaync/style.css"][..]),
    ]);

    for module in modules {
        if let Some(files) = config_targets.get(module.as_str()) {
            for rel in *files {
                let source = home.join(rel);
                let dest = root.join("modules").join(module).join("files").join(rel);

                if source.exists() {
                    if capture_file(&source, &dest, rel, home, dry_run)? {
                        captured_count += 1;
                    }
                }
            }
        }
    }

    Ok(captured_count)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_secret_detection() {
        assert!(contains_secret("Bearer eyJhbGciOi..."));
        assert!(contains_secret("ghp_1234567890abcdef"));
        assert!(!contains_secret("normal configuration text"));
    }

    #[test]
    fn test_path_sanitization() {
        let home = Path::new("/home/testuser");
        let content = "config_dir = /home/testuser/.config/myapp";
        let sanitized = sanitize("config.ini", content, home).unwrap();
        assert_eq!(sanitized, "config_dir = @RDOT_HOME@/.config/myapp");
    }
}
