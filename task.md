# Raccon Dots for Hyprland

Branch `raccon-dots`, from `main` (Rad Dots for Wayfire, the old one) at f7f18a2.

## Done
- [x] `modules/hyprland`: modular Lua config in `~/.config/hypr` (one file per concern)
- [x] `crates/hypr-canvas`: Rust canvas daemon, `extras/install-hypr-canvas.sh`, setup action `hypr-canvas`
- [x] `profiles/hyprland-desktop.json`; `hyprland` replaces `wayfire` in the default modules
- [x] `INSTALL-HYPRLAND.txt`
- [x] Installer tests: 447 pass

## Port from Wayfire (modules still tied to it)
- [ ] `desktop-styles` requires `wayfire`: move borders and styles to `hypr/conf/look.lua`, then drop it from the requirement and add it to the profile
- [ ] `display-mode` (7 Wayfire calls): port to `hyprctl`/monitor rules; bound to Super+P
- [ ] `wallpaper-restore` (1 Wayfire call)
- [ ] `wf-tile`, `wf-focus-fx`, `raccon-wayfire-config.service`, `canvas-session`: replace or retire
- [ ] `modules/wayfire/plugins/snap-tiling`: no Hyprland equivalent; decide between layouts and drop
- [ ] `crates/raccon`: 7 sources mention Wayfire (menu shortcuts, working mode)
- [ ] Tests: about 20 `tests/test_wf_*`, `test_wayfire_*`, `test_snap_*` need Hyprland counterparts or removal
- [ ] `docs/*.md` and README still describe Wayfire

## Plugins and features
- [ ] `hyprpm`: enable `hyprexpo` (overview) and add its bind, plus `hyprpm reload` in autostart
- [ ] Wayfire-only effects without an equivalent: cube, wobbly, zoom, minimap, MRU, pin

## Validate in a real session
- [ ] Autostart: waybar, swaync, swayosd, awww, cliphist, hypridle, raccon-* services
- [ ] Keyboard and mouse binds of `hypr-canvas` (only the commands were tested, in a nested Hyprland)
- [ ] CPU and fans under load, compared with Wayfire

## Open
- [ ] Snapshot of the 160 uncommitted changes on `main` as "rad-dots wayfire (old)": needs a decision
