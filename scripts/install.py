#!/usr/bin/env python3
"""Raccon Dots installer CLI and component orchestrator."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import functools
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from install_context import Context, ROOT
from terminal_ui import Terminal

import install_selection as _sel
import install_widgets as _wid
import install_render as _ren
import install_plan as _plan
import install_setup as _setup
import install_screens as _screens
import install_wizard as _wiz

CATALOG = json.loads((ROOT / 'modules.json').read_text())
RELEASE = json.loads((ROOT / '.rdot').read_text())
MASCOT = (ROOT / 'assets/raccoon.txt').read_text()
WIDGET_PRESETS = json.loads((ROOT / 'widget-presets.json').read_text())
WIDGET_COMPONENTS = _wid.WIDGET_COMPONENTS
TEMPLATE_OWNERS = _ren.TEMPLATE_OWNERS
ZSH_PERSONAL = _ren.ZSH_PERSONAL
FEATURES = _screens.FEATURES
APPS = _screens.APPS
GROUP_LABELS = _screens.GROUP_LABELS


def _wrap(fn):
    code = getattr(fn, '__code__', None)
    if not code or 'ctx' not in code.co_varnames:
        return fn

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if 'ctx' not in kwargs:
            kwargs['ctx'] = globals()
        return fn(*args, **kwargs)
    return wrapper


json_bytes = _wrap(_sel.json_bytes)
choices_for = _wrap(_sel.choices_for)
validate_selection = _wrap(_sel.validate_selection)
load_selection = _wrap(_sel.load_selection)
selection_for = _wrap(_sel.selection_for)
profile_destination = _wrap(_sel.profile_destination)
save_profile = _wrap(_sel.save_profile)
read_receipt = _wrap(_sel.read_receipt)
with_previous = _wrap(_sel.with_previous)
resolve_modules = _wrap(_sel.resolve_modules)
packages_for = _wrap(_sel.packages_for)
install_packages = _wrap(_sel.install_packages)
environment_snapshot = _wrap(_sel.environment_snapshot)
package_label = _wrap(_sel.package_label)

validate_widget_options = _wrap(_wid.validate_widget_options)
source_path = _wrap(_wid.source_path)
active_widget_profile = _wrap(_wid.active_widget_profile)
selected_modules = _wrap(_wid.selected_modules)
effective_setup = _wrap(_wid.effective_setup)
execution_selection = _wrap(_wid.execution_selection)
widget_rows = _wrap(_wid.widget_rows)

render = _wrap(_ren.render)

safe_relative = _wrap(_plan.safe_relative)
safe_destination = _wrap(_plan.safe_destination)
file_plan = _wrap(_plan.file_plan)
unchanged = _wrap(_plan.unchanged)
digest = _wrap(_plan.digest)
atomic_write = _wrap(_plan.atomic_write)
installation_lock = _wrap(_plan.installation_lock)
undo = _wrap(_plan.undo)
apply_plan = _wrap(_plan.apply_plan)
restore = _wrap(_plan.restore)
preview = _wrap(_plan.preview)

setup_preflight = _wrap(_setup.setup_preflight)
run_logged_command = _wrap(_setup.run_logged_command)
run_setup = _wrap(_setup.run_setup)
readiness = _wrap(_setup.readiness)
component_details = _wrap(_setup.component_details)

clear_screen = _wrap(_screens.clear_screen)
welcome = _wrap(_screens.welcome)
package_screen = _wrap(_screens.package_screen)
recovery_screen = _wrap(_screens.recovery_screen)
rows_for = _wrap(_screens.rows_for)
row_details = _wrap(_screens.row_details)

interactive = _wrap(_wiz.interactive)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Raccon Dots - personal desktop setup with saved profiles.')
    parser.add_argument('--update', action='store_true', help='Refresh installed modules; no packages or setup')
    parser.add_argument('--force-update', action='store_true', help='Overwrite locally modified files during --update (backups retained)')
    parser.add_argument('--modules', help='Comma-separated features/apps; terminal, shell, launcher, etc. are accepted')
    parser.add_argument('--target', type=Path, default=Path.home(), help='Target HOME; use a temporary directory to try the setup')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing files, installing packages or running app setup')
    parser.add_argument('--files', action='store_true', help='Show every configuration path')
    parser.add_argument('--packages', action=argparse.BooleanOptionalAction, default=None, help='Install selected app packages/dependencies with sudo pacman --needed')
    parser.add_argument('--extra-packages', help='Additional package names, separated by commas')
    parser.add_argument('--setup', help='Optional app setup: vscode-extensions,nvim-plugins,tinywidgets,plymouth,ai-skills (or none)')
    parser.add_argument('--tinywidgets-source', help='Local tinyWidgets source directory for its optional build/install')
    parser.add_argument('--widget-profile', choices=['keep', *WIDGET_PRESETS['profiles']], help='Active tinyWidgets layout; keep preserves existing instances')
    parser.add_argument('--widget-theme', choices=list(WIDGET_PRESETS['themes']), help='Personal tinyWidgets appearance preset')
    parser.add_argument('--widget-motion', choices=list(WIDGET_PRESETS['motions']), help='Personal tinyWidgets animation preset')
    parser.add_argument('--widget-install', choices=['auto', 'build', 'configure'], help='Install missing tinyWidgets, rebuild it, or configure only')
    parser.add_argument('--widget-components', help='Comma-separated tinyWidgets subfeatures, or none')
    parser.add_argument('--plain', action='store_true', help='Use a plain line-based interface instead of the interactive terminal UI')
    parser.add_argument('--check', action='store_true', help='Check the complete installation plan and requirements without changing files')
    parser.add_argument('--profile', type=Path, help='Load a saved JSON profile or an installed .rdot receipt')
    parser.add_argument('--save-profile', type=Path, help='Export the selected setup to a JSON profile after installation')
    parser.add_argument('--list', action='store_true', help='List available features, apps, alternatives and setup actions')
    parser.add_argument('--yes', action='store_true', help='Apply the selected setup without the interactive wizard')
    parser.add_argument('--restore', type=Path, help='Restore a previous installation backup for the target HOME')
    parser.add_argument('--version', action='version', version=RELEASE['version'])
    for key, info in CATALOG['choices'].items():
        parser.add_argument('--' + key, choices=info['options'])
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Python 3.11 or newer is required.')
    original_target = args.target.expanduser().absolute()
    if original_target.is_symlink():
        parser.error('--target must not be a symbolic link.')
    args.target = original_target.resolve()
    if args.target == Path('/') or (args.target.exists() and not args.target.is_dir()):
        parser.error('--target must be a valid HOME directory.')
    if args.force_update and not args.update:
        parser.error('--force-update requires --update.')
    if args.update:
        from module_update import run
        return run(args)
    if args.list:
        print(f'Raccon Dots {RELEASE["version"]}\n')
        for key, info in CATALOG['modules'].items():
            print(f'{key:16} {info["label"]}')
        print('\n' + '\n'.join(f'{k}: {", ".join(v["options"])}' for k, v in CATALOG['choices'].items()))
        print('\nOptional setup: ' + ', '.join(CATALOG['setup_actions']))
        return 0
    if args.restore:
        if any((args.dry_run, args.check, args.packages is not None, args.modules, args.profile, args.setup,
                args.extra_packages, args.save_profile, args.tinywidgets_source, args.widget_profile,
                args.widget_theme, args.widget_motion, args.widget_install, args.widget_components)):
            parser.error('--restore cannot be combined with installation or profile options.')
        if not args.yes:
            if not sys.stdin.isatty() or input('Restore this installation backup? [y/N]: ').lower() != 'y':
                return 0
        restore(args.restore, args.target)
        return 0
    args.selection = load_selection(args.target, args.profile)
    args.packages = args.selection['packages'] if args.packages is None else args.packages
    args.extra_packages = ([p.strip() for p in args.extra_packages.split(',') if p.strip()]
                           if args.extra_packages is not None else list(args.selection['extra_packages']))
    args.setup = ([] if args.setup == 'none' else args.setup.split(',')) if args.setup is not None else list(args.selection['setup'])
    args.tinywidgets_source = args.tinywidgets_source if args.tinywidgets_source is not None else args.selection['tinywidgets_source']
    args.widget_options = dict(args.selection['widgets'])
    for key in ('profile', 'theme', 'motion', 'install'):
        value = getattr(args, 'widget_' + key)
        if value is not None:
            args.widget_options[key] = value
    if args.widget_install is not None:
        args.setup = [name for name in args.setup if name != 'tinywidgets']
    if args.widget_components is not None:
        args.widget_options['components'] = [] if args.widget_components == 'none' else args.widget_components.split(',')
    requested = [name.strip() for name in args.modules.split(',')] if args.modules else list(args.selection['requested'])
    wizard = not args.modules and not args.dry_run and not args.check and not args.yes
    if wizard:
        if not sys.stdin.isatty():
            parser.error('Use --dry-run or --yes when running without an interactive terminal.')
        requested = interactive(args)
        if requested is None:
            return 0
        args.yes = True
    else:
        print(MASCOT)
    if args.modules and not args.profile:
        requested = with_previous(args.target, requested, choices_for(args))
    selection = selection_for(args, requested)
    modules = selected_modules(selection, args.target)
    execution = execution_selection(selection, args.target)
    plan = file_plan(args.target, modules, selection['choices'], selection)
    preview(args.target, modules, selection['choices'], plan, args.files, selection)
    report = readiness(selection, args.target, environment_snapshot())
    for message in report['blockers']:
        print('NEEDS ATTENTION: ' + message)
    for message in report['notes']:
        print('NOTE: ' + message)
    if args.dry_run or args.check:
        print('Preview only: no files written, packages installed or app setup executed.')
        return 1 if args.check and report['blockers'] else 0
    if not args.yes:
        if not sys.stdin.isatty():
            parser.error('Use --yes to apply this setup or --dry-run to review it.')
        if input('Install this setup and back up existing files? [y/N]: ').lower() != 'y':
            return 0
    if (selection['packages'] or execution['setup']) and args.target != Path.home().resolve():
        parser.error('Packages and app setup require your real HOME. Use --dry-run with a temporary --target.')
    if report['blockers']:
        raise ValueError('Complete these requirements before installing:\n- ' + '\n- '.join(report['blockers']))
    if args.save_profile:
        profile_destination(args.save_profile)
    if selection['packages']:
        print('[1/3] Preparing app packages and dependencies ...', flush=True)
        install_packages(packages_for(modules, selection['extra_packages'], execution['setup']))
    else:
        print('[1/3] Using your existing packages.', flush=True)
    print('[2/3] Installing configuration and saving your den ...', flush=True)
    apply_plan(args.target, plan, modules, selection['choices'], selection)
    if args.save_profile:
        save_profile(args.save_profile, selection)
    print('[3/3] ' + ('Setting up applications ...' if execution['setup'] else 'No app downloads or builds selected.'), flush=True)
    run_setup(execution, args.target)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Raccon Dots: {exc}', file=sys.stderr)
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.', file=sys.stderr)
        raise SystemExit(130)
