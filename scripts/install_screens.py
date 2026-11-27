from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from install_context import Context, ROOT

CATALOG = json.loads((ROOT / 'modules.json').read_text())
RELEASE = json.loads((ROOT / '.rdot').read_text())
MASCOT = (ROOT / 'assets/raccoon.txt').read_text()
WIDGET_PRESETS = json.loads((ROOT / 'widget-presets.json').read_text())

FEATURES = ['hyprland', 'desktop', 'power', 'themes', 'wallpaper', 'audio', 'chat-theme', 'tinywidgets', 'desktop-styles', 'quickshell']
APPS = ['terminal', 'shell', 'launcher', 'notifications', 'lock', 'browser', 'filemanager', 'tools', 'git', 'nvim', 'vscode', 'ai']
GROUP_LABELS = {'terminal': 'Terminal application', 'shell': 'Shell and prompt',
                'launcher': 'Application launcher', 'notifications': 'Notifications', 'lock': 'Screen locker',
                'browser': 'Web browser', 'filemanager': 'File manager'}


def clear_screen():
    if sys.stdout.isatty() and os.environ.get('TERM', '') not in ('', 'dumb'):
        print('\033[2J\033[H', end='', flush=True)


def welcome(args, ctx=None):
    clear_screen()
    print(MASCOT)
    print(f'RACCON DOTS  {RELEASE["version"]}')
    print('Personal dotfiles to set up a comfortable, colorful Wayland desktop.\n')
    print('FEATURES')
    print('  Hyprland window management, an island dock and the raccoon app menu.')
    print('  Wallpaper-based Material You colors, GTK / Qt themes and matching apps.')
    print('  Terminal and shell choices, development tools and battery-aware effects.')
    print('  Optional tinyWidgets, editor setup, saved profiles and file recovery.\n')
    print('BEFORE YOU START')
    print('  Linux, Python 3.11+, a UTF-8 terminal and a writable user HOME.')
    print('  Hyprland + Wayland for the desktop modules.')
    print('  Arch / CachyOS + pacman + sudo when installing app dependencies.')
    print('  Internet access for package installation or app/plugin downloads.')
    print('  tinyWidgets setup also needs its local source and Rust/GTK build tools.')
    print('  Network, Bluetooth and audio services should be configured on your system.\n')
    print(f'Target HOME: {args.target}')
    print('Choose features and apps next. Existing files get installation backups.')
    return input('Press Enter to select components, or q to quit: ').strip().lower() != 'q'


def package_screen(args, modules, ctx=None):
    c = Context(ctx)
    print(f'  0. [{"x" if args.packages else " "}] Install selected apps and dependencies with pacman')
    required = set(c.packages_for(modules, setup=args.setup))
    for index, (name, label) in enumerate(CATALOG['optional_packages'].items(), 1):
        mark = '+' if name in required else 'x' if name in args.extra_packages else ' '
        print(f'  {index}. [{mark}] {name:12} {label}')
    print(f'\n  {len(required)} required packages from selected components. Press d to review the list.')
    print('  [+] Dependencies are automatic. Optional package choices are saved in your profile.')


