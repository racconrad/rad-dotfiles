use anyhow::{anyhow, Result};
use canvas_session::resources::{Host, Resources, Snapshot};
use std::cell::RefCell;
use std::path::{Path, PathBuf};
use std::time::Duration;
use tempfile::TempDir;

type Hook = RefCell<Box<dyn FnMut(&str) -> Result<()>>>;

struct Mock {
    which: RefCell<Option<PathBuf>>,
    controls: RefCell<Vec<Vec<String>>>,
    spawns: RefCell<Vec<PathBuf>>,
    ws_spawns: RefCell<Vec<PathBuf>>,
    terminated: RefCell<Vec<(i64, bool)>>,
    on_control: Hook,
    on_spawn: Hook,
    on_ws_spawn: Hook,
    on_terminate: Hook,
}

fn nothing() -> Hook {
    RefCell::new(Box::new(|_| Ok(())))
}

impl Host for Mock {
    fn which(&self, _: &str) -> Option<PathBuf> {
        self.which.borrow().clone()
    }

    fn control(&self, command: &Path, profile: &str, action: &str) -> Result<()> {
        self.controls.borrow_mut().push(vec![command.display().to_string(), profile.into(), action.into()]);
        (self.on_control.borrow_mut())(action)
    }

    fn spawn_tiler(&self, path: &Path) -> Result<()> {
        self.spawns.borrow_mut().push(path.into());
        (self.on_spawn.borrow_mut())("")
    }

    fn spawn_ws_watcher(&self, path: &Path) -> Result<()> {
        self.ws_spawns.borrow_mut().push(path.into());
        (self.on_ws_spawn.borrow_mut())("")
    }

    fn terminate(&self, pid: i64, same: &dyn Fn() -> bool) -> Result<()> {
        self.terminated.borrow_mut().push((pid, same()));
        (self.on_terminate.borrow_mut())(&pid.to_string())
    }
}

struct Fixture {
    _temp: TempDir,
    home: PathBuf,
    profile: String,
    proc: PathBuf,
    host: Mock,
}

fn process(proc: &Path, pid: u32, args: &[&str], birth: &str) {
    let dir = proc.join(pid.to_string());
    std::fs::create_dir_all(&dir).unwrap();
    let cmdline: Vec<u8> = args.iter().flat_map(|a| a.bytes().chain([0])).collect();
    std::fs::write(dir.join("cmdline"), cmdline).unwrap();
    std::fs::write(dir.join("stat"), format!("{pid} (name with spaces) S {}{birth} 0", "0 ".repeat(18))).unwrap();
}

fn remove(proc: &Path, pid: u32) {
    let _ = std::fs::remove_dir_all(proc.join(pid.to_string()));
}

impl Fixture {
    fn new() -> Self {
        let temp = TempDir::new().unwrap();
        let home = temp.path().to_path_buf();
        let profile = home.join(".config/eww");
        std::fs::create_dir_all(&profile).unwrap();
        let proc = home.join("proc");
        std::fs::create_dir(&proc).unwrap();
        let host = Mock {
            which: RefCell::new(Some("/bin/widgetctl".into())),
            controls: RefCell::default(),
            spawns: RefCell::default(),
            ws_spawns: RefCell::default(),
            terminated: RefCell::default(),
            on_control: nothing(),
            on_spawn: nothing(),
            on_ws_spawn: nothing(),
            on_terminate: nothing(),
        };
        let profile = std::fs::canonicalize(profile).unwrap().to_string_lossy().into_owned();
        Fixture { _temp: temp, home, profile, proc, host }
    }

    fn resources(&self) -> Resources<'_> {
        Resources {
            proc_root: self.proc.clone(),
            home: self.home.clone(),
            config: Some(PathBuf::from(&self.profile)),
            uid: unsafe { libc::getuid() },
            own_pid: std::process::id(),
            drain: Duration::ZERO,
            host: &self.host,
        }
    }

    fn eww(&self, pid: u32) {
        process(&self.proc, pid, &["eww", "--config", &self.profile, "daemon"], "101");
    }

    fn tiler_args(&self) -> String {
        self.home.join(".local/bin/wf-tile").display().to_string()
    }

    fn ws_watch_args(&self) -> String {
        self.home.join(".local/bin/wf-ws-watch").display().to_string()
    }

    fn pids(&self) -> Vec<i64> {
        self.resources().snapshot().processes.iter().map(|p| p.pid).collect()
    }

    fn on_control(&self, hook: impl FnMut(&str) -> Result<()> + 'static) {
        *self.host.on_control.borrow_mut() = Box::new(hook);
    }
}

fn message(result: Result<()>) -> String {
    format!("{:#}", result.unwrap_err())
}

