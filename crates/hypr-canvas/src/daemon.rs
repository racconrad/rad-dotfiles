//! The daemon: state plus the command and event handlers, and the poll loop that drives them.
//!
//! The loop blocks in poll(2). With no gesture active it wakes only for a Hyprland event or a CLI
//! command; during a drag it wakes every frame to sample the cursor, and goes back to sleep after.

use crate::canvas::Canvas;
use crate::config::Config;
use crate::control::{self, Cmd, DragMode};
use crate::ipc::{focus_direction_expr, focus_expr, move_expr, Hypr};
use crate::model::{parse_clients, parse_view, Client, Rect, View};
use crate::nav::find_target;
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::time::{Duration, Instant};

const FRAME: Duration = Duration::from_millis(16);
const DRAG_IDLE_LIMIT: Duration = Duration::from_secs(10);

struct Drag {
    mode: DragMode,
    last: (i32, i32),
    view: View,
    dragged: Option<String>,
    acc: (f64, f64),
    last_motion: Instant,
}

pub struct Daemon {
    hypr: Hypr,
    canvas: Canvas,
    cfg: Config,
    drag: Option<Drag>,
}

fn other(msg: &str) -> io::Error {
    io::Error::new(io::ErrorKind::Other, msg.to_string())
}

impl Daemon {
    pub fn new(hypr: Hypr, cfg: Config) -> Self {
        Self { hypr, canvas: Canvas::default(), cfg, drag: None }
    }

    pub fn dragging(&self) -> bool {
        self.drag.is_some()
    }

    fn refresh(&mut self) -> io::Result<View> {
        let view = parse_view(&self.hypr.json("monitors")?).ok_or_else(|| other("no monitor"))?;
        self.canvas.sync(&parse_clients(&self.hypr.json("clients")?));
        Ok(view)
    }

    fn active(&self) -> io::Result<Option<Client>> {
        Ok(Client::from_json(&self.hypr.json("activewindow")?))
    }

    fn cursor(&self) -> io::Result<(i32, i32)> {
        let j = self.hypr.json("cursorpos")?;
        let n = |k: &str| j.get(k).and_then(|v| v.int()).map(|v| v as i32);
        n("x").zip(n("y")).ok_or_else(|| other("bad cursorpos"))
    }

    /// Puts the camera at `off` and sends every resulting window move, plus `extra`, as one batch.
    fn glide(&mut self, view: &View, off: (i32, i32), extra: Vec<String>, keep: Option<&str>) -> io::Result<()> {
        let mut exprs: Vec<String> = self
            .canvas
            .pan_to(view.ws, off, &view.rect, self.cfg.margin, keep)
            .iter()
            .map(|m| move_expr(&m.addr, m.x, m.y))
            .collect();
        exprs.extend(extra);
        self.hypr.batch(&exprs)
    }

