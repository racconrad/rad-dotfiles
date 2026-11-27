use std::collections::VecDeque;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::menu::walls::catalogue::{catalogue, current_wallpaper, kind_of, resolve_wallpaper_dir};
use crate::menu::walls::thumbs::{cached_thumb, css_url, generate_thumb};
use crate::util::atomic::write_atomic;
use crate::util::hash::token;
use crate::util::paths::{cache_dir, home_dir, runtime_root};
use crate::util::watch::{emit_line, DirWatch};

pub const COLUMNS: usize = 4;
pub const PAGE_SIZE: usize = 12;

pub fn request_path() -> PathBuf {
    runtime_root().join("raccon-float-gallery.json")
}

pub fn make_token() -> String {
    let ns = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos();
    token(&format!("{}-{}", ns, std::process::id()))
}

pub fn request_gallery(section: &str, page: Option<usize>) -> Result<(), String> {
    if !matches!(section, "all" | "images" | "videos") {
        return Err("Unknown wallpaper section".into());
    }
    let val = serde_json::json!({"section": section, "page": page, "token": make_token()});
    write_atomic(&request_path(), val.to_string().as_bytes()).map_err(|e| e.to_string())
}

pub fn read_gallery_request() -> (String, Option<usize>, String) {
    if let Ok(text) = fs::read_to_string(request_path()) {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&text) {
            if let Some(sec) = v.get("section").and_then(|s| s.as_str()) {
                if matches!(sec, "all" | "images" | "videos") {
                    let page = v.get("page").and_then(|p| p.as_u64()).map(|p| p as usize);
                    let tok = v.get("token").and_then(|t| t.as_str()).unwrap_or("initial").to_string();
                    return (sec.to_string(), page, tok);
                }
            }
        }
    }
    ("all".to_string(), None, "initial".to_string())
}

#[derive(Clone)]
pub struct Tile {
    pub index: usize,
    pub name: String,
    pub source: String,
    pub video: bool,
    pub thumb: String,
    pub has_thumb: bool,
    pub current: bool,
}

pub fn tiles_to_json(tiles: &[Tile], dir: &Path, section: &str, page: usize, pages: usize, counts: (usize, usize, usize), loading: bool, error: &str) -> String {
    let rows: Vec<serde_json::Value> = tiles
        .chunks(COLUMNS)
        .enumerate()
        .map(|(r, chunk)| {
            let tile_json: Vec<serde_json::Value> = chunk
                .iter()
                .map(|t| {
                    serde_json::json!({
                        "index": t.index,
                        "name": t.name,
                        "source": t.source,
                        "video": t.video,
                        "thumb": t.thumb,
                        "has_thumb": t.has_thumb,
                        "current": t.current,
                    })
                })
                .collect();
            serde_json::json!({"i": r, "count": chunk.len(), "tiles": tile_json})
        })
        .collect();
    let dir_name = dir.file_name().and_then(|s| s.to_str()).unwrap_or("").to_string();
    serde_json::json!({
        "rows": rows,
        "section": section,
        "page": page,
        "pages": pages,
        "dir_path": dir.to_string_lossy(),
        "dir_name": if dir_name.is_empty() { dir.to_string_lossy().into_owned() } else { dir_name },
        "counts": {"all": counts.0, "images": counts.1, "videos": counts.2},
        "loading": loading,
        "error": error,
    })
    .to_string()
}

