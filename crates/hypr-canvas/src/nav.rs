//! Directional window choice: nearest aligned window, else nearest ahead, else wrap to the far side.

use crate::model::Rect;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Dir {
    Left,
    Right,
    Up,
    Down,
}

impl Dir {
    pub fn parse(s: &str) -> Option<Dir> {
        match s {
            "left" | "l" => Some(Dir::Left),
            "right" | "r" => Some(Dir::Right),
            "up" | "u" => Some(Dir::Up),
            "down" | "d" => Some(Dir::Down),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Dir::Left => "left",
            Dir::Right => "right",
            Dir::Up => "up",
            Dir::Down => "down",
        }
    }

    pub fn vector(self) -> (i32, i32) {
        match self {
            Dir::Left => (-1, 0),
            Dir::Right => (1, 0),
            Dir::Up => (0, -1),
            Dir::Down => (0, 1),
        }
    }
}

/// Distance along `dir` between centers (positive when `c` lies ahead) and the sideways offset.
fn measure(dir: Dir, from: &Rect, c: &Rect) -> (i32, i32) {
    let (fx, fy) = from.center();
    let (cx, cy) = c.center();
    let (vx, vy) = dir.vector();
    ((cx - fx) * vx + (cy - fy) * vy, ((cx - fx) * vy + (cy - fy) * vx).abs())
}

fn overlaps_sideways(dir: Dir, a: &Rect, b: &Rect) -> bool {
    match dir {
        Dir::Left | Dir::Right => a.y < b.bottom() && b.y < a.bottom(),
        Dir::Up | Dir::Down => a.x < b.right() && b.x < a.right(),
    }
}

pub fn find_target<'a>(cands: &'a [(String, Rect)], from: &Rect, dir: Dir) -> Option<&'a str> {
    let ahead: Vec<_> = cands.iter().map(|(a, r)| (a, r, measure(dir, from, r))).filter(|(_, _, m)| m.0 > 0).collect();
    let pick = |aligned: bool| {
        ahead
            .iter()
            .filter(|(_, r, _)| !aligned || overlaps_sideways(dir, from, r))
            .min_by_key(|(_, _, m)| (m.0, m.1))
            .map(|(a, _, _)| a.as_str())
    };
    if let Some(a) = pick(true).or_else(|| pick(false)) {
        return Some(a);
    }
    // Nothing ahead: wrap around to the window farthest on the opposite side.
    let behind = |c: &Rect| measure(dir, from, c).0;
    cands.iter().filter(|(_, r)| behind(r) < 0).min_by_key(|(_, r)| behind(r)).map(|(a, _)| a.as_str())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn w(name: &str, x: i32, y: i32) -> (String, Rect) {
        (name.to_string(), Rect::new(x, y, 100, 100))
    }

    #[test]
    fn prefers_aligned_then_any_ahead() {
        let me = Rect::new(0, 0, 100, 100);
        let c = [w("far-aligned", 900, 0), w("near-diagonal", 300, 500)];
        assert_eq!(find_target(&c, &me, Dir::Right), Some("far-aligned"));
        assert_eq!(find_target(&[w("only", 300, 500)], &me, Dir::Right), Some("only"));
    }

    #[test]
    fn wraps_to_the_farthest_opposite_window() {
        let me = Rect::new(500, 0, 100, 100);
        let c = [w("a", 0, 0), w("b", 300, 0)];
        assert_eq!(find_target(&c, &me, Dir::Right), Some("a"));
        assert_eq!(find_target(&[], &me, Dir::Up), None);
    }
}
