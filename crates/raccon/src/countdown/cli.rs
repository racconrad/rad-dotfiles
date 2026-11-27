use crate::countdown::controller;
use crate::menu::runtime;

pub fn run(args: Vec<String>) -> Result<(), String> {
    if args.is_empty() {
        let status = controller::read_status();
        println!(
            "State: {} | Remaining: {} | Duration: {}s",
            status.state, status.time_formatted, status.duration_seconds
        );
        return Ok(());
    }

    match args[0].as_str() {
        "--supervisor" => {
            controller::run_supervisor();
            Ok(())
        }
        "--listen" => {
            controller::run_listen();
            Ok(())
        }
        "start" => {
            let spec = args
                .get(1)
                .ok_or("Missing time specification. Example: countdown start 25m")?;
            let label = args.get(2).map(|s| s.as_str()).unwrap_or("");
            let dur = controller::start(spec, label)?;
            println!("Countdown started: {}s (target: {})", dur, spec);
            Ok(())
        }
        "pause" => {
            controller::pause()?;
            println!("Countdown paused.");
            Ok(())
        }
        "resume" => {
            controller::resume()?;
            println!("Countdown resumed.");
            Ok(())
        }
        "toggle" => {
            controller::toggle()?;
            Ok(())
        }
        "stop" => {
            controller::stop()?;
            println!("Countdown stopped.");
            Ok(())
        }
        "open" => controller::open_ui(),
        "dock" => controller::dock_ui(),
        "ui" => runtime::open_menu(Some("timer")),
        "status" => {
            let json_flag = args.iter().any(|a| a == "--json");
            let status = controller::read_status();
            if json_flag {
                println!("{}", serde_json::to_string(&status).unwrap_or_default());
            } else {
                println!(
                    "State: {} | Time: {} | Percent: {}% | Label: {}",
                    status.state, status.time_formatted, status.percent, status.label
                );
            }
            Ok(())
        }
        "-h" | "--help" | "help" => {
            println!("Raccon Countdown Timer CLI\n");
            println!("Usage:");
            println!(
                "  countdown start <spec> [label]   Start a timer (e.g., 25m, 1h30m, 45s, 18:30, 5pm)"
            );
            println!("  countdown pause                  Pause active countdown");
            println!("  countdown resume                 Resume paused countdown");
            println!("  countdown toggle                 Toggle between pause and resume");
            println!("  countdown stop                   Stop timer and close UI");
            println!("  countdown status [--json]        Show timer status");
            println!("  countdown --listen               Stream timer status as JSON");
            Ok(())
        }
        _ => Err(format!("Unknown countdown command: {}", args[0])),
    }
}
