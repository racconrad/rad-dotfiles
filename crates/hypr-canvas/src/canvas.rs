//! The camera model. Pure logic: no IO, so it is testable without a compositor.
//!
//! Every floating window has a fixed canvas position; the camera offset decides where it sits on the
//! screen (`screen = canvas - offset`). Windows that are off screen before and after a camera move are
//! not touched, so a pan costs IPC work proportional to what is visible.

use crate::model::{Client, Rect};
use std::collections::{HashMap, HashSet};

#[derive(Default)]
struct Camera {
    off: (i32, i32),
    previous: Option<(i32, i32)>,
}

struct Win {
    canvas: (i32, i32),
    size: (i32, i32),
    shown: (i32, i32), // where Hyprland last had it on screen
    ws: i64,
}

impl Win {
    fn screen(&self) -> Rect {
        Rect::new(self.shown.0, self.shown.1, self.size.0, self.size.1)
    }
}

pub struct Move {
    pub addr: String,
    pub x: i32,
    pub y: i32,
}

#[derive(Default)]
pub struct Canvas {
    cams: HashMap<i64, Camera>,
    wins: HashMap<String, Win>,
    /// A window the next `pan_to` must place even if it ends up off screen (the one being moved by key).
    pub priority: Option<String>,
}

impl Canvas {
    pub fn offset(&self, ws: i64) -> (i32, i32) {
        self.cams.get(&ws).map_or((0, 0), |c| c.off)
    }

    /// Adopts Hyprland's view of the windows. A window found somewhere other than where we put it was
    /// moved by the user or the app, so its canvas position follows.
    pub fn sync(&mut self, clients: &[Client]) {
        let live: HashSet<&str> = clients.iter().filter(|c| c.floating && !c.fullscreen).map(|c| c.addr.as_str()).collect();
        self.wins.retain(|a, _| live.contains(a.as_str()));
        for c in clients.iter().filter(|c| live.contains(c.addr.as_str())) {
            let at = (c.rect.x, c.rect.y);
            let size = (c.rect.w, c.rect.h);
            let off = self.offset(c.ws);
            let win = self.wins.entry(c.addr.clone()).or_insert(Win { canvas: (0, 0), size, shown: (i32::MIN, 0), ws: c.ws });
            if win.shown != at || win.ws != c.ws {
                win.canvas = (at.0 + off.0, at.1 + off.1);
                win.shown = at;
                win.ws = c.ws;
            }
            win.size = size;
        }
    }

    pub fn is_empty(&self, ws: i64) -> bool {
        !self.wins.values().any(|w| w.ws == ws)
    }

    pub fn windows_on(&self, ws: i64) -> Vec<(String, Rect)> {
        self.wins.iter().filter(|(_, w)| w.ws == ws).map(|(a, w)| (a.clone(), Rect::new(w.canvas.0, w.canvas.1, w.size.0, w.size.1))).collect()
    }

    pub fn canvas_rect(&self, addr: &str) -> Option<Rect> {
        self.wins.get(addr).map(|w| Rect::new(w.canvas.0, w.canvas.1, w.size.0, w.size.1))
    }

    pub fn screen_rect(&self, addr: &str) -> Option<Rect> {
        self.wins.get(addr).map(Win::screen)
    }

    /// Camera offset that puts the window in the middle of the view.
    pub fn offset_to_center(&self, addr: &str, view: &Rect) -> Option<(i32, i32)> {
        let (cx, cy) = self.canvas_rect(addr)?.center();
        let (vx, vy) = view.center();
        Some((cx - vx, cy - vy))
    }

    pub fn remember(&mut self, ws: i64) {
        let cam = self.cams.entry(ws).or_default();
        cam.previous = Some(cam.off);
    }

    pub fn back(&mut self, ws: i64) -> Option<(i32, i32)> {
        let cam = self.cams.get_mut(&ws)?;
        let target = cam.previous?;
        cam.previous = Some(cam.off);
        Some(target)
    }

    /// Records where the user currently holds a window, so its canvas position can be rebased.
    pub fn observe(&mut self, addr: &str, at: (i32, i32)) {
        if let Some(w) = self.wins.get_mut(addr) {
            w.shown = at;
        }
    }

    /// Moves a window on the canvas; the next `pan_to` places it on screen.
    pub fn shift_window(&mut self, addr: &str, dx: i32, dy: i32) {
        if let Some(w) = self.wins.get_mut(addr) {
            w.canvas = (w.canvas.0 + dx, w.canvas.1 + dy);
        }
    }

