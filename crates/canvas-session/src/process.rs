use anyhow::{bail, Result};
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus};
use std::time::{Duration, Instant};

pub fn which(name: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    std::env::split_paths(&path)
        .map(|dir| dir.join(name))
        .find(|p| p.metadata().is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0))
}

pub fn wait_timeout(child: &mut Child, timeout: Duration) -> Result<ExitStatus> {
    let deadline = Instant::now() + timeout;
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(status);
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            bail!("timed out after {timeout:?}");
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

// Runs the command to completion; a failure status or a timeout is an error.
pub fn run_checked(command: &mut Command, timeout: Duration) -> Result<()> {
    let status = wait_timeout(&mut command.spawn()?, timeout)?;
    if !status.success() {
        bail!("{status}");
    }
    Ok(())
}
