#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

for arg in "$@"; do
    case "$arg" in
        --check|--widget-*|--tinywidgets-*|--profile*|--save-profile*)
            command -v python3 >/dev/null 2>&1 || { echo 'Raccon Dots requires Python 3.11+ for profile options.' >&2; exit 1; }
            exec python3 "$ROOT/scripts/install.py" "$@"
            ;;
    esac
done

RACCON_BIN="$ROOT/crates/raccon/target/release/raccon"
if [ -x "$RACCON_BIN" ]; then
    exec "$RACCON_BIN" install "$@"
fi

if command -v raccon >/dev/null 2>&1; then
    exec raccon install "$@"
fi

command -v python3 >/dev/null 2>&1 || { echo 'Raccon Dots requires Rust or Python 3.11+.' >&2; exit 1; }
exec python3 "$ROOT/scripts/install.py" "$@"