    pub fn handle(&mut self, cmd: Cmd) -> io::Result<String> {
        let view = match cmd {
            Cmd::DragEnd | Cmd::Quit => None,
            _ => Some(self.refresh()?),
        };
        let ok = || Ok("ok".to_string());
        match (cmd, view) {
            (Cmd::Pan(dir, px), Some(v)) => {
                let (vx, vy) = dir.vector();
                let step = px.unwrap_or(self.cfg.step);
                let off = self.canvas.offset(v.ws);
                self.canvas.remember(v.ws);
                self.glide(&v, (off.0 + vx * step, off.1 + vy * step), vec![], None)?;
                ok()
            }
            (Cmd::Look(dir), Some(v)) => {
                if self.canvas.is_empty(v.ws) {
                    self.hypr.batch(&[focus_direction_expr(dir.name())])?;
                    return ok();
                }
                let active = self.active()?.map(|c| c.addr);
                let off = self.canvas.offset(v.ws);
                let (cx, cy) = v.rect.center();
                let from = active
                    .as_deref()
                    .and_then(|a| self.canvas.canvas_rect(a))
                    .unwrap_or(Rect::new(cx + off.0, cy + off.1, 1, 1));
                let cands: Vec<_> = self.canvas.windows_on(v.ws).into_iter().filter(|(a, _)| Some(a) != active.as_ref()).collect();
                let Some(target) = find_target(&cands, &from, dir).map(str::to_string) else { return Ok("none".into()) };
                let to = self.canvas.offset_to_center(&target, &v.rect).ok_or_else(|| other("window vanished"))?;
                self.canvas.remember(v.ws);
                self.glide(&v, to, vec![focus_expr(&target)], None)?;
                ok()
            }
            (Cmd::Move(dir), Some(v)) => {
                let Some(win) = self.active()?.filter(|c| c.floating && !c.fullscreen) else { return Ok("none".into()) };
                let (vx, vy) = dir.vector();
                let (dx, dy) = (vx * self.cfg.step, vy * self.cfg.step);
                let r = Rect::new(win.rect.x + dx, win.rect.y + dy, win.rect.w, win.rect.h);
                // Past the screen edge the window stays put and the rest of the canvas moves instead.
                let over = |lo: i32, hi: i32, vlo: i32, vhi: i32, d: i32| match d.signum() {
                    1 => (hi - vhi).max(0),
                    -1 => (lo - vlo).min(0),
                    _ => 0,
                };
                let off = self.canvas.offset(v.ws);
                let to = (
                    off.0 + over(r.x, r.right(), v.rect.x, v.rect.right(), dx),
                    off.1 + over(r.y, r.bottom(), v.rect.y, v.rect.bottom(), dy),
                );
                self.canvas.shift_window(&win.addr, dx, dy);
                self.canvas.priority = Some(win.addr);
                self.glide(&v, to, vec![], None)?;
                ok()
            }
            (Cmd::Center, Some(v)) => {
                let Some(win) = self.active()? else { return Ok("none".into()) };
                let to = self.canvas.offset_to_center(&win.addr, &v.rect).ok_or_else(|| other("not a floating window"))?;
                self.canvas.remember(v.ws);
                self.glide(&v, to, vec![], None)?;
                ok()
            }
            (Cmd::Home, Some(v)) => {
                self.canvas.remember(v.ws);
                self.glide(&v, (0, 0), vec![], None)?;
                ok()
            }
            (Cmd::Back, Some(v)) => {
                let Some(to) = self.canvas.back(v.ws) else { return Ok("none".into()) };
                self.glide(&v, to, vec![], None)?;
                ok()
            }
            (Cmd::DragStart(mode), Some(v)) => {
                let dragged = match mode {
                    DragMode::Edge => Some(self.active()?.ok_or_else(|| other("no active window"))?.addr),
                    DragMode::Pan => None,
                };
                self.canvas.remember(v.ws);
                self.drag = Some(Drag { mode, last: self.cursor()?, view: v, dragged, acc: (0.0, 0.0), last_motion: Instant::now() });
                ok()
            }
            (Cmd::DragEnd, _) => {
                self.drag = None;
                ok()
            }
            (Cmd::Status, Some(v)) => {
                let o = self.canvas.offset(v.ws);
                Ok(format!("workspace={} offset={},{} windows={}", v.ws, o.0, o.1, self.canvas.windows_on(v.ws).len()))
            }
            _ => Ok("bye".into()),
        }
    }

    /// Hyprland event socket line, e.g. `activewindowv2>>55d0c0f0`.
    pub fn on_event(&mut self, line: &str) -> io::Result<()> {
        let Some(addr) = line.strip_prefix("activewindowv2>>").filter(|a| !a.is_empty()) else { return Ok(()) };
        if !self.cfg.follow || self.drag.is_some() {
            return Ok(());
        }
        let addr = format!("0x{addr}");
        let v = self.refresh()?;
        let Some(screen) = self.canvas.screen_rect(&addr) else { return Ok(()) };
        if screen.overlap_area(&v.rect) * 2 >= screen.area() {
            return Ok(());
        }
        if let Some(to) = self.canvas.offset_to_center(&addr, &v.rect) {
            self.canvas.remember(v.ws);
            self.glide(&v, to, vec![], None)?;
        }
        Ok(())
    }

    /// One drag frame. A failure ends the drag so a broken socket cannot spam errors at 60 Hz.
    pub fn tick(&mut self) -> io::Result<()> {
        let Some(mut d) = self.drag.take() else { return Ok(()) };
        if self.step_drag(&mut d)? {
            self.drag = Some(d);
        }
        Ok(())
    }

