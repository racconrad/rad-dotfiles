use std::fs;
use std::process::Command;

use crate::menu::walls::catalogue::{catalogue, current_wallpaper, expand_tilde, resolve_wallpaper_dir};
use crate::menu::walls::gallery::{request_gallery, watch_gallery};
use crate::util::atomic::write_atomic;
use crate::util::paths::home_dir;

pub fn execute(args: &[String]) -> Result<(), String> {
    let cmd = args.first().map(|s| s.as_str()).unwrap_or("");
    match cmd {
        "watch" => {
            watch_gallery();
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
        "set" => {
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
            Ok(())
        }
        _ => Err(format!("Unknown walls command: {}", cmd)),
    }
}
