use hypr_canvas::{control, daemon};

const USAGE: &str = "usage: hypr-canvas daemon\n       hypr-canvas pan|look|move left|right|up|down [px]\n       hypr-canvas center|home|back|status|quit\n       hypr-canvas drag-start pan|edge | drag-end";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        None | Some("-h") | Some("--help") => println!("{USAGE}"),
        Some("daemon") => {
            if let Err(e) = daemon::run() {
                eprintln!("hypr-canvas: {e}");
                std::process::exit(1);
            }
        }
        Some(_) => match control::send(&args.join(" ")) {
            Ok(reply) => {
                if !reply.is_empty() {
                    println!("{reply}");
                }
                if reply.starts_with("error") {
                    std::process::exit(1);
                }
            }
            Err(_) => {
                eprintln!("hypr-canvas: daemon is not running (start it with `hypr-canvas daemon`)");
                std::process::exit(1);
            }
        },
    }
}