    fn step_drag(&mut self, d: &mut Drag) -> io::Result<bool> {
        let now = self.cursor()?;
        let (dx, dy) = (now.0 - d.last.0, now.1 - d.last.1);
        d.last = now;
        if dx == 0 && dy == 0 {
            return Ok(d.last_motion.elapsed() < DRAG_IDLE_LIMIT);
        }
        d.last_motion = Instant::now();
        let off = self.canvas.offset(d.view.ws);
        match d.mode {
            DragMode::Pan => {
                let k = self.cfg.speed * if self.cfg.invert { -1.0 } else { 1.0 };
                d.acc = (d.acc.0 + dx as f64 * k, d.acc.1 + dy as f64 * k);
                let (ix, iy) = (d.acc.0.round() as i32, d.acc.1.round() as i32);
                d.acc = (d.acc.0 - ix as f64, d.acc.1 - iy as f64);
                if ix != 0 || iy != 0 {
                    self.glide(&d.view, (off.0 - ix, off.1 - iy), vec![], None)?;
                }
            }
            DragMode::Edge => {
                let addr = d.dragged.clone().unwrap_or_default();
                let Some(win) = self.active()?.filter(|c| c.addr == addr) else { return Ok(false) };
                let (r, v, m) = (win.rect, d.view.rect, self.cfg.edge);
                let push = |lo: i32, hi: i32, vlo: i32, vhi: i32, delta: i32| {
                    if (delta > 0 && hi >= vhi - m) || (delta < 0 && lo <= vlo + m) { delta } else { 0 }
                };
                let (px, py) = (push(r.x, r.right(), v.x, v.right(), dx), push(r.y, r.bottom(), v.y, v.bottom(), dy));
                if px != 0 || py != 0 {
                    self.canvas.observe(&addr, (r.x, r.y));
                    self.glide(&d.view, (off.0 + px, off.1 + py), vec![], Some(&addr))?;
                }
            }
        }
        Ok(true)
    }
}

struct SocketGuard(std::path::PathBuf);

impl Drop for SocketGuard {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn serve_one(daemon: &mut Daemon, listener: &std::os::unix::net::UnixListener) -> bool {
    let Ok((mut stream, _)) = listener.accept() else { return true };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let mut line = String::new();
    let _ = stream.read_to_string(&mut line);
    let (reply, keep_running) = match control::parse(&line) {
        Ok(Cmd::Quit) => ("bye".to_string(), false),
        Ok(cmd) => (daemon.handle(cmd).unwrap_or_else(|e| format!("error: {e}")), true),
        Err(e) => (format!("error: {e}"), true),
    };
    let _ = stream.write_all(reply.as_bytes());
    keep_running
}

fn poll(fds: &mut [libc::pollfd], timeout_ms: i32) -> io::Result<()> {
    loop {
        // SAFETY: `fds` is a valid slice of pollfd for the whole call.
        let n = unsafe { libc::poll(fds.as_mut_ptr(), fds.len() as libc::nfds_t, timeout_ms) };
        if n >= 0 {
            return Ok(());
        }
        let err = io::Error::last_os_error();
        if err.kind() != io::ErrorKind::Interrupted {
            return Err(err);
        }
    }
}

pub fn run() -> io::Result<()> {
    let hypr = Hypr::from_env()?;
    let path = control::socket_path();
    let listener = control::listen(&path)?;
    let _guard = SocketGuard(path);
    let mut events = hypr.events()?;
    let mut daemon = Daemon::new(hypr, Config::load());
    let (mut pending, mut chunk) = (String::new(), [0u8; 4096]);
    let mut last_tick = Instant::now();
    let mut last_error = String::new();
    let mut report = |e: io::Error| {
        let msg = e.to_string();
        if msg != last_error {
            eprintln!("hypr-canvas: {msg}");
            last_error = msg;
        }
    };

    loop {
        let wait = if daemon.dragging() { FRAME.saturating_sub(last_tick.elapsed()).as_millis() as i32 } else { -1 };
        let mut fds = [
            libc::pollfd { fd: events.as_raw_fd(), events: libc::POLLIN, revents: 0 },
            libc::pollfd { fd: listener.as_raw_fd(), events: libc::POLLIN, revents: 0 },
        ];
        poll(&mut fds, wait)?;

        if fds[0].revents != 0 {
            match events.read(&mut chunk) {
                Ok(0) | Err(_) => return Ok(()), // Hyprland went away
                Ok(n) => pending.push_str(&String::from_utf8_lossy(&chunk[..n])),
            }
            while let Some(end) = pending.find('\n') {
                if let Err(e) = daemon.on_event(&pending[..end]) {
                    report(e);
                }
                pending.drain(..=end);
            }
            if pending.len() > 65536 {
                pending.clear();
            }
        }
        if fds[1].revents & libc::POLLIN != 0 && !serve_one(&mut daemon, &listener) {
            return Ok(());
        }
        if daemon.dragging() && last_tick.elapsed() >= FRAME {
            last_tick = Instant::now();
            if let Err(e) = daemon.tick() {
                report(e);
            }
        }
    }
}
