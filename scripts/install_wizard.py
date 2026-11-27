from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import sys
from contextlib import redirect_stdout

from install_context import Context, ROOT
from terminal_ui import Terminal
from install_widgets import WIDGET_COMPONENTS, WIDGET_PRESETS
from install_screens import (
    FEATURES, APPS, GROUP_LABELS, CATALOG, RELEASE,
    clear_screen, welcome, package_screen, recovery_screen, rows_for, row_details,
)


def interactive(args, ctx=None):
    c = Context(ctx)
    if not c.welcome(args):
        return None
    requested = list(args.selection['requested'])
    args.widget_options = copy.deepcopy(getattr(args, 'widget_options', args.selection['widgets']))
    page, cursors = 'f', {}
    inventory = c.environment_snapshot() if sys.stdout.isatty() else {'known': False}
    notice = 'Loaded saved preferences.' if c.read_receipt(args.target) or getattr(args, 'profile', None) else 'Choose what belongs in your den. Press ? to inspect dependencies.'
    tabs = [('f', 'Features'), ('a', 'Apps'), ('l', 'Choices'), ('t', 'Widgets'), ('p', 'Deps'), ('s', 'Setup'), ('r', 'Profiles')]
    titles = {'f': 'DESKTOP FEATURES', 'a': 'APPLICATIONS', 'l': 'APP ALTERNATIVES',
              't': 'TINYWIDGETS / YOUR PERSONAL DEN', 'p': 'APP PACKAGES AND DEPENDENCIES',
              's': 'OPTIONAL APPLICATION SETUP', 'r': 'CHOOSE A STARTING PROFILE'}
    with Terminal(plain=getattr(args, 'plain', False)) as ui:
        while True:
            choices = c.choices_for(args)
            selection = c.selection_for(args, requested) if requested else {**args.selection, 'requested': [], 'choices': choices, 'widgets': args.widget_options}
            modules = c.selected_modules(selection, args.target) if requested else []
            report = c.readiness(selection, args.target, inventory) if requested else {'blockers': ['Select at least one feature or application.'], 'notes': []}
            rows = c.rows_for(page, args, requested, selection, modules, inventory)
            cursor = max(0, min(cursors.get(page, 0), len(rows) - 1))
            details = c.row_details(page, rows[cursor], args, requested, selection, modules, inventory)
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
                    inventory = c.environment_snapshot()
                    notice = 'Dependency checks refreshed from local package databases.'
                    continue
                if action == '?' or (action == 'd' and page == 'p'):
                    lines = details if action == '?' else [c.package_label(p, inventory) for p in c.packages_for(modules, args.extra_packages, c.effective_setup(selection, args.target))]
                    ui.show('DEPENDENCIES / ' + rows[cursor]['label'], lines)
                    continue
                if action == 'path' and page in ('s', 't'):
                    args.tinywidgets_source = ui.prompt('tinyWidgets source directory: ') or args.tinywidgets_source
                    continue
                if action == 'w':
                    profile = getattr(args, 'save_profile', None) or c.ROOT / 'profiles/personal.json'
                    with redirect_stdout(io.StringIO()):
                        c.save_profile(profile, c.selection_for(args, requested))
                    notice = f'Profile saved: {profile}'
                    continue
                if action == 'h':
                    if ui.suspend(lambda: c.recovery_screen(args)):
                        args.selection = c.load_selection(args.target)
                        requested = list(args.selection['requested'])
                        for key, value in args.selection['choices'].items():
                            setattr(args, key, value)
                        for key in ('packages', 'extra_packages', 'setup', 'tinywidgets_source'):
                            setattr(args, key, args.selection[key])
                        args.widget_options = copy.deepcopy(args.selection['widgets'])
                        notice = 'Previous files and preferences restored.'
                    continue
                if action in ('v', 'i'):
                    selection = c.selection_for(args, requested)
                    modules = c.selected_modules(selection, args.target)
                    plan = c.file_plan(args.target, modules, choices, selection)
                    output = io.StringIO()
                    with redirect_stdout(output):
                        c.preview(args.target, modules, choices, plan, show_files=action == 'v', selection=selection)
                    report = c.readiness(selection, args.target, inventory)
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
                            parents = [n for n in requested if choices.get(name, name) in c.resolve_modules([n], choices)]
                            notice = 'Required by: ' + ', '.join(parents) + '. Disable that parent to remove this dependency.'
                        else:
                            requested.append(name)
                            if name == 'tinywidgets':
                                page = 't'
                                cursors['t'] = 1
                                notice = 'tinyWidgets enabled. Choose your personal layouts, theme and app installation below.'
                        active = c.resolve_modules(requested, choices) if requested else []
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
                        preset = c.load_selection(args.target, Path(command))
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
                    c.selection_for(args, requested)
            except (OSError, ValueError) as exc:
                vars(args).clear()
                vars(args).update(snapshot)
                requested = old_requested
                notice = str(exc)
