use anyhow::{bail, Result};
use canvas_session::system::{live_resources, sync_config, Live};
use std::path::Path;

fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let resources = live_resources(&Live);
    match args.as_slice() {
        [action] if action == "overlay" => {
            print!("{}", include_str!("overlay.ini"));
            Ok(())
        }
        [action] if action == "snapshot" => {
            println!("{}", serde_json::to_string(&resources.snapshot())?);
            Ok(())
        }
        [action, state] if action == "stop" => resources.stop(&serde_json::from_str(state)?),
        [action, state] if action == "restore" => resources.restore(&serde_json::from_str(state)?),
        [action, ini] if action == "sync" => sync_config(Path::new(ini)),
        _ => bail!("usage: canvas-session overlay|snapshot|stop JSON|restore JSON|sync INI"),
    }
}

fn main() -> Result<()> {
    run()
}
