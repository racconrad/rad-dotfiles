#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v python3 >/dev/null 2>&1 || { echo 'Raccon Dots requires Python 3.11 or newer.' >&2; exit 1; }
exec python3 "$ROOT/scripts/install.py" "$@"
