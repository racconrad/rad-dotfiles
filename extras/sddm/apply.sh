#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec bash "$root/modules/desktop-styles/files/.local/share/raccon/sddm/apply.sh" "$@"