#[test]
fn snapshot_excludes_other_profiles_users_and_arbitrary_commands() {
    let f = Fixture::new();
    f.eww(11);
    process(&f.proc, 12, &["eww", "--config", &f.home.join("music").display().to_string(), "daemon"], "101");
    process(&f.proc, 13, &["other", "--config", &f.profile, "watch"], "101");
    process(&f.proc, 14, &["python3", &f.tiler_args(), "watch"], "101");
    let state = f.resources().snapshot();
    assert!(state.widgets && state.tiler);
    assert_eq!(f.pids(), [11, 14]);
    assert!(!serde_json::to_string(&state).unwrap().contains("cmdline"));
    let mut other_user = f.resources();
    other_user.uid += 1;
    assert!(other_user.snapshot().processes.is_empty());
}

#[test]
fn stop_uses_explicit_profile_and_checks_drain() {
    let f = Fixture::new();
    process(&f.proc, 11, &["eww", "-c", &f.profile, "daemon"], "101");
    let state = f.resources().snapshot();
    let proc = f.proc.clone();
    f.on_control(move |_| Ok(remove(&proc, 11)));
    f.resources().stop(&state).unwrap();
    assert_eq!(*f.host.controls.borrow(), [vec!["/bin/widgetctl".to_string(), f.profile.clone(), "stop".into()]]);
}

#[test]
fn eww_clients_are_not_running_widget_resources() {
    let f = Fixture::new();
    for (pid, command) in [(21, "logs"), (22, "active-windows"), (23, "get"), (24, "open")] {
        process(&f.proc, pid, &["eww", "--config", &f.profile, command, "daemon"], "101");
    }
    let state = f.resources().snapshot();
    assert!(!state.widgets && state.processes.is_empty());
    f.resources().stop(&state).unwrap();
    assert!(f.host.controls.borrow().is_empty());
}

#[test]
fn eww_client_cannot_satisfy_daemon_restart_check() {
    let f = Fixture::new();
    let mut state = f.resources().snapshot();
    state.widgets = true;
    let (proc, profile) = (f.proc.clone(), f.profile.clone());
    f.on_control(move |_| Ok(process(&proc, 21, &["eww", "--config", &profile, "logs"], "101")));
    assert!(message(f.resources().restore(&state)).contains("TinyWidgets did not restart"));
}

#[test]
fn eww_daemon_subcommand_allows_global_flags_and_config_positions() {
    let f = Fixture::new();
    let config = format!("--config={}", f.profile);
    let commands: [Vec<&str>; 4] = [
        vec!["--config", &f.profile, "--no-daemonize", "daemon"],
        vec!["--no-daemonize", "daemon", "-c", &f.profile],
        vec!["daemon", &config, "--no-daemonize"],
        vec!["--debug", "-c", &f.profile, "daemon"],
    ];
    for (offset, args) in commands.iter().enumerate() {
        let mut full = vec!["eww"];
        full.extend(args);
        process(&f.proc, 21 + offset as u32, &full, "101");
    }
    assert_eq!(f.pids(), [21, 22, 23, 24]);
}

#[test]
fn surviving_widgets_fail_closed() {
    let f = Fixture::new();
    f.eww(11);
    assert!(message(f.resources().stop(&f.resources().snapshot())).contains("still running"));
}

#[test]
fn missing_controller_is_noop_only_without_widgets() {
    let f = Fixture::new();
    *f.host.which.borrow_mut() = None;
    f.resources().stop(&f.resources().snapshot()).unwrap();
    f.eww(11);
    assert!(message(f.resources().stop(&f.resources().snapshot())).contains("widgetctl"));
    assert!(f.host.controls.borrow().is_empty());
}

#[test]
fn reused_pid_is_never_signalled() {
    let f = Fixture::new();
    process(&f.proc, 14, &["python3", &f.tiler_args(), "watch"], "101");
    let state = f.resources().snapshot();
    process(&f.proc, 14, &["unrelated"], "202");
    f.resources().stop(&state).unwrap();
    assert!(f.host.terminated.borrow().is_empty());
}

#[test]
fn restore_only_previously_running_resources_without_duplicates() {
    let f = Fixture::new();
    let mut state = f.resources().snapshot();
    f.resources().restore(&state).unwrap();
    assert!(f.host.controls.borrow().is_empty() && f.host.spawns.borrow().is_empty());
    state.widgets = true;
    state.tiler = true;
    let (proc, profile, tiler) = (f.proc.clone(), f.profile.clone(), f.tiler_args());
    f.on_control(move |_| Ok(process(&proc, 11, &["eww", "--config", &profile, "daemon"], "101")));
    let proc = f.proc.clone();
    *f.host.on_spawn.borrow_mut() = Box::new(move |_| Ok(process(&proc, 14, &["python3", &tiler, "watch"], "101")));
    f.resources().restore(&state).unwrap();
    assert_eq!(f.host.controls.borrow()[0][2], "start");
    assert_eq!(*f.host.spawns.borrow(), [f.home.join(".local/bin/wf-tile")]);
    f.resources().restore(&state).unwrap();
    assert_eq!((f.host.controls.borrow().len(), f.host.spawns.borrow().len()), (1, 1));
}

