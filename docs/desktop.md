# Desktop

## Styles

Run `desktop-style` (or open **Estilo del escritorio**) to preview and apply Default, Transparent, Classic, Mono, Retro or Night. A style changes Waybar, Rofi, Raccon Menu, window borders and Matugen app themes together. Colors follow your wallpaper; Night keeps a fixed palette. **Restaurar original** restores the previous look. Some apps need reopening.

## Raccon Menu

Opens from the bar or with <kbd>Super</kbd>: app search, power modes, sound, Wi-Fi, Bluetooth, calendar and shortcuts. See the [Raccon Menu README](../modules/desktop/files/.config/raccon-menu/README.md).

## Power modes

With the `power` module, click the battery in Waybar to cycle Auto → Ahorro → Balanced → Complete → Working, or run `desktop-power set MODE`.

**Working** keeps widgets visible, turns off animations and animated wallpapers, and prevents idle suspend and auto-lock, so long-running agents keep going. Manual lock, manual suspend and lid close still work. `desktop-power set auto` goes back to automatic rules.

## Tiling

| Keys | Action |
| --- | --- |
| Super+I | Direction for the next window |
| Super+D | Move window into a new split |
| Super+R | Resize with arrows (Enter/Esc to finish) |
| Super+G | Cycle 50/60/70% split |
| Super+Ctrl+Z | Undo layout (Shift: redo) |
| Super+Ctrl+S / L | Save / load the workspace layout |
| Super+Ctrl+G | Toggle smart gaps |
| Super+F6/F7/F8 | Scratchpads (Shift: assign, Ctrl: release) |

`wf-tile status` checks the service; `wf-tile restart` reloads it. Full list: [wayfire-keys.md](../modules/wayfire/files/.config/wayfire-keys.md).

## Quick Kitty panel

With the Kitty module, **Super+Space** shows or hides a terminal at the right edge. It hides when focus leaves and keeps its session. **Super+Shift+Space** closes the session.

The Waybar terminal icon toggles it (left click), hides it (middle) or closes it (right). Commands: `raccon-term toggle|show|hide|close|status`. Settings: `~/.config/raccon-term/config.json` and `~/.config/kitty/raccon-panel.conf`.

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
- **Polkit dialogs:** install `mate-polkit`; `desktop-polkit` starts it with the session theme.
