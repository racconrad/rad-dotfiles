use anyhow::{bail, Result};
use std::process::{Child, Command, ExitStatus};
use std::time::{Duration, Instant};

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