pub fn watch_gallery() {
    let thumbs_dir = cache_dir().join("raccon-float/thumbs");
    let _ = fs::create_dir_all(&thumbs_dir);
    let dir_cfg = home_dir().join(".config/raccon/wallpaper-dir");
    let curr_file = cache_dir().join("current-wallpaper");
    let req_file = request_path();
    let wake_file = runtime_root().join("raccon-float-thumb.wake");
    let watcher = DirWatch::new(&[req_file, curr_file, dir_cfg, wake_file.clone()], &[]);

    let mut active_token = String::new();
    let mut active_dir = PathBuf::new();
    let mut active_section = "all".to_string();
    let mut page_num = 0usize;
    let mut page_count = 1usize;
    let mut counts = (0usize, 0usize, 0usize);
    let mut tiles: Vec<Tile> = Vec::new();
    let queue: Arc<Mutex<VecDeque<(String, usize, PathBuf)>>> = Arc::new(Mutex::new(VecDeque::new()));
    let results: Arc<Mutex<Vec<(String, usize, String)>>> = Arc::new(Mutex::new(Vec::new()));
    let active_gen = Arc::new(Mutex::new(String::new()));

    for _ in 0..2 {
        let q = Arc::clone(&queue);
        let r = Arc::clone(&results);
        let g = Arc::clone(&active_gen);
        let td = thumbs_dir.clone();
        let wf = wake_file.clone();
        std::thread::spawn(move || loop {
            let job = { q.lock().ok().and_then(|mut dq| dq.pop_front()) };
            if let Some((gen_tok, idx, path)) = job {
                let current_gen = g.lock().ok().map(|s| s.clone()).unwrap_or_default();
                if current_gen == gen_tok {
                    let out = generate_thumb(&path, &td);
                    if let Ok(mut res) = r.lock() {
                        res.push((gen_tok, idx, out));
                    }
                    let _ = fs::write(&wf, b"1");
                }
            } else {
                std::thread::sleep(Duration::from_millis(80));
            }
        });
    }

    let mut last_emit = Instant::now();
    let mut dirty = false;

    loop {
        let (sec, req_page, req_tok) = read_gallery_request();
        let cur_dir = resolve_wallpaper_dir();
        if req_tok != active_token || cur_dir != active_dir {
            active_token = req_tok.clone();
            active_dir = cur_dir.clone();
            active_section = sec.clone();
            if let Ok(mut g) = active_gen.lock() {
                *g = active_token.clone();
            }
            if let Ok(mut q) = queue.lock() {
                q.clear();
            }
            let (dir, images, videos) = catalogue();
            let mut all = [images.as_slice(), videos.as_slice()].concat();
            all.sort();
            counts = (all.len(), images.len(), videos.len());
            let files = match sec.as_str() {
                "images" => images,
                "videos" => videos,
                _ => all,
            };
            page_count = ((files.len() + PAGE_SIZE - 1) / PAGE_SIZE).max(1);
            page_num = req_page.unwrap_or(0).min(page_count - 1);
            let offset = if req_page.is_some() { page_num * PAGE_SIZE } else { 0 };
            let slice = if req_page.is_some() {
                &files[offset..files.len().min(offset + PAGE_SIZE)]
            } else {
                &files[..]
            };
            let current = current_wallpaper();
            tiles.clear();
            let mut jobs = VecDeque::new();
            for (i, p) in slice.iter().enumerate() {
                let cached = cached_thumb(p, &thumbs_dir);
                let source = fs::canonicalize(p).unwrap_or_else(|_| p.clone()).to_string_lossy().into_owned();
                let name = p.file_stem().and_then(|s| s.to_str()).unwrap_or("").to_string();
                let is_vid = kind_of(p) == Some("videos");
                if cached.is_empty() {
                    jobs.push_back((active_token.clone(), tiles.len(), p.clone()));
                }
                tiles.push(Tile {
                    index: offset + i,
                    name,
                    video: is_vid,
                    thumb: css_url(&cached),
                    has_thumb: !cached.is_empty(),
                    current: !current.is_empty() && source == current,
                    source,
                });
            }
            let loading = !jobs.is_empty();
            if let Ok(mut q) = queue.lock() {
                *q = jobs;
            }
            let json = tiles_to_json(&tiles, &dir, &active_section, page_num, page_count, counts, loading, "");
            if !emit_line(&json) { return; }
            last_emit = Instant::now();
            dirty = false;
        }

        let current = current_wallpaper();
        for t in &mut tiles {
            let sel = !current.is_empty() && t.source == current;
            if t.current != sel {
                t.current = sel;
                dirty = true;
            }
        }
        if let Ok(mut res) = results.lock() {
            for (gen_tok, idx, out) in res.drain(..) {
                if gen_tok == active_token {
                    if let Some(t) = tiles.get_mut(idx) {
                        t.thumb = css_url(&out);
                        t.has_thumb = !out.is_empty();
                        dirty = true;
                    }
                }
            }
        }
        let still_loading = queue.lock().map(|q| !q.is_empty()).unwrap_or(false);
        if dirty && (!still_loading || last_emit.elapsed() >= Duration::from_millis(150)) {
            let (_, _, latest_tok) = read_gallery_request();
            if latest_tok == active_token {
                let json = tiles_to_json(&tiles, &active_dir, &active_section, page_num, page_count, counts, still_loading, "");
                if !emit_line(&json) { return; }
            }
            dirty = false;
            last_emit = Instant::now();
        }
        let timeout_ms = if dirty {
            150i32.saturating_sub(last_emit.elapsed().as_millis() as i32).max(10)
        } else {
            -1
        };
        watcher.wait(timeout_ms);
    }
}
