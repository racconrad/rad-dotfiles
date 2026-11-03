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

## Install your den

```sh
cd ~/projects/raccon-dots
./install.sh
```

The English installer starts with the raccoon, features and requirements. Its terminal interface supports **arrow keys, Space and Tab**. The focused component shows what it does and which dependencies it needs. Press **`?`** for the full details, including installed, missing or manually sourced packages. Small terminals use a compact layout; `--plain` keeps numbered, line-based controls.

A complete starting profile includes your desktop and personal widgets:

```sh
./install.sh --profile profiles/raccoon-desktop.json
```

### Starting profiles

| Profile | Contents |
| --- | --- |
| `profiles/raccoon-desktop.json` | Your Wayfire desktop, tools, personal tinyWidgets layout, Minecraft, wallpaper colors and AI skills/preferences |
| `profiles/light-desktop.json` | Your desktop with the compact Gaming widget layout, quiet theme and no transitions |
| `profiles/terminal-only.json` | Terminal, shell and CLI tools |
| `profiles/default.json` | The base desktop selection; package installation off and tinyWidgets available as an optional feature |

Use **`r`** to load a starting or saved profile inside the installer. Loading a profile changes the draft selection; review it before installing.

## Requirements

- Linux, **Python 3.11+**, a UTF-8 terminal and a writable user HOME.
- **Wayland and Wayfire 0.11** for the desktop modules and tinyWidgets. Wayfire IPC/window-rules must be available when widgets run.
- **Arch / CachyOS, pacman and sudo** when enabling automatic dependency installation. On other distributions, install applications with your usual package manager and apply configuration only.
- Internet access when downloading packages, plugins, extensions or Cargo dependencies.
- For a tinyWidgets build: its local source checkout, Cargo, a C compiler, pkg-config, GTK3/gtk-layer-shell and Python GObject/Cairo support. These packages are included when dependency installation is enabled.

