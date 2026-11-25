use anyhow::{anyhow, bail, Result};
use serde::{Deserialize, Serialize};
use std::os::unix::fs::MetadataExt;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

const KINDS: [&str; 5] = ["eww", "watcher", "provider", "tiler", "ws_watcher"];

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Process {
    pub pid: i64,
    pub start: String,
    pub uid: u32,
    pub kind: String,
}

// The normal-mode resources that were running before canvas mode took over.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Snapshot {
    pub profile: String,
    pub widgets: bool,
    pub tiler: bool,
    #[serde(default)]
    pub ws_watcher: bool,
    pub processes: Vec<Process>,
}

// What the stop and restore steps do to the system, so tests can stand in for it.
pub trait Host {
    fn which(&self, name: &str) -> Option<PathBuf>;
    fn control(&self, command: &Path, profile: &str, action: &str) -> Result<()>;
    fn spawn_tiler(&self, path: &Path) -> Result<()>;
    fn spawn_ws_watcher(&self, path: &Path) -> Result<()> {
        use std::os::unix::process::CommandExt;
        std::process::Command::new(path)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .process_group(0)
            .spawn()?;
        Ok(())
    }
    // Signals the process; `same` is checked again once a handle to it is held, so a reused pid is never hit.
    fn terminate(&self, pid: i64, same: &dyn Fn() -> bool) -> Result<()>;
}

pub struct Resources<'a> {
    pub proc_root: PathBuf,
    pub home: PathBuf,
    pub config: Option<PathBuf>,
    pub uid: u32,
    pub own_pid: u32,
    pub drain: Duration,
    pub host: &'a dyn Host,
}

fn resolve(path: &Path) -> PathBuf {
    std::fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf())
}

fn file_name(arg: &str) -> &str {
    Path::new(arg).file_name().and_then(|n| n.to_str()).unwrap_or("")
}

