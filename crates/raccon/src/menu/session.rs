use std::process::Command;

pub fn execute(action: &str) -> Result<(), String> {
    match action {
        "suspend" => {
            Command::new("systemctl")
                .arg("suspend")
                .spawn()
                .map_err(|e| e.to_string())?;
        }
        "reboot" => {
            Command::new("systemctl")
                .arg("reboot")
                .spawn()
                .map_err(|e| e.to_string())?;
        }
        "poweroff" => {
            Command::new("systemctl")
                .arg("poweroff")
                .spawn()
                .map_err(|e| e.to_string())?;
        }
        "logout" => {
            let user = std::env::var("USER").unwrap_or_default();
            Command::new("loginctl")
                .args(["terminate-user", &user])
                .spawn()
                .map_err(|e| e.to_string())?;
        }
        "cancel" => {}
        _ => return Err(format!("Unknown session action: {}", action)),
    }
    Ok(())
}
