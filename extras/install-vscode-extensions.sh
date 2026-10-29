#!/bin/sh
# Explicit optional operation; each extension is installed by VS Code itself.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CODE_BIN=${CODE_BIN:-code}
command -v "$CODE_BIN" >/dev/null 2>&1 || { echo 'Install VS Code or set CODE_BIN.' >&2; exit 1; }
while IFS= read -r extension; do
    case "$extension" in ''|'#'*) continue ;; esac
    "$CODE_BIN" --install-extension "$extension"
done < "$ROOT/extras/vscode-extensions.txt"
