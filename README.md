# Raccon Dots

```text
⠀⠀⠀⠀⢀⣠⠤⠒⠒⠒⠒⠒⠒⠤⠤⣀⣀⣀⣀⣀⡤⠤⠤⠄⠤⡤⣲⣽⡇⠀
⠀⠀⡠⠖⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠁⠉⠁⠀⠀⠚⠛⠿⠰⠟⣿⡇⠀
⠀⡴⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡏⠀⠀⠀⠀⠙⡄⠀
⢰⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣇⠀⢸⣿⣷⣦⡇⠀
⣼⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡿⠷⣄⠉⠛⠈⠀⠀
⣇⠀⠀⠀⠀⣧⠀⠀⠀⠀⠀⠈⢦⠀⠀⠀⠀⠀⠀⠀⠀⣼⣆⠀⠈⢂⠀⣀⣡⠀
⠹⣴⣿⣶⣶⣿⣆⠀⠀⠀⠀⠀⠈⣷⡀⠀⠀⠀⠀⠀⠰⠿⠿⠦⠤⠶⣷⣿⣧⣄
⠀⢻⣩⣶⣿⣾⣏⠢⠀⠀⠀⠀⠀⢻⠈⠑⢄⠀⠀⢀⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠈⠿⢋⣥⣶⣿⣆⠑⡀⠀⠀⠀⡞⠀⠀⠈⢶⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠈⢼⡿⠋⢀⣠⣵⡘⢦⣤⣬⣤⣴⣤⣄⠘⠿⠶⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠁⢴⣿⡟⠉⢑⡌⠉⠉⠉⠛⠳⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠙⢄⣾⡿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
```

Your personal desktop, packed for the next machine. Version **0.3.0**, defined in [`.rdot`](.rdot).

## Gallery

![Raccon desktop with the Night style: clock, pixel widgets, workspaces, taskbar and status bar](assets/screenshots/desktop.jpg)

Raccon Menu opens from the bar or with <kbd>Super</kbd>: search apps, switch power
modes, control audio, Wi-Fi and Bluetooth, and look up every shortcut.

| Shortcuts | Power modes |
| :---: | :---: |
| ![Raccon Menu with the shortcuts panel](assets/screenshots/menu-shortcuts.jpg) | ![Raccon Menu with the power modes panel](assets/screenshots/menu-modes.jpg) |

Six desktop styles change the bar, Raccon Menu, window borders and app themes
together. Colors follow your own wallpaper (none is bundled); Night keeps a
fixed navy, ivory and coral palette.

| Default | Transparent | Classic |
| :---: | :---: | :---: |
| ![Default style](modules/desktop-styles/files/.config/desktop-style/previews/modern.png) | ![Transparent style](modules/desktop-styles/files/.config/desktop-style/previews/glass.png) | ![Classic style](modules/desktop-styles/files/.config/desktop-style/previews/terminal.png) |
| **Mono** | **Retro** | **Night** |
| ![Mono style](modules/desktop-styles/files/.config/desktop-style/previews/monochrome.png) | ![Retro style](modules/desktop-styles/files/.config/desktop-style/previews/retro.png) | ![Night style](modules/desktop-styles/files/.config/desktop-style/previews/ascii.png) |

<table>
<tr>
<td width="60%"><img src="modules/desktop-styles/files/.local/share/raccon/sddm/raccon/preview.png" alt="Raccon SDDM login screen"></td>
<td width="40%"><img src="extras/plymouth/raccon-code/raccoon.png" alt="Raccoon Plymouth boot splash"></td>
</tr>
<tr>
<td align="center">Login screen for SDDM (<code>extras/install-sddm.sh</code>)</td>
<td align="center">Boot splash that types code (<code>--setup plymouth</code>)</td>
</tr>
</table>

## Install

Needs Linux, Python 3.11+ and Wayfire 0.11. Automatic package installation needs Arch or CachyOS.

```sh
git clone https://github.com/racconrad/dotfiles.git ~/projects/raccon-dots
cd ~/projects/raccon-dots
./install.sh                                         # interactive installer
./install.sh --profile profiles/raccoon-desktop.json # full desktop
```

The installer previews every change, backs up the files it replaces and lets you restore them with `h`.

## Docs

- [Install](docs/install.md): requirements, profiles, installer keys, CLI, recovery
- [Desktop](docs/desktop.md): styles, Raccon Menu, power modes, tiling, Kitty panel, Zsh prompt
- [tinyWidgets](docs/widgets.md): widget layouts, themes and install modes
- [Maintenance](docs/maintenance.md): `rdot`, AI skills, what is never shipped, tests
