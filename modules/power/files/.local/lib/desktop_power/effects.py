"""Desktop adapters. Only transition changes write to the compositor."""
import json
import os
from pathlib import Path
import signal
import subprocess

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


def hyprland(profile):
    factor = profile['animation_factor']
    def flag(key):
        return str(profile.get(key, True)).lower()
    code = (f'require("conf.animations")({factor})\n'
            f'hl.config({{ decoration = {{ blur = {{ enabled = {flag("blur")}, '
            f'passes = {2 if factor == 1 else 1} }}, shadow = {{ enabled = {flag("shadow")} }} }} }})\n')
    result = run(['hyprctl', 'eval', code])
    if result != 'ok':
        raise RuntimeError(result)
    config = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
    write_text(config / 'hypr/desktop-power.lua', code)


def widget_policy():
    """Explicit adapter for tinyWidgets; other profiles keep their own policy."""
    ctl=HOME/'.local/bin/widgetctl'
    status=STATE/'status.json'
    if not ctl.is_file() or not status.is_file():return
    command=[str(ctl),'--config',str(HOME/'.config/eww')]
    general=json.loads(run([*command,'style']))
    if isinstance(general,dict) and 'frame' in general:
        run([*command,'policy',str(status)])


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
