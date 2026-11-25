#!/bin/sh
# Builds the hypr-canvas daemon from crates/hypr-canvas and installs it into ~/.local/bin.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CRATE="$ROOT/crates/hypr-canvas"
command -v cargo >/dev/null 2>&1 || { echo 'cargo is required (pacman -S rust).' >&2; exit 1; }
cargo build --release --locked --manifest-path "$CRATE/Cargo.toml" --target-dir "${XDG_CACHE_HOME:-$HOME/.cache}/raccon-dots/hypr-canvas-target"
install -Dm755 "${XDG_CACHE_HOME:-$HOME/.cache}/raccon-dots/hypr-canvas-target/release/hypr-canvas" "$HOME/.local/bin/hypr-canvas"
echo "Installed $HOME/.local/bin/hypr-canvas"
