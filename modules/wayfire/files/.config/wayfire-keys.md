# Wayfire window-management shortcuts

Source of truth: `~/.config/wayfire.ini` (+ `~/.local/bin/wf-tile`). `Super` = logo key.

## Application menu

| Shortcut | Action |
|---|---|
| Super (tap and release) | Toggle Raccon Menu (Eww) |
| Super+Ctrl+Enter | Search applications (Fuzzel) |
| Super+A / Super+Shift+Enter | Toggle Raccon Menu (Eww) |
| Waybar launcher button | Hidden; use the shortcuts above |
| Super+L / Super+Ctrl+Q | Open Raccon session actions |
| Super+Shift+L | Lock the screen directly |

## Focus, move, resize (wf-tile)

| Shortcut | Tiled window | Floating window |
|---|---|---|
| Super+Arrows | Focus neighbour | Focus neighbour (tiled or floating) |
| Super+Alt+Arrows | Swap with neighbour | Move 60px (clamped to workarea) |
| Super+Ctrl+Alt+Arrows (repeat) | Resize split by 5% | Right/Down grow, Left/Up shrink 60px (min 240x160) |
| Super+J | Toggle the current split direction | — |
| Super+Ctrl+J | Rebuild the current tiled layout as Dwindle | Leave floating windows untouched |
| Super+Ctrl+T | Repair rendering and re-attach orphaned tiles; preserve layout | — |
| Super+Shift+T | Current workspace: tiling <-> floating | same |
| Super+T | Center as a comfortable floating window | Re-tile; remember floating size for next toggle |
| Super+LeftDrag / Super+RightDrag | Move / resize with mouse | same |

## Advanced tiling

| Shortcut | Action |
|---|---|
| Super+I, then an arrow | Choose where the next tiled window opens; preview lasts 20 seconds |
| Super+D, then arrows | Move the focused window into new splits |
| Super+R, then arrows | Resize the focused window; Enter/Esc finishes |
| Super+Esc | Cancel a mode or pending insertion |
| Super+Ctrl+Z / Super+Ctrl+Shift+Z | Undo / redo this workspace's layout changes |
| Super+Ctrl+S / Super+Ctrl+L | Save / load this workspace's favorite layout |
| Super+G | Focused split share: 50%, 60%, 70% |
| Super+Ctrl+G | Toggle smart gaps / the theme's normal gaps |
| Super+F6 / F7 / F8 | Show/hide scratchpad 1 / 2 / 3 on this workspace |
| Super+Shift+F6 / F7 / F8 | Assign the focused application to scratchpad 1 / 2 / 3 and hide it |
| Super+Ctrl+F6 / F7 / F8 | Release scratchpad 1 / 2 / 3 as a normal window here |
| Super+U / Super+Shift+U / Super+Ctrl+U | Scratchpad 1: toggle / assign / release |

Move and resize modes also accept H/J/K/L. Enter/Esc ends the mode and keeps
the result; use undo to restore the previous layout. Repeated adjustments in a
mode form one undo step. Existing swaps and floating-grid shortcuts still work.

The resident service starts automatically on the first tiling shortcut and
replaces the old insertion observer. Hotkeys use `wf-tile-ctl`, a small native
sender compiled locally on startup, and reuse the service's Wayfire connection.
`wf-tile status` reports its health; `wf-tile restart` restarts just this helper.

Saved layouts match applications on the current workspace, including after a
login; missing windows are skipped and additional tiles are kept. Multiple
windows from one application match in creation order. History and scratchpads
only use IDs from the current compositor session. Releasing a scratchpad returns
it to the current workspace's normal tiled/floating mode.

Smart gaps remove gaps when each visible monitor has at most one tile. Wayfire's
gap settings are global, so normal theme gaps are retained whenever any visible
monitor contains several tiles. Config edits are picked up by the service.

## Snapping (grid) — floating windows

Tiled windows are positioned by simple-tile; press Super+T to float first.

| Shortcut (laptop) | Keypad | Action |
|---|---|---|
| Super+Shift+Left | Super+KP4 | Left half |
| Super+Shift+Right | Super+KP6 | Right half |
| Super+Shift+Up | Super+KP8 | Top half |
| Super+Shift+Down | Super+KP2 | Bottom half |
| Super+Shift+Y | Super+KP7 | Top-left quarter |
| Super+Shift+I | Super+KP9 | Top-right quarter |
| Super+Shift+N | Super+KP1 | Bottom-left quarter |
| Super+Shift+M | Super+KP3 | Bottom-right quarter |
| Super+Shift+C | Super+KP5 | Center / fill workarea |
| Super+Shift+Z | Super+KP0 | Restore previous geometry |

## Window state (wm-actions, core)

| Shortcut | Action |
|---|---|
| Super+F | Fullscreen |
| Super+M | Maximize |
| Super+Shift+P | Always on top |
| Super+Shift+O | Sticky (show on all workspaces) |
| Super+Shift+H | Minimize (restore from taskbar) |
| Super+Shift+D | Show desktop |
| Super+Q | Close window |

## Workspaces and overview

| Shortcut | Action |
|---|---|
| Super+1..9, Super+0 | Go to workspace 1..10 |
| Super+Shift+1..9, Super+Shift+0 | Send window to workspace 1..10 |
| Super+Ctrl+Arrows | Switch workspace |
| Super+Ctrl+Shift+Arrows | Switch workspace carrying the window |
| Super+Backspace | Last workspace |
| Super+S | Expo (workspace overview) |
| Super+` | Scale (windows on workspace) |
| Super+Ctrl+Tab | Scale (all workspaces) |
| Alt+Tab / Alt+Shift+Tab | Switcher next / previous |
| Super+Ctrl+LeftDrag, Super+MiddleDrag | Cube |
| 3-finger swipe | Switch workspace |

## Power button

Waybar: a short click does nothing. Hold the left mouse button for 2 seconds, then release to power off. A hold longer than 12 seconds expires. Super+L or Super+Ctrl+Q opens Raccon session actions. Super+Shift+L locks directly.

Raccon Menu: `Super+L` o `Super+Ctrl+Q` abre Sesión; `Ctrl+1–4` cambia sección; `Ctrl+F` busca aplicaciones. El indicador de batería abre un selector de modo con Aplicar explícito.

## Automatic Dwindle layout

`wf-tile watch` listens for newly mapped windows. Two windows form columns; the next divides the active column into rows; the following divides the active row into columns. Other tiles and their manual split ratios stay intact. It does not re-layout continuously when focus changes.

The dedicated tiling observer owns insertion and floating-workspace adoption. `wf-focus-fx` handles opacity only, avoiding two competing floating operations. Workspace 10 and workspaces set to floating with Super+Shift+T remain floating, and utility/Picture-in-Picture exceptions are preserved.

Super+T remembers the size and position you chose while floating, and restores them on the next toggle. Without a previous floating size, it centers a window at 60% of the workarea width and 65% of its height. Fullscreen windows are left alone.

Tiled resizing applies the real client geometry directly (`simple-tile.animation_duration = 0`) instead of crossfading snapshots. Other compositor effects remain configured as before. Super+Ctrl+T rebuilds the current tile nodes to recover their scale transforms without toggling the whole desktop or losing the split tree.

Validation: `python3 tests/check_tiling_installed.py` uses a private Wayfire and animated test clients to check Dwindle cuts, per-window floating geometry restoration, workspace floating, utility exceptions, resize and live content updates. It does not move user windows.
