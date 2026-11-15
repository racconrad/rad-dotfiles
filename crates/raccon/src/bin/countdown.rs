use std::env;
use std::process;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if let Err(err) = raccon::countdown::cli::run(args) {
        eprintln!("countdown: {}", err);
        process::exit(1);
    }
}
