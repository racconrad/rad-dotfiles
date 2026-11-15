use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process;

use raccon::dotfiles::capture::capture_module_configs;
use raccon::dotfiles::catalog::Catalog;
use raccon::dotfiles::doctor::diagnose;
use raccon::dotfiles::installer::{apply_plan, build_plan};
use raccon::dotfiles::updater::update_modules;
use raccon::dotfiles::wayfire::sync_wayfire;
use raccon::util::paths;

#[derive(Parser)]
#[command(name = "raccon", version, about = "Raccon Dots Unified Manager")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Desktop menu controls and data providers
    Menu {
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        args: Vec<String>,
    },
    /// Countdown timer utility and floating pill controller
    #[command(alias = "timer")]
    Countdown {
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        args: Vec<String>,
    },
    /// Interactive desktop UI launcher
    Ui {
        /// UI component to launch (timer, menu, music, wallpaper, session)
        #[arg(default_value = "menu")]
        target: String,
    },
    /// Install dotfiles modules
    Install {
        /// Target HOME directory (defaults to $HOME)
        #[arg(long, alias = "target")]
        target_home: Option<PathBuf>,
        /// Preview changes without writing files
        #[arg(long)]
        dry_run: bool,
        /// Comma-separated list of modules to install (defaults to profile/defaults)
        #[arg(long)]
        modules: Option<String>,
        /// Proceed without confirmation prompt
        #[arg(long)]
        yes: bool,
        /// Package installation flag (noop/forwarded)
        #[arg(long)]
        packages: bool,
    },
    /// Update installed module files
    Update {
        /// Target HOME directory (defaults to $HOME)
        #[arg(long, alias = "target")]
        target_home: Option<PathBuf>,
        /// Preview changes without writing files
        #[arg(long)]
        dry_run: bool,
        /// Comma-separated list of installed modules to refresh
        #[arg(long)]
        modules: Option<String>,
    },
    /// Diagnostics for installed components and processes
    Doctor {
        /// Target HOME directory (defaults to $HOME)
        #[arg(long, alias = "target")]
        target_home: Option<PathBuf>,
        /// Output diagnostics formatted as JSON
        #[arg(long)]
        json: bool,
    },
    /// Capture reviewed configurations back into the repository
    Capture {
        /// Target HOME directory (defaults to $HOME)
        #[arg(long)]
        target_home: Option<PathBuf>,
        /// Preview changes without writing to repo
        #[arg(long)]
        dry_run: bool,
        /// Comma-separated list of modules to capture
        #[arg(long)]
        modules: Option<String>,
    },
    /// Synchronize Wayfire configuration layers (raccon.ini + user.ini -> wayfire.ini)
    Wayfire {
        /// Synchronize layers now
        #[arg(long)]
        sync: bool,
        /// Path to config directory (defaults to $XDG_CONFIG_HOME or ~/.config)
        #[arg(long)]
        config_dir: Option<PathBuf>,
    },
}

fn repo_root() -> PathBuf {
    let current = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if current.join("modules.json").is_file() {
        return current;
    }
    for ancestor in current.ancestors() {
        if ancestor.join("modules.json").is_file() {
            return ancestor.to_path_buf();
        }
    }
    PathBuf::from("/mnt/code/projects/rad-dotfiles")
}

