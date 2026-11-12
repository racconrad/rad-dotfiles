"""Read-only diagnostics for components recorded in an installation receipt."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import install

EXECUTABLES = {
    'desktop': ['eww', 'python3'], 'desktop-styles': ['eww', 'python3'],
    'wayfire': ['wayfire'], 'waybar': ['waybar'], 'kitty': ['kitty'],
    'alacritty': ['alacritty'], 'fuzzel': ['fuzzel'], 'rofi': ['rofi'],
    'swaync': ['swaync'], 'mako': ['mako'], 'gtklock': ['gtklock'],
    'swaylock': ['swaylock'], 'zsh': ['zsh'], 'fish': ['fish'],
    'nvim': ['nvim'], 'git': ['git'], 'vscode': ['code'],
    'firefox': ['firefox'], 'chromium': ['chromium'],
    'dolphin': ['dolphin'], 'thunar': ['thunar'], 'widgets': ['eww'],
}


def observe_processes(proc=Path('/proc')):
    observed, incomplete = set(), False
    try:
        entries = list(proc.iterdir())
    except OSError:
        return observed, True
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid == os.getuid():
                observed.add((entry / 'comm').read_text().strip())
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError:
            incomplete = True
    return observed, incomplete


def runtime_checks(home, modules, add):
    selected = {'waybar', 'wayfire'} & set(modules)
    if not selected:
        return
    if home.resolve() != Path.home().resolve() or not os.environ.get('WAYLAND_DISPLAY'):
        for name in sorted(selected):
            add('Runtime', name, 'warn', 'Unknown: foreign HOME or no current Wayland session; not probed.')
        return
    observed, incomplete = observe_processes()
    for name in sorted(selected):
        if name in observed:
            add('Runtime', name, 'ok', 'Running (process observed; not functional health proof).')
        elif incomplete:
            add('Runtime', name, 'warn', 'Unknown: process state is partly inaccessible.')
        else:
            add('Runtime', name, 'warn', 'Not running.', 'Inspect the current session startup or application logs.')


def unit_checks(units, add):
    if not units:
        return
    command = shutil.which('systemctl')
    if not command:
        add('Services', 'User services', 'warn', 'Unknown: systemctl is unavailable.')
        return
    for unit in units:
        try:
            result = subprocess.run([command, '--user', 'show', unit, '--no-pager',
                                     '--property=LoadState,ActiveState,Result,NeedDaemonReload'],
                                    capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired) as error:
            add('Services', unit, 'warn', f'Unknown: {error}')
            continue
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if result.returncode or not values.get('ActiveState'):
            add('Services', unit, 'warn', 'Unknown: user service state could not be read.')
            continue
        state, outcome = values['ActiveState'], values.get('Result', '')
        failed = state == 'failed' or outcome not in ('', 'success')
        missing = values.get('LoadState') in ('not-found', 'error', 'masked')
        add('Services', unit, 'fail' if failed or missing else 'ok',
            f'LoadState={values.get("LoadState", "unknown")}; ActiveState={state}; Result={outcome or "unknown"}',
            f'Inspect with: systemctl --user status {unit}' if failed or missing else '')
        if values.get('NeedDaemonReload') == 'yes':
            add('Services', unit + ' reload', 'warn', 'needs-reload: NeedDaemonReload=yes',
                'Review the unit, then run: systemctl --user daemon-reload')


def collect(home):
    checks = []

    def add(category, name, status, detail, hint=''):
        checks.append(dict(category=category, name=name, status=status, detail=detail, hint=hint))

    receipt = install.read_receipt(home)
    if not receipt or not receipt.get('modules'):
        add('Installation', 'Installed components', 'warn', 'Unknown: no installed-component receipt found.')
        return checks
    modules = sorted(set(receipt['modules']))
    for module in modules:
        known = module in install.CATALOG['modules']
        add('Components', module, 'ok' if known else 'warn',
            'Recorded in installation receipt.' if known else 'Recorded component is absent from this catalog.')
        for executable in EXECUTABLES.get(module, []):
            found = shutil.which(executable)
            add('Executables', executable, 'ok' if found else 'fail', found or 'Executable not found in PATH.',
                '' if found else f'Install the application required by {module}, or fix PATH.')
    runtime_checks(home, modules, add)
    if {'desktop', 'desktop-styles'} & set(modules):
        for executable in ('cc', 'pkg-config'):
            found = shutil.which(executable)
            add('Build prerequisites', executable, 'ok' if found else 'warn',
                found or 'Missing native UI rebuild prerequisite; cached adapters may still work.',
                '' if found else 'Install this tool before rebuilding the native UI adapters.')
    records = receipt.get('files', {})
    if not isinstance(records, dict) or not records:
        add('Files', 'Managed files', 'warn', 'Unknown: receipt has no file hashes.')
        return checks
    intact, units = 0, []
    for relative, record in sorted(records.items()):
        try:
            path = install.safe_destination(home, relative)
            if not isinstance(record, dict) or not isinstance(record.get('mode'), int) or not record.get('sha256'):
                raise ValueError('receipt has no valid hash and mode')
            expected = record['sha256'] + ':' + oct(record['mode'])
            current = install.digest(path)
            if current == 'missing':
                add('Files', relative, 'fail', f'Missing managed file: {relative}', 'Restore the file or preview its module update.')
            elif current != expected:
                add('Files', relative, 'warn', f'Locally modified: {relative}', 'Review local changes before updating; they are protected by default.')
            else:
                intact += 1
            if path.is_file() and relative.startswith('.local/bin/') and not os.access(path, os.X_OK):
                add('Executables', relative, 'fail', 'Installed script is not executable.')
            if Path(relative).parent == Path('.config/systemd/user') and relative.endswith('.service'):
                units.append(Path(relative).name)
        except (OSError, ValueError, TypeError) as error:
            add('Files', str(relative), 'fail', f'Cannot verify {relative}: {error}')
    status = ('fail' if any(c['status'] == 'fail' for c in checks if c['category'] == 'Files')
              else 'warn' if intact != len(records) else 'ok')
    add('Files', 'Managed files', status, f'{intact}/{len(records)} files match receipt hashes and modes.')
    unit_checks(units, add)
    return checks


def run(home, as_json=False):
    checks = collect(home)
    failed = any(check['status'] == 'fail' for check in checks)
    if as_json:
        print(json.dumps({'checks': checks}, indent=2, ensure_ascii=False))
    else:
        print('Raccon Dots Doctor\n')
        category = None
        for check in checks:
            if category != check['category']:
                category = check['category']
                print(f'[{category}]')
            print(f'  {check["status"].upper()} {check["name"]}: {check["detail"]}')
            if check['hint']:
                print('    ' + check['hint'])
        print('\nSummary: ' + ', '.join(f'{sum(c["status"] == status for c in checks)} {status}'
                                          for status in ('ok', 'warn', 'fail')))
    return int(failed)
