from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from install_context import Context, ROOT

CATALOG = json.loads((ROOT / 'modules.json').read_text())
RELEASE = json.loads((ROOT / '.rdot').read_text())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def choices_for(args, ctx=None):
    c = Context(ctx)
    saved = getattr(args, 'selection', {}).get('choices', c.read_receipt(args.target).get('choices', {}))
    return {key: getattr(args, key, None) or saved.get(key, info['default']) for key, info in CATALOG['choices'].items()}


def validate_selection(data, ctx=None):
    """Profiles are data only. Reject unknown settings instead of executing them."""
    c = Context(ctx)
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
    if not isinstance(source, str) or any(ch in source for ch in '\x00\n\r'):
        raise ValueError('Invalid tinyWidgets source path.')
    widget_options = c.validate_widget_options(data.get('widgets', {}))
    if 'tinywidgets' in requested:
        WIDGET_COMPONENTS = ['widgets-profiles', 'widgets-themes', 'widgets-motion', 'widgets-palette',
                             'widgets-music', 'widgets-github', 'widgets-minecraft']
        WIDGET_PRESETS = json.loads((ROOT / 'widget-presets.json').read_text())
        requested = [name for name in requested if name not in WIDGET_COMPONENTS]
        requested += widget_options['components']
        if widget_options['profile'] != 'keep':
            requested += ['widgets-profiles', *WIDGET_PRESETS['profiles'][widget_options['profile']]['requires']]
    modules = c.resolve_modules(requested, choices)
    for action in setup:
        needed = CATALOG['setup_actions'][action]['module']
        if needed not in modules:
            raise ValueError(f'{action} setup requires the {needed} module.')
    return {**RELEASE, 'requested': list(dict.fromkeys(requested)), 'choices': choices,
            'packages': packages, 'extra_packages': sorted(set(extras)),
            'setup': list(dict.fromkeys(setup)), 'tinywidgets_source': source, 'widgets': widget_options}


def load_selection(home, profile=None, ctx=None):
    c = Context(ctx)
    if profile:
        return c.validate_selection(json.loads(profile.expanduser().read_text()))
    receipt = c.read_receipt(home)
    if receipt:
        return c.validate_selection(receipt)
    return c.validate_selection(json.loads((ROOT / 'profiles/default.json').read_text()))


def selection_for(args, requested, ctx=None):
    c = Context(ctx)
    source = getattr(args, 'tinywidgets_source', '') or ''
    if source.startswith(str(args.target) + '/'):
        source = '~/' + str(Path(source).relative_to(args.target))
    return c.validate_selection({'requested': requested, 'choices': c.choices_for(args),
        'packages': bool(args.packages), 'extra_packages': getattr(args, 'extra_packages', []),
        'setup': getattr(args, 'setup', []), 'tinywidgets_source': source,
        'widgets': getattr(args, 'widget_options', getattr(args, 'selection', {}).get('widgets', {}))})


def profile_destination(path, ctx=None):
    c = Context(ctx)
    path = path.expanduser().absolute()
    if path.suffix != '.json' or path.is_symlink():
        raise ValueError('Save profiles to regular .json files, for example profiles/personal.json.')
    if path.is_relative_to(c.ROOT / 'modules') or path == c.ROOT / 'modules.json':
        raise ValueError('Choose a profile path outside the module sources.')
    if path.exists() and not path.is_file():
        raise ValueError(f'Expected a JSON profile file: {path}')
    for parent in path.parents:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f'Profile directory needs manual review: {parent}')
    return path


def save_profile(path, selection, ctx=None):
    c = Context(ctx)
    path = c.profile_destination(path)
    data = json_bytes(c.validate_selection(selection))
    if path.exists() and path.read_bytes() != data:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        history = c.profile_destination(path.parent / '.history' / path.stem / (stamp + '.json'))
        c.atomic_write(history, path.read_bytes(), 0o600)
        print(f'Previous profile saved: {history}')
    if not c.unchanged(path, data, 0o600):
        c.atomic_write(path, data, 0o600)
    print(f'Profile saved: {path}')


def read_receipt(home, ctx=None):
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


def with_previous(home, requested, choices, ctx=None):
    """Re-render installed modules too, so changing an alternative updates its users."""
    c = Context(ctx)
    previous = c.read_receipt(home).get('modules', [])
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


def resolve_modules(requested, choices, ctx=None):
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
    for group in ('terminal', 'notifications', 'lock', 'shell', 'browser', 'filemanager'):
        options = set(CATALOG['choices'][group]['options']).intersection(result)
        if len(options) > 1:
            raise ValueError(f'Choose one alternative for {group}: {", ".join(sorted(options))}')
        if options and choices[group] not in options:
            raise ValueError(f'Use --{group} {next(iter(options))} to select that alternative.')
    return result


def packages_for(modules, extra_packages=(), setup=(), ctx=None):
    packages = {p for name in modules for p in CATALOG['modules'][name]['packages']}
    packages.update(extra_packages)
    for action in setup:
        packages.update(CATALOG['setup_actions'][action]['packages'])
    return sorted(packages)


def install_packages(packages, ctx=None):
    c = Context(ctx)
    shutil_which = getattr(c.shutil, 'which', None) or c.shutil.which
    if not shutil_which('pacman'):
        raise ValueError('--packages requires Arch/CachyOS with pacman. You can install dotfiles without it.')
    subprocess_run = getattr(c.subprocess, 'run', None) or c.subprocess.run
    pending = [p for p in packages if subprocess_run(['pacman', '-Q', p],
               stdout=subprocess_run.__globals__['subprocess'].DEVNULL if hasattr(subprocess_run, '__globals__') and 'subprocess' in subprocess_run.__globals__ else None,
               stderr=None).returncode] if False else []
    import subprocess
    pending = [p for p in packages if subprocess_run(['pacman', '-Q', p],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode]
    missing = [p for p in pending if subprocess_run(['pacman', '-Si', p], stdout=subprocess.DEVNULL,
               stderr=subprocess.DEVNULL).returncode]
    if missing:
        raise ValueError('Packages unavailable in your repositories: ' + ', '.join(missing) +
                         '. Install them with your package manager, then retry without --packages.')
    if pending:
        subprocess_run(['sudo', 'pacman', '-S', '--needed', '--', *pending], check=True)
    else:
        print('All selected packages are already installed.')


def environment_snapshot(ctx=None):
    """Read package databases once; never refresh repositories or contact the network."""
    c = Context(ctx)
    result = {'installed': set(), 'available': set(), 'known': False}
    shutil_which = getattr(c.shutil, 'which', None) or c.shutil.which
    subprocess_run = getattr(c.subprocess, 'run', None) or c.subprocess.run
    if shutil_which('pacman'):
        try:
            installed = subprocess_run(['pacman', '-Qq'], capture_output=True, text=True, timeout=5)
            available = subprocess_run(['pacman', '-Slq'], capture_output=True, text=True, timeout=5)
            if installed.returncode == 0:
                result.update(installed=set(installed.stdout.splitlines()), known=True)
            if available.returncode == 0:
                result['available'] = set(available.stdout.splitlines())
        except (OSError, c.subprocess.TimeoutExpired if hasattr(c.subprocess, 'TimeoutExpired') else Exception):
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
