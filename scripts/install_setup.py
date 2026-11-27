from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from install_context import Context, ROOT

CATALOG = json.loads((ROOT / 'modules.json').read_text())
RELEASE = json.loads((ROOT / '.rdot').read_text())


def setup_preflight(selection, home, ctx=None):
    c = Context(ctx)
    for name in selection['setup']:
        if name == 'tinywidgets':
            source = c.source_path(selection['tinywidgets_source'], home)
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
            shutil_which = getattr(c.shutil, 'which', None) or c.shutil.which
            missing = [program for program in needed if not shutil_which(program)]
            if missing:
                raise ValueError('Missing setup tools: ' + ', '.join(missing) + '. Enable package installation or install them first.')


def run_logged_command(command, env, output, label, ctx=None):
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


def run_setup(selection, home, ctx=None):
    c = Context(ctx)
    if not selection['setup']:
        return
    with c.installation_lock(home) as state:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        status_path = c.safe_destination(home, '.local/state/raccon-dots/setup.json')
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
        subprocess_run = getattr(c.subprocess, 'run', None) or c.subprocess.run
        for name in selection['setup']:
            log = c.safe_destination(home, f'.local/state/raccon-dots/setup-logs/{stamp}-{name}.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            entry = {'status': 'running', 'log': str(log)}
            status['actions'][name] = entry
            c.atomic_write(status_path, c.json_bytes(status), 0o600)
            if name == 'vscode-extensions':
                command = ['sh', str(c.ROOT / 'extras/install-vscode-extensions.sh')]
            elif name == 'nvim-plugins':
                command = ['nvim', '--headless', '+Lazy! sync', '+qa']
            elif name == 'plymouth':
                command = ['sh', str(c.ROOT / 'extras/install-plymouth.sh')]
            elif name == 'hypr-canvas':
                command = ['sh', str(c.ROOT / 'extras/install-hypr-canvas.sh')]
            elif name == 'ai-skills':
                command = [sys.executable, str(c.ROOT / 'scripts/capture_ai.py'), str(c.ROOT / 'modules/ai/files/.config/raccon-dots/ai-skills.json')]
            else:
                command = ['sh', str(c.ROOT / 'extras/install-tinywidgets.sh'), str(c.source_path(selection['tinywidgets_source'], home))]
            print(f'App setup: {CATALOG["setup_actions"][name]["label"]} ...', flush=True)
            try:
                with log.open('w') as output:
                    log.chmod(0o600)
                    if name == 'plymouth':
                        subprocess_run(command, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
                    else:
                        c.run_logged_command(command, env, output, name)
            except (OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
                entry['status'] = 'cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed'
                c.atomic_write(status_path, c.json_bytes(status), 0o600)
                if isinstance(exc, KeyboardInterrupt):
                    raise
                raise ValueError(f'{name} setup failed. Dotfiles and preferences are saved. See {log}, then retry the saved profile.') from None
            entry['status'] = 'complete'
            entry['finished_at'] = datetime.now(timezone.utc).isoformat()
            c.atomic_write(status_path, c.json_bytes(status), 0o600)
            print(f'  Complete. Log: {log}')


def readiness(selection, home, inventory=None, ctx=None):
    c = Context(ctx)
    inventory = inventory or {'known': False}
    modules = c.selected_modules(selection, home)
    execution = c.execution_selection(selection, home)
    blockers, notes = [], []
    if 'widgets' in modules:
        config = home / '.config/eww'
        if (config / 'eww.yuck').exists() and not (config / '.modular-active').exists():
            blockers.append('Eww belongs to another configuration. Move or migrate that configuration before installing tinyWidgets.')
        if selection['widgets']['install'] == 'configure' and not (home / '.local/bin/widgetctl').exists():
            notes.append('tinyWidgets is not installed. Configure only saves preferences; choose Auto or Build to install its app.')
    try:
        c.setup_preflight(execution, home)
    except ValueError as exc:
        blockers.append(str(exc))
    needed = c.packages_for(modules, selection['extra_packages'], execution['setup'])
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
        active = c.active_widget_profile(selection, home)
        if active != 'keep':
            document = json.loads((c.ROOT / f'modules/widgets-profiles/files/.config/eww/profiles/{active}.json').read_text())
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


def component_details(name, requested, choices, modules, inventory, selection=None, home=None, ctx=None):
    c = Context(ctx)
    name = choices.get(name, name)
    meta = CATALOG['modules'][name]
    deps = [choices.get(dep, dep) for dep in meta['requires']]
    labels = [CATALOG['modules'][dep]['label'] for dep in deps if dep != 'base']
    lines = [meta['label'], meta.get('description', 'Installs this application and its reviewed configuration.'),
             'Needs: ' + (', '.join(labels) or 'user session environment')]
    packages = list(dict.fromkeys([*meta['packages'], *c.packages_for(c.resolve_modules([name], choices))]))
    lines.append('Packages: ' + (', '.join(packages) or 'no additional packages'))
    if inventory.get('known'):
        missing = set(packages) - inventory['installed']
        lines.append(f'{len(packages) - len(missing)}/{len(packages)} dependencies installed. {len(missing)} to prepare.')
    lines += ['  ' + c.package_label(p, inventory) for p in packages]
    parents = []
    for candidate in requested:
        resolved = choices.get(candidate, candidate)
        if resolved != name and name in c.resolve_modules([candidate], choices):
            parents.append(CATALOG['modules'][resolved]['label'])
    if parents:
        lines.append('Required by: ' + ', '.join(parents))
    if name == 'tinywidgets' and selection and home:
        actions = c.effective_setup(selection, home)
        lines += ['App: ' + ('build and install from local source' if 'tinywidgets' in actions else 'use the installed app / configure preferences'),
                  'Source: ' + selection['tinywidgets_source'],
                  'Build needs: ' + ', '.join(CATALOG['setup_actions']['tinywidgets']['packages']),
                  'Personal layout: ' + selection['widgets']['profile'],
                  'Theme / motion: ' + selection['widgets']['theme'] + ' / ' + selection['widgets']['motion']]
    return lines
