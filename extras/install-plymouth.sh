#!/bin/sh
# Explicit optional operation; the boot splash lives outside HOME, so it needs sudo.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
THEME=raccon-code
command -v plymouth-set-default-theme >/dev/null 2>&1 || { echo 'Install plymouth and add its initramfs hook first.' >&2; exit 1; }
sudo install -Dm644 -t "/usr/share/plymouth/themes/$THEME" "$ROOT/extras/plymouth/$THEME"/*
sudo plymouth-set-default-theme --rebuild-initrd "$THEME"
echo "Boot splash set to $THEME. Undo with: sudo plymouth-set-default-theme -R <previous-theme>"
