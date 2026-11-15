use std::env;
use std::process;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if let Err(err) = raccon::menu::cli::run(args) {
        eprintln!("desktop-menu: {}", err);
        process::exit(1);
    }
}
