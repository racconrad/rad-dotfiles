# Desktop

## Styles

The desktop uses the fixed **Collage** style: sharp Vocaloid/UTAU paper-cutout layers and bold ink slices. Surfaces, Rofi, Raccon Menu, window borders and Matugen app themes adapt together to the active wallpaper colors. Run `desktop-style apply` or change wallpapers to update colors.

## Raccon Menu and Quickshell overlays

Raccon Menu, the floating music/wallpaper/session cards, and the countdown chip run in a single resident Quickshell instance (`qs -c raccon`, defined in [`shell.qml`](../modules/quickshell/files/.config/quickshell/raccon/shell.qml)). Launchers (`desktop-menu`, `raccon-float`, `raccon-music`, `countdown`) drive `qs -c raccon ipc` through the Rust `raccon` binary.

Raccon Menu opens from the bar or with <kbd>Super</kbd>: app search, power modes, sound, Wi-Fi, Bluetooth, calendar, timer, and shortcuts.

## Power modes

With the `power` module, use the Raccon Menu power page to cycle Auto → Ahorro → Balanced → Complete → Working, or run `desktop-power set MODE`.

**Working** keeps widgets visible, turns off animations and animated wallpapers, and prevents idle suspend and auto-lock, so long-running agents keep going. Manual lock, manual suspend and lid close still work. `desktop-power set auto` goes back to automatic rules.

## Window management

Hyprland configuration is split into modular Lua files under `~/.config/hypr/` (one file per concern). Use `hypr-canvas` (`--setup hypr-canvas`) for the infinite canvas daemon.

## Zsh prompt

The Zsh module ships the **raccon** theme. It works with or without Oh My Zsh and needs no Nerd Font.

```text
╭─ raccon  ~/projects/raccon-dots  git:main +*?  3s
╰─ ❯
```

It shows git state (`+` staged, `*` modified, `?` untracked, `!` conflicts, `↑↓` ahead/behind), failed exit codes and slow command durations. Set `RACCON_PROMPT_ASCII=1` for plain ASCII, or `RACCON_PROMPT_GIT=0` to skip git in huge repos.

To use it in an existing Oh My Zsh setup, copy [`raccon.zsh-theme`](../modules/zsh/files/.oh-my-zsh/custom/themes/raccon.zsh-theme) into `${ZSH_CUSTOM:-$ZSH/custom}/themes/` and set `ZSH_THEME="raccon"`.

## Login, boot and authorization

- **SDDM theme:** `./extras/install-sddm.sh --preview`, then `--apply` (sudo, saves a backup). See [extras/sddm](../extras/sddm/README.md).
- **Boot splash:** Setup page, see [install](install.md#setup-actions).
- **Polkit dialogs:** `hyprpolkitagent` is included with the `hyprland` module.
