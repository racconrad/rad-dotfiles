//! Hyprland command socket client. One short connection per request, no process forks.

use crate::json::{self, Json};
use std::io::{self, Read, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::time::Duration;

const TIMEOUT: Duration = Duration::from_secs(2);

pub struct Hypr {
    dir: PathBuf,
}

impl Hypr {
    pub fn from_env() -> io::Result<Self> {
        let get = |k: &str| std::env::var(k).map_err(|_| io::Error::new(io::ErrorKind::NotFound, format!("{k} is not set")));
        Ok(Self::at(PathBuf::from(get("XDG_RUNTIME_DIR")?).join("hypr").join(get("HYPRLAND_INSTANCE_SIGNATURE")?)))
    }

    pub fn at(dir: PathBuf) -> Self {
        Self { dir }
    }

    fn request(&self, payload: &str) -> io::Result<String> {
        let mut s = UnixStream::connect(self.dir.join(".socket.sock"))?;
        s.set_read_timeout(Some(TIMEOUT))?;
        s.set_write_timeout(Some(TIMEOUT))?;
        s.write_all(payload.as_bytes())?;
        let mut out = Vec::new();
        s.read_to_end(&mut out)?;
        Ok(String::from_utf8_lossy(&out).into_owned())
    }

    /// Read-only query: "clients", "monitors", "activewindow", "cursorpos".
    pub fn json(&self, what: &str) -> io::Result<Json> {
        let text = self.request(&format!("j/{what}"))?;
        json::parse(&text).ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, format!("bad reply to {what}")))
    }

    /// All expressions in one request, so Hyprland starts their animations in the same frame.
    pub fn batch(&self, exprs: &[String]) -> io::Result<()> {
        if exprs.is_empty() {
            return Ok(());
        }
        let mut payload = String::from("[[BATCH]]");
        for (i, e) in exprs.iter().enumerate() {
            if i > 0 {
                payload.push(';');
            }
            payload.push_str("/dispatch ");
            payload.push_str(e);
        }
        let reply = self.request(&payload)?;
        match reply.lines().find(|l| l.starts_with("error")) {
            Some(err) => Err(io::Error::new(io::ErrorKind::Other, err.to_string())),
            None => Ok(()),
        }
    }

    pub fn events(&self) -> io::Result<UnixStream> {
        UnixStream::connect(self.dir.join(".socket2.sock"))
    }
}

/// Window addresses come from Hyprland, but they end up inside a Lua expression: keep them to hex.
fn safe(addr: &str) -> &str {
    if addr.starts_with("0x") && addr[2..].bytes().all(|b| b.is_ascii_hexdigit()) { addr } else { "0x0" }
}

pub fn move_expr(addr: &str, x: i32, y: i32) -> String {
    format!(r#"hl.dsp.window.move({{ window = "address:{}", x = {x}, y = {y}, relative = false }})"#, safe(addr))
}

pub fn focus_expr(addr: &str) -> String {
    format!(r#"hl.dsp.focus({{ window = "address:{}" }})"#, safe(addr))
}

pub fn focus_direction_expr(dir: &str) -> String {
    format!(r#"hl.dsp.focus({{ direction = "{dir}" }})"#)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expressions_never_carry_non_hex_addresses() {
        assert!(move_expr("0xabc", 1, -2).contains(r#"address:0xabc", x = 1, y = -2"#));
        assert!(focus_expr("0x1\"}); os.exit()--").contains("address:0x0"));
    }
}
