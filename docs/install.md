# Installing Raccon Dots

## Requirements

- Linux, **Python 3.11+**, a UTF-8 terminal and a writable user HOME.
- **Wayland and Wayfire 0.11** for the desktop modules and tinyWidgets.
- **Arch / CachyOS, pacman and sudo** for automatic dependency installation. On other distributions, install the apps yourself and apply configuration only.
- Internet access when downloading packages, plugins or extensions.

The installer does not change the display manager, enable system services or change the login shell. Configure login, network, Bluetooth, PipeWire and power-profiles-daemon on the system as needed.

## Starting profiles

| Profile | Contents |
| --- | --- |
| `profiles/raccoon-desktop.json` | Full Wayfire desktop, tools, personal tinyWidgets layout, wallpaper colors and AI skills |
| `profiles/light-desktop.json` | The desktop with compact widgets, quiet theme and no transitions |
| `profiles/terminal-only.json` | Terminal, shell and CLI tools |
| `profiles/default.json` | Base desktop; no package installation, tinyWidgets optional |

Press **`r`** in the installer to load a profile, then review it before installing.

## Installer pages

**Arrows** move, **Space/Enter** select, **Tab/Shift+Tab** switch pages. `--plain` uses numbered input (`1 3 5`). `[x]` is selected; `[+]` is required by another selection.

| Key | Page / action |
| --- | --- |
| `f` | Features: Wayfire, dock, panels, power, themes, wallpapers, audio, tinyWidgets, styles |
| `a` | Apps: terminal, shell, launcher, notifications, locker, browser, editors, tools, AI |
| `l` | Alternative app for each role |
| `t` | [tinyWidgets](widgets.md) options |
| `p` | Package dependencies and optional extras |
| `s` | Setup: editor plugins/extensions, app rebuild, boot splash |
| `?` | Explain the focused component and its dependencies |
| `c` | Refresh checks |
| `v` | Review planned files and setup |
| `w` | Export the selection to `profiles/personal.json` |
| `h` | Restore a previous installation |
| `i` | Check, review and install |

Nothing is installed while browsing or checking.

### Alternatives

| Role | Options |
| --- | --- |
| Terminal | Kitty, Alacritty |
| Shell | Zsh, Fish |
| Launcher | Raccon Menu, Fuzzel, Rofi |
| Notifications | SwayNC, Mako |
| Screen lock | GTKLock, Swaylock |
| Browser | Firefox, Chromium |
| File manager | Dolphin, Thunar |

Packages are installed with `sudo pacman -S --needed`, keeping pacman's confirmation. Installed packages (including AUR builds) are kept.

## Command line

```sh
# Show every change without writing or downloading
./install.sh --dry-run --files

# Check a setup; nonzero exit status on blockers
./install.sh --profile profiles/raccoon-desktop.json --check

# Install a setup with its packages
./install.sh --profile profiles/raccoon-desktop.json --yes

# Save a selection as a profile
./install.sh --modules terminal,shell,tools --shell fish \
  --save-profile profiles/my-laptop.json --yes
```

Each run starts from the last installed choices in `~/.rdot`; `--profile` takes precedence. `--modules` without a profile adds to the previous selection.

## Setup actions

The Setup page can install the VS Code extensions in [`extras/vscode-extensions.txt`](../extras/vscode-extensions.txt), sync Neovim plugins, rebuild tinyWidgets, or install the **Raccon Code** boot splash ([`extras/plymouth/raccon-code`](../extras/plymouth/raccon-code)). The splash needs sudo and the `plymouth` initramfs hook already enabled.

## Recovery

Replaced files are backed up under `~/.local/state/raccon-dots/backups/TIMESTAMP-ID/`. Restore with **`h`** or:

```sh
./install.sh --restore ~/.local/state/raccon-dots/backups/TIMESTAMP-ID --yes
```

Restore newest first. Files edited after installing stop the restore instead of being overwritten. Restoring does not uninstall packages, editor plugins or tinyWidgets.
