#!/usr/bin/env python3
"""Raccon Dots: modular, previewable installation using Python's standard library."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))
from terminal_ui import Terminal
CATALOG = json.loads((ROOT / 'modules.json').read_text())
RELEASE = json.loads((ROOT / '.rdot').read_text())
MASCOT = (ROOT / 'assets/raccoon.txt').read_text()
WIDGET_PRESETS = json.loads((ROOT / 'widget-presets.json').read_text())
WIDGET_COMPONENTS = ['widgets-profiles', 'widgets-themes', 'widgets-motion', 'widgets-palette',
                     'widgets-music', 'widgets-github', 'widgets-minecraft']
TEMPLATE_OWNERS = {
    'waybar': 'waybar', 'swaync': 'swaync', 'wlogout': 'desktop', 'swayosd': 'desktop',
    'kitty': 'kitty', 'fuzzel': 'fuzzel', 'swaylock': 'swaylock',
    'gtk3': 'themes', 'gtk4': 'themes', 'wayfire': 'wayfire', 'eww': 'widgets-palette',
    'starship': 'shell', 'cava': 'tools', 'fastfetch': 'tools', 'rofi': 'wallpaper',
    'qt5ct': 'themes', 'qt6ct': 'themes', 'yazi': 'tools', 'nvim': 'nvim',
    'gtklock': 'gtklock', 'legcord': 'chat-theme',
    'desktop_style_source': 'desktop-styles',
}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def choices_for(args):
    saved = getattr(args, 'selection', {}).get('choices', read_receipt(args.target).get('choices', {}))
    return {key: getattr(args, key, None) or saved.get(key, info['default']) for key, info in CATALOG['choices'].items()}


def validate_selection(data):
    """Profiles are data only. Reject unknown settings instead of executing them."""
    if not isinstance(data, dict):
        raise ValueError('A setup profile must be a JSON object.')
    data = data.get('selection', data)
    if not isinstance(data, dict) or data.get('name', RELEASE['name']) != RELEASE['name']:
        raise ValueError('This is not a Raccon Dots setup profile.')
    if data.get('schema', 1) != 1:
        raise ValueError('Unsupported setup profile schema.')
    requested = data.get('requested', data.get('modules', CATALOG['defaults']))
    allowed = {*CATALOG['modules'], *CATALOG['choices']}
    if (not isinstance(requested, list) or not requested or
            not all(isinstance(name, str) and name in allowed for name in requested)):
        raise ValueError('The profile must select known features or applications.')
    values = data.get('choices', {})
    if not isinstance(values, dict) or any(k not in CATALOG['choices'] for k in values):
        raise ValueError('Unknown alternatives in the setup profile.')
    choices = {}
    for key, info in CATALOG['choices'].items():
        value = values.get(key, info['default'])
        if value not in info['options']:
            raise ValueError(f'Invalid {key} alternative: {value}')
        choices[key] = value
    if 'requested' not in data and 'modules' in data:
        migrated = []
        for name in requested:
            if name == 'base':
                continue
            for group, info in CATALOG['choices'].items():
                if name in info['options']:
                    # Fuzzel can be an auxiliary dependency of another primary launcher.
                    name = group if name == choices[group] else None
                    break
            if name is not None and name not in migrated:
                migrated.append(name)
        requested = migrated
        if not requested:
            raise ValueError('The saved receipt has no selectable components.')
    packages = data.get('packages', False)
    if not isinstance(packages, bool):
        raise ValueError('The packages setting must be true or false.')
    extras = data.get('extra_packages', [])
    if not isinstance(extras, list) or not all(isinstance(p, str) and
            re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9@._+:-]*', p) for p in extras):
        raise ValueError('Invalid extra package names in the setup profile.')
    setup = data.get('setup', [])
    if not isinstance(setup, list) or not all(isinstance(s, str) and s in CATALOG['setup_actions'] for s in setup):
        raise ValueError('Unknown application setup action.')
    source = data.get('tinywidgets_source', '')
    if not isinstance(source, str) or any(c in source for c in '\x00\n\r'):
        raise ValueError('Invalid tinyWidgets source path.')
    widget_options = validate_widget_options(data.get('widgets', {}))
    if 'tinywidgets' in requested:
        requested = [name for name in requested if name not in WIDGET_COMPONENTS]
        requested += widget_options['components']
        if widget_options['profile'] != 'keep':
            requested += ['widgets-profiles', *WIDGET_PRESETS['profiles'][widget_options['profile']]['requires']]
    modules = resolve_modules(requested, choices)
    for action in setup:
        needed = CATALOG['setup_actions'][action]['module']
        if needed not in modules:
            raise ValueError(f'{action} setup requires the {needed} module.')
    return {**RELEASE, 'requested': list(dict.fromkeys(requested)), 'choices': choices,
            'packages': packages, 'extra_packages': sorted(set(extras)),
            'setup': list(dict.fromkeys(setup)), 'tinywidgets_source': source, 'widgets': widget_options}


def validate_widget_options(data):
    if not isinstance(data, dict):
        raise ValueError('tinyWidgets preferences must be an object.')
    options = {**WIDGET_PRESETS['defaults'], **data}
    if not all(isinstance(options[k], str) for k in ('install', 'theme', 'motion', 'profile')):
        raise ValueError('tinyWidgets install, layout, theme and motion choices must be text.')
    if options['install'] not in ('auto', 'build', 'configure'):
        raise ValueError('Choose Auto, Build from source or Configure only for tinyWidgets.')
    for key, collection in [('theme', 'themes'), ('motion', 'motions')]:
        if options[key] not in WIDGET_PRESETS[collection]:
            raise ValueError(f'Unknown tinyWidgets {key}: {options[key]}')
    if options['profile'] not in ('keep', *WIDGET_PRESETS['profiles']):
        raise ValueError('Unknown tinyWidgets layout profile.')
    for key, allowed in [('profiles', WIDGET_PRESETS['profiles']), ('components', WIDGET_COMPONENTS)]:
        if not isinstance(options[key], list) or not all(isinstance(v, str) and v in allowed for v in options[key]):
            raise ValueError(f'Unknown tinyWidgets {key}.')
        options[key] = list(dict.fromkeys(options[key]))
    if options['profile'] != 'keep' and options['profile'] not in options['profiles']:
        raise ValueError('Include the active tinyWidgets layout in the saved profiles selection.')
    if 'widgets-profiles' in options['components'] and not options['profiles']:
        raise ValueError('Select at least one saved tinyWidgets profile or turn off saved profiles.')
    return options


def load_selection(home, profile=None):
    if profile:
        return validate_selection(json.loads(profile.expanduser().read_text()))
    receipt = read_receipt(home)
    if receipt:
        return validate_selection(receipt)
    return validate_selection(json.loads((ROOT / 'profiles/default.json').read_text()))


def selection_for(args, requested):
    source = getattr(args, 'tinywidgets_source', '') or ''
    # Keep a HOME-relative path portable when exporting to another machine.
    if source.startswith(str(args.target) + '/'):
        source = '~/' + str(Path(source).relative_to(args.target))
    return validate_selection({'requested': requested, 'choices': choices_for(args),
        'packages': bool(args.packages), 'extra_packages': getattr(args, 'extra_packages', []),
        'setup': getattr(args, 'setup', []), 'tinywidgets_source': source,
        'widgets': getattr(args, 'widget_options', getattr(args, 'selection', {}).get('widgets', {}))})


def profile_destination(path):
    path = path.expanduser().absolute()
    if path.suffix != '.json' or path.is_symlink():
        raise ValueError('Save profiles to regular .json files, for example profiles/personal.json.')
    # A profile export must never overwrite the release marker or installation sources.
    if path.is_relative_to(ROOT / 'modules') or path == ROOT / 'modules.json':
        raise ValueError('Choose a profile path outside the module sources.')
    if path.exists() and not path.is_file():
        raise ValueError(f'Expected a JSON profile file: {path}')
    for parent in path.parents:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f'Profile directory needs manual review: {parent}')
    return path


def save_profile(path, selection):
    path = profile_destination(path)
    data = json_bytes(validate_selection(selection))
    if path.exists() and path.read_bytes() != data:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        history = profile_destination(path.parent / '.history' / path.stem / (stamp + '.json'))
        atomic_write(history, path.read_bytes(), 0o600)
        print(f'Previous profile saved: {history}')
    if not unchanged(path, data, 0o600):
        atomic_write(path, data, 0o600)
    print(f'Profile saved: {path}')


def read_receipt(home):
    marker = home / '.rdot'
    if marker.is_file() and not marker.is_symlink():
        try:
            data = json.loads(marker.read_text())
            if (isinstance(data, dict) and data.get('name') == RELEASE['name'] and
                    isinstance(data.get('modules', []), list) and
                    all(isinstance(m, str) for m in data.get('modules', [])) and
                    isinstance(data.get('choices', {}), dict) and
                    all(v in CATALOG['choices'].get(k, {}).get('options', []) for k, v in data.get('choices', {}).items())):
                return data
        except (OSError, ValueError, TypeError):
            pass
    return {}


def with_previous(home, requested, choices):
    """Re-render installed modules too, so changing an alternative updates its users."""
    previous = read_receipt(home).get('modules', [])
    for name in previous:
        if name not in CATALOG['modules']:
            continue
        for group, info in CATALOG['choices'].items():
            if name in info['options'] and not (group == 'launcher' and name == 'fuzzel'):
                name = choices[group]
                break
        if name not in requested:
            requested.append(name)
    return requested


def resolve_modules(requested, choices):
    result, visiting = [], set()

    def visit(name):
        name = choices.get(name, name)
        if name not in CATALOG['modules']:
            raise ValueError(f'Unknown module: {name}. Use --list.')
        if name in result:
            return
        if name in visiting:
            raise ValueError(f'Circular dependency in {name}')
        visiting.add(name)
        for dependency in CATALOG['modules'][name]['requires']:
            visit(dependency)
        visiting.remove(name)
        result.append(name)

    for name in requested:
        visit(name)
    # The search helper Fuzzel may coexist with another primary launcher.
    for group in ('terminal', 'notifications', 'lock', 'shell', 'browser', 'filemanager'):
        options = set(CATALOG['choices'][group]['options']).intersection(result)
        if len(options) > 1:
            raise ValueError(f'Choose one alternative for {group}: {", ".join(sorted(options))}')
        if options and choices[group] not in options:
            raise ValueError(f'Use --{group} {next(iter(options))} to select that alternative.')
    return result


def set_ini(text, key, value):
    return re.sub(r'^' + re.escape(key) + r'\s*=.*$', lambda _: key + ' = ' + value, text, flags=re.M)


ZSH_PERSONAL = '# >>> personal (kept on reinstall, never captured)'


def render(relative, content, home, modules, choices):
    try:
        text = content.decode()
    except UnicodeDecodeError:
        return content
    terminal = choices['terminal']
    text = text.replace('@RDOT_HOME@', str(home)).replace('@RDOT_TERMINAL@', terminal)
    if relative == '.zshrc':
        # Replacing the shell config must not lose the user's personal block.
        try:
            current = (home / '.zshrc').read_text()
        except (OSError, UnicodeDecodeError):
            current = ''
        if ZSH_PERSONAL in current and ZSH_PERSONAL in text:
            text = text.split(ZSH_PERSONAL)[0] + ZSH_PERSONAL + current.split(ZSH_PERSONAL, 1)[1]
    if relative == '.config/wayfire.ini':
        text = set_ini(text, 'command_terminal', terminal)
        text = set_ini(text, 'command_monitor', terminal + ' -e btop')
        text = set_ini(text, 'command_browser', choices['browser'])
        text = set_ini(text, 'command_files', choices['filemanager'])
        text = set_ini(text, 'command_editor', terminal + ' -e nvim')
        launcher = {'desktop-menu': '~/.local/bin/desktop-menu', 'fuzzel': 'fuzzel',
                    'rofi': 'rofi -show drun'}[choices['launcher']]
        text = set_ini(text, 'command_launcher', launcher)
        if 'desktop-styles' not in modules:
            text = re.sub(r'^(?:binding_desktop_style|command_desktop_style|desktop_style)\s*=.*\n', '', text, flags=re.M)
        text = set_ini(text, 'notifications', choices['notifications'])
        text = set_ini(text, 'command_notifications',
                       'swaync-client -t -sw' if choices['notifications'] == 'swaync' else 'makoctl dismiss -a')
        if 'widgets' not in modules:
            text = re.sub(r'^(?:binding_widgets\w*|command_widgets\w*|widgets)\s*=.*\n', '', text, flags=re.M)
        else:
            text = set_ini(text, 'widgets', 'sh -c \'[ -x "$HOME/.local/bin/widgetctl" ] && "$HOME/.local/bin/widgetctl" start\'')
        disabled = []
        if 'waybar' not in modules:
            disabled += ['bar', 'bar_power']
            text = re.sub(r'^bar\s*=.*\n', '', text, flags=re.M)
        if 'wallpaper' not in modules:
            disabled += ['wallpaper', 'wallpaper_quick', 'scheme']
            text = re.sub(r'^(?:wallpaper|wallpaper_daemon|skydome_texture)\s*=.*\n', '', text, flags=re.M)
            text = set_ini(text, 'background_mode', 'simple')
        if 'power' not in modules:
            text = re.sub(r'^(?:desktop_power|idle)\s*=.*\n', '', text, flags=re.M)
        if 'desktop' not in modules:
            if 'wallpaper' in modules:
                text = set_ini(text, 'command_wallpaper', '~/.local/bin/wallpaper-grid')
            disabled += ['files', 'monitor', 'clipboard', 'shot_area', 'shot_full', 'mute', 'micmute',
                         'vol_up', 'vol_down', 'bright_up', 'bright_down', 'play', 'pause', 'next', 'prev', 'session']
            text = re.sub(r'^(?:raccon_menu|raccon_float|desktop_controls|osd|clip_text|clip_image)\s*=.*\n', '', text, flags=re.M)
        if 'vscode' in modules:
            text = set_ini(text, 'command_editor', 'code --ozone-platform-hint=wayland')
        elif 'nvim' not in modules:
            disabled.append('editor')
        for group, command in [('browser', 'browser'), ('filemanager', 'files')]:
            if choices[group] not in modules:
                disabled.append(command)
        for name in disabled:
            text = re.sub(r'^(?:binding_|repeatable_binding_|command_)' + re.escape(name) + r'\s*=.*\n', '', text, flags=re.M)
    elif relative == '.config/waybar/config.jsonc':
        data = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        data['modules-right'] = [m for m in data['modules-right'] if m != 'custom/notification']
        data.pop('custom/notification', None)
        text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    elif relative == '.config/matugen/config.toml':
        blocks = re.split(r'(?=^\[templates\.)', text, flags=re.M)
        kept = [blocks[0]]
        for block in blocks[1:]:
            name = re.match(r'\[templates\.([^\]]+)\]', block)[1]
            owner = TEMPLATE_OWNERS.get(name)
            if owner == 'shell':
                enabled = bool({'zsh', 'fish'}.intersection(modules))
            elif name == 'rofi':
                enabled = bool({'wallpaper', 'rofi', 'desktop'}.intersection(modules))
            else:
                enabled = owner in modules
            if enabled:
                kept.append(block)
        text = ''.join(kept)
    elif relative in ('.local/bin/desktop-menu', '.local/lib/raccon_menu/backend.py',
                       '.local/lib/raccon_menu/legacy_menu.py'):
        text = text.replace("['brave']", repr([choices['browser']]))
        text = text.replace("['dolphin']", repr([choices['filemanager']]))
        text = text.replace("['code', '--ozone-platform-hint=wayland']", repr([terminal, '-e', 'nvim']))
        if 'widgets' not in modules:
            text = '\n'.join(line for line in text.splitlines() if "('Mis widgets'," not in line) + '\n'
        if 'wallpaper' not in modules:
            text = '\n'.join(line for line in text.splitlines() if "('Fondos'," not in line) + '\n'
        if 'vscode' in modules:
            text = text.replace(repr([terminal, '-e', 'nvim']), repr(['code', '--ozone-platform-hint=wayland']))
        elif 'nvim' not in modules:
            text = '\n'.join(line for line in text.splitlines() if "('Editor'," not in line) + '\n'
        for group, label in [('browser', 'Navegador'), ('filemanager', 'Archivos')]:
            if choices[group] not in modules:
                text = '\n'.join(line for line in text.splitlines() if "('" + label + "'," not in line) + '\n'
    if relative in ('.config/waybar/config.jsonc', '.local/bin/desktop-menu',
                    '.local/lib/raccon_menu/backend.py', '.local/lib/raccon_menu/legacy_menu.py'):
        text = text.replace('kitty -e ', terminal + ' -e ').replace("['kitty']", repr([terminal]))
    if relative == '.config/fuzzel/fuzzel.ini':
        text = re.sub(r'^terminal=.*$', 'terminal=' + terminal, text, flags=re.M)
    style_import = None
    if relative == '.config/waybar/style.css':
        style_import = f'@import "{home}/.config/desktop-style/current/waybar.css";'
    elif relative in ('.config/raccon-menu/eww.scss', '.config/raccon-float/eww.scss', '.config/raccon-music/eww.scss'):
        # Keep the adapter before motion/interaction overrides.
        if 'desktop-styles' not in modules:
            text = re.sub(r'^@import "(?:../raccon-menu/)?desktop-style";\n?', '', text, flags=re.M)
    elif relative.startswith('.config/rofi/') and relative.endswith('.rasi') and not relative.endswith('/colors.rasi'):
        style_import = f'@import "{home}/.config/desktop-style/current/rofi.rasi"'
    elif relative in ('.config/swaync/style.css','.config/swayosd/style.css'):
        name=relative.split('/')[1]
        style_import = f'@import "{home}/.config/desktop-style/current/{name}.css";'
    if style_import is not None:
        text = '\n'.join(line for line in text.splitlines()
                         if not ('@import' in line and ('desktop-style/current/' in line or '"desktop-style"' in line))) + '\n'
        if 'desktop-styles' in modules:
            text += '\n' + style_import + '\n'
        if relative == '.config/waybar/style.css':
            text = re.sub(r'^@import "orientation.css";\n?', '', text, flags=re.M)
            text += '\n@import "orientation.css";\n'
    if relative == '.local/bin/wallpaper-theme' and 'desktop-styles' not in modules:
        text = re.sub(r'\nif \[\[ -x "\$HOME/\.local/bin/desktop-style" \]\]; then\n.*?\nfi\n', '\n', text, flags=re.S)
    shell_enabled = choices['shell'] in modules
    if relative == '.config/kitty/kitty.conf' and shell_enabled:
        text += '\nshell ' + choices['shell'] + '\n'
    elif relative == '.config/alacritty/alacritty.toml' and shell_enabled:
        text += '\n[terminal.shell]\nprogram = "' + choices['shell'] + '"\n'
    elif relative == '.config/Code/User/settings.json' and shell_enabled:
        settings = json.loads(text)
        shell = choices['shell']
        settings['terminal.integrated.defaultProfile.linux'] = shell
        settings['terminal.integrated.profiles.linux'] = {shell: {'path': '/usr/bin/' + shell}}
        text = json.dumps(settings, ensure_ascii=False, indent=2) + '\n'
    if '@RDOT_' in text:
        raise ValueError(f'Unresolved variable: {relative}')
    return text.encode()


def safe_relative(relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts):
        raise ValueError(f'Invalid module path: {relative}')
    return path


def safe_destination(home, relative):
    destination = home / safe_relative(relative)
    # Never traverse a symlinked parent (e.g. .config -> another disk).
    parent = destination.parent
    while parent != home:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f'Parent directory needs manual review: {parent}')
        parent = parent.parent
    if destination.exists() and destination.is_dir():
        raise ValueError(f'Expected a file, found a directory: {destination}')
    return destination


def file_plan(home, modules, choices, selection=None, render_modules=None):
    plan = {}
    options = validate_widget_options((selection or {}).get('widgets', {}))
    for module in modules:
        base = ROOT / 'modules' / module / 'files'
        for source in sorted(base.rglob('*')):
            if '__pycache__' in source.parts or source.suffix in ('.pyc', '.pyo'):
                continue
            if source.is_symlink():
                raise ValueError(f'Source symlinks are not supported: {source}')
            if not source.is_file():
                continue
            relative = source.relative_to(base).as_posix()
            if module == 'widgets-profiles' and source.parent.name == 'profiles' and source.stem not in options['profiles']:
                continue
            safe_destination(home, relative)
            if relative in plan:
                raise ValueError(f'Two modules write {relative}')
            plan[relative] = (render(relative, source.read_bytes(), home, render_modules or modules, choices),
                              source.stat().st_mode & 0o777)
    # Parent of the Eww palette is created before Matugen writes to it.
    if 'widgets' in modules:
        palette = plan.get('.config/eww/_colors.scss')
        if palette:
            dest = home / '.local/state/randly-widgets/palette.scss'
            if not dest.exists():
                plan['.local/state/randly-widgets/palette.scss'] = palette
    if 'widgets-themes' in modules:
        plan['.config/eww/style.json'] = plan[f'.config/eww/presets/themes/{options["theme"]}.json']
    if 'widgets-motion' in modules:
        plan['.config/eww/animation.json'] = plan[f'.config/eww/presets/motion/{options["motion"]}.json']
    if 'widgets-profiles' in modules:
        profile = options['profile']
        if profile == 'keep' and not (home / '.config/eww/instances.json').exists():
            profile = 'Trabajo' if 'Trabajo' in options['profiles'] else options['profiles'][0]
        if profile != 'keep':
            document = json.loads(plan[f'.config/eww/profiles/{profile}.json'][0])
            plan['.config/eww/instances.json'] = (json_bytes({'version': 1, 'revision': 1,
                                                          'widgets': document['widgets']}), 0o600)
            if 'widgets-motion' not in modules and document.get('animation'):
                plan['.config/eww/animation.json'] = (json_bytes(document['animation']), 0o644)
    return plan


def unchanged(path, data, mode):
    return (path.is_file() and not path.is_symlink() and path.read_bytes() == data and
            path.stat().st_mode & 0o777 == mode)


def digest(path):
    if path.is_symlink():
        return 'link:' + os.readlink(path)
    if not path.exists():
        return 'missing'
    return hashlib.sha256(path.read_bytes()).hexdigest() + ':' + oct(path.stat().st_mode & 0o777)


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.rdot-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def installation_lock(home):
    state = home / '.local/state/raccon-dots'
    safe_destination(home, '.local/state/raccon-dots/install.lock')
    state.mkdir(parents=True, exist_ok=True)
    lock_path = state / 'install.lock'
    if lock_path.is_symlink():
        raise ValueError(f'Invalid lock: {lock_path}')
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another installation is already running.') from None
        yield state


def undo(home, backup, records):
    for record in reversed(records):
        dest = safe_destination(home, record['path'])
        if record['previous'] == 'missing':
            dest.unlink(missing_ok=True)
        elif record['previous'] == 'link':
            dest.unlink(missing_ok=True)
            dest.symlink_to(record['link'])
        else:
            source = backup / 'files' / record['path']
            atomic_write(dest, source.read_bytes(), record['mode'])


def apply_plan(home, plan, modules, choices, selection=None, partial=False, expected=None):
    plan = dict(plan)
    if selection is not None:
        selection = validate_selection(selection)
        plan['.config/raccon-dots/profile.json'] = (json_bytes(selection), 0o600)
    with installation_lock(home) as state:
        # Check again after taking the lock and before changing any files.
        for relative in [*plan, '.rdot']:
            safe_destination(home, relative)
        for relative, baseline in (expected or {}).items():
            if digest(safe_destination(home, relative)) != baseline:
                raise ValueError(f'File changed after preview: {relative}; review the update again.')
        changes = {rel: value for rel, value in plan.items() if not unchanged(home / rel, *value)}
        previous = read_receipt(home)
        old_modules = set(previous.get('modules', []))
        # Keep a receipt of earlier modules when applying an additional module.
        all_modules = set(modules) if selection is not None else old_modules.union(modules)
        for group in CATALOG['choices']:
            for option in CATALOG['choices'][group]['options']:
                if choices[group] in modules and option not in modules:
                    all_modules.discard(option)
        receipt_choices = dict(previous.get('choices', {}))
        for key, value in choices.items():
            if value in modules:
                receipt_choices[key] = value
        receipt = {**RELEASE, 'modules': sorted(all_modules), 'choices': receipt_choices}
        if partial and 'selection' in previous:
            receipt['selection'] = previous['selection']
        if selection is not None:
            receipt['selection'] = selection
        receipt['files'] = {rel: {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode}
                            for rel, (data, mode) in plan.items()}
        if partial:
            receipt['files'] = {**previous.get('files', {}), **receipt['files']}
        comparable = {k: previous.get(k) for k in receipt}
        if not changes and comparable == receipt:
            print('Everything is up to date. No files were replaced.')
            return None
        receipt['installed_at'] = datetime.now(timezone.utc).isoformat()
        changes['.rdot'] = (json_bytes(receipt), 0o644)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        safe_destination(home, f'.local/state/raccon-dots/backups/{stamp}/manifest.json')
        backup = state / 'backups' / stamp
        backup.mkdir(parents=True, mode=0o700)
        records = []
        journal = {'schema': 1, 'home': str(home), 'status': 'applying', 'files': records}

        def save_journal():
            atomic_write(backup / 'manifest.json', json_bytes(journal), 0o600)

        try:
            for relative, (data, mode) in changes.items():
                dest = safe_destination(home, relative)
                record = {'path': relative, 'previous': 'missing', 'after': hashlib.sha256(data).hexdigest() + ':' + oct(mode)}
                if dest.is_symlink():
                    record.update(previous='link', link=os.readlink(dest))
                elif dest.exists():
                    saved = backup / 'files' / relative
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, saved)
                    record.update(previous='file', mode=dest.stat().st_mode & 0o777)
                records.append(record)
                save_journal()  # Persist undo information BEFORE replacing a file.
                atomic_write(dest, data, mode)
            journal['status'] = 'installed'
            save_journal()
        except BaseException:
            undo(home, backup, records)
            journal['status'] = 'rolled-back'
            save_journal()
            raise
        print(f'Installed {len(changes) - 1} files. Version {RELEASE["version"]}.')
        print(f'Backup: {backup}')
        print('Log out and back into Wayfire to load the desktop.')
        return backup


def restore(backup, home):
    backup = backup.resolve()
    journal = json.loads((backup / 'manifest.json').read_text())
    if journal.get('status') != 'installed' or journal.get('home') != str(home):
        raise ValueError('This backup is not an active installation for the target HOME.')
    with installation_lock(home):
        for record in journal['files']:
            dest = safe_destination(home, record['path'])
            if digest(dest) != record['after']:
                raise ValueError(f'File changed since installation: {dest}. Recover its backup manually.')
            if record['previous'] == 'file':
                saved = backup / 'files' / safe_relative(record['path'])
                if not saved.is_file() or saved.is_symlink():
                    raise ValueError(f'Missing backup file: {saved}')
        undo(home, backup, journal['files'])
        journal['status'] = 'restored'
        atomic_write(backup / 'manifest.json', json_bytes(journal), 0o600)
    print('Previous files restored. Installed packages are kept.')


def packages_for(modules, extra_packages=(), setup=()):
    packages = {p for name in modules for p in CATALOG['modules'][name]['packages']}
    packages.update(extra_packages)
    for action in setup:
        packages.update(CATALOG['setup_actions'][action]['packages'])
    return sorted(packages)


def install_packages(packages):
    if not shutil.which('pacman'):
        raise ValueError('--packages requires Arch/CachyOS with pacman. You can install dotfiles without it.')
    # Skip installed packages, including AUR packages absent from repository databases.
    pending = [p for p in packages if subprocess.run(['pacman', '-Q', p],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode]
    missing = [p for p in pending if subprocess.run(['pacman', '-Si', p], stdout=subprocess.DEVNULL,
               stderr=subprocess.DEVNULL).returncode]
    if missing:
        raise ValueError('Packages unavailable in your repositories: ' + ', '.join(missing) +
                         '. Install them with your package manager, then retry without --packages.')
    if pending:
        subprocess.run(['sudo', 'pacman', '-S', '--needed', '--', *pending], check=True)
    else:
        print('All selected packages are already installed.')


def environment_snapshot():
    """Read package databases once; never refresh repositories or contact the network."""
    result = {'installed': set(), 'available': set(), 'known': False}
    if shutil.which('pacman'):
        try:
            installed = subprocess.run(['pacman', '-Qq'], capture_output=True, text=True, timeout=5)
            available = subprocess.run(['pacman', '-Slq'], capture_output=True, text=True, timeout=5)
            if installed.returncode == 0:
                result.update(installed=set(installed.stdout.splitlines()), known=True)
            if available.returncode == 0:
                result['available'] = set(available.stdout.splitlines())
        except (OSError, subprocess.TimeoutExpired):
            pass
    return result


def package_label(name, inventory):
    if not inventory.get('known'):
        return name + ' [check with your package manager]'
    if name in inventory['installed']:
        return name + ' [installed]'
    if name in inventory['available']:
        return name + ' [needs install]'
    return name + ' [manual package source]'


def readiness(selection, home, inventory=None):
    inventory = inventory or {'known': False}
    modules = selected_modules(selection, home)
    execution = execution_selection(selection, home)
    blockers, notes = [], []
    if 'widgets' in modules:
        config = home / '.config/eww'
        if (config / 'eww.yuck').exists() and not (config / '.modular-active').exists():
            blockers.append('Eww belongs to another configuration. Move or migrate that configuration before installing tinyWidgets.')
        if selection['widgets']['install'] == 'configure' and not (home / '.local/bin/widgetctl').exists():
            notes.append('tinyWidgets is not installed. Configure only saves preferences; choose Auto or Build to install its app.')
    try:
        setup_preflight(execution, home)
    except ValueError as exc:
        blockers.append(str(exc))
    needed = packages_for(modules, selection['extra_packages'], execution['setup'])
    if inventory.get('known'):
        missing = set(needed) - inventory['installed']
        unavailable = missing - inventory['available']
        if selection['packages'] and unavailable:
            blockers.append('Packages need a manual source: ' + ', '.join(sorted(unavailable)) +
                            '. Install them with your package manager, then refresh checks (c).')
        elif missing and not selection['packages']:
            notes.append(f'{len(missing)} dependencies are missing. Enable Packages (p, then 0) or install them separately.')
    if 'widgets-github' in modules:
        notes.append('GitHub widgets need your own gh authentication. Run gh auth login after installing; no credentials are copied.')
    if 'widgets-music' in modules:
        notes.append('Music widgets use an active MPRIS player. The player and your music library are not bundled.')
    if 'ai' in modules:
        notes.append('AI keeps only the list of skills.sh skills. Add the ai-skills setup to download them with npx skills.')
    if 'widgets-profiles' in modules:
        active = active_widget_profile(selection, home)
        if active != 'keep':
            document = json.loads((ROOT / f'modules/widgets-profiles/files/.config/eww/profiles/{active}.json').read_text())
            desktop_ids = []
            for widget in document['widgets']:
                for entry in json.loads(widget.get('opts', {}).get('launchers', '[]')):
                    desktop_ids.append(entry['desktop_id'])
            locations = [home / '.local/share/applications', Path('/usr/share/applications'),
                         Path('/var/lib/flatpak/exports/share/applications'), home / '.local/share/flatpak/exports/share/applications']
            missing_apps = sorted({app for app in desktop_ids if not any((location / app).is_file() for location in locations)})
            if missing_apps:
                notes.append('Saved launcher shortcuts need these apps, installed separately: ' + ', '.join(missing_apps))
    return {'blockers': blockers, 'notes': notes, 'packages': needed, 'modules': modules, 'actions': execution['setup']}


def component_details(name, requested, choices, modules, inventory, selection=None, home=None):
    name = choices.get(name, name)
    meta = CATALOG['modules'][name]
    deps = [choices.get(dep, dep) for dep in meta['requires']]
    labels = [CATALOG['modules'][dep]['label'] for dep in deps if dep != 'base']
    lines = [meta['label'], meta.get('description', 'Installs this application and its reviewed configuration.'),
             'Needs: ' + (', '.join(labels) or 'user session environment')]
    packages = list(dict.fromkeys([*meta['packages'], *packages_for(resolve_modules([name], choices))]))
    lines.append('Packages: ' + (', '.join(packages) or 'no additional packages'))
    if inventory.get('known'):
        missing = set(packages) - inventory['installed']
        lines.append(f'{len(packages) - len(missing)}/{len(packages)} dependencies installed. {len(missing)} to prepare.')
    lines += ['  ' + package_label(p, inventory) for p in packages]
    parents = []
    for candidate in requested:
        resolved = choices.get(candidate, candidate)
        if resolved != name and name in resolve_modules([candidate], choices):
            parents.append(CATALOG['modules'][resolved]['label'])
    if parents:
        lines.append('Required by: ' + ', '.join(parents))
    if name == 'tinywidgets' and selection and home:
        actions = effective_setup(selection, home)
        lines += ['App: ' + ('build and install from local source' if 'tinywidgets' in actions else 'use the installed app / configure preferences'),
                  'Source: ' + selection['tinywidgets_source'],
                  'Build needs: ' + ', '.join(CATALOG['setup_actions']['tinywidgets']['packages']),
                  'Personal layout: ' + selection['widgets']['profile'],
                  'Theme / motion: ' + selection['widgets']['theme'] + ' / ' + selection['widgets']['motion']]
    return lines


def preview(home, modules, choices, plan, show_files=False, selection=None):
    changed = sum(not unchanged(home / rel, *value) for rel, value in plan.items())
    print(f'\nRaccon Dots {RELEASE["version"]} -> {home}')
    print('Features and apps: ' + ', '.join(modules))
    print('Alternatives: ' + ', '.join(f'{k}={v}' for k, v in choices.items()))
    print(f'Configuration files: {len(plan)} | changes: {changed}')
    selection = selection or {}
    actions = effective_setup(selection, home) if selection.get('widgets') else selection.get('setup', [])
    packages = packages_for(modules, selection.get('extra_packages', []), actions)
    enabled = selection.get('packages', False)
    print(f'Package installation: {"enabled" if enabled else "disabled (configuration only)"}')
    print('App packages and dependencies: ' + ' '.join(packages))
    print('Application setup: ' + (', '.join(actions) or 'none'))
    if 'widgets' in modules and selection.get('widgets'):
        options = selection['widgets']
        print(f'tinyWidgets: {active_widget_profile(selection, home)} layout | {options["theme"]} theme | {options["motion"]} motion | {options["install"]} installation')
    print('\nDEPENDENCIES BY COMPONENT')
    for name in modules:
        meta = CATALOG['modules'][name]
        deps = ', '.join(choices.get(dep, dep) for dep in meta['requires']) or 'none'
        print(f'  {name}: requires {deps}')
        print('    Packages: ' + (', '.join(meta['packages']) or 'included in dependencies'))
    print('Preferences: saved to ~/.rdot and ~/.config/raccon-dots/profile.json after installation.')
    if 'widgets' in modules and 'tinywidgets' not in actions and not (home / '.local/bin/widgetctl').exists():
        print('tinyWidgets app is missing. Enable its setup or use extras/install-tinywidgets.sh SOURCE.')
    if show_files:
        for relative, value in plan.items():
            print(('  = ' if unchanged(home / relative, *value) else '  + ') + relative)


def clear_screen():
    if sys.stdout.isatty() and os.environ.get('TERM', '') not in ('', 'dumb'):
        print('\033[2J\033[H', end='', flush=True)


def welcome(args):
    clear_screen()
    print(MASCOT)
    print(f'RACCON DOTS  {RELEASE["version"]}')
    print('Personal dotfiles to set up a comfortable, colorful Wayland desktop.\n')
    print('FEATURES')
    print('  Wayfire window management, an island dock and the raccoon app menu.')
    print('  Wallpaper-based Material You colors, GTK / Qt themes and matching apps.')
    print('  Terminal and shell choices, development tools and battery-aware effects.')
    print('  Optional tinyWidgets, editor setup, saved profiles and file recovery.\n')
    print('BEFORE YOU START')
    print('  Linux, Python 3.11+, a UTF-8 terminal and a writable user HOME.')
    print('  Wayfire 0.11 + Wayland for the desktop modules.')
    print('  Arch / CachyOS + pacman + sudo when installing app dependencies.')
    print('  Internet access for package installation or app/plugin downloads.')
    print('  tinyWidgets setup also needs its local source and Rust/GTK build tools.')
    print('  Network, Bluetooth and audio services should be configured on your system.\n')
    print(f'Target HOME: {args.target}')
    print('Choose features and apps next. Existing files get installation backups.')
    return input('Press Enter to select components, or q to quit: ').strip().lower() != 'q'


FEATURES = ['wayfire', 'waybar', 'desktop', 'power', 'themes', 'wallpaper', 'audio', 'chat-theme', 'tinywidgets', 'desktop-styles']
APPS = ['terminal', 'shell', 'launcher', 'notifications', 'lock', 'browser', 'filemanager', 'tools', 'git', 'nvim', 'vscode', 'ai']
GROUP_LABELS = {'terminal': 'Terminal application', 'shell': 'Shell and prompt',
                'launcher': 'Application launcher', 'notifications': 'Notifications', 'lock': 'Screen locker',
                'browser': 'Web browser', 'filemanager': 'File manager'}


def package_screen(args, modules):
    print(f'  0. [{"x" if args.packages else " "}] Install selected apps and dependencies with pacman')
    required = set(packages_for(modules, setup=args.setup))
    for index, (name, label) in enumerate(CATALOG['optional_packages'].items(), 1):
        mark = '+' if name in required else 'x' if name in args.extra_packages else ' '
        print(f'  {index}. [{mark}] {name:12} {label}')
    print(f'\n  {len(required)} required packages from selected components. Press d to review the list.')
    print('  [+] Dependencies are automatic. Optional package choices are saved in your profile.')


def recovery_screen(args):
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
    restore(backup, args.target)
    input('Restored. Press Enter to return: ')
    return True


def widget_rows(args, requested, modules, inventory):
    options = args.widget_options
    enabled = 'tinywidgets' in requested
    rows = [{'id': 'tinywidgets', 'label': 'Enable tinyWidgets and personal presets', 'mark': 'x' if enabled else ' ',
             'command': 'master'}]
    descriptions = {
        'profile': ('Active layout', options['profile']),
        'theme': ('Theme', WIDGET_PRESETS['themes'][options['theme']]['label']),
        'motion': ('Motion', WIDGET_PRESETS['motions'][options['motion']]['label']),
        'install': ('App installation', {'auto': 'Auto / install when missing', 'build': 'Build from source', 'configure': 'Configure only'}[options['install']]),
    }
    for key, (label, value) in descriptions.items():
        rows.append({'id': key, 'label': f'{label}: {value}', 'mark': '~', 'command': 'choice:' + key})
    rows.append({'id': 'source', 'label': 'Source: ' + (args.tinywidgets_source or 'choose a local checkout'), 'mark': '~', 'command': 'source'})
    for key in WIDGET_COMPONENTS:
        mark = 'x' if key in options['components'] else '+' if key in modules else ' '
        rows.append({'id': key, 'label': CATALOG['modules'][key]['label'], 'mark': mark, 'command': 'component:' + key})
    for key, meta in WIDGET_PRESETS['profiles'].items():
        rows.append({'id': 'profile:' + key, 'label': f'Save {key} layout ({meta["active_widgets"]}/{meta["widgets"]} active widgets)',
                     'mark': 'x' if key in options['profiles'] else ' ', 'command': 'saved:' + key})
    return rows


def rows_for(page, args, requested, selection, modules, inventory):
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
        return widget_rows(args, requested, modules, inventory)
    if page == 'p':
        required = set(packages_for(modules, setup=effective_setup(selection, args.target)))
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
                validate_selection(data)
            except (OSError, ValueError):
                continue
            rows.append({'id': path.stem, 'label': data.get('title', path.stem.replace('-', ' ').title()),
                         'mark': '~', 'command': str(path)})
        return rows
    return [{'id': key, 'label': info['label'], 'mark': 'x' if key in args.setup else ' ', 'command': key}
            for key, info in CATALOG['setup_actions'].items()]


def row_details(page, row, args, requested, selection, modules, inventory):
    key = row['id']
    if page in ('f', 'a', 'l') or (page == 't' and key in CATALOG['modules']):
        return component_details(key, selection['requested'], selection['choices'], modules, inventory, selection, args.target)
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
            source = source_path(args.tinywidgets_source, args.target)
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
            result += [package_label(p, inventory) for p in packages_for(modules, args.extra_packages, effective_setup(selection, args.target))]
            return result
        return [row['label'], package_label(key, inventory), 'Enable package installation to install this optional package.']
    if page == 'r':
        data = json.loads(Path(row['command']).read_text())
        preset = validate_selection(data)
        included = selected_modules(preset, args.target)
        return [row['label'], data.get('description', 'Your saved setup selection.'),
                'Needs: ' + ', '.join(included),
                'Packages: ' + str(len(packages_for(included))) + ' dependencies; review before installation.',
                'Loads the selection for review. It does not install anything.']
    meta = CATALOG['setup_actions'][key]
    return [meta['label'], 'Needs feature: ' + meta['module'],
            'Build dependencies: ' + (', '.join(meta['packages']) or 'the selected app'),
            'Runs after configuration installation. Status and logs are saved for retry.']


def interactive(args):
    import copy
    if not welcome(args):
        return None
    requested = list(args.selection['requested'])
    args.widget_options = copy.deepcopy(getattr(args, 'widget_options', args.selection['widgets']))
    page, cursors = 'f', {}
    inventory = environment_snapshot() if sys.stdout.isatty() else {'known': False}
    notice = 'Loaded saved preferences.' if read_receipt(args.target) or getattr(args, 'profile', None) else 'Choose what belongs in your den. Press ? to inspect dependencies.'
    tabs = [('f', 'Features'), ('a', 'Apps'), ('l', 'Choices'), ('t', 'Widgets'), ('p', 'Deps'), ('s', 'Setup'), ('r', 'Profiles')]
    titles = {'f': 'DESKTOP FEATURES', 'a': 'APPLICATIONS', 'l': 'APP ALTERNATIVES',
              't': 'TINYWIDGETS / YOUR PERSONAL DEN', 'p': 'APP PACKAGES AND DEPENDENCIES',
              's': 'OPTIONAL APPLICATION SETUP', 'r': 'CHOOSE A STARTING PROFILE'}
    with Terminal(plain=getattr(args, 'plain', False)) as ui:
        while True:
            choices = choices_for(args)
            selection = selection_for(args, requested) if requested else {**args.selection, 'requested': [], 'choices': choices, 'widgets': args.widget_options}
            modules = selected_modules(selection, args.target) if requested else []
            report = readiness(selection, args.target, inventory) if requested else {'blockers': ['Select at least one feature or application.'], 'notes': []}
            rows = rows_for(page, args, requested, selection, modules, inventory)
            cursor = max(0, min(cursors.get(page, 0), len(rows) - 1))
            details = row_details(page, rows[cursor], args, requested, selection, modules, inventory)
            ready = f'{len(report["blockers"])} needs attention' if report['blockers'] else 'Ready to review'
            if not report['blockers'] and not args.packages and inventory.get('known') and set(report.get('packages', [])) - inventory['installed']:
                ready = 'Config only / dependencies missing'
            summary = f'{len(modules)} components | packages {"on" if args.packages else "off"} | {ready} | c refresh checks'
            ui.render(version=RELEASE['version'], page=titles[page], tabs=tabs, rows=rows, cursor=cursor,
                      details=details, summary=summary,
                      notice=notice or ('Needs attention: ' + report['blockers'][0] if report['blockers'] else ''))
            action = ui.read()
            notice = ''
            if action == 'q':
                return None
            if action in ('up', 'down', 'pageup', 'pagedown'):
                direction = -1 if action in ('up', 'pageup') else 1
                step = 8 if action in ('pageup', 'pagedown') else 1
                cursors[page] = max(0, min(len(rows) - 1, cursor + direction * step))
                continue
            if action == 'resize':
                continue
            if action in ('tab', 'backtab'):
                keys = [key for key, _ in tabs]
                page = keys[(keys.index(page) + (1 if action == 'tab' else -1)) % len(keys)]
                continue
            snapshot, old_requested = copy.deepcopy(vars(args)), list(requested)
            try:
                if action in titles:
                    page = action
                    continue
                if action == 'c':
                    inventory = environment_snapshot()
                    notice = 'Dependency checks refreshed from local package databases.'
                    continue
                if action == '?' or (action == 'd' and page == 'p'):
                    lines = details if action == '?' else [package_label(p, inventory) for p in packages_for(modules, args.extra_packages, effective_setup(selection, args.target))]
                    ui.show('DEPENDENCIES / ' + rows[cursor]['label'], lines)
                    continue
                if action == 'path' and page in ('s', 't'):
                    args.tinywidgets_source = ui.prompt('tinyWidgets source directory: ') or args.tinywidgets_source
                    continue
                if action == 'w':
                    profile = getattr(args, 'save_profile', None) or ROOT / 'profiles/personal.json'
                    with redirect_stdout(io.StringIO()):
                        save_profile(profile, selection_for(args, requested))
                    notice = f'Profile saved: {profile}'
                    continue
                if action == 'h':
                    if ui.suspend(lambda: recovery_screen(args)):
                        args.selection = load_selection(args.target)
                        requested = list(args.selection['requested'])
                        for key, value in args.selection['choices'].items():
                            setattr(args, key, value)
                        for key in ('packages', 'extra_packages', 'setup', 'tinywidgets_source'):
                            setattr(args, key, args.selection[key])
                        args.widget_options = copy.deepcopy(args.selection['widgets'])
                        notice = 'Previous files and preferences restored.'
                    continue
                if action in ('v', 'i'):
                    selection = selection_for(args, requested)
                    modules = selected_modules(selection, args.target)
                    plan = file_plan(args.target, modules, choices, selection)
                    output = io.StringIO()
                    with redirect_stdout(output):
                        preview(args.target, modules, choices, plan, show_files=action == 'v', selection=selection)
                    report = readiness(selection, args.target, inventory)
                    lines = output.getvalue().splitlines()
                    lines += [''] + ['NEEDS ATTENTION: ' + message for message in report['blockers']]
                    lines += ['NOTE: ' + message for message in report['notes']]
                    if action == 'v' or report['blockers'] or ui.native:
                        ui.show('REVIEW YOUR DEN', lines)
                    else:
                        print('\n'.join(lines))
                    if report['blockers']:
                        notice = 'Resolve the listed requirements before installation. Use t for tinyWidgets or p for packages.'
                    elif action == 'i' and ui.prompt('Install this setup and back up existing files? [y/N]: ').lower() == 'y':
                        return requested
                    continue
                if action == 'toggle':
                    targets = [rows[cursor]]
                elif action.replace(',', ' ').replace(' ', '').isdigit():
                    numbers = [int(n) for n in action.replace(',', ' ').split()]
                    by_number = {row.get('number', n + 1): row for n, row in enumerate(rows)}
                    if not all(n in by_number for n in numbers):
                        raise ValueError('Choose a number from this page, or use arrows and Space.')
                    targets = [by_number[n] for n in numbers]
                    cursors[page] = rows.index(targets[-1])
                else:
                    notice = 'Use arrows / Space, or choose a page. ? explains the focused component.'
                    continue
                for row in targets:
                    command = row['command']
                    if page in ('f', 'a'):
                        name = command
                        if name in requested:
                            if name == 'tinywidgets':
                                requested = [n for n in requested if n not in ['tinywidgets', 'widgets', *WIDGET_COMPONENTS]]
                            else:
                                requested.remove(name)
                        elif choices.get(name, name) in modules:
                            parents = [n for n in requested if choices.get(name, name) in resolve_modules([n], choices)]
                            notice = 'Required by: ' + ', '.join(parents) + '. Disable that parent to remove this dependency.'
                        else:
                            requested.append(name)
                            if name == 'tinywidgets':
                                page = 't'
                                cursors['t'] = 1
                                notice = 'tinyWidgets enabled. Choose your personal layouts, theme and app installation below.'
                        active = resolve_modules(requested, choices) if requested else []
                        args.setup = [a for a in args.setup if CATALOG['setup_actions'][a]['module'] in active]
                    elif page == 'l':
                        key = command
                        options = CATALOG['choices'][key]['options']
                        old = choices[key]
                        value = options[(options.index(old) + 1) % len(options)]
                        setattr(args, key, value)
                        choices[key] = value
                        requested = [value if name == old else name for name in requested]
                    elif page == 'p':
                        if command == 'packages':
                            args.packages = not args.packages
                        elif row['mark'] == '+':
                            notice = 'Required by your selected components; inspect ? for its dependency status.'
                        elif command in args.extra_packages:
                            args.extra_packages.remove(command)
                        else:
                            args.extra_packages.append(command)
                            args.packages = True
                    elif page == 't':
                        if command == 'master':
                            if 'tinywidgets' in requested:
                                requested = [n for n in requested if n not in ['tinywidgets', 'widgets', *WIDGET_COMPONENTS]]
                                args.setup = [name for name in args.setup if name != 'tinywidgets']
                            else:
                                requested.append('tinywidgets')
                            continue
                        if 'tinywidgets' not in requested:
                            requested.append('tinywidgets')
                        if command == 'source':
                            args.tinywidgets_source = ui.prompt('tinyWidgets source directory: ') or args.tinywidgets_source
                        elif command.startswith('choice:'):
                            key = command.split(':')[1]
                            options = {'profile': ['keep', *args.widget_options['profiles']],
                                       'theme': list(WIDGET_PRESETS['themes']), 'motion': list(WIDGET_PRESETS['motions']),
                                       'install': ['auto', 'build', 'configure']}[key]
                            old = args.widget_options[key]
                            args.widget_options[key] = options[(options.index(old) + 1) % len(options)]
                            required = {'profile': 'widgets-profiles', 'theme': 'widgets-themes', 'motion': 'widgets-motion'}.get(key)
                            if required and required not in args.widget_options['components']:
                                args.widget_options['components'].append(required)
                            if key == 'install' and 'tinywidgets' in args.setup:
                                args.setup.remove('tinywidgets')
                        elif command.startswith('component:'):
                            key = command.split(':')[1]
                            if key in args.widget_options['components']:
                                args.widget_options['components'].remove(key)
                            elif row['mark'] == '+':
                                notice = 'Required by the active layout. Choose another layout before disabling this integration.'
                            else:
                                args.widget_options['components'].append(key)
                        elif command.startswith('saved:'):
                            key = command.split(':')[1]
                            if key in args.widget_options['profiles']:
                                args.widget_options['profiles'].remove(key)
                            else:
                                args.widget_options['profiles'].append(key)
                    elif page == 'r':
                        preset = load_selection(args.target, Path(command))
                        args.selection = preset
                        requested = list(preset['requested'])
                        args.widget_options = copy.deepcopy(preset['widgets'])
                        for key, value in preset['choices'].items():
                            setattr(args, key, value)
                        for key in ('packages', 'extra_packages', 'setup', 'tinywidgets_source'):
                            setattr(args, key, copy.deepcopy(preset[key]))
                        page = 'f'
                        notice = row['label'] + ' loaded. Review your den before installing.'
                    else:
                        if command in args.setup:
                            args.setup.remove(command)
                        else:
                            args.setup.append(command)
                            if command == 'tinywidgets':
                                args.widget_options['install'] = 'build'
                            needed = CATALOG['setup_actions'][command]['module']
                            if needed not in modules and needed not in requested:
                                requested.append(needed)
                if requested:
                    selection_for(args, requested)
            except (OSError, ValueError) as exc:
                vars(args).clear()
                vars(args).update(snapshot)
                requested = old_requested
                notice = str(exc)

def source_path(value, home):
    return home / value[2:] if value.startswith('~/') else Path(value).expanduser().absolute()


def active_widget_profile(selection, home):
    options = selection['widgets']
    if options['profile'] == 'keep' and not (home / '.config/eww/instances.json').exists():
        return 'Trabajo' if 'Trabajo' in options['profiles'] else next(iter(options['profiles']), 'keep')
    return options['profile']


def selected_modules(selection, home):
    requested = list(selection['requested'])
    modules = resolve_modules(requested, selection['choices'])
    if 'widgets-profiles' in modules:
        active = active_widget_profile(selection, home)
        if active != 'keep':
            requested += WIDGET_PRESETS['profiles'][active]['requires']
    return resolve_modules(requested, selection['choices'])


def effective_setup(selection, home):
    actions = [name for name in selection['setup'] if name != 'tinywidgets' or selection['widgets']['install'] != 'configure']
    if 'tinywidgets' in selection['requested']:
        mode = selection['widgets']['install']
        installed = (home / '.local/bin/widgetctl').is_file() and (home / '.local/lib/randly-widgets/randly-widget-manager').is_file()
        if 'widgets-minecraft' in selected_modules(selection, home) and not (home / '.config/eww/widgets/minecraft/collection.json').is_file():
            installed = False
        state = home / '.local/state/raccon-dots/setup.json'
        try:
            previous = json.loads(state.read_text()).get('actions', {}).get('tinywidgets', {})
            if previous.get('status') in ('failed', 'running', 'cancelled'):
                installed = False
        except (OSError, ValueError, AttributeError):
            pass
        if mode == 'build' or (mode == 'auto' and not installed):
            if 'tinywidgets' not in actions:
                actions.append('tinywidgets')
    return actions


def execution_selection(selection, home):
    return {**selection, 'setup': effective_setup(selection, home)}


def setup_preflight(selection, home):
    for name in selection['setup']:
        if name == 'tinywidgets':
            source = source_path(selection['tinywidgets_source'], home)
            if not all((source / path).is_file() for path in ('Cargo.toml', 'scripts/install.sh')) or not (source / 'python/randly_widgets').is_dir():
                raise ValueError('Set a valid tinyWidgets source directory on the App setup page or with --tinywidgets-source.')
            needed = ['cargo', 'pkgconf', 'cc', 'eww']
        elif name == 'plymouth':
            needed = ['plymouth-set-default-theme', 'sudo']
        elif name == 'ai-skills':
            needed = ['npx']
        else:
            needed = ['code' if name == 'vscode-extensions' else 'nvim']
        if not selection['packages']:
            missing = [program for program in needed if not shutil.which(program)]
            if missing:
                raise ValueError('Missing setup tools: ' + ', '.join(missing) + '. Enable package installation or install them first.')


def run_logged_command(command, env, output, label):
    if not sys.stdout.isatty():
        subprocess.run(command, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, check=True)
        return
    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=output,
                               stderr=subprocess.STDOUT, start_new_session=True)
    start, last = time.monotonic(), -1
    try:
        while process.poll() is None:
            seconds = int(time.monotonic() - start)
            if seconds != last:
                print(f'\r  {label} / {seconds}s elapsed / writing setup log', end='', flush=True)
                last = seconds
            time.sleep(0.15)
        print()
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        raise


def run_setup(selection, home):
    if not selection['setup']:
        return
    # External app installers own their application data and build backups.
    with installation_lock(home) as state:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        status_path = safe_destination(home, '.local/state/raccon-dots/setup.json')
        try:
            previous = json.loads(status_path.read_text())
            history = previous.get('actions', {}) if isinstance(previous, dict) else {}
            history = history if isinstance(history, dict) else {}
        except (OSError, ValueError):
            history = {}
        status = {'version': RELEASE['version'], 'actions': history}
        env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'),
               'XDG_DATA_HOME': str(home / '.local/share'), 'XDG_STATE_HOME': str(home / '.local/state'),
               'XDG_CACHE_HOME': str(home / '.cache')}
        for name in selection['setup']:
            log = safe_destination(home, f'.local/state/raccon-dots/setup-logs/{stamp}-{name}.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            entry = {'status': 'running', 'log': str(log)}
            status['actions'][name] = entry
            atomic_write(status_path, json_bytes(status), 0o600)
            if name == 'vscode-extensions':
                command = ['sh', str(ROOT / 'extras/install-vscode-extensions.sh')]
            elif name == 'nvim-plugins':
                command = ['nvim', '--headless', '+Lazy! sync', '+qa']
            elif name == 'plymouth':
                command = ['sh', str(ROOT / 'extras/install-plymouth.sh')]
            elif name == 'ai-skills':
                command = [sys.executable, str(ROOT / 'scripts/capture_ai.py'), str(ROOT / 'modules/ai/files/.config/raccon-dots/ai-skills.json')]
            else:
                command = ['sh', str(ROOT / 'extras/install-tinywidgets.sh'), str(source_path(selection['tinywidgets_source'], home))]
            print(f'App setup: {CATALOG["setup_actions"][name]["label"]} ...', flush=True)
            try:
                with log.open('w') as output:
                    log.chmod(0o600)
                    if name == 'plymouth':
                        # sudo asks on the terminal, so this action stays in the foreground session.
                        subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
                    else:
                        run_logged_command(command, env, output, name)
            except (OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
                entry['status'] = 'cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed'
                atomic_write(status_path, json_bytes(status), 0o600)
                if isinstance(exc, KeyboardInterrupt):
                    raise
                raise ValueError(f'{name} setup failed. Dotfiles and preferences are saved. See {log}, then retry the saved profile.') from None
            entry['status'] = 'complete'
            entry['finished_at'] = datetime.now(timezone.utc).isoformat()
            atomic_write(status_path, json_bytes(status), 0o600)
            print(f'  Complete. Log: {log}')


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
