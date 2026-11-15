use std::ffi::CString;
use std::os::unix::ffi::OsStrExt;
use std::path::Path;

pub const PAGES: &[(&str, &str)] = &[
    ("home", "0"),
    ("apps", "1"),
    ("modes", "2"),
    ("session", "3"),
    ("audio", "4"),
    ("connections", "5"),
    ("bluetooth", "6"),
    ("calendar", "7"),
    ("shortcuts", "8"),
    ("timer", "9"),
];

pub fn page_index(name: &str) -> Option<&'static str> {
    PAGES
        .iter()
        .find(|(k, _)| *k == name)
        .map(|(_, v)| *v)
}

pub fn parse_request(args: &[String]) -> Option<String> {
    if args.is_empty() || (args.len() == 1 && args[0] == "toggle") {
        return Some("toggle".to_string());
    }
    if args.len() == 1 {
        if let Some(idx) = page_index(&args[0]) {
            return Some(format!("show {}", idx));
        }
        if args[0] == "close" {
            return Some("hide".to_string());
        }
    }
    if args.len() == 2 {
        if args[0] == "tab" {
            if let Some(idx) = page_index(&args[1]) {
                return Some(format!("tab {}", idx));
            }
        }
        if args[0] == "close" && args[1] == "super" {
            return Some("hide-super".to_string());
        }
    }
    None
}

pub fn send(command: &str, runtime_dir: &Path) -> bool {
    let mapped_file = runtime_dir.join("mapped");
    if !mapped_file.exists() {
        return false;
    }

    let control_pipe = runtime_dir.join("control");
    let c_path = match CString::new(control_pipe.as_os_str().as_bytes()) {
        Ok(p) => p,
        Err(_) => return false,
    };

    unsafe {
        let fd = libc::open(
            c_path.as_ptr(),
            libc::O_WRONLY | libc::O_NONBLOCK | libc::O_NOFOLLOW,
        );
        if fd < 0 {
            return false;
        }

        let mut stat_buf: libc::stat = std::mem::zeroed();
        if libc::fstat(fd, &mut stat_buf) != 0 {
            libc::close(fd);
            return false;
        }

        // Verify it is a FIFO owned by current user
        if (stat_buf.st_mode & libc::S_IFMT) != libc::S_IFIFO || stat_buf.st_uid != libc::getuid() {
            libc::close(fd);
            return false;
        }

        let payload = format!("{}\n", command);
        let written = libc::write(
            fd,
            payload.as_ptr() as *const libc::c_void,
            payload.len(),
        );
        libc::close(fd);

        written == payload.len() as isize
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_request() {
        assert_eq!(parse_request(&[]), Some("toggle".to_string()));
        assert_eq!(parse_request(&["toggle".to_string()]), Some("toggle".to_string()));
        assert_eq!(parse_request(&["apps".to_string()]), Some("show 1".to_string()));
        assert_eq!(parse_request(&["tab".to_string(), "session".to_string()]), Some("tab 3".to_string()));
        assert_eq!(parse_request(&["close".to_string()]), Some("hide".to_string()));
        assert_eq!(parse_request(&["close".to_string(), "super".to_string()]), Some("hide-super".to_string()));
        assert_eq!(parse_request(&["unknown".to_string()]), None);
    }

    #[test]
    fn test_page_index() {
        assert_eq!(page_index("home"), Some("0"));
        assert_eq!(page_index("apps"), Some("1"));
        assert_eq!(page_index("modes"), Some("2"));
        assert_eq!(page_index("shortcuts"), Some("8"));
        assert_eq!(page_index("timer"), Some("9"));
        assert_eq!(page_index("invalid"), None);
    }
}

