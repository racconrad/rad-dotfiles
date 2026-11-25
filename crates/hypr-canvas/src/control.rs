//! The control socket: the CLI sends one line, the daemon answers with one line.

use crate::nav::Dir;
use std::io::{self, Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::PathBuf;
use std::time::Duration;

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum DragMode {
    Pan,  // drag the empty desktop: every window follows the cursor
    Edge, // drag a window: at a screen edge the others are pushed the other way
}

#[derive(Debug, PartialEq, Eq)]
pub enum Cmd {
    Pan(Dir, Option<i32>),
    Look(Dir),
    Move(Dir),
    Center,
    Home,
    Back,
    DragStart(DragMode),
    DragEnd,
    Status,
    Quit,
}

pub fn parse(line: &str) -> Result<Cmd, String> {
    let mut words = line.split_whitespace();
    let name = words.next().ok_or("empty command")?;
    let arg = words.next();
    let dir = || arg.and_then(Dir::parse).ok_or_else(|| format!("{name} needs left|right|up|down"));
    match name {
        "pan" => Ok(Cmd::Pan(dir()?, words.next().and_then(|p| p.parse().ok()))),
        "look" => Ok(Cmd::Look(dir()?)),
        "move" => Ok(Cmd::Move(dir()?)),
        "center" => Ok(Cmd::Center),
        "home" => Ok(Cmd::Home),
        "back" => Ok(Cmd::Back),
        "drag-start" => match arg {
            Some("pan") => Ok(Cmd::DragStart(DragMode::Pan)),
            Some("edge") => Ok(Cmd::DragStart(DragMode::Edge)),
            _ => Err("drag-start needs pan|edge".into()),
        },
        "drag-end" => Ok(Cmd::DragEnd),
        "status" => Ok(Cmd::Status),
        "quit" => Ok(Cmd::Quit),
        other => Err(format!("unknown command '{other}'")),
    }
}

pub fn socket_path() -> PathBuf {
    PathBuf::from(std::env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/tmp".into())).join("hypr-canvas.sock")
}

/// Binds the control socket; fails if another daemon already answers on it.
pub fn listen(path: &PathBuf) -> io::Result<UnixListener> {
    if UnixStream::connect(path).is_ok() {
        return Err(io::Error::new(io::ErrorKind::AddrInUse, "hypr-canvas is already running"));
    }
    let _ = std::fs::remove_file(path);
    let listener = UnixListener::bind(path)?;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
    Ok(listener)
}

pub fn send(line: &str) -> io::Result<String> {
    let mut s = UnixStream::connect(socket_path())?;
    s.set_read_timeout(Some(Duration::from_secs(3)))?;
    s.write_all(line.as_bytes())?;
    s.shutdown(std::net::Shutdown::Write)?;
    let mut reply = String::new();
    s.read_to_string(&mut reply)?;
    Ok(reply)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_commands() {
        assert_eq!(parse("pan left 120"), Ok(Cmd::Pan(Dir::Left, Some(120))));
        assert_eq!(parse("pan up"), Ok(Cmd::Pan(Dir::Up, None)));
        assert_eq!(parse("look r\n"), Ok(Cmd::Look(Dir::Right)));
        assert_eq!(parse("drag-start edge"), Ok(Cmd::DragStart(DragMode::Edge)));
        assert!(parse("pan sideways").is_err());
        assert!(parse("").is_err());
        assert!(parse("explode").is_err());
    }
}
