//! Minimal JSON reader for what Hyprland returns. No dependency; depth is capped.

#[derive(Debug, Clone, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

impl Json {
    pub fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(items) => items.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn str(&self) -> Option<&str> {
        if let Json::Str(s) = self { Some(s) } else { None }
    }

    pub fn int(&self) -> Option<i64> {
        if let Json::Num(n) = self { Some(*n as i64) } else { None }
    }

    pub fn bool(&self) -> Option<bool> {
        if let Json::Bool(b) = self { Some(*b) } else { None }
    }

    pub fn arr(&self) -> &[Json] {
        if let Json::Arr(v) = self { v } else { &[] }
    }
}

pub fn parse(text: &str) -> Option<Json> {
    let mut p = Parser { b: text.as_bytes(), i: 0, depth: 0 };
    p.ws();
    let v = p.value()?;
    p.ws();
    (p.i == p.b.len()).then_some(v)
}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
    depth: u32,
}

impl Parser<'_> {
    fn ws(&mut self) {
        while matches!(self.b.get(self.i), Some(b' ' | b'\n' | b'\t' | b'\r')) {
            self.i += 1;
        }
    }

    fn eat(&mut self, c: u8) -> Option<()> {
        (self.b.get(self.i) == Some(&c)).then(|| self.i += 1)
    }

    fn lit(&mut self, word: &str, v: Json) -> Option<Json> {
        self.b[self.i..].starts_with(word.as_bytes()).then(|| {
            self.i += word.len();
            v
        })
    }

    fn value(&mut self) -> Option<Json> {
        match *self.b.get(self.i)? {
            b'{' => self.object(),
            b'[' => self.array(),
            b'"' => self.string().map(Json::Str),
            b't' => self.lit("true", Json::Bool(true)),
            b'f' => self.lit("false", Json::Bool(false)),
            b'n' => self.lit("null", Json::Null),
            _ => self.number(),
        }
    }

    fn enter(&mut self) -> Option<()> {
        self.depth += 1;
        (self.depth <= 64).then_some(())
    }

    fn object(&mut self) -> Option<Json> {
        self.enter()?;
        self.i += 1;
        let mut items = Vec::new();
        self.ws();
        if self.eat(b'}').is_none() {
            loop {
                self.ws();
                let key = self.string()?;
                self.ws();
                self.eat(b':')?;
                self.ws();
                items.push((key, self.value()?));
                self.ws();
                if self.eat(b',').is_some() {
                    continue;
                }
                self.eat(b'}')?;
                break;
            }
        }
        self.depth -= 1;
        Some(Json::Obj(items))
    }

    fn array(&mut self) -> Option<Json> {
        self.enter()?;
        self.i += 1;
        let mut items = Vec::new();
        self.ws();
        if self.eat(b']').is_none() {
            loop {
                self.ws();
                items.push(self.value()?);
                self.ws();
                if self.eat(b',').is_some() {
                    continue;
                }
                self.eat(b']')?;
                break;
            }
        }
        self.depth -= 1;
        Some(Json::Arr(items))
    }

    fn number(&mut self) -> Option<Json> {
        let start = self.i;
        while matches!(self.b.get(self.i), Some(b'+' | b'-' | b'.' | b'e' | b'E' | b'0'..=b'9')) {
            self.i += 1;
        }
        std::str::from_utf8(&self.b[start..self.i]).ok()?.parse().ok().map(Json::Num)
    }

    fn hex4(&mut self) -> Option<u32> {
        let digits = self.b.get(self.i..self.i + 4)?;
        self.i += 4;
        u32::from_str_radix(std::str::from_utf8(digits).ok()?, 16).ok()
    }

    fn string(&mut self) -> Option<String> {
        self.eat(b'"')?;
        let mut out = Vec::new();
        loop {
            let c = *self.b.get(self.i)?;
            self.i += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let e = *self.b.get(self.i)?;
                    self.i += 1;
                    match e {
                        b'"' | b'\\' | b'/' => out.push(e),
                        b'b' => out.push(8),
                        b'f' => out.push(12),
                        b'n' => out.push(b'\n'),
                        b'r' => out.push(b'\r'),
                        b't' => out.push(b'\t'),
                        b'u' => {
                            let mut cp = self.hex4()?;
                            if (0xD800..0xDC00).contains(&cp) && self.b[self.i..].starts_with(b"\\u") {
                                self.i += 2;
                                let low = self.hex4()?;
                                cp = 0x10000 + ((cp - 0xD800) << 10) + low.wrapping_sub(0xDC00);
                            }
                            let ch = char::from_u32(cp).unwrap_or('\u{FFFD}');
                            out.extend_from_slice(ch.encode_utf8(&mut [0; 4]).as_bytes());
                        }
                        _ => return None,
                    }
                }
                _ => out.push(c),
            }
        }
        Some(String::from_utf8_lossy(&out).into_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_hyprland_shapes() {
        let j = parse(r#"[{"address":"0x1","at":[10,-20],"floating":true,"title":"a \"q\" é😀","w":{"id":3}}]"#).unwrap();
        let c = &j.arr()[0];
        assert_eq!(c.get("address").unwrap().str(), Some("0x1"));
        assert_eq!(c.get("at").unwrap().arr()[1].int(), Some(-20));
        assert_eq!(c.get("floating").unwrap().bool(), Some(true));
        assert_eq!(c.get("title").unwrap().str(), Some("a \"q\" \u{e9}\u{1f600}"));
        assert_eq!(c.get("w").unwrap().get("id").unwrap().int(), Some(3));
    }

    #[test]
    fn rejects_garbage_and_deep_nesting() {
        assert!(parse("{\"a\":").is_none());
        assert!(parse("[1,]").is_none());
        assert!(parse("").is_none());
        assert!(parse(&"[".repeat(100)).is_none());
    }
}
