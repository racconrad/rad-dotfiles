from __future__ import annotations

import json
from pathlib import Path

from install_context import Context, ROOT

CATALOG = json.loads((ROOT / 'modules.json').read_text())
WIDGET_PRESETS = json.loads((ROOT / 'widget-presets.json').read_text())
WIDGET_COMPONENTS = ['widgets-profiles', 'widgets-themes', 'widgets-motion', 'widgets-palette',
                     'widgets-music', 'widgets-github', 'widgets-minecraft']


def validate_widget_options(data, ctx=None):
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


def source_path(value, home):
    return home / value[2:] if value.startswith('~/') else Path(value).expanduser().absolute()


def active_widget_profile(selection, home, ctx=None):
    options = selection['widgets']
    if options['profile'] == 'keep' and not (home / '.config/eww/instances.json').exists():
        return 'Trabajo' if 'Trabajo' in options['profiles'] else next(iter(options['profiles']), 'keep')
    return options['profile']


def selected_modules(selection, home, ctx=None):
    c = Context(ctx)
    requested = list(selection['requested'])
    modules = c.resolve_modules(requested, selection['choices'])
    if 'widgets-profiles' in modules:
        active = c.active_widget_profile(selection, home)
        if active != 'keep':
            requested += WIDGET_PRESETS['profiles'][active]['requires']
    return c.resolve_modules(requested, selection['choices'])


def effective_setup(selection, home, ctx=None):
    c = Context(ctx)
    actions = [name for name in selection['setup'] if name != 'tinywidgets' or selection['widgets']['install'] != 'configure']
    if 'tinywidgets' in selection['requested']:
        mode = selection['widgets']['install']
        installed = (home / '.local/bin/widgetctl').is_file() and (home / '.local/lib/randly-widgets/randly-widget-manager').is_file()
        if 'widgets-minecraft' in c.selected_modules(selection, home) and not (home / '.config/eww/widgets/minecraft/collection.json').is_file():
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


def execution_selection(selection, home, ctx=None):
    c = Context(ctx)
    return {**selection, 'setup': c.effective_setup(selection, home)}


def widget_rows(args, requested, modules, inventory, ctx=None):
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
