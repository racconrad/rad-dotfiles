use std::io;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

use crate::util::{paths, watch::FileLock};

fn qs() -> Command {
    let mut command = Command::new("qs");
    command.args(["-c", "raccon"]).stdin(Stdio::null());
    command
}

pub fn qs_ipc(function: &str, args: &[&str]) -> Result<String, String> {
    let output = qs()
        .args(["ipc", "call", "raccon", function])
        .args(args)
        .output()
        .map_err(qs_error)?;
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if output.status.success() {
        return Ok(stdout);
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    let message = [stderr.trim(), stdout.as_str()]
        .into_iter()
        .find(|s| !s.is_empty())
        .unwrap_or("Quickshell IPC did not respond.");
    Err(message.into())
}

pub fn qs_ensure() -> Result<(), String> {
    if qs_ipc("ping", &[]).is_ok() {
        return Ok(());
    }
    let _lock = FileLock::lock(&paths::runtime_root().join("raccon-quickshell-start.lock"))
        .ok_or("Could not lock Quickshell startup.")?;
    if qs_ipc("ping", &[]).is_ok() {
        return Ok(());
    }

    qs().args(["--no-duplicate", "--daemonize"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map_err(qs_error)?;
    // The instance can exist before its QML handler is registered.
    for _ in 0..40 {
        if qs_ipc("ping", &[]).is_ok() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(50));
    }
    Err("The raccon Quickshell instance did not respond; check qs -c raccon log.".into())
}

fn qs_error(error: io::Error) -> String {
    format!("Could not run qs: {error}")
}
