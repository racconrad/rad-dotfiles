use std::collections::BTreeSet;
use std::ffi::CString;
use std::os::unix::ffi::OsStrExt;
use std::os::unix::io::{AsRawFd, RawFd};
use std::path::{Path, PathBuf};

/// Linux inotify watcher over parent directories of tracked paths.
pub struct DirWatch {
    fd: RawFd,
}

impl DirWatch {
    pub fn new(files: &[PathBuf], dirs: &[PathBuf]) -> Self {
        let fd = unsafe { libc::inotify_init1(libc::IN_NONBLOCK | libc::IN_CLOEXEC) };
        let w = Self { fd };
        if fd < 0 {
            return w;
        }
        let mut unique = BTreeSet::new();
        for f in files {
            if let Some(p) = f.parent() {
                unique.insert(p.to_path_buf());
            }
        }
        for d in dirs {
            unique.insert(d.clone());
        }
        let mask = libc::IN_CLOSE_WRITE
            | libc::IN_MOVED_TO
            | libc::IN_CREATE
            | libc::IN_DELETE
            | libc::IN_MODIFY
            | libc::IN_ATTRIB;
        for dir in unique {
            let _ = std::fs::create_dir_all(&dir);
            if let Ok(c) = CString::new(dir.as_os_str().as_bytes()) {
                unsafe {
                    libc::inotify_add_watch(fd, c.as_ptr(), mask);
                }
            }
        }
        w
    }

    pub fn raw_fd(&self) -> RawFd {
        self.fd
    }

    pub fn drain(&self) -> bool {
        if self.fd < 0 {
            return false;
        }
        let mut buf = [0u8; 4096];
        let mut any = false;
        loop {
            let n = unsafe { libc::read(self.fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len()) };
            if n > 0 {
                any = true;
            } else {
                break;
            }
        }
        any
    }

    pub fn wait(&self, timeout_ms: i32) {
        if self.fd < 0 {
            let sleep_ms = if timeout_ms < 0 { 250 } else { timeout_ms.min(500) };
            std::thread::sleep(std::time::Duration::from_millis(sleep_ms as u64));
            return;
        }
        let mut pfd = libc::pollfd {
            fd: self.fd,
            events: libc::POLLIN,
            revents: 0,
        };
        unsafe {
            libc::poll(&mut pfd, 1, timeout_ms);
        }
        self.drain();
    }
}

impl AsRawFd for DirWatch {
    fn as_raw_fd(&self) -> RawFd {
        self.fd
    }
}

impl Drop for DirWatch {
    fn drop(&mut self) {
        if self.fd >= 0 {
            unsafe {
                libc::close(self.fd);
            }
        }
    }
}

/// Write one JSON line to stdout and return false if the pipe closed cleanly.
pub fn emit_line(line: &str) -> bool {
    use std::io::Write;
    let mut out = std::io::stdout().lock();
    writeln!(out, "{}", line).is_ok() && out.flush().is_ok()
}

/// Set a file descriptor to non-blocking mode.
pub fn set_nonblocking(fd: RawFd) {
    unsafe {
        let flags = libc::fcntl(fd, libc::F_GETFL, 0);
        if flags >= 0 {
            libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK);
        }
    }
}

/// Advisory exclusive file lock guard using flock(2).
pub struct FileLock {
    _file: std::fs::File,
}

impl FileLock {
    pub fn lock(path: &Path) -> Option<Self> {
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let file = std::fs::OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(false)
            .open(path)
            .ok()?;
        let rc = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX) };
        if rc == 0 {
            Some(Self { _file: file })
        } else {
            None
        }
    }

    pub fn try_lock(path: &Path) -> Option<Self> {
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let file = std::fs::OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(false)
            .open(path)
            .ok()?;
        let rc = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
        if rc == 0 {
            Some(Self { _file: file })
        } else {
            None
        }
    }
}
