use std::collections::VecDeque;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::util::atomic::write_atomic;
use crate::util::hash::{sha1_hex, token};
use crate::util::paths::{cache_dir, home_dir, runtime_root};
use crate::util::watch::{emit_line, DirWatch, FileLock};

const COLUMNS: usize = 4;
const PAGE_SIZE: usize = 12;

fn kind_of(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?.to_ascii_lowercase();
    let trimmed = ext.trim_end_matches('\'');
    match trimmed {
        "jpg" | "jpeg" | "png" | "webp" | "gif" => Some("images"),
        "mp4" | "webm" | "mkv" | "mov" => Some("videos"),
        _ => None,
    }
}

fn expand_tilde(raw: &str, home: &Path) -> PathBuf {
    if let Some(rest) = raw.strip_prefix("~/") {
        home.join(rest)
    } else if raw == "~" {
        home.to_path_buf()
    } else {
        PathBuf::from(raw)
    }
}

fn dir_has_entries(path: &Path) -> bool {
    path.is_dir() && fs::read_dir(path).map(|mut d| d.next().is_some()).unwrap_or(false)
}

pub fn resolve_wallpaper_dir() -> PathBuf {
    let home = home_dir();
    if let Ok(line) = fs::read_to_string(home.join(".config/raccon/wallpaper-dir")) {
        let p = expand_tilde(line.trim(), &home);
        if p.is_dir() {
            return p;
        }
    }
    if let Ok(env_dir) = std::env::var("WALLPAPER_DIR") {
        let p = expand_tilde(env_dir.trim(), &home);
        if p.is_dir() {
            return p;
        }
    }
    let default_dir = home.join("Pictures/Wallpapers");
    if dir_has_entries(&default_dir) {
        return default_dir;
    }
    if let Ok(text) = fs::read_to_string(home.join(".config/waypaper/config.ini")) {
        for line in text.lines() {
            if let Some(rest) = line.trim().strip_prefix("folder") {
                if let Some((_, val)) = rest.split_once('=') {
                    let p = expand_tilde(val.trim(), &home);
                    if dir_has_entries(&p) {
                        return p;
                    }
                }
            }
        }
    }
    for cand in [home.join("Pictures/Wallpapers"), home.join("Pictures"), home.join(".local/share/wallpapers/raccon")] {
        if dir_has_entries(&cand) {
            return cand;
        }
    }
    default_dir
}

fn catalogue() -> (PathBuf, Vec<PathBuf>, Vec<PathBuf>) {
    let target = resolve_wallpaper_dir();
    let mut files = Vec::new();
    if let Ok(entries) = fs::read_dir(&target) {
        for entry in entries.flatten() {
            let p = entry.path();
            if p.is_file() && kind_of(&p).is_some() {
                files.push(p);
            }
        }
    }
    files.sort();
    let images: Vec<PathBuf> = files.iter().filter(|p| kind_of(p) == Some("images")).cloned().collect();
    let videos: Vec<PathBuf> = files.iter().filter(|p| kind_of(p) == Some("videos")).cloned().collect();
    (target, images, videos)
}

fn mtime_le(src: &Path, dst: &Path) -> bool {
    let Ok(s) = fs::metadata(src) else { return false; };
    let Ok(d) = fs::metadata(dst) else { return false; };
    d.len() > 0 && s.modified().ok() <= d.modified().ok()
}

fn cached_thumb(src: &Path, thumbs_dir: &Path) -> String {
    let out = thumbs_dir.join(format!("{}.png", sha1_hex(&src.to_string_lossy())));
    if mtime_le(src, &out) {
        out.to_string_lossy().into_owned()
    } else {
        String::new()
    }
}

fn generate_thumb(src: &Path, thumbs_dir: &Path) -> String {
    let out = thumbs_dir.join(format!("{}.png", sha1_hex(&src.to_string_lossy())));
    if mtime_le(src, &out) {
        return out.to_string_lossy().into_owned();
    }
    let _ = fs::create_dir_all(thumbs_dir);
    let temp = thumbs_dir.join(format!(".thumb-{}-{}.png", std::process::id(), sha1_hex(&src.to_string_lossy())));
    let vf = "scale=480:300:force_original_aspect_ratio=increase,crop=480:300";
    let seeks: &[&[&str]] = if kind_of(src) == Some("videos") { &[&["-ss", "1"], &[]] } else { &[&[]] };
    for seek in seeks {
        let ok = Command::new("ffmpeg")
            .args(["-nostdin", "-loglevel", "error", "-y", "-threads", "1"])
            .args(*seek)
            .arg("-i")
            .arg(src)
            .args(["-filter_threads", "1", "-frames:v", "1", "-vf", vf, "-threads", "1"])
            .arg(&temp)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if ok && temp.metadata().map(|m| m.len() > 0).unwrap_or(false) && fs::rename(&temp, &out).is_ok() {
            return out.to_string_lossy().into_owned();
        }
    }
    let _ = fs::remove_file(&temp);
    String::new()
}