fn main() {
    let cli = Cli::parse();
    let root = repo_root();

    match cli.command {
        Commands::Menu { args } => {
            if let Err(err) = raccon::menu::cli::run(args) {
                eprintln!("raccon menu: {}", err);
                process::exit(1);
            }
        }
        Commands::Countdown { args } => {
            if let Err(err) = raccon::countdown::cli::run(args) {
                eprintln!("raccon countdown: {}", err);
                process::exit(1);
            }
        }
        Commands::Ui { target } => match target.as_str() {
            "timer" | "countdown" => {
                let _ = raccon::countdown::cli::run(vec!["ui".to_string()]);
            }
            "music" => {
                let _ = std::process::Command::new("raccon-music").spawn();
            }
            "wallpaper" => {
                let _ = std::process::Command::new("raccon-float").arg("wallpaper").spawn();
            }
            "session" => {
                let _ = std::process::Command::new("raccon-float").arg("session").spawn();
            }
            _ => {
                let _ = raccon::menu::cli::run(vec![]);
            }
        },
        Commands::Install {
            target_home,
            dry_run,
            modules,
            yes: _,
            packages: _,
        } => {
            let home = target_home.unwrap_or_else(paths::home_dir);
            let catalog = match Catalog::load_from_root(&root) {
                Ok(c) => c,
                Err(err) => {
                    eprintln!("raccon install: {}", err);
                    process::exit(1);
                }
            };

            let choices = catalog.default_choices();
            let requested: Vec<String> = match modules {
                Some(mods) => mods.split(',').map(|s| s.trim().to_string()).collect(),
                None => catalog.defaults.clone(),
            };

            let resolved = match catalog.resolve_modules(&requested, &choices) {
                Ok(r) => r,
                Err(err) => {
                    eprintln!("raccon install: {}", err);
                    process::exit(1);
                }
            };

            let plan = match build_plan(&root, &home, &resolved, &choices) {
                Ok(p) => p,
                Err(err) => {
                    eprintln!("raccon install: {}", err);
                    process::exit(1);
                }
            };

            if let Err(err) = apply_plan(&home, &plan, &resolved, &choices, dry_run) {
                eprintln!("raccon install: {}", err);
                process::exit(1);
            }
        }
        Commands::Update {
            target_home,
            dry_run,
            modules,
        } => {
            let home = target_home.unwrap_or_else(paths::home_dir);
            let selected = modules.map(|m| m.split(',').map(|s| s.trim().to_string()).collect());

            if let Err(err) = update_modules(&root, &home, selected, dry_run) {
                eprintln!("raccon update: {}", err);
                process::exit(1);
            }
        }
        Commands::Doctor { target_home, json } => {
            let home = target_home.unwrap_or_else(paths::home_dir);
            let checks = diagnose(&home);

            if json {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&checks).unwrap_or_default()
                );
            } else {
                println!("Raccon Doctor - System Diagnostics\n");
                for check in checks {
                    let mark = match check.status.as_str() {
                        "ok" => "[✓]",
                        "warn" => "[!]",
                        _ => "[✗]",
                    };
                    println!(
                        "{} {:<14} {:<24} {}",
                        mark, check.category, check.name, check.detail
                    );
                    if !check.hint.is_empty() {
                        println!("    Hint: {}", check.hint);
                    }
                }
            }
        }
        Commands::Capture {
            target_home,
            dry_run,
            modules,
        } => {
            let home = target_home.unwrap_or_else(paths::home_dir);
            let target_modules: Vec<String> = match modules {
                Some(mods) => mods.split(',').map(|s| s.trim().to_string()).collect(),
                None => vec![
                    "wayfire".into(),
                    "waybar".into(),
                    "desktop".into(),
                    "power".into(),
                    "themes".into(),
                    "kitty".into(),
                ],
            };

            match capture_module_configs(&root, &home, &target_modules, dry_run) {
                Ok(count) => {
                    if dry_run {
                        println!("Dry-run capture: {} files identified.", count);
                    } else {
                        println!("Captured {} files into repository.", count);
                    }
                }
                Err(err) => {
                    eprintln!("raccon capture: {}", err);
                    process::exit(1);
                }
            }
        }
        Commands::Wayfire { sync, config_dir } => {
            let cfg = config_dir.unwrap_or_else(|| paths::home_dir().join(".config"));
            if sync {
                match sync_wayfire(&cfg) {
                    Ok(changed) => {
                        if changed {
                            println!("Wayfire layers synchronized: updated ~/.config/wayfire.ini");
                        } else {
                            println!("Wayfire layers are already up to date.");
                        }
                    }
                    Err(err) => {
                        eprintln!("raccon wayfire: {}", err);
                        process::exit(1);
                    }
                }
            } else {
                println!("Usage: raccon wayfire --sync");
            }
        }
    }
}
