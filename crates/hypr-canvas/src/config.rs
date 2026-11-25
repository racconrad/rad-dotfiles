//! `key = value` file at ~/.config/hypr-canvas/config. Missing file or keys mean defaults.

pub struct Config {
    pub step: i32,        // px of a keyboard pan or window move
    pub margin: i32,      // windows this close to the screen are kept in place during a pan
    pub follow: bool,     // center the camera on a window that gets focus off screen
    pub edge: i32,        // px from the screen edge where a dragged window starts pushing the canvas
    pub speed: f64,       // cursor-to-canvas ratio of the desktop drag
    pub invert: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self { step: 400, margin: 240, follow: true, edge: 10, speed: 1.6, invert: false }
    }
}

impl Config {
    pub fn parse(text: &str) -> Config {
        let mut c = Config::default();
        for line in text.lines().map(|l| l.split('#').next().unwrap_or("").trim()) {
            let Some((key, value)) = line.split_once('=') else { continue };
            let value = value.trim();
            match key.trim() {
                "step" => c.step = value.parse().unwrap_or(c.step).max(1),
                "margin" => c.margin = value.parse().unwrap_or(c.margin).max(0),
                "follow" => c.follow = value.parse().unwrap_or(c.follow),
                "edge" => c.edge = value.parse().unwrap_or(c.edge).max(0),
                "speed" => c.speed = value.parse().unwrap_or(c.speed),
                "invert" => c.invert = value.parse().unwrap_or(c.invert),
                _ => {}
            }
        }
        c
    }

    pub fn load() -> Config {
        let dir = std::env::var("XDG_CONFIG_HOME")
            .unwrap_or_else(|_| format!("{}/.config", std::env::var("HOME").unwrap_or_default()));
        std::fs::read_to_string(format!("{dir}/hypr-canvas/config")).map(|t| Config::parse(&t)).unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_known_keys_and_ignores_the_rest() {
        let c = Config::parse("step = 90 # px\nfollow=false\nspeed = nope\nunknown = 1\n# c\n");
        assert_eq!((c.step, c.follow, c.speed), (90, false, 1.6));
    }
}
