#!/usr/bin/env python3
"""Build the optional native Snap plugin without changing the desktop session."""
import argparse
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'modules/wayfire/plugins/snap-tiling'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', required=True, type=Path,
                        help='Dedicated Meson build directory outside the plugin source')
    parser.add_argument('--target-home', type=Path, default=Path.home(),
                        help='HOME whose .local prefix receives an explicit installation')
    parser.add_argument('--install', action='store_true',
                        help='Install the library and metadata; never enable or restart Wayfire')
    args = parser.parse_args(argv)
    build = args.build_dir.expanduser().resolve()
    home = args.target_home.expanduser().resolve()
    if build == SOURCE or SOURCE in build.parents or build in SOURCE.parents:
        parser.error('--build-dir must be separate from the plugin source tree')
    if home == Path('/') or (home.exists() and not home.is_dir()):
        parser.error('--target-home must be a valid HOME directory')
    setup = ['meson', 'setup']
    if (build / 'meson-private/coredata.dat').is_file():
        setup.append('--reconfigure')
    setup += [str(build), str(SOURCE), '--prefix', str(home / '.local'), '--libdir', 'lib']
    try:
        subprocess.run(setup, check=True)
        subprocess.run(['meson', 'compile', '-C', str(build)], check=True)
        if args.install:
            subprocess.run(['meson', 'install', '-C', str(build), '--no-rebuild'], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f'Snap build failed: {error}', file=sys.stderr)
        return 1
    print('Snap plugin built. Wayfire configuration and running session are unchanged.')
    if args.install:
        print(f'Installed under {home / ".local"}. Resolve plugin and key conflicts before enabling.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