def recovery_screen(args, ctx=None):
    c = Context(ctx)
    base = args.target / '.local/state/raccon-dots/backups'
    backups = []
    for path in sorted(base.glob('*/manifest.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
        try:
            journal = json.loads(path.read_text())
            if journal.get('status') == 'installed' and journal.get('home') == str(args.target):
                backups.append((path.parent, len(journal['files'])))
        except (OSError, ValueError, KeyError):
            continue
    if not backups:
        print('No restorable Raccon Dots backups for this HOME.')
        input('Press Enter to return: ')
        return False
    print('\nRESTORE A PREVIOUS INSTALLATION')
    print('Restore the newest backup first. Later edits are protected.')
    for index, (path, count) in enumerate(backups, 1):
        print(f'  {index}. {path.name} | {count} files')
    value = input('Backup number, or Enter to return: ').strip()
    if not value:
        return False
    if not value.isdigit() or not 1 <= int(value) <= len(backups):
        raise ValueError('Choose a backup number from the list.')
    backup = backups[int(value) - 1][0]
    if input(f'Restore {backup.name} and its previous preferences? [y/N]: ').lower() != 'y':
        return False
    c.restore(backup, args.target)
    input('Restored. Press Enter to return: ')
    return True


def rows_for(page, args, requested, selection, modules, inventory, ctx=None):
    c = Context(ctx)
    choices = selection['choices']
    if page in ('f', 'a'):
        rows = []
        for name in FEATURES if page == 'f' else APPS:
            resolved = choices.get(name, name)
            label = GROUP_LABELS.get(name, CATALOG['modules'].get(name, {}).get('label', name))
            mark = 'x' if name in requested else '+' if resolved in modules else ' '
            if name in choices:
                label += ': ' + choices[name]
            rows.append({'id': name, 'label': label, 'mark': mark, 'command': name})
        return rows
    if page == 'l':
        return [{'id': key, 'label': GROUP_LABELS[key] + ': ' + choices[key], 'mark': '~', 'command': key}
                for key in CATALOG['choices']]
    if page == 't':
        return c.widget_rows(args, requested, modules, inventory)
    if page == 'p':
        required = set(c.packages_for(modules, setup=c.effective_setup(selection, args.target)))
        rows = [{'id': 'packages', 'number': 0, 'label': 'Install app packages and dependencies',
                 'mark': 'x' if args.packages else ' ', 'command': 'packages'}]
        for index, (key, label) in enumerate(CATALOG['optional_packages'].items(), 1):
            mark = '+' if key in required else 'x' if key in args.extra_packages else ' '
            rows.append({'id': key, 'number': index, 'label': key + ' / ' + label,
                         'mark': mark, 'command': key})
        return rows
    if page == 'r':
        rows = []
        for path in sorted((ROOT / 'profiles').glob('*.json')):
            try:
                data = json.loads(path.read_text())
                c.validate_selection(data)
            except (OSError, ValueError):
                continue
            rows.append({'id': path.stem, 'label': data.get('title', path.stem.replace('-', ' ').title()),
                         'mark': '~', 'command': str(path)})
        return rows
    return [{'id': key, 'label': info['label'], 'mark': 'x' if key in args.setup else ' ', 'command': key}
            for key, info in CATALOG['setup_actions'].items()]


def row_details(page, row, args, requested, selection, modules, inventory, ctx=None):
    c = Context(ctx)
    key = row['id']
    if page in ('f', 'a', 'l') or (page == 't' and key in CATALOG['modules']):
        return c.component_details(key, selection['requested'], selection['choices'], modules, inventory, selection, args.target)
    if page == 't':
        if key.startswith('profile:'):
            name = key.split(':', 1)[1]
            meta = WIDGET_PRESETS['profiles'][name]
            return [name + ' / saved layout', meta['description'],
                    'Needs: ' + (', '.join(meta['requires']) or 'tinyWidgets base widgets'),
                    f'{meta["active_widgets"]} active widgets. Private sources are left inactive.',
                    'Use Active layout above to make this the startup layout.']
        if key == 'profile':
            name = args.widget_options['profile']
            meta = WIDGET_PRESETS['profiles'].get(name)
            return ['Startup layout: ' + name,
                    meta['description'] if meta else 'Preserve the existing layout. New installs start with Trabajo or your first selected saved profile.',
                    'Needs: ' + (', '.join(meta['requires']) if meta and meta['requires'] else 'personal layout presets'),
                    'Changing this layout writes instances.json with an installation backup.']
        if key in ('theme', 'motion'):
            group = 'themes' if key == 'theme' else 'motions'
            meta = WIDGET_PRESETS[group][args.widget_options[key]]
            return [meta['label'], meta['description'],
                    'Needs: ' + ('Personal themes' if key == 'theme' else 'Animation presets'),
                    'Space cycles presets. Colors follow Matugen when wallpaper integration is selected.']
        if key == 'source':
            source = c.source_path(args.tinywidgets_source, args.target)
            found = (source / 'scripts/install.sh').is_file() and (source / 'Cargo.toml').is_file()
            return ['tinyWidgets local source', 'Path: ' + args.tinywidgets_source,
                    'Needs: Cargo.toml, scripts/install.sh, python/randly_widgets',
                    'Status: ' + ('checkout found' if found else 'missing / choose your tinyWidgets checkout'),
                    'Get source from https://github.com/racconrad/tinyWidgets.']
        return ['tinyWidgets application',
                'Auto uses the installed app and builds it only when missing. Build always runs the source installer. Configure only writes settings.',
                'Source: ' + args.tinywidgets_source,
                'Needs for build: ' + ', '.join(CATALOG['setup_actions']['tinywidgets']['packages']),
                'Use a local checkout of https://github.com/racconrad/tinyWidgets.']
    if page == 'p':
        if key == 'packages':
            result = ['Install selected app packages and dependencies',
                      'Packages are resolved from every selected feature and integration. Existing packages are kept.',
                      'Needs: Arch / CachyOS, pacman, sudo and network for package downloads.']
            result += [c.package_label(p, inventory) for p in c.packages_for(modules, args.extra_packages, c.effective_setup(selection, args.target))]
            return result
        return [row['label'], c.package_label(key, inventory), 'Enable package installation to install this optional package.']
    if page == 'r':
        data = json.loads(Path(row['command']).read_text())
        preset = c.validate_selection(data)
        included = c.selected_modules(preset, args.target)
        return [row['label'], data.get('description', 'Your saved setup selection.'),
                'Needs: ' + ', '.join(included),
                'Packages: ' + str(len(c.packages_for(included))) + ' dependencies; review before installation.',
                'Loads the selection for review. It does not install anything.']
    meta = CATALOG['setup_actions'][key]
    return [meta['label'], 'Needs feature: ' + meta['module'],
            'Build dependencies: ' + (', '.join(meta['packages']) or 'the selected app'),
            'Runs after configuration installation. Status and logs are saved for retry.']
