use std::fs;
use std::os::unix::io::AsRawFd;
use std::path::Path;
use std::process::{Child, Command, Stdio};

use crate::util::watch::set_nonblocking;

const GLYPHS: [&str; 8] = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"];

pub fn config_text(bars: usize, framerate: u32, max_range: usize) -> String {
    format!(
        "[general]\nframerate = {framerate}\nbars = {bars}\nautosens = 1\nsleep_timer = 2\n\n[input]\nmethod = pulse\nsource = auto\n\n[output]\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\nascii_max_range = {max_range}\nbar_delimiter = 59\n"
    )
}

pub fn parse_line(line: &str, bars: usize, max_range: usize) -> Option<Vec<usize>> {
    let raw: Vec<&str> = line.trim().split(';').filter(|s| !s.is_empty()).collect();
    if raw.is_empty() {
        return None;
    }
    let mut values = Vec::with_capacity(bars);
    for part in raw.iter().take(bars) {
        let v: usize = part.parse().ok()?;
        values.push(v.min(max_range));
    }
    values.resize(bars, 0);
    Some(values)
}

pub fn energy_level(values: &[usize], max_range: usize) -> usize {
    if values.is_empty() || max_range == 0 {
        return 0;
    }
    let sum: usize = values.iter().sum();
    let avg = sum as f64 / values.len() as f64;
    let peak = *values.iter().max().unwrap_or(&0) as f64;
    let score = (avg * 0.65 + peak * 0.35) / max_range as f64;
    if score >= 0.62 {
        3
    } else if score >= 0.36 {
        2
    } else if score >= 0.12 {
        1
    } else {
        0
    }
}

pub fn bars_text(values: &[usize]) -> String {
    values
        .iter()
        .map(|&v| GLYPHS[v.min(GLYPHS.len() - 1)])
        .collect()
}

pub fn spawn(conf_path: &Path, bars: usize, framerate: u32, max_range: usize) -> std::io::Result<Child> {
    if let Some(parent) = conf_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(conf_path, config_text(bars, framerate, max_range))?;
    let child = Command::new("cava")
        .args(["-p", &conf_path.to_string_lossy()])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()?;
    if let Some(ref stdout) = child.stdout {
        set_nonblocking(stdout.as_raw_fd());
    }
    Ok(child)
}

pub fn stop(child: &mut Option<Child>) {
    if let Some(mut proc) = child.take() {
        let _ = proc.kill();
        let _ = proc.wait();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cava_parsing_and_levels() {
        let parsed = parse_line("0;3;7;12;", 8, 7).unwrap();
        assert_eq!(parsed, vec![0, 3, 7, 7, 0, 0, 0, 0]);
        assert_eq!(bars_text(&[0, 3, 7, 99]), "▁▄██");
        assert_eq!(energy_level(&[0; 8], 7), 0);
        assert_eq!(energy_level(&[7; 8], 7), 3);
    }
}
