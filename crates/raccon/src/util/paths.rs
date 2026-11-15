use std::path::PathBuf;

pub fn home_dir() -> PathBuf {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/"))
}

pub fn runtime_dir() -> PathBuf {
    if let Some(xdg) = std::env::var_os("XDG_RUNTIME_DIR") {
        PathBuf::from(xdg).join("raccon-menu")
    } else {
        home_dir().join(".cache").join("raccon-menu")
    }
}

pub fn state_dir() -> PathBuf {
    if let Some(xdg) = std::env::var_os("XDG_STATE_HOME") {
        PathBuf::from(xdg).join("raccon-menu")
    } else {
        home_dir().join(".local").join("state").join("raccon-menu")
    }
}

pub fn share_dir() -> PathBuf {
    if let Some(xdg) = std::env::var_os("XDG_DATA_HOME") {
        PathBuf::from(xdg).join("desktop-menu")
    } else {
        home_dir().join(".local").join("share").join("desktop-menu")
    }
}

pub fn config_dir() -> PathBuf {
    if let Some(xdg) = std::env::var_os("XDG_CONFIG_HOME") {
        PathBuf::from(xdg).join("raccon-menu")
    } else {
        home_dir().join(".config").join("raccon-menu")
    }
}