    /// Sets the camera and returns the windows that must move. `keep` stays where the user holds it
    /// (a window being dragged) and its canvas position is rebased instead.
    pub fn pan_to(&mut self, ws: i64, off: (i32, i32), view: &Rect, margin: i32, keep: Option<&str>) -> Vec<Move> {
        self.cams.entry(ws).or_default().off = off;
        let near = view.grow(margin);
        let priority = self.priority.take();
        let mut moves = Vec::new();
        for (addr, w) in self.wins.iter_mut().filter(|(_, w)| w.ws == ws) {
            if keep == Some(addr.as_str()) {
                w.canvas = (w.shown.0 + off.0, w.shown.1 + off.1);
                continue;
            }
            let target = (w.canvas.0 - off.0, w.canvas.1 - off.1);
            if target == w.shown {
                continue;
            }
            let destination = Rect::new(target.0, target.1, w.size.0, w.size.1);
            // Move what will be (or is now) visible; anything else stays parked off screen.
            if destination.intersects(&near) || w.screen().intersects(view) || priority.as_deref() == Some(addr.as_str()) {
                moves.push(Move { addr: addr.clone(), x: target.0, y: target.1 });
                w.shown = target;
            }
        }
        moves
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn client(addr: &str, x: i32, y: i32) -> Client {
        Client { addr: addr.into(), rect: Rect::new(x, y, 400, 300), floating: true, fullscreen: false, ws: 1 }
    }

    fn view() -> Rect {
        Rect::new(0, 0, 1920, 1080)
    }

    #[test]
    fn pan_moves_visible_windows_and_parks_distant_ones() {
        let mut c = Canvas::default();
        c.sync(&[client("0xa", 100, 100), client("0xb", 8000, 100), client("0xc", 6000, 100)]);
        let moves = c.pan_to(1, (50, 0), &view(), 200, None);
        assert_eq!(moves.len(), 1);
        assert_eq!((moves[0].addr.as_str(), moves[0].x), ("0xa", 50));
        // Panning far enough brings the parked window into range: it jumps to its true place.
        let moves = c.pan_to(1, (7500, 0), &view(), 200, None);
        let b = moves.iter().find(|m| m.addr == "0xb").expect("b enters the view");
        assert_eq!(b.x, 500);
        assert!(moves.iter().any(|m| m.addr == "0xa"), "a leaves the view and must be moved or parked");
    }

    #[test]
    fn user_moves_are_adopted_and_closed_windows_forgotten() {
        let mut c = Canvas::default();
        c.sync(&[client("0xa", 100, 100)]);
        c.pan_to(1, (30, 0), &view(), 200, None);
        c.sync(&[client("0xa", 500, 100)]); // the user dragged it to x=500 while the camera was at 30
        assert_eq!(c.canvas_rect("0xa").unwrap().x, 530);
        c.sync(&[]);
        assert!(c.canvas_rect("0xa").is_none());
    }

    #[test]
    fn dragged_window_is_kept_and_rebased() {
        let mut c = Canvas::default();
        c.sync(&[client("0xa", 100, 100), client("0xb", 600, 100)]);
        let moves = c.pan_to(1, (40, 0), &view(), 200, Some("0xa"));
        assert!(moves.iter().all(|m| m.addr == "0xb") && moves.len() == 1);
        assert_eq!(c.canvas_rect("0xa").unwrap().x, 140);
    }

    #[test]
    fn priority_window_is_placed_even_off_screen() {
        let mut c = Canvas::default();
        c.sync(&[client("0xa", 9000, 0)]);
        assert!(c.pan_to(1, (0, 0), &view(), 200, None).is_empty());
        c.shift_window("0xa", 400, 0);
        c.priority = Some("0xa".into());
        let moves = c.pan_to(1, (0, 0), &view(), 200, None);
        assert_eq!((moves.len(), moves[0].x), (1, 9400));
        assert!(c.priority.is_none());
    }

    #[test]
    fn centering_and_back() {
        let mut c = Canvas::default();
        c.sync(&[client("0xa", 4000, 2000)]);
        assert_eq!(c.offset_to_center("0xa", &view()), Some((4200 - 960, 2150 - 540)));
        c.remember(1);
        c.pan_to(1, (10, 20), &view(), 0, None);
        assert_eq!(c.back(1), Some((0, 0)));
        assert_eq!(c.back(1), Some((10, 20)));
    }

    #[test]
    fn fullscreen_and_tiled_windows_are_ignored() {
        let mut c = Canvas::default();
        let mut tiled = client("0xt", 0, 0);
        tiled.floating = false;
        let mut full = client("0xf", 0, 0);
        full.fullscreen = true;
        c.sync(&[tiled, full]);
        assert!(c.is_empty(1));
    }
}
