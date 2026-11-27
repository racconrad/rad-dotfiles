# Raccon Dots for Hyprland

Branch `raccon-dots` (default), rebased on `rad-dots-wayfire-old` (the former `main`, Rad Dots for Wayfire) at 89fe3ab.

## Done
- [x] `modules/hyprland`: modular Lua config in `~/.config/hypr` (one file per concern)
- [x] `crates/hypr-canvas`: Rust canvas daemon, `extras/install-hypr-canvas.sh`, setup action `hypr-canvas`
- [x] `modules/wayfire` retired and removed; `rad-dots-wayfire-old` preserves the Wayfire setup
- [x] `modules.json` and `profiles/*.json`: `hyprland` replaces `wayfire` across profiles and dependencies
- [x] `scripts/` (`install.py`, `doctor.py`, `capture.py`, `module_update.py`): Wayfire logic removed; `snap_build.py` and `wayfire_layers.py` deleted
- [x] `tests/`: Wayfire-only tests removed and remaining tests updated for Hyprland
- [x] `docs/*.md`, `README.md`, and `INSTALL-HYPRLAND.txt` updated for Hyprland
- [x] `desktop-styles`: borders and styles moved to `hypr/conf/window-style.lua` (`hyprland-theme-apply`)
- [x] `display-mode`: ported to `hyprctl` / monitor rules in `modules/hyprland/files/.local/bin/display-mode` (Super+P)
- [x] `wallpaper-restore`: Wayfire calls removed
- [x] `crates/raccon`: menu shortcuts, working mode, and Quickshell IPC bridge (`menu/qs.rs`) updated for Hyprland
- [x] `modules/quickshell`: all Eww widgets ported to Quickshell QML (`qs -c raccon`, `LazyLoader` IPC, `matugen` `quickshell-colors.json`)
- [x] Eww widget configs, GTK/C helpers, and dead `raccon_menu`/`raccon_countdown` Python removed; `tinywidgets` kept as optional legacy Eww
- [x] `scripts/`, `tests/`, and docs aligned with Quickshell and `crates/raccon`

## Remaining: plugins and real-session validation
- [x] `hyprpm reload -n` in autostart; run `hyprpm enable hyprexpo` and add its bind manually (needs network and confirmation)
- [ ] Autostart: swaync, swayosd, awww, cliphist, hypridle, `qs -c raccon --no-duplicate`, desktop-power
- [ ] Quickshell overlays (`menu`, `music`, `wallpaper`, `session`, `countdown`) in a real Hyprland session
- [ ] Keyboard and mouse binds of `hypr-canvas` (only the commands were tested, in a nested Hyprland)
- [ ] CPU and fans under load, compared with Wayfire

## Repository
- [x] Pending changes committed on the old branch; `main` renamed to `rad-dots-wayfire-old`; `raccon-dots` is the default branch
