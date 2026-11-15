use std::fs::{self, File, Permissions};
use std::io::{self, Write};
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

pub fn write_atomic(path: &Path, content: &[u8]) -> io::Result<()> {
    write_atomic_with_mode(path, content, 0o644)
}

pub fn write_atomic_with_mode(path: &Path, content: &[u8], mode: u32) -> io::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let pid = std::process::id();
    let temp_name = format!(
        ".{}.tmp.{}",
        path.file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("file"),
        pid
    );
    let temp_path = path.with_file_name(temp_name);

    {
        let mut file = File::create(&temp_path)?;
        fs::set_permissions(&temp_path, Permissions::from_mode(mode))?;
        file.write_all(content)?;
        file.sync_all()?;
    }

    fs::rename(&temp_path, path).map_err(|err| {
        let _ = fs::remove_file(&temp_path);
        err
    })
}
