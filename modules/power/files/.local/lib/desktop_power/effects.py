"""Desktop adapters. Only transition changes write to the compositor."""
import configparser
import json
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import time
import xml.etree.ElementTree as ET

from .storage import STATE, read_json, write_json, write_text

HOME = Path.home()
WIDGET_REVISION = '1'


def widgets_need_install():
    path = STATE / 'eww-revision'
    return not path.exists() or path.read_text().strip() != WIDGET_REVISION


def run(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'No se pudo ejecutar ' + argv[0])
    return result.stdout.strip()


def ipc(method, data=None):
    path = os.environ.get('WAYFIRE_SOCKET')
    if not path:
        runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        path = next(iter(sorted(runtime.glob('wayfire-*.socket'))), None)
    if not path:
        raise RuntimeError('WAYFIRE_SOCKET no disponible')
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(3)
        sock.connect(str(path))
        body = json.dumps({'method': method, 'data': data or {}}).encode()
        sock.sendall(struct.pack('<I', len(body)) + body)
        def exact(n):
            result = b''
            while len(result) < n:
                part = sock.recv(n - len(result))
                if not part:
                    raise RuntimeError('Wayfire cerró la conexión')
                result += part
            return result
        size = struct.unpack('<I', exact(4))[0]
        if size > 4 * 1024 * 1024:
            raise RuntimeError('Respuesta IPC demasiado grande')
        return json.loads(exact(size))


def desktop_transition():
    """Briefly fade every mapped app window to its original opacity and back."""
    views = ipc('window-rules/list-views')
    originals = {}
    if not isinstance(views, list):
        return
    for view in views:
        if view.get('role') != 'toplevel' or not view.get('mapped'):
            continue
        view_id = view.get('id')
        if view_id is None:
            continue
        response = ipc('wf/alpha/get-view-alpha', {'view-id': view_id})
        if isinstance(response, dict) and response.get('error'):
            raise RuntimeError(str(response['error']))
        alpha = response.get('alpha') if isinstance(response, dict) else None
        if isinstance(alpha, (int, float)):
            originals[view_id] = max(0.0, min(1.0, float(alpha)))
    if not originals:
        return
    try:
        # Every window fades together so the wallpaper briefly comes through,
        # then its own pre-existing opacity is restored exactly.
        for factor in (0.92, 0.82, 0.70, 0.62, 0.70, 0.82, 0.92, 1.0):
            for view_id, original in originals.items():
                response = ipc('wf/alpha/set-view-alpha', {'view-id': view_id, 'alpha': original * factor})
                if isinstance(response, dict) and response.get('error'):
                    raise RuntimeError(str(response['error']))
            time.sleep(0.035)
    finally:
        for view_id, alpha in originals.items():
            try:
                ipc('wf/alpha/set-view-alpha', {'view-id': view_id, 'alpha': alpha})
            except (OSError, RuntimeError, ValueError):
                pass


def baseline_options(ini):
    """Canonical user settings win; XML supplies defaults for untouched settings."""
    result = {}
    for plugin in ('animate', 'vswitch', 'expo', 'scale', 'cube', 'switcher'):
        path = Path('/usr/share/wayfire/metadata') / (plugin + '.xml')
        if path.exists():
            for option in ET.parse(path).iter('option'):
                name = option.get('name', '')
                if option.get('type') == 'animation' or (plugin == 'animate' and name.endswith('enabled_for')):
                    value = option.findtext('default')
                    if value is not None:
                        result[f'{plugin}/{name}'] = value
        if ini.has_section(plugin):
            for key, value in ini.items(plugin):
                if 'duration' in key or (plugin == 'switcher' and key == 'speed') or (plugin == 'animate' and key.endswith('enabled_for')):
                    result[f'{plugin}/{key}'] = value
    return result


def scaled_duration(value, factor):
    match = re.match(r'^(\d+)(ms)?(.*)$', str(value).strip())
    if not match:
        return value
    return str(round(int(match[1]) * factor)) + (match[2] or '') + match[3]


def wayfire(profile, force=False):
    ini = configparser.ConfigParser(interpolation=None, strict=False)
    ini.read(HOME / '.config/wayfire.ini')
    original = ini.get('core', 'plugins')
    # Wayfire 0.11 animate inhibits rendering for the first 400ms. Unloading it
    # cancels the release timer without removing that inhibit: black desktop,
    # with only the hardware cursor visible. Keep it loaded and disable effects.
    disabled = set(profile['disable_plugins']) - {'animate'}
    desired = {'core/plugins': ' '.join(p for p in original.split() if p not in disabled)}
    factor = profile['animation_factor']
    desired.update({key: 'none' if factor == 0 and key.endswith('enabled_for') else scaled_duration(value, factor)
                    for key, value in baseline_options(ini).items()})
    desired['blur/kawase_iterations'] = ini.get('blur', 'kawase_iterations', fallback='3') if factor == 1 else '1'
    changed = {}
    for key, value in desired.items():
        current = ipc('wayfire/get-config-option', {'option': key})
        if key == 'core/plugins' and (not isinstance(current, dict) or current.get('result') != 'ok'):
            raise RuntimeError('Wayfire no permitió leer core/plugins')
        if isinstance(current, dict) and current.get('result') == 'ok' and str(current.get('value')) != str(value):
            changed[key] = value
    if changed:
        result = ipc('wayfire/set-config-options', changed)
        if not isinstance(result, dict) or result.get('result') != 'ok':
            raise RuntimeError('Wayfire no confirmó el cambio de opciones: ' + str(result))
    if factor == 0:
        views = ipc('window-rules/list-views')
        if isinstance(views, list):
            for view in views:
                if view.get('role') == 'toplevel' and view.get('mapped'):
                    ipc('wf/alpha/set-view-alpha', {'view-id': view['id'], 'alpha': 1.0})