Auto mode uses an installed tinyWidgets runtime; it builds from local source when the app or requested Minecraft collection is missing. The source directory defaults to `~/projects/tinyWidgets`; change it on the widget page. Get the source from [racconrad/tinyWidgets](https://github.com/racconrad/tinyWidgets). This installer keeps that project independent and does not download its source automatically.

The graphical login, network, Bluetooth, PipeWire/WirePlumber and power-profiles-daemon services should be configured on the system as needed. The installer does not change the display manager, enable system services or change the login shell.

## Choose components

| Key | Page | Choose |
| --- | --- | --- |
| `f` | Features | Wayfire, dock, panels, power, themes, wallpapers, audio, tinyWidgets and global styles |
| `a` | Apps | Terminal, shell, launcher, notifications, locker, browser, file manager, editors, tools and AI settings/skills |
| `l` | Choices | Alternative applications for each role |
| `t` | Widgets | Your tinyWidgets layouts, themes, animations, integrations and app installation |
| `p` | Dependencies | Install selected app packages and dependencies; choose optional extras |
| `s` | Setup | Editor plugins/extensions or an explicit app rebuild |
| `r` | Profiles | Start from a complete or saved setup |

**Arrows** move focus, **Space/Enter** selects, **Tab/Shift+Tab** switches pages. In plain mode, type item numbers, including several at once such as `1 3 5`. `[x]` is explicitly selected; `[+]` means another selection needs it. Inspect the item to see its parent instead of guessing why it remains enabled.

| Action | Result |
| --- | --- |
| `?` | Explain the focused component and its dependencies |
| `c` | Refresh checks from local package databases |
| `v` | Review planned files, component dependencies and app setup |
| `w` | Export the current selection to `profiles/personal.json` |
| `h` | Browse and restore a previous installation |
| `i` | Check requirements, review and confirm installation |
| `q` | Quit |

Blocking requirements are shown before installation, with a recovery action. Checks cover the source checkout/build tools, an Eww configuration owned by another project, and unavailable packages when package installation is enabled. Nothing is installed while browsing or checking.

### Application alternatives

| Role | Options |
| --- | --- |
| Terminal | Kitty, Alacritty |
| Shell | Zsh, Fish |
| Launcher | Personal raccoon menu, Fuzzel, Rofi |
| Notifications | SwayNC, Mako |
| Screen lock | GTKLock, Swaylock |
| Browser | Firefox, Chromium |
| File manager | Dolphin, Thunar |

Helpers such as Fuzzel/Rofi can still be required by clipboard or wallpaper selectors. Neovim and VS Code can both be selected; VS Code owns the editor shortcut when selected. The chosen terminal runs the selected shell when its module is enabled.

Optional extra packages include jq, curl, wget, rsync, mpv and bluetuith. Dependencies are resolved per component. The installer reads local package databases, validates availability before invoking `sudo pacman -S --needed`, and keeps pacman's confirmation. Already-installed packages, including AUR builds, are kept. Missing packages outside configured repositories require your usual package manager.

## tinyWidgets: your personal feature

Enable **tinyWidgets** on Features to open its own page. The full feature includes the runtime and your selected personalization packs. The legacy `widgets` module remains available for configuration-only compatibility.

| Subfeature | What it provides | Dependencies |
| --- | --- | --- |
| Runtime | Visual editor, base widget catalog, Rust manager and theme bridge | Eww, GTK3, gtk-layer-shell, Python GObject/Cairo and fonts; Rust/C tools for builds |
| Saved layouts | Your profiles and editor grid/size preferences | tinyWidgets; active layouts add their integration dependencies |
| Themes | Your personal style plus Quiet, Pixel and Terminal presets | tinyWidgets |
| Motion | Your 60 FPS settings, Balanced 24 FPS or Quiet/no transitions | tinyWidgets |
| Wallpaper colors | Matugen palette updates without reopening windows | tinyWidgets + Matugen/theme module |
| Music | MPRIS display and playback controls | `playerctl` and an active player |
| GitHub | Activity and avatar support | GitHub CLI, ImageMagick and your own `gh auth login` |
| Minecraft | Your animated scene support | Pillow (`python-pillow`) and the collection bundled with tinyWidgets |

The source installer ships the app's bundled components. Integration checkboxes prepare their dependencies and your startup layout; they do not remove built-in components from tinyWidgets.

### Your layouts

- **Personal:** your current positions and sizing, including Minecraft and saved application shortcuts.
- **Trabajo:** clock, tasks, habits, system and app chest.
- **Gaming:** compact hardware and music widgets.
- **Dashboard:** clock, music, app chest, system and disks.
- **Cyberpunk:** clock, processes, cat, GitHub and system.
- **silly:** your playful arrangement with personal sizing.

Choose which saved layouts to install and which one should be active. **Keep** preserves an existing `instances.json`; on a fresh installation it starts with Trabajo, or the first saved layout you selected. Choosing a different active layout backs up and replaces the instances file. Gaming/Dashboard add music dependencies; Cyberpunk adds GitHub; Personal adds Minecraft.

Private command/API/photo/note entries keep their placement and appearance but start disabled. Shell commands, URLs, tokens, paths to photos, private task/habit data and provider credentials are not exported. Saved launcher entries retain portable desktop application IDs; the corresponding applications may need separate installation, which the review notes identify.

Your **Personal** appearance is `bento / focus / surface`, captured from the desktop. Quiet, Pixel and Terminal are additional supported preset combinations. Motion is independent: your 60 FPS preset preserves the entrance/exit timings, workspace delay, stagger and two animation lanes. Other choices reduce the frame rate or disable transitions. The global style/animation files receive the selected preset; preset JSON files remain available under `~/.config/eww/presets/`.

After installing inside your Wayfire session:

```sh
widgetctl profile list
widgetctl profile apply Trabajo
widgetctl editor
```

### App installation modes

- **Auto:** use the installed app, or build when the runtime/requested collection is missing. Incomplete app setup stays retryable.
- **Build:** rebuild and install from the source directory you chose.
- **Configure:** install settings and layouts without executing the application installer.

The review shows the planned action and build dependencies. Long app setup displays real elapsed time and writes a log. Cancelling stops the child process group and preserves a retryable setup status.

## Check, install and save

```sh
# Inspect every configuration change without writes or downloads
./install.sh --dry-run --files

# Check a complete setup; returns a nonzero exit status for blockers
./install.sh --profile profiles/raccoon-desktop.json --check

# Install a chosen setup with package dependencies
./install.sh --profile profiles/raccoon-desktop.json --yes

# Choose widget presets explicitly
./install.sh --modules tinywidgets --widget-profile Personal \
  --widget-theme quiet --widget-motion balanced --packages --yes

# Configure an existing runtime; no rebuild or package installation
./install.sh --modules tinywidgets --widget-install configure \
  --no-packages --setup none --yes

# Export a selection into this repository
./install.sh --modules terminal,shell,tools --shell fish \
  --save-profile profiles/my-laptop.json --yes
```

Each run loads the last installed preferences from `~/.rdot`; `--profile FILE` takes precedence. An explicit `--modules` command without a profile adds modules to the previous selection. The wizard/profile selection is authoritative: disabled optional consumers stop starting those features next session, while their old files/packages remain available.

After installation:

- `~/.rdot` records version, resolved modules, alternatives, widget options, full setup recipe and configuration hashes/permissions.
- `~/.config/raccon-dots/profile.json` stores the portable setup recipe.
- `w` / `--save-profile` exports a repository copy; changed exports retain previous versions under `profiles/.history/PROFILE/` (ignored by Git).

A profile records the setup you applied. Later edits from graphical apps are not silently imported. To refresh the personal widget bundle, review the diff produced by:

```sh
python3 scripts/capture_widget_presets.py --from-home "$HOME"
python3 scripts/inventory.py
```

The exporter keeps portable appearance/layout settings and public launcher application IDs. tinyWidgets source remains in its canonical repository.

## Recovery

Replaced files and symlinks are backed up under `~/.local/state/raccon-dots/backups/TIMESTAMP-ID/`. Use **`h`**, or the exact printed path:

```sh
./install.sh --restore ~/.local/state/raccon-dots/backups/TIMESTAMP-ID --yes
```

Restore from newest to oldest. Files and previous preferences are recovered; newly introduced files from that delivery are removed. Later edits stop restoration before they are overwritten, allowing manual recovery from the backup. Identical files retain their inodes. Copy failures roll back; a journal saved before replacement preserves manual recovery information after abrupt interruption.

Packages, downloaded editor plugins/extensions and tinyWidgets application files have their own lifecycles. Dotfile restoration does not uninstall them. tinyWidgets keeps its installation backups under `~/.local/state/tinyWidgets/install-backups/`. App setup records/logs live under `~/.local/state/raccon-dots/`; a failed build keeps your saved selection for retry.

## Other app setup

The Setup page can install the extension IDs in [extras/vscode-extensions.txt](extras/vscode-extensions.txt), run Neovim's Lazy headless sync, explicitly rebuild tinyWidgets, or install the **Raccon Code** boot splash ([extras/plymouth/raccon-code](extras/plymouth/raccon-code)): the raccoon types code while the system boots, with boot progress and the disk-unlock prompt. It copies the theme to `/usr/share/plymouth/themes` and rebuilds the initramfs with sudo; the `plymouth` initramfs hook must already be enabled. Actions run after configuration installation and are saved in the setup profile. They may need network access. Source paths inside HOME are exported as `~/...` for portability.

## Global desktop styles

The desktop starting profiles include `desktop-styles`. Open **Estilo del escritorio**
from the applications or run `desktop-style` to preview and apply Default,
Transparent, Classic, Mono, Retro or Night. Default combines the former Modern,
GNOME and Windows profiles. Colors follow your wallpaper; Night keeps its navy,
ivory and coral palette. **Restaurar original** restores the previous appearance.

The module coordinates Waybar, Rofi, Raccon Menu, window decorations and the
configured Matugen application templates. It works without tinyWidgets and
integrates an installed runtime automatically. Old theme identifiers still work.
The resident picker loads one cached preview at a time. Photos, multicolor icons and application content keep their
colors. Some applications load their new theme when reopened.

```sh
# Preview the module and its dependencies without installing anything
./install.sh --modules desktop-styles --dry-run

# Export only the selector code and public assets, excluding personal state
python3 scripts/capture.py --from-home "$HOME" --styles-only
```

Silkscreen and its OFL license are bundled for Retro. The module declares GTK3,
Python GObject, librsvg and Adwaita fonts as dependencies. Runtime selections,
rollback snapshots and active overrides are generated locally and never exported.
Imports are enabled only when the styles module is selected. The menu's existing
structure, input handling and power controls are preserved.

## Bring changes from your primary instance

Use `rdot` to review and bring portable settings from your master machine into
this checkout. Desktop, style, AI and widget exporters are included:

```sh
./rdot master
./rdot changes
./rdot changes --modules ai,zsh --diff
./rdot capture --modules ai,zsh
```

Review changes nothing. Capture backs up previous working files, including
uncommitted edits, and only writes changed files. The base module installs the
`rdot` launcher.

## AI skills

The optional **ai** module keeps only the list of skills you installed with
skills.sh. No MCP servers, app settings or credentials are stored. The
`ai-skills` setup downloads them again with `npx skills add`.

```sh
python3 scripts/capture.py --from-home "$HOME" --ai-only
./install.sh --modules ai --setup ai-skills --yes
```

It is not in the default profile.

## Raccon Zsh prompt

The Zsh module enables the native **raccon** theme for Oh My Zsh. It also works
without Oh My Zsh and uses the terminal's ANSI palette, following the desktop
colors without running a palette generator on each command. Starship remains
available for Fish or manual use; Zsh no longer starts it automatically.

```text
╭─ raccon  ~/projects/raccon-dots  git:main +*?  3s
╰─ ❯
```

The prompt shows the current directory, branch (or detached commit), staged `+`,
modified `*`, untracked `?` and conflicted `!` files, plus commits ahead `↑` or
behind `↓` the upstream. Failed commands show `exit N` and a red prompt;
commands taking at least two seconds show their duration. SSH sessions include
`user@host`; root uses `#`. Narrow terminals shorten the path and branch and
hide secondary details when needed. No Nerd Font or extra prompt engine is required.

For an existing Oh My Zsh installation, copy
`modules/zsh/files/.oh-my-zsh/custom/themes/raccon.zsh-theme` into
`${ZSH_CUSTOM:-$ZSH/custom}/themes/`, set `ZSH_THEME="raccon"` in `~/.zshrc`,
and remove any later `starship init zsh` line. Open a new terminal to apply it.
To use plain ASCII, set `RACCON_PROMPT_ASCII=1` before loading the theme.
Set `RACCON_PROMPT_GIT=0` to disable repository inspection in very large trees.

## Contents and exclusions

Run `python3 scripts/inventory.py` to list every file locally. [modules.json](modules.json) defines dependencies and app alternatives; [widget-presets.json](widget-presets.json) describes the personal widget bundle.

Included settings cover Wayfire, the island dock and raccoon menu, Matugen/GTK/Qt, wallpapers, notification/locker choices, power profiles, shells/terminals, Yazi/LazyGit/Git/Delta, btop/Cava/Fastfetch, Neovim, optional Code and Legcord preferences, and quality Bluetooth audio without device identifiers. The personal keyboard layout is `us` with `altgr-intl`. Papirus supplies the portable icon theme. Oh My Zsh is optional.

**Orbit remains excluded.** Credentials, SSH/GPG keys, browser profiles, application sessions, histories, caches, private widget content and Git identity/authentication are not shipped.

## Development

```sh
# Try a complete widget configuration in a disposable HOME
./install.sh --target /tmp/raccon-preview-home --modules tinywidgets \
  --widget-install configure --widget-profile Personal --no-packages --setup none --yes

python3 -m unittest discover -s tests -v
python3 scripts/inventory.py
```

Package installation and external app setup require the real user HOME. Tests use disposable homes, package/app command mocks, portable layout contracts, terminal size fixtures and a local child process for progress logging. They cover profile persistence/history, dependencies, dry runs, setup failure recovery, symlinks, rollback and idempotence.

Edit `modules/MODULE/files/` as the versioned source. `scripts/capture.py --from-home PATH` captures a reviewed desktop allowlist; inspect the changes before keeping them. Widget presets use their separate exporter above so desktop capture does not overwrite your personal bundle.

### Modo Working

Con el módulo `power`, ejecuta `desktop-power set working` o selecciónalo con clics en la batería de Waybar (Auto → Ahorro → Balanced → Complete → Working). Mantiene los widgets visibles, desactiva animaciones y fondos animados, usa energía `balanced` y evita la suspensión por inactividad para trabajar con agentes. Evita también el bloqueo automático de pantalla y persiste entre reinicios; conserva el bloqueo manual. `desktop-power set auto` restaura las reglas automáticas. La suspensión manual y al cerrar la tapa no cambian.

### Raccon Menu in Eww

The desktop module now ships Raccon Menu as an Eww surface matching Waybar, with live theme colors and Waybar outlines, large daily app tiles, immediate native type-to-search, and compact attached PC mode/session panels. Account names and optional photos replace the mascot. `desktop-menu` remains the entry point. tinyWidgets keeps its own generated Eww configuration; sound/Wi-Fi/Bluetooth controls are compact side dropdowns inside Raccon Menu, just like PC Mode. They share its only Eww window and follow Waybar on all four edges with a 4px gap; the calendar retains GTK. Prewarming constructs the main window and attached dropdowns before first use; all five PC modes survive theme reloads. The menu includes a GTK fallback if Eww fails to open.

See [Raccon Menu](modules/desktop/files/.config/raccon-menu/README.md) for controls and theme management. `desktop-login-sddm --check` audits login managers; applying `--apply` with sudo is a separate, explicit system administration step. The dots installer does not change display managers.

The optional [Raccon SDDM theme](extras/sddm/README.md) matches the active desktop palette, font and shapes with a solid background. Run `./extras/install-sddm.sh --preview` to try it, then `--apply` to install it with sudo. Installation saves a backup and keeps the current session running.

Graphical authorization dialogs use MATE Polkit (GTK 3), launched by
`desktop-polkit` at Wayfire startup. It uses the session's GTK theme and color
files. Install it with `sudo pacman -S --needed mate-polkit`; the next login
selects it automatically. `desktop-polkit --check` prints the available agent.
During an incomplete package installation the launcher retains an available KDE
or GNOME agent. This changes the dialog application, without changing polkit
authorization rules.

## Tiling controls

The Wayfire module includes a resident Dwindle controller with a small themed
preview. **Super+I** chooses the next window's direction; **Super+D** moves a
window into a new split; **Super+R** resizes it with arrows. Enter/Esc finishes a
mode. Existing focus, swap and floating-grid shortcuts remain available.

**Super+Ctrl+Z** undoes a layout change; add Shift to redo. **Super+Ctrl+S/L**
saves/loads the workspace's favorite layout, and **Super+G** cycles 50/60/70%
split proportions. **Super+Ctrl+G** toggles smart gaps.

**Super+F6/F7/F8** toggles three application scratchpads. Add Shift to assign and
hide the focused window, or Ctrl to release it into the current workspace.
Super+U is an alias for slot 1. The independent Kitty panel keeps its own shortcut.

The first tiling shortcut starts the service and builds its native sender. Use
`wf-tile status` to check it, or `wf-tile restart` after updating the helper.
See [the shortcut reference](modules/wayfire/files/.config/wayfire-keys.md).

## Quick Kitty sidebar

With the Kitty module, **Super+Space** (or **Super+F12**) shows or hides a terminal panel at the right
edge. Rapid presses during a transition are coalesced; repeated toggles are
limited to one every 280ms. The terminal icon in Raccon Menu opens the same panel. **Ctrl+Esc** hides it
while keeping its shell, commands and scrollback. **Super+Shift+F12** or
**Ctrl+Shift+Q** in the panel closes that terminal session completely; the next
open starts a fresh shell. `exit` / Ctrl+D also ends it.

Commands: `raccon-term toggle|show|hide|close|status`. Layout and animation settings
are in `~/.config/raccon-term/config.json`, and the panel's Kitty settings are in
`~/.config/kitty/raccon-panel.conf`. It inherits the normal Kitty configuration
and colors. Size remains fixed during the animation so terminal applications do
not reflow. Position respects the active monitor and Waybar.

Waybar has two controls: a terminal icon to show/hide and a close button. The terminal icon is underlined when visible,
has a quiet underline while its session is hidden, and returns to its idle color
when closed. Hover for the state and shortcuts. Left click toggles, middle click
hides, and right click closes the session. The close icon disappears when
there is no running panel. After updating an existing session, reload Waybar
with `pkill -SIGUSR2 -x waybar` to load these controls.

The controller launches a normal dedicated Kitty window with a private local
control socket. Wayfire sets one fixed in-bounds geometry per reveal; opacity follows the menu’s cubic ease-out (170ms in, 113ms out), with one persistent IPC connection per worker. Nothing moves or
resizes while minimized. Kitty never receives offscreen layer-shell margins. The panel
is excluded from tiling, global window animations and Waybar's task list. Startup
errors are reported and logged at `~/.local/state/raccon-term/panel.log`. No
background controller service is needed.

Bindings and the controller are included only with the Kitty module.

The quick terminal hides when focus leaves it, retaining its session.
**Super+Shift+Space** closes it; the existing F12 shortcuts remain available.

Current quick panel: 520×520px, vertically centered at the right edge.
Opening/hiding uses an opacity fade at a fixed position. Initial
placement is checked against committed bounds before revealing. Waybar marks
the open panel with a thin underline, without a dot or background fill.

### Progressive popup loading

Raccon Menu seeds cached applications and desktop data before the live providers update them. Menu and Style controls appear together with a short 130ms surface fade. The wallpaper picker streams cached thumbnails first, then missing previews in bounded batches with two decoder workers; changing categories discards stale results. Style shows existing previews before refreshing them in the background, and its resident visibility commands bypass the theme renderer.

Style state, gallery requests and video-preview state use directory notifications
that survive atomic JSON replacement. Idle listeners block until a change; decoder
completions wake the gallery and only pending preview batches have a timer.
Quick-terminal Waybar modules refresh on startup and `SIGRTMIN+9`, with native
Wayfire events covering focus, minimize and external close. All four music buttons
share one `playerctl --follow status` provider across outputs. Subscribers reconnect
after failures; the provider exits and releases its player when the last bar leaves.

Menu and Style retain their GTK trees but unmap idle Wayland surfaces, releasing
pointer and keyboard input at the compositor. Reopening reuses the loaded tree.
Style, wallpaper/session and music panels release exclusive keyboard focus after
opening, so applications can regain focus with a click. `desktop-input-recover`
closes only Raccon popup daemons if an older panel still holds input; applications
and widgets keep running. Menu preparation waits for
GTK's ready marker and retries login-time failures. Wayfire also prepares the
wallpaper selector's daemon and adapter without opening a card. The app catalogue
uses GIO application-change notifications and emits only changed data.
`desktop-menu diagnose` includes `mapped`, `parked`, `open_us` and `map_us` to
separate native opening work from rendering/animation and launcher startup.

Typing an app search hides the utility/navigation rows until the search is
cleared. The wallpaper picker disables the active tile; the shared setter also
ignores the current canonical file under a transaction lock, including repeated
video requests. Failed image application preserves the previous selection.
