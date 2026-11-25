# hypr-canvas

An infinite canvas for Hyprland, written in Rust. It keeps a camera over your floating windows and
moves them through Hyprland's own IPC socket. Based on the Wayfire `canvas` plugin and on
`sarodscommits/hyprland-infinitie-desktop-v2`, without Python and without reading input devices.

- One thread, one `poll(2)`. With no gesture active it only wakes for a Hyprland event or a command.
- No `hyprctl` forks, no `input` group, no evdev. The cursor is read over IPC only while you drag.
- Each camera move is a single `[[BATCH]]` request, so Hyprland animates all windows together.
- Windows that stay off screen are not touched, so cost follows what is visible.
- About 370 KB binary and 2.5 MB resident.

## Build and install

    cargo build --release
    install -Dm755 target/release/hypr-canvas ~/.local/bin/hypr-canvas

Start `hypr-canvas daemon` from your Hyprland autostart. Requires Hyprland with the Lua config (0.55+).

## Commands

| Command | Does |
|---|---|
| `look <dir>` | focus the nearest floating window that way and center on it; wraps to the far side |
| `pan <dir> [px]` | move the camera |
| `move <dir>` | move the focused window; at the screen edge the canvas moves instead |
| `center`, `home`, `back` | center the focused window, return to the origin, previous camera position |
| `drag-start pan\|edge`, `drag-end` | desktop drag, or edge push while dragging a window (bind to mouse buttons) |
| `status`, `quit` | |

Focusing a window that is mostly off screen (launcher, notification, `look`) centers the camera on it.
Only floating, non-fullscreen windows take part. Each workspace has its own camera.

## Config

`~/.config/hypr-canvas/config`, `key = value`:

    step = 400     # px for pan and move
    margin = 240   # windows within this distance of the screen stay in sync during a pan
    follow = true  # center on windows focused off screen
    edge = 10      # px from the screen edge where a dragged window pushes the canvas
    speed = 1.6    # cursor to canvas ratio of the desktop drag
    invert = false

## Limits

No zoom: Hyprland has no per-window transform API outside a C++ plugin. The desktop drag stops at the
screen edge because the cursor does. Restarting the daemon takes the current layout as the new origin.