def widgets(profile):
    if not (HOME / '.local/bin/widgetctl').is_file():
        return
    # Only the desktop profile is affected; other Eww projects have separate daemons.
    import hashlib
    config = str((HOME / '.config/eww').resolve())
    key = hashlib.sha256(config.encode()).hexdigest()[:12]
    editing = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'randly-widgets' / key / 'eww-widgets-editing'
    command = [str(HOME / '.local/bin/widgetctl'), '--config', config]
    if not profile['widgets'] and not editing.exists():
        run([*command, 'stop'])
    elif profile['widgets']:
        run([*command, 'start'])
    write_text(STATE / 'eww-revision', WIDGET_REVISION)


def cpu(profile):
    wanted = profile['cpu_profile']
    if run(['powerprofilesctl', 'get']) != wanted:
        run(['powerprofilesctl', 'set', wanted])


def focus_fx(profile):
    """One-time migration: a running Python daemon must load its new policy hook."""
    revision = STATE / 'focus-revision'
    if revision.exists() and revision.read_text().strip() == '1':
        return
    script = HOME / '.local/bin/wf-focus-fx'
    if not script.exists():
        return
    targets = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            argv = (path / 'cmdline').read_bytes().split(b'\0')
            if os.fsencode(script) in argv:
                targets.append((int(path.name), process_identity(path.name)[0]))
                os.kill(int(path.name), signal.SIGTERM)
        except (OSError, ValueError):
            continue
    deadline = time.monotonic() + 2
    while targets:
        remaining = []
        for pid, birth in targets:
            try:
                identity, state = process_identity(pid)
                if identity == birth and state != 'Z':
                    remaining.append((pid, birth))
            except OSError:
                pass
        if not remaining:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('El indicador de foco anterior aún no terminó')
        targets = remaining
        time.sleep(.05)
    # The advisory lock also handles a concurrent Wayfire autostart.
    log = (STATE / 'focus.log').open('a')
    subprocess.Popen([str(script)], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    log.close()
    write_text(revision, '1')


def process_identity(pid):
    raw = (Path('/proc') / str(pid) / 'stat').read_text()
    end = raw.rindex(')')
    fields = raw[end + 2:].split()
    return fields[19], fields[0]


def wallpaper(profile, config):
    paused_path = STATE / 'paused.json'
    paused = read_json(paused_path)
    allow = set(config['wallpaper']['processes'])
    if profile['animated_wallpaper']:
        for pid, birth in list(paused.items()):
            try:
                if process_identity(pid)[0] == birth:
                    os.kill(int(pid), signal.SIGCONT)
                paused.pop(pid, None)
            except ProcessLookupError:
                paused.pop(pid, None)
            except FileNotFoundError:
                paused.pop(pid, None)
        write_json(paused_path, paused)
    else:
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():
                continue
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                args = (path / 'cmdline').read_bytes().split(b'\0')
                if not args or Path(os.fsdecode(args[0])).name not in allow:
                    continue
                birth, state = process_identity(path.name)
                if state not in ('T', 't'):
                    os.kill(int(path.name), signal.SIGSTOP)
                    paused[path.name] = birth
                    write_json(paused_path, paused)
            except (OSError, ValueError):
                continue
    # GIFs rendered by awww need a still instead of pausing its IPC daemon.
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(HOME / '.cache')))
    source = cache / 'current-wallpaper'
    frozen = STATE / 'frozen-gif.json'
    if source.exists():
        original = source.read_text().strip()
        if Path(original).suffix.lower() == '.gif' and not profile['animated_wallpaper']:
            frame = cache / 'wallpaper-frame.png'
            stamp = frame.stat().st_mtime_ns if frame.exists() else None
            frozen_state = read_json(frozen)
            if stamp is not None and (frozen_state.get('source') != original or frozen_state.get('frame_stamp') != stamp):
                run(['awww', 'img', str(frame), '--transition-type', 'none'])
                write_json(frozen, {'source': original, 'frame_stamp': stamp})
        elif profile['animated_wallpaper'] and frozen.exists():
            # Respect a wallpaper changed by the user while in savings mode.
            if read_json(frozen).get('source') == original:
                run(['awww', 'img', original, '--transition-type', 'none'])
            frozen.unlink(missing_ok=True)
