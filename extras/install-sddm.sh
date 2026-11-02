#!/usr/bin/env bash
# Prepare without privileges; apply only the fully prepared theme as root.
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mode=${1:---prepare}
case "$mode" in
  --prepare|--preview|--apply) ;;
  *) printf 'Usage: %s --prepare|--preview|--apply [--background solid|wallpaper]\n' "$0" >&2; exit 2 ;;
esac
shift "$(( $# > 0 ? 1 : 0 ))"
theme=$(python3 "$root/extras/sddm/prepare.py" "$@")
case "$mode" in
  --prepare) printf 'Prepared: %s\nPreview: %q --preview\nInstall: %q --apply\n' "$theme" "$0" "$0" ;;
  --preview) exec sddm-greeter-qt6 --test-mode --theme "$theme" ;;
  --apply)
    # This only copies assets and selects a theme. Never restart SDDM or a session.
    sudo bash "$root/extras/sddm/apply.sh" "$theme"
    ;;
esac
