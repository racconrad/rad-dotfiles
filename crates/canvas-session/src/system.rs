use crate::process::run_checked;
use anyhow::Result;
use std::process::{Command, Stdio};
use std::time::Duration;

pub fn sync_config() -> Result<()> {
    run_checked(
        Command::new("hyprctl").arg("reload").stdin(Stdio::null()),
        Duration::from_secs(10),
    )
}
