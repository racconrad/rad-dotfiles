from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from install_context import Context, ROOT
from install_render import TEMPLATE_OWNERS, ZSH_PERSONAL, render

CATALOG = json.loads((ROOT / 'modules.json').read_text())
RELEASE = json.loads((ROOT / '.rdot').read_text())


def safe_relative(relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts):
        raise ValueError(f'Invalid module path: {relative}')
    return path


def safe_destination(home, relative):
    destination = home / safe_relative(relative)
    parent = destination.parent
    while parent != home:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f'Parent directory needs manual review: {parent}')
        parent = parent.parent
    if destination.exists() and destination.is_dir():
        raise ValueError(f'Expected a file, found a directory: {destination}')
    return destination


def file_plan(home, modules, choices, selection=None, render_modules=None, ctx=None):
    c = Context(ctx)
    plan = {}
    options = c.validate_widget_options((selection or {}).get('widgets', {}))
    for module in modules:
        base = c.ROOT / 'modules' / module / 'files'
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
            c.safe_destination(home, relative)
            if relative in plan:
                raise ValueError(f'Two modules write {relative}')
            plan[relative] = (c.render(relative, source.read_bytes(), home, render_modules or modules, choices),
                              source.stat().st_mode & 0o777)
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
            plan['.config/eww/instances.json'] = (c.json_bytes({'version': 1, 'revision': 1,
                                                          'widgets': document['widgets']}), 0o600)
            if 'widgets-motion' not in modules and document.get('animation'):
                plan['.config/eww/animation.json'] = (c.json_bytes(document['animation']), 0o644)
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
def installation_lock(home, ctx=None):
    c = Context(ctx)
    state = home / '.local/state/raccon-dots'
    c.safe_destination(home, '.local/state/raccon-dots/install.lock')
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


def undo(home, backup, records, ctx=None):
    c = Context(ctx)
    for record in reversed(records):
        dest = c.safe_destination(home, record['path'])
        if record['previous'] == 'missing':
            dest.unlink(missing_ok=True)
        elif record['previous'] == 'link':
            dest.unlink(missing_ok=True)
            dest.symlink_to(record['link'])
        else:
            source = backup / 'files' / record['path']
            c.atomic_write(dest, source.read_bytes(), record['mode'])


def apply_plan(home, plan, modules, choices, selection=None, partial=False, expected=None, ctx=None):
    c = Context(ctx)
    plan = dict(plan)
    if selection is not None:
        selection = c.validate_selection(selection)
        plan['.config/raccon-dots/profile.json'] = (c.json_bytes(selection), 0o600)
    with c.installation_lock(home) as state:
        for relative in [*plan, '.rdot']:
            c.safe_destination(home, relative)
        for relative, baseline in (expected or {}).items():
            if c.digest(c.safe_destination(home, relative)) != baseline:
                raise ValueError(f'File changed after preview: {relative}; review the update again.')
        changes = {rel: value for rel, value in plan.items() if not c.unchanged(home / rel, *value)}
        previous = c.read_receipt(home)
        old_modules = set(previous.get('modules', []))
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
        changes['.rdot'] = (c.json_bytes(receipt), 0o644)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        c.safe_destination(home, f'.local/state/raccon-dots/backups/{stamp}/manifest.json')
        backup = state / 'backups' / stamp
        backup.mkdir(parents=True, mode=0o700)
        records = []
        journal = {'schema': 1, 'home': str(home), 'status': 'applying', 'files': records}

        def save_journal():
            c.atomic_write(backup / 'manifest.json', c.json_bytes(journal), 0o600)

        try:
            for relative, (data, mode) in changes.items():
                dest = c.safe_destination(home, relative)
                record = {'path': relative, 'previous': 'missing', 'after': hashlib.sha256(data).hexdigest() + ':' + oct(mode)}
                if dest.is_symlink():
                    record.update(previous='link', link=os.readlink(dest))
                elif dest.exists():
                    saved = backup / 'files' / relative
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, saved)
                    record.update(previous='file', mode=dest.stat().st_mode & 0o777)
                records.append(record)
                save_journal()
                c.atomic_write(dest, data, mode)
            journal['status'] = 'installed'
            save_journal()
        except BaseException:
            c.undo(home, backup, records)
            journal['status'] = 'rolled-back'
            save_journal()
            raise
        print(f'Installed {len(changes) - 1} files. Version {RELEASE["version"]}.')
        print(f'Backup: {backup}')
        print('Log out and back into Hyprland to load the desktop.')
        return backup


def restore(backup, home, ctx=None):
    c = Context(ctx)
    backup = backup.resolve()
    journal = json.loads((backup / 'manifest.json').read_text())
    if journal.get('status') != 'installed' or journal.get('home') != str(home):
        raise ValueError('This backup is not an active installation for the target HOME.')
    with c.installation_lock(home):
        for record in journal['files']:
            dest = c.safe_destination(home, record['path'])
            if c.digest(dest) != record['after']:
                raise ValueError(f'File changed since installation: {dest}. Recover its backup manually.')
            if record['previous'] == 'file':
                saved = backup / 'files' / safe_relative(record['path'])
                if not saved.is_file() or saved.is_symlink():
                    raise ValueError(f'Missing backup file: {saved}')
        c.undo(home, backup, journal['files'])
        journal['status'] = 'restored'
        c.atomic_write(backup / 'manifest.json', c.json_bytes(journal), 0o600)
    print('Previous files restored. Installed packages are kept.')


def preview(home, modules, choices, plan, show_files=False, selection=None, ctx=None):
    c = Context(ctx)
    changed = sum(not c.unchanged(home / rel, *value) for rel, value in plan.items())
    print(f'\nRaccon Dots {RELEASE["version"]} -> {home}')
    print('Features and apps: ' + ', '.join(modules))
    print('Alternatives: ' + ', '.join(f'{k}={v}' for k, v in choices.items()))
    print(f'Configuration files: {len(plan)} | changes: {changed}')
    selection = selection or {}
    actions = c.effective_setup(selection, home) if selection.get('widgets') else selection.get('setup', [])
    packages = c.packages_for(modules, selection.get('extra_packages', []), actions)
    enabled = selection.get('packages', False)
    print(f'Package installation: {"enabled" if enabled else "disabled (configuration only)"}')
    print('App packages and dependencies: ' + ' '.join(packages))
    print('Application setup: ' + (', '.join(actions) or 'none'))
    if 'widgets' in modules and selection.get('widgets'):
        options = selection['widgets']
        print(f'tinyWidgets: {c.active_widget_profile(selection, home)} layout | {options["theme"]} theme | {options["motion"]} motion | {options["install"]} installation')
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
            print(('  = ' if c.unchanged(home / relative, *value) else '  + ') + relative)
