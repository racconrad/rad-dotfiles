#!/bin/sh
# tinyWidgets keeps its own source, build and installation backups.
set -eu
if [ "$#" -ne 1 ]; then
    echo 'Usage: extras/install-tinywidgets.sh /path/to/tinyWidgets' >&2
    echo 'Get the project from https://github.com/racconrad/tinyWidgets' >&2
    exit 2
fi
SOURCE=$(CDPATH= cd -- "$1" && pwd)
if [ ! -f "$SOURCE/Cargo.toml" ] || [ ! -f "$SOURCE/scripts/install.sh" ] || [ ! -d "$SOURCE/python/randly_widgets" ]; then
    echo 'The source path does not contain tinyWidgets.' >&2
    exit 1
fi
exec sh "$SOURCE/scripts/install.sh"
