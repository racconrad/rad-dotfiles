use anyhow::{bail, Result};
use canvas_session::system::sync_config;

fn main() -> Result<()> {
    match std::env::args().skip(1).collect::<Vec<_>>().as_slice() {
        [action] if action == "sync" => sync_config(),
        _ => bail!("usage: canvas-session sync (canvas controls are provided by hypr-canvas)"),
    }
}