impl Resources<'_> {
    fn profile(&self) -> String {
        let path = self.config.clone().unwrap_or_else(|| self.home.join(".config/eww"));
        resolve(&path).to_string_lossy().into_owned()
    }

    fn kind(&self, args: &[String], profile: &str) -> Option<&'static str> {
        if args.is_empty() {
            return None;
        }
        let tiler = self.home.join(".local/bin/wf-tile").to_string_lossy().into_owned();
        let python = file_name(&args[0]).starts_with("python");
        let watch = [tiler.clone(), "watch".to_string()];
        if args == watch || (python && args[1..] == watch) {
            return Some("tiler");
        }
        let ws_watch = self.home.join(".local/bin/wf-ws-watch").to_string_lossy().into_owned();
        if args == [ws_watch.as_str()] || (python && args[1..] == [ws_watch.as_str()]) {
            return Some("ws_watcher");
        }
        let mut configs: Vec<&str> = args[..args.len() - 1]
            .iter()
            .enumerate()
            .filter(|(_, a)| *a == "--config" || *a == "-c")
            .map(|(i, _)| args[i + 1].as_str())
            .collect();
        configs.extend(args.iter().filter_map(|a| a.strip_prefix("--config=")));
        if configs.len() != 1 || !Path::new(configs[0]).is_absolute() || resolve(Path::new(configs[0])).to_string_lossy() != profile {
            return None;
        }
        let name = file_name(&args[0]);
        if name == "eww" {
            let mut rest = args[1..].iter();
            while let Some(arg) = rest.next() {
                if arg == "--config" || arg == "-c" {
                    rest.next();
                } else if !arg.starts_with('-') {
                    return (arg == "daemon").then_some("eww");
                }
            }
            return None;
        }
        let entry = self.home.join(".local/lib/randly_widgets/entry.py").to_string_lossy().into_owned();
        let widgetctl = self.home.join(".local/bin/widgetctl").to_string_lossy().into_owned();
        let managed_python = python && args.len() > 1 && (args[1] == entry || args[1] == widgetctl);
        if args.last().map(String::as_str) == Some("watch") && (name == "randly-widget-manager" || managed_python) {
            return Some("watcher");
        }
        if python && args.len() > 1 && args[1] == entry && args[2..].iter().any(|a| a == "data" || a == "options") {
            return Some("provider");
        }
        None
    }

    fn read(&self, pid: i64, profile: &str) -> Option<Process> {
        let dir = self.proc_root.join(pid.to_string());
        if dir.metadata().ok()?.uid() != self.uid || pid == i64::from(self.own_pid) {
            return None;
        }
        let stat = std::fs::read_to_string(dir.join("stat")).ok()?;
        let fields: Vec<&str> = stat.rsplit_once(')')?.1.split_whitespace().collect();
        if *fields.first()? == "Z" {
            return None;
        }
        let args = std::fs::read(dir.join("cmdline"))
            .ok()?
            .split(|b| *b == 0)
            .filter(|part| !part.is_empty())
            .map(|part| String::from_utf8(part.to_vec()))
            .collect::<std::result::Result<Vec<_>, _>>()
            .ok()?;
        let kind = self.kind(&args, profile)?;
        Some(Process { pid, start: fields.get(19)?.to_string(), uid: self.uid, kind: kind.into() })
    }

    fn processes(&self, profile: &str) -> Vec<Process> {
        let Ok(entries) = std::fs::read_dir(&self.proc_root) else { return vec![] };
        let mut names: Vec<String> =
            entries.flatten().map(|e| e.file_name().to_string_lossy().into_owned()).filter(|n| n.bytes().all(|b| b.is_ascii_digit()) && !n.is_empty()).collect();
        names.sort();
        names.iter().filter_map(|n| n.parse().ok()).filter_map(|pid| self.read(pid, profile)).collect()
    }

    pub fn snapshot(&self) -> Snapshot {
        let profile = self.profile();
        let processes = self.processes(&profile);
        Snapshot {
            widgets: processes.iter().any(|p| is_widget_kind(&p.kind)),
            tiler: processes.iter().any(|p| p.kind == "tiler"),
            ws_watcher: processes.iter().any(|p| p.kind == "ws_watcher"),
            profile,
            processes,
        }
    }

    fn validate(&self, state: &Snapshot) -> Result<String> {
        let profile = self.profile();
        if state.profile != profile {
            bail!("Managed widget profile changed; refusing to control another profile");
        }
        for p in &state.processes {
            if p.pid <= 0 || p.uid != self.uid || !KINDS.contains(&p.kind.as_str()) {
                bail!("Invalid resource process identity");
            }
        }
        Ok(profile)
    }

    fn control(&self, profile: &str, action: &str) -> Result<()> {
        let command = self
            .host
            .which("widgetctl")
            .ok_or_else(|| anyhow!("widgetctl is required to control the running TinyWidgets profile"))?;
        self.host.control(&command, profile, action).map_err(|_| anyhow!("TinyWidgets {action} failed"))
    }

    fn terminate(&self, process: &Process, profile: &str) -> Result<()> {
        if self.read(process.pid, profile).as_ref() != Some(process) {
            return Ok(());
        }
        self.host
            .terminate(process.pid, &|| self.read(process.pid, profile).as_ref() == Some(process))
            .map_err(|_| anyhow!("Cannot safely terminate managed resource"))
    }

    fn wait(&self, profile: &str, done: impl Fn(&[Process]) -> bool) -> Vec<Process> {
        let deadline = Instant::now() + self.drain;
        loop {
            let current = self.processes(profile);
            if done(&current) || Instant::now() >= deadline {
                return current;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    pub fn stop(&self, state: &Snapshot) -> Result<()> {
        let profile = self.validate(state)?;
        if self.processes(&profile).iter().any(|p| is_widget_kind(&p.kind)) {
            self.control(&profile, "stop")?;
            let current = self.wait(&profile, |ps| !ps.iter().any(|p| is_widget_kind(&p.kind)));
            // Eww can leave its deflisten providers alive after closing its pipe.
            for process in current.iter().filter(|p| p.kind == "provider") {
                self.terminate(process, &profile)?;
            }
        }
        for process in state.processes.iter().filter(|p| p.kind == "tiler" || p.kind == "ws_watcher") {
            self.terminate(process, &profile)?;
        }
        if !self.wait(&profile, |ps| ps.is_empty()).is_empty() {
            bail!("Managed normal-mode resources are still running");
        }
        Ok(())
    }

    fn running(&self, profile: &str, kind: &str) -> bool {
        self.processes(profile).iter().any(|p| p.kind == kind)
    }

    fn appears(&self, profile: &str, kind: &str) -> bool {
        self.wait(profile, |ps| ps.iter().any(|p| p.kind == kind)).iter().any(|p| p.kind == kind)
    }

    pub fn restore(&self, state: &Snapshot) -> Result<()> {
        let profile = self.validate(state)?;
        let current = self.processes(&profile);
        let daemon = current.iter().any(|p| p.kind == "eww");
        let watcher = current.iter().any(|p| p.kind == "watcher");
        let needs_watcher = state.processes.iter().any(|p| p.kind == "watcher");
        if state.widgets && (!daemon || (needs_watcher && !watcher)) {
            if daemon || watcher {
                self.control(&profile, "stop")?;
                let remaining = self.wait(&profile, |ps| !ps.iter().any(|p| is_widget_kind(&p.kind)));
                if remaining.iter().any(|p| is_widget_kind(&p.kind)) {
                    bail!("TinyWidgets resources are still running before restart");
                }
            }
            self.control(&profile, "start")?;
            if !self.appears(&profile, "eww") {
                bail!("TinyWidgets did not restart");
            }
            if needs_watcher && !self.appears(&profile, "watcher") {
                bail!("TinyWidgets watcher did not restart");
            }
        }
        if state.tiler && !self.running(&profile, "tiler") {
            self.host
                .spawn_tiler(&self.home.join(".local/bin/wf-tile"))
                .map_err(|_| anyhow!("Cannot restart wf-tile watcher"))?;
            if !self.appears(&profile, "tiler") {
                bail!("wf-tile watcher did not restart");
            }
        }
        if state.ws_watcher && !self.running(&profile, "ws_watcher") {
            self.host
                .spawn_ws_watcher(&self.home.join(".local/bin/wf-ws-watch"))
                .map_err(|_| anyhow!("Cannot restart wf-ws-watch"))?;
            if !self.appears(&profile, "ws_watcher") {
                bail!("wf-ws-watch did not restart");
            }
        }
        Ok(())
    }
}

fn is_widget_kind(kind: &str) -> bool {
    matches!(kind, "eww" | "watcher" | "provider")
}
