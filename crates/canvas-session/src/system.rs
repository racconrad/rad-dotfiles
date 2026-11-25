use crate::process::{run_checked, which};
use crate::resources::{Host, Resources};
use anyhow::{bail, Result};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

pub struct Live;

impl Host for Live {
    fn which(&self, name: &str) -> Option<PathBuf> {
        which(name)
    }

    fn control(&self, command: &Path, profile: &str, action: &str) -> Result<()> {
        run_checked(
            Command::new(command).args(["--config", profile, action]).stdin(Stdio::null()).stdout(Stdio::null()),
            Duration::from_secs(15),
        )
    }

    fn spawn_tiler(&self, path: &Path) -> Result<()> {
        use std::os::unix::process::CommandExt;
        // A new session keeps the watcher alive after this tool exits.
        Command::new(path).arg("watch").stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).process_group(0).spawn()?;
        Ok(())
    }

    // A pidfd keeps pid reuse between verification and signalling harmless.
    fn terminate(&self, pid: i64, same: &dyn Fn() -> bool) -> Result<()> {
        let fd = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) } as i32;
        if fd < 0 {
            let error = std::io::Error::last_os_error();
            if error.raw_os_error() == Some(libc::ESRCH) {
                return Ok(());
            }
            bail!(error);
        }
        let result = if same() {
            let sent = unsafe { libc::syscall(libc::SYS_pidfd_send_signal, fd, libc::SIGTERM, 0, 0) };
            if sent < 0 { Err(std::io::Error::last_os_error()) } else { Ok(()) }
        } else {
            Ok(())
        };
        unsafe { libc::close(fd) };
        match result {
            Err(e) if e.raw_os_error() != Some(libc::ESRCH) => bail!(e),
            _ => Ok(()),
        }
    }
}

// The widget resources of the real session: /proc, the user's home and the managed profile.
pub fn live_resources(host: &Live) -> Resources<'_> {
    Resources {
        proc_root: PathBuf::from("/proc"),
        home: dirs_home(),
        config: std::env::var_os("RANDLY_WIDGETS_CONFIG").map(PathBuf::from),
        uid: unsafe { libc::getuid() },
        own_pid: std::process::id(),
        drain: Duration::from_secs(2),
        host,
    }
}

pub fn dirs_home() -> PathBuf {
    std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("/"))
}

pub fn sync_config(ini: &Path) -> Result<()> {
    if ini == dirs_home().join(".config/wayfire/user.ini") {
        run_checked(Command::new("wayfire-config").arg("sync").stdin(Stdio::null()).stdout(Stdio::null()),
            Duration::from_secs(10))?;
    }
    Ok(())
}
