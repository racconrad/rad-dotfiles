//! Plain data the daemon works with, parsed from Hyprland's JSON replies.

use crate::json::Json;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

impl Rect {
    pub fn new(x: i32, y: i32, w: i32, h: i32) -> Self {
        Self { x, y, w, h }
    }

    pub fn right(&self) -> i32 {
        self.x + self.w
    }

    pub fn bottom(&self) -> i32 {
        self.y + self.h
    }

    pub fn center(&self) -> (i32, i32) {
        (self.x + self.w / 2, self.y + self.h / 2)
    }

    pub fn grow(&self, m: i32) -> Rect {
        Rect::new(self.x - m, self.y - m, self.w + 2 * m, self.h + 2 * m)
    }

    pub fn intersects(&self, o: &Rect) -> bool {
        self.x < o.right() && o.x < self.right() && self.y < o.bottom() && o.y < self.bottom()
    }

    pub fn overlap_area(&self, o: &Rect) -> i64 {
        let w = self.right().min(o.right()) - self.x.max(o.x);
        let h = self.bottom().min(o.bottom()) - self.y.max(o.y);
        if w > 0 && h > 0 { w as i64 * h as i64 } else { 0 }
    }

    pub fn area(&self) -> i64 {
        self.w.max(0) as i64 * self.h.max(0) as i64
    }
}

#[derive(Clone, Debug)]
pub struct Client {
    pub addr: String,
    pub rect: Rect,
    pub floating: bool,
    pub fullscreen: bool,
    pub ws: i64,
}

fn pair(j: Option<&Json>) -> Option<(i32, i32)> {
    let a = j?.arr();
    Some((a.first()?.int()? as i32, a.get(1)?.int()? as i32))
}

impl Client {
    /// None for windows that are not mapped or are hidden.
    pub fn from_json(j: &Json) -> Option<Client> {
        if j.get("mapped")?.bool()? == false || j.get("hidden").and_then(Json::bool) == Some(true) {
            return None;
        }
        let (x, y) = pair(j.get("at"))?;
        let (w, h) = pair(j.get("size"))?;
        Some(Client {
            addr: j.get("address")?.str()?.to_string(),
            rect: Rect::new(x, y, w, h),
            floating: j.get("floating")?.bool()?,
            fullscreen: j.get("fullscreen").and_then(Json::int).unwrap_or(0) > 0,
            ws: j.get("workspace")?.get("id")?.int()?,
        })
    }
}

pub fn parse_clients(j: &Json) -> Vec<Client> {
    j.arr().iter().filter_map(Client::from_json).collect()
}

/// The focused monitor's usable area (bars excluded) and its active workspace.
#[derive(Clone, Copy, Debug)]
pub struct View {
    pub rect: Rect,
    pub ws: i64,
}

pub fn parse_view(monitors: &Json) -> Option<View> {
    let all = monitors.arr();
    let m = all.iter().find(|m| m.get("focused").and_then(Json::bool) == Some(true)).or(all.first())?;
    let r = m.get("reserved").map(|r| r.arr()).unwrap_or(&[]);
    let side = |i: usize| r.get(i).and_then(Json::int).unwrap_or(0) as i32;
    let (x, y) = (m.get("x")?.int()? as i32, m.get("y")?.int()? as i32);
    let (w, h) = (m.get("width")?.int()? as i32, m.get("height")?.int()? as i32);
    // reserved = [left, top, right, bottom]; a scaled monitor reports logical size via "scale".
    let scale = match m.get("scale") {
        Some(Json::Num(s)) if *s > 0.0 => *s,
        _ => 1.0,
    };
    let (w, h) = ((w as f64 / scale).round() as i32, (h as f64 / scale).round() as i32);
    Some(View {
        rect: Rect::new(x + side(0), y + side(1), w - side(0) - side(2), h - side(1) - side(3)),
        ws: m.get("activeWorkspace")?.get("id")?.int()?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json::parse;

    #[test]
    fn client_parses_and_skips_unmapped() {
        let j = parse(r#"[{"address":"0xa","mapped":true,"hidden":false,"at":[5,6],"size":[7,8],"floating":true,"fullscreen":0,"workspace":{"id":2}},
            {"address":"0xb","mapped":false,"hidden":false,"at":[0,0],"size":[1,1],"floating":true,"workspace":{"id":1}}]"#).unwrap();
        let c = parse_clients(&j);
        assert_eq!(c.len(), 1);
        assert_eq!((c[0].rect, c[0].ws, c[0].fullscreen), (Rect::new(5, 6, 7, 8), 2, false));
    }

    #[test]
    fn view_subtracts_reserved_and_scale() {
        let j = parse(r#"[{"focused":true,"x":0,"y":0,"width":2880,"height":1800,"scale":1.5,"reserved":[0,40,0,0],"activeWorkspace":{"id":4}}]"#).unwrap();
        let v = parse_view(&j).unwrap();
        assert_eq!((v.rect, v.ws), (Rect::new(0, 40, 1920, 1160), 4));
    }

    #[test]
    fn rect_overlap() {
        let a = Rect::new(0, 0, 10, 10);
        assert!(a.intersects(&Rect::new(9, 9, 5, 5)));
        assert!(!a.intersects(&Rect::new(10, 0, 5, 5)));
        assert_eq!(a.overlap_area(&Rect::new(5, 5, 10, 10)), 25);
    }
}