fn css_url(path: &str) -> String {
    path.replace('\\', "\\\\").replace('"', "\\\"")
}

fn current_wallpaper() -> String {
    fs::read_to_string(cache_dir().join("current-wallpaper"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .and_then(|s| fs::canonicalize(s).ok())
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default()
}

fn request_path() -> PathBuf {
    runtime_root().join("raccon-float-gallery.json")
}

fn make_token() -> String {
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

fn read_gallery_request() -> (String, Option<usize>, String) {
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
struct Tile {
    index: usize,
    name: String,
    source: String,
    video: bool,
    thumb: String,
    has_thumb: bool,
    current: bool,
}

fn tiles_to_json(tiles: &[Tile], dir: &Path, section: &str, page: usize, pages: usize, counts: (usize, usize, usize), loading: bool, error: &str) -> String {
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

fn preview_root() -> PathBuf {
    cache_dir().join("raccon-float/preview")
}

fn preview_state_path() -> PathBuf {
    preview_root().join("state.json")
}

fn read_preview_state() -> serde_json::Value {
    fs::read_to_string(preview_state_path())
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_else(|| serde_json::json!({}))
}

fn write_preview_state(val: &serde_json::Value) {
    let _ = write_atomic(&preview_state_path(), val.to_string().as_bytes());
}

fn list_jpgs(dir: &Path) -> Vec<String> {
    let mut items = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for e in entries.flatten() {
            let p = e.path();
            if p.extension().and_then(|s| s.to_str()) == Some("jpg") {
                items.push(p.to_string_lossy().into_owned());
            }
        }
    }
    items.sort();
    items
}

pub fn wall_preview_stop(selection: &str) {
    let prev = read_preview_state();
    if !selection.is_empty() && prev.get("selection").and_then(|v| v.as_str()) != Some(selection) {
        return;
    }
    write_preview_state(&serde_json::json!({"token": make_token(), "active": false}));
}

pub fn wall_preview_start(path: &Path, selection: &str, hover: bool) {
    let prev = read_preview_state();
    if prev.get("active").and_then(|v| v.as_bool()) == Some(true)
        && !selection.is_empty()
        && prev.get("selection").and_then(|v| v.as_str()) == Some(selection)
    {
        return;
    }
    let tok = make_token();
    write_preview_state(&serde_json::json!({
        "token": tok, "selection": selection, "active": true, "message": "Loading preview…"
    }));
    if hover {
        std::thread::sleep(Duration::from_millis(180));
        if read_preview_state().get("token").and_then(|v| v.as_str()) != Some(tok.as_str()) {
            return;
        }
    }
    let root = preview_root();
    let _ = fs::create_dir_all(&root);
    let mtime_ns = fs::metadata(path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let key = token(&format!("tile-v2:{}:{}", path.to_string_lossy(), mtime_ns));
    let target = root.join(key);
    let _lock = FileLock::lock(&root.join("decode.lock"));
    if read_preview_state().get("token").and_then(|v| v.as_str()) != Some(tok.as_str()) {
        return;
    }
    if list_jpgs(&target).is_empty() {
        let temp = root.join(format!(".prev-{}", std::process::id()));
        let _ = fs::remove_dir_all(&temp);
        let _ = fs::create_dir_all(&temp);
        let ok = Command::new("ffmpeg")
            .args([
                "-nostdin", "-loglevel", "error", "-y", "-threads", "1",
                "-i",
            ])
            .arg(path)
            .args([
                "-t", "4", "-an", "-filter_threads", "1", "-vf",
                "fps=12,scale=340:214:force_original_aspect_ratio=increase,crop=340:214",
                "-frames:v", "48", "-q:v", "5", "-threads", "1",
            ])
            .arg(temp.join("%03d.jpg"))
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if !ok || list_jpgs(&temp).is_empty() {
            let _ = fs::remove_dir_all(&temp);
            if read_preview_state().get("token").and_then(|v| v.as_str()) == Some(tok.as_str()) {
                write_preview_state(&serde_json::json!({
                    "token": tok, "selection": selection, "active": true, "message": "Could not preview this video."
                }));
            }
            return;
        }
        let _ = fs::remove_dir_all(&target);
        let _ = fs::rename(&temp, &target);
    }
    let frames = list_jpgs(&target);
    if read_preview_state().get("token").and_then(|v| v.as_str()) == Some(tok.as_str()) {
        write_preview_state(&serde_json::json!({
            "token": tok, "selection": selection, "active": true, "frames": frames, "message": "Preview · muted"
        }));
    }
}

pub fn watch_preview() {
    let path = preview_state_path();
    let watcher = DirWatch::new(&[path], &[]);
    let mut last = String::new();
    loop {
        let state = read_preview_state();
        let active = state.get("active").and_then(|v| v.as_bool()).unwrap_or(false);
        let clip = if active {
            state
                .get("frames")
                .and_then(|f| f.as_array())
                .and_then(|arr| arr.first())
                .and_then(|v| v.as_str())
                .and_then(|p| Path::new(p).parent())
                .map(|p| p.to_string_lossy().into_owned())
                .unwrap_or_default()
        } else {
            String::new()
        };
        let selection = state.get("selection").and_then(|v| v.as_str()).unwrap_or("");
        let line = serde_json::json!({
            "active": active,
            "selection": selection,
            "clip": clip,
            "playback": format!("{selection}\n{clip}"),
            "message": state.get("message").and_then(|v| v.as_str()).unwrap_or(""),
        })
        .to_string();
        if line != last {
            if !emit_line(&line) { return; }
            last = line;
        }
        watcher.wait(-1);
    }
}

pub fn execute(args: &[String]) -> Result<(), String> {
    let cmd = args.first().map(|s| s.as_str()).unwrap_or("");
    match cmd {
        "watch" => {
            watch_gallery();
            Ok(())
        }
        "preview-watch" => {
            watch_preview();
            Ok(())
        }
        "request" => {
            let sec = args.get(1).map(|s| s.as_str()).unwrap_or("all");
            let page = args.get(2).and_then(|s| s.parse::<usize>().ok());
            request_gallery(sec, page)
        }
        "dir" => {
            println!("{}", resolve_wallpaper_dir().display());
            Ok(())
        }
        "set-dir" => {
            let raw = args.get(1).ok_or("Missing directory")?;
            let target = fs::canonicalize(expand_tilde(raw, &home_dir())).map_err(|e| e.to_string())?;
            if !target.is_dir() {
                return Err(format!("{} is not a valid directory", target.display()));
            }
            write_atomic(&home_dir().join(".config/raccon/wallpaper-dir"), format!("{}\n", target.display()).as_bytes())
                .map_err(|e| e.to_string())?;
            println!("Wallpaper directory updated to: {}", target.display());
            Ok(())
        }
        "preview-stop" => {
            wall_preview_stop(args.get(1).map(|s| s.as_str()).unwrap_or(""));
            Ok(())
        }
        "preview" | "preview-hover" | "set" => {
            let sec = args.get(1).ok_or("Missing section")?;
            let idx: usize = args.get(2).ok_or("Missing index")?.parse().map_err(|_| "Invalid index")?;
            let (_, images, videos) = catalogue();
            let mut all = [images.as_slice(), videos.as_slice()].concat();
            all.sort();
            let list = match sec.as_str() {
                "all" => all,
                "images" => images,
                "videos" => videos,
                _ => return Err("Unknown wallpaper section".into()),
            };
            let path = list.get(idx).ok_or("Wallpaper index out of range")?;
            if cmd == "set" {
                let resolved = fs::canonicalize(path).unwrap_or_else(|_| path.clone()).to_string_lossy().into_owned();
                if resolved == current_wallpaper() {
                    return Ok(());
                }
                let status = Command::new(home_dir().join(".local/bin/wallpaper-set"))
                    .arg(path)
                    .status()
                    .map_err(|e| e.to_string())?;
                if !status.success() {
                    return Err("wallpaper-set failed".into());
                }
                return Ok(());
            }
            if kind_of(path) != Some("videos") {
                return Err("Preview requires a video".into());
            }
            wall_preview_start(path, &format!("{sec}:{idx}"), cmd == "preview-hover");
            Ok(())
        }
        _ => Err(format!("Unknown walls command: {}", cmd)),
    }
}
