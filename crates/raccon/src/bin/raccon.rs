use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process;

use raccon::dotfiles::capture::capture_module_configs;
use raccon::dotfiles::catalog::Catalog;
use raccon::dotfiles::doctor::diagnose;
use raccon::dotfiles::installer::{apply_plan, build_plan};
use raccon::dotfiles::updater::update_modules;
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
    /// Wallpaper selector and directory configuration
    Wallpaper {
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

fn resolve_wallpaper_dir() -> PathBuf {
    let cfg = paths::home_dir().join(".config").join("raccon").join("wallpaper-dir");
    if let Ok(content) = std::fs::read_to_string(&cfg) {
        let trimmed = content.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    if let Ok(env_dir) = std::env::var("WALLPAPER_DIR") {
        if !env_dir.trim().is_empty() {
            return PathBuf::from(env_dir.trim());
        }
    }
    paths::home_dir().join("Pictures").join("Wallpapers")
}

fn set_wallpaper_dir(raw: &str) {
    let p = match std::fs::canonicalize(raw) {
        Ok(canon) if canon.is_dir() => canon,
        _ => {
            eprintln!("raccon wallpaper: '{}' is not a valid directory", raw);
            process::exit(1);
        }
    };
    let home = paths::home_dir();
    let cfg = home.join(".config").join("raccon").join("wallpaper-dir");
    if let Some(parent) = cfg.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(&cfg, format!("{}\n", p.display()));

    let waypaper_ini = home.join(".config").join("waypaper").join("config.ini");
    if let Ok(content) = std::fs::read_to_string(&waypaper_ini) {
        let updated: String = content
            .lines()
            .map(|line| {
                if line.starts_with("folder =") || line.starts_with("folder=") {
                    format!("folder = {}", p.display())
                } else {
                    line.to_string()
                }
            })
            .collect::<Vec<_>>()
            .join("\n")
            + "\n";
        let _ = std::fs::write(&waypaper_ini, updated);
    }

    let float_bin = home.join(".local/bin/raccon-float");
    if float_bin.is_file() {
        let _ = std::process::Command::new(float_bin).arg("refresh").status();
    }
    println!("Wallpaper directory set to: {}", p.display());
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
        Commands::Wallpaper { args } => {
            if args.is_empty() {
                let _ = std::process::Command::new("raccon-float").arg("wallpaper").spawn();
            } else if args[0] == "set-dir" && args.len() > 1 {
                set_wallpaper_dir(&args[1]);
            } else if args[0] == "dir" {
                println!("{}", resolve_wallpaper_dir().display());
            } else {
                let _ = std::process::Command::new("wallpaper-grid").args(&args).spawn();
            }
        }
        Commands::Ui { target } => {
            use raccon::menu::runtime::{open_menu, widget};
            let result = match target.as_str() {
                "timer" | "countdown" => open_menu(Some("timer")),
                name => widget("toggle", name),
            };
            if let Err(error) = result {
                eprintln!("raccon ui: {error}");
                process::exit(1);
            }
        }
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
                    "hyprland".into(),
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
    }
}