#[test]
fn partial_stop_restore_restarts_missing_daemon_without_duplicate_watcher() {
    let f = Fixture::new();
    process(&f.proc, 12, &["randly-widget-manager", "--config", &f.profile, "watch"], "101");
    let state = f.resources().snapshot();
    let (proc, profile) = (f.proc.clone(), f.profile.clone());
    f.on_control(move |action| {
        if action == "stop" {
            remove(&proc, 12);
        } else {
            process(&proc, 11, &["eww", "--config", &profile, "daemon"], "101");
            process(&proc, 12, &["randly-widget-manager", "--config", &profile, "watch"], "101");
        }
        Ok(())
    });
    f.resources().restore(&state).unwrap();
    let actions: Vec<String> = f.host.controls.borrow().iter().map(|c| c[2].clone()).collect();
    assert_eq!(actions, ["stop", "start"]);
}

#[test]
fn restore_requires_previously_running_watcher_to_return() {
    let f = Fixture::new();
    process(&f.proc, 12, &["randly-widget-manager", "--config", &f.profile, "watch"], "101");
    let state = f.resources().snapshot();
    remove(&f.proc, 12);
    let (proc, profile) = (f.proc.clone(), f.profile.clone());
    f.on_control(move |_| Ok(process(&proc, 11, &["eww", "--config", &profile, "daemon"], "101")));
    assert!(message(f.resources().restore(&state)).contains("watcher did not restart"));
}

#[test]
fn provider_cleanup_uses_a_handle_and_exact_identity() {
    let f = Fixture::new();
    let entry = f.home.join(".local/lib/randly_widgets/entry.py").display().to_string();
    process(&f.proc, 11, &["python3", &entry, "--config", &f.profile, "data", "clock"], "101");
    let state = f.resources().snapshot();
    let proc = f.proc.clone();
    *f.host.on_terminate.borrow_mut() = Box::new(move |_| Ok(remove(&proc, 11)));
    f.resources().stop(&state).unwrap();
    assert_eq!(*f.host.terminated.borrow(), [(11, true)]);
}

#[test]
fn control_failure_and_wrong_profile_are_errors() {
    let f = Fixture::new();
    let mut state = f.resources().snapshot();
    state.widgets = true;
    f.on_control(|_| Err(anyhow!("widgetctl failed")));
    assert!(message(f.resources().restore(&state)).contains("start failed"));
    state.profile = "/different/profile".into();
    assert!(message(f.resources().stop(&state)).contains("profile changed"));
}

#[test]
fn provider_and_manager_are_identified_with_exact_profile() {
    let f = Fixture::new();
    let entry = f.home.join(".local/lib/randly_widgets/entry.py").display().to_string();
    process(&f.proc, 11, &["python3", &entry, "--config", &f.profile, "data", "clock"], "101");
    process(&f.proc, 12, &["randly-widget-manager", "--config", &f.profile, "watch"], "101");
    let kinds: Vec<String> = f.resources().snapshot().processes.iter().map(|p| p.kind.clone()).collect();
    assert_eq!(kinds, ["provider", "watcher"]);
}

#[test]
fn snapshot_roundtrips_as_json() {
    let f = Fixture::new();
    f.eww(11);
    let state = f.resources().snapshot();
    let back: Snapshot = serde_json::from_str(&serde_json::to_string(&state).unwrap()).unwrap();
    assert_eq!(back, state);
}

#[test]
fn ws_watcher_is_stopped_and_restored_without_touching_widgets() {
    let f = Fixture::new();
    let ws = f.ws_watch_args();
    process(&f.proc, 15, &["python3", &ws], "101");
    let state = f.resources().snapshot();
    assert!(!state.widgets && !state.tiler && state.ws_watcher);
    assert_eq!(state.processes.iter().map(|p| p.kind.as_str()).collect::<Vec<_>>(), ["ws_watcher"]);

    let proc = f.proc.clone();
    *f.host.on_terminate.borrow_mut() = Box::new(move |_| Ok(remove(&proc, 15)));
    f.resources().stop(&state).unwrap();
    assert!(f.host.controls.borrow().is_empty());
    assert_eq!(*f.host.terminated.borrow(), [(15, true)]);

    assert!(message(f.resources().restore(&state)).contains("wf-ws-watch did not restart"));
    f.host.ws_spawns.borrow_mut().clear();

    let proc = f.proc.clone();
    *f.host.on_ws_spawn.borrow_mut() = Box::new(move |_| Ok(process(&proc, 16, &[&ws], "202")));
    f.resources().restore(&state).unwrap();
    assert_eq!(*f.host.ws_spawns.borrow(), [f.home.join(".local/bin/wf-ws-watch")]);
    f.resources().restore(&state).unwrap();
    assert_eq!(f.host.ws_spawns.borrow().len(), 1);
}
