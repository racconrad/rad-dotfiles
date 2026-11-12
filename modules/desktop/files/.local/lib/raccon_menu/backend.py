"""Eww shell data/actions. desktop-power remains the sole owner of power policy."""
import datetime as dt
import fcntl
import hashlib
import json
import locale
import os
import pwd
from functools import lru_cache
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
import unicodedata

HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'raccon-menu'
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'raccon-menu'
POWER = STATE.parent / 'desktop-power'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', HOME / '.cache')) / 'raccon-menu'
HERE = Path(__file__).resolve().parent
BIN = HOME / '.local/bin'
MODES = ('auto', 'performance', 'balanced', 'complete', 'working')
PAGES = ('home', 'apps', 'modes', 'session', 'audio', 'connections', 'bluetooth', 'calendar', 'shortcuts')
WINDOW = 'raccon-menu'
SIMPLE_PAGES = False
BACKEND = HERE / 'backend.py'
NAMES = dict(zip(MODES, ('Automatic', 'Power saver', 'Balanced', 'Full', 'Working')))
ICONS = dict(zip(MODES, ('preferences-system-symbolic', 'battery-low-symbolic',
    'power-profile-balanced-symbolic', 'weather-clear-symbolic', 'computer-symbolic')))
ENGLISH_DESCRIPTIONS = {
    'Sin animaciones ni widgets; efectos mínimos y fondos animados pausados.':
        'Minimal effects; widgets hidden and animated wallpapers paused.',
    'Escritorio completo con transiciones breves, blur ligero y sin efectos continuos en widgets.':
        'Full desktop with brief transitions and light blur; no continuous widget effects.',
    'Todos tus widgets, animaciones y efectos originales.':
        'All your widgets, animations and original effects.',
    'Trabajo con agentes: sin bloqueo ni suspensión por inactividad, sin animaciones; energía balanceada.':
        'Agent work: no idle lock or suspend, no animations; balanced power.',
}
_daemon_process = None
sys.path.insert(0, str(HERE))
from transport import send as native_send, source_revision
import positioning
import home_apps
import recent_apps
import search_catalogue
# Providers may import GTK for accessibility settings; they must not load Eww's
# visibility adapter or compete for its FIFO. Only ensure_daemon adds it back.
if os.environ.get('RACCON_MENU_CONFIG'):
    os.environ.pop('GTK_MODULES', None)


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.' + str(os.getpid()))
    tmp.write_text(value)
    tmp.replace(path)


def run(argv, timeout=4):
    result = subprocess.run([str(x) for x in argv], text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'The operation did not complete.')
    return result.stdout.strip()


def transient_ipc(message):
    return 'Resource temporarily unavailable' in message or 'channel closed' in message


def eww(*args, timeout=4, env=None):
    # Eww 0.5 has a short internal socket deadline even when our timeout is longer.
    # Retry only idempotent requests; opening is confirmed separately below.
    attempts = 5 if args and args[0] in ('update', 'get', 'active-windows', 'ping') else 1
    for attempt in range(attempts):
        result = subprocess.run(['eww', '-c', str(CONFIG), '--no-daemonize', *args], text=True,
                                capture_output=True, timeout=timeout, env=env)
        if not result.returncode:
            return result.stdout.strip()
        message = result.stderr.strip() or result.stdout.strip() or 'Eww did not respond.'
        if attempt + 1 == attempts or not transient_ipc(message):
            raise RuntimeError(message)
        time.sleep(.08 * (attempt + 1))


def ensure_daemon(env):
    global _daemon_process
    revision = env.get('RACCON_MENU_REVISION', '')
    try:
        eww('ping', timeout=0.6)
        # Eww 0.5 ping may return success without stdout. Never start duplicates.
        installed = (RUNTIME / 'revision').read_text().strip() if (RUNTIME / 'revision').exists() else ''
        if not revision or revision == installed:
            return
        eww('kill')  # Upgrade only this menu's input module, never desktop widgets.
        time.sleep(.1)
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        pass
    STATE.mkdir(parents=True, exist_ok=True)
    log_path = STATE / 'daemon.log'
    with log_path.open('a') as log:
        child = subprocess.Popen(['eww', '-c', str(CONFIG), '--no-daemonize', 'daemon'],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env, start_new_session=True)
    _daemon_process = child
    for _ in range(30):
        try:
            eww('ping', timeout=.3)
            if revision and (RUNTIME / 'revision').read_text().strip() != revision:
                raise RuntimeError('The input adapter is still starting.')
            return
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            if child.poll() is not None:
                break
            time.sleep(.05)
    raise RuntimeError(f'Eww could not start. Log: {log_path}\n{log_path.read_text()[-2000:]}')


def update(**values):
    eww('update', *(f'{key}={json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value}'
                   for key, value in values.items()))


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def applications():
    from gi.repository import Gio, GLib
    apps = []
    for app in Gio.AppInfo.get_all():
        app_id = app.get_id()
        if not app.should_show() or not app_id:
            continue
        icon = app.get_icon()
        names = icon.get_names() if isinstance(icon, Gio.ThemedIcon) else []
        filename = icon.get_file().get_path() if isinstance(icon, Gio.FileIcon) else ''
        has_file = bool(filename and Path(filename).is_file())
        name = app.get_display_name()
        if isinstance(app, Gio.DesktopAppInfo):
            name = app.get_string('Name') or name
            entry = GLib.KeyFile()
            try:
                entry.load_from_file(app.get_filename(), GLib.KeyFileFlags.KEEP_TRANSLATIONS)
                name = entry.get_locale_string('Desktop Entry', 'Name', 'en') or name
            except (GLib.Error, TypeError):
                pass
        apps.append(dict(id=app_id, token=hashlib.sha256(app_id.encode()).hexdigest(),
            name=name, icon=names[0] if names else 'application-x-executable',
            file=filename if has_file else str(CONFIG / 'assets/empty.svg'), has_file=has_file,
            search=normalize(name + ' ' + app.get_display_name() + ' ' + (app.get_description() or ''))))
    apps.sort(key=lambda a: normalize(a['name']))
    write(STATE / 'apps.json', json.dumps(apps, ensure_ascii=False))
    return apps


def cached_applications():
    path = STATE / 'apps.json'
    if path.exists() and time.time() - path.stat().st_mtime < 300:
        catalog = read(path, [])
        for app in catalog:
            if not app.get('has_file') or not Path(app.get('file', '')).is_file():
                app.update(file=str(CONFIG / 'assets/empty.svg'), has_file=False)
        return catalog
    return applications()


def load_apps():
    # The resident GTK list is filtered locally, never replaced per keystroke.
    catalog = cached_applications()
    update(catalogue=catalogue(catalog), apps_loading=False)


def watch_catalogue():
    """Keep the GTK app list stable until installed applications actually change."""
    from gi.repository import Gio, GLib
    previous = None
    pending = 0
    current = read(STATE/'apps.json', [])

    def emit(catalog):
        nonlocal previous
        value = json.dumps(catalogue(catalog), ensure_ascii=False)
        if value != previous:
            print(value, flush=True)
            previous = value

    def refresh():
        nonlocal pending, current
        pending = 0
        try:
            current = applications()  # Enumerating also rearms AppInfoMonitor.
            emit(current)
        except (OSError, RuntimeError) as exc:
            print('Raccon catalogue: '+str(exc), file=sys.stderr)
        return GLib.SOURCE_REMOVE

    def changed(_monitor):
        nonlocal pending
        if not pending:
            pending = GLib.timeout_add(150, refresh)

    def preferences_changed(_monitor, path, other, _event):
        names = {item.get_basename() for item in (path, other) if item is not None}
        if names & {'home-apps.json', 'favorites.json', 'recent-apps.json'}:
            emit(current)

    STATE.mkdir(parents=True, exist_ok=True)
    preferences = Gio.File.new_for_path(str(STATE)).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
    preferences.connect('changed', preferences_changed)
    monitor = Gio.AppInfoMonitor.get()
    monitor.connect('changed', changed)
    emit(current)
    pending = GLib.idle_add(refresh)
    GLib.MainLoop().run()


def catalogue(catalog):
    value = home_apps.presentation(STATE, catalog)
    value['search'] = search_catalogue.rows(value['apps'])
    value.update(recent_apps.presentation(STATE, catalog))
    return value


def daily_apps(catalog):
    return catalogue(catalog)['favorites']


@lru_cache(maxsize=1)
def identity():
    account = pwd.getpwuid(os.getuid())
    name = account.pw_gecos.split(',', 1)[0].strip() or account.pw_name
    candidates = [HOME / '.face', HOME / '.face.icon']
    # AccountsService's exported user data is readable without privileged files.
    try:
        from gi.repository import Gio
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        from gi.repository import GLib
        result = bus.call_sync('org.freedesktop.Accounts', '/org/freedesktop/Accounts',
            'org.freedesktop.Accounts', 'FindUserById', GLib.Variant('(x)', (os.getuid(),)),
            None, Gio.DBusCallFlags.NONE, 400, None)
        properties = bus.call_sync('org.freedesktop.Accounts', result.unpack()[0],
            'org.freedesktop.DBus.Properties', 'GetAll',
            GLib.Variant('(s)', ('org.freedesktop.Accounts.User',)),
            None, Gio.DBusCallFlags.NONE, 400, None).unpack()[0]
        name = properties.get('RealName') or name
        icon = properties.get('IconFile')
        if icon:
            candidates.insert(0, Path(icon))
    except Exception:
        pass
    candidates.append(Path('/var/lib/AccountsService/icons') / account.pw_name)
    avatar = next((str(path) for path in candidates if path.is_file() and os.access(path, os.R_OK)), '')
    return dict(user=name, avatar=avatar, has_avatar=bool(avatar))


def filter_apps(query):
    words = normalize(query).split()
    return [app for app in read(STATE / 'apps.json', []) if all(word in app['search'] for word in words)]


def filter_search(query):
    words = normalize(query).split()
    rows = search_catalogue.rows(read(STATE / 'apps.json', []))
    return [row for row in rows if all(word in normalize(row['search']) for word in words)]


def appearance_tokens():
    value = read(HOME / '.config/desktop-style/current/tokens.json')
    return value if isinstance(value, dict) else {}


def sync_popup_appearance(tokens, palette_text):
    """Eww watches its own directory; keep each popup's imports local."""
    override = CONFIG / '_desktop-style.scss'
    css = override.read_text() if override.exists() else '/* Original appearance */\n'
    for name in ('raccon-float', 'raccon-music'):
        folder = HOME / '.config' / name
        if not folder.is_dir():
            continue
        for filename, text in (('_palette.scss', palette_text), ('_desktop-style.scss', css)):
            path = folder / filename
            if not path.exists() or path.read_text() != text:
                write(path, text)
    folder = HOME / '.config/raccon-float'
    if folder.is_dir():
        def number(key, default):
            value = tokens.get(key)
            return value if type(value) in (int, float) and 0 <= value <= 100 else default
        font = str(tokens.get('font') or 'Inter').replace('"', '').replace('\\', '').replace('\n', '')
        text = (f'$radius: {number("radius", 20)}px;\n$control_radius: {number("control_radius", 12)}px;\n'
                f'$border: {number("border", 0)}px;\n$opacity: {min(1, number("opacity", 1))};\n$font: "{font}";\n'
                f'$panel_padding: {number("panel_padding", 16)}px;\n$control_padding: {number("control_padding", 8)}px;\n')
        path = folder / '_tokens.scss'
        if not path.exists() or path.read_text() != text:
            write(path, text)


def palette():
    colors = dict(primary='#a6c8ff', on_primary='#02315f', secondary='#bdc7dc', tertiary='#dabde2',
        surface='#111318', surface_container='#1d2024', surface_container_high='#282a2f',
        surface_container_highest='#32353a', on_surface='#e1e2e9', on_surface_variant='#c4c6cf',
        outline_variant='#43474e', shadow='#000000', error='#ffb4ab')
    for path, pattern in ((HOME / '.config/eww/_colors.scss', r'\$(\w+):\s*(#[\da-fA-F]{6})'),
                          (HOME / '.config/waybar/colors.css', r'@define-color\s+(\w+)\s+(#[\da-fA-F]{6});')):
        try:
            colors.update(re.findall(pattern, path.read_text()))
        except OSError:
            pass
    tokens = appearance_tokens()
    resolved = tokens.get('colors', {})
    if isinstance(resolved, dict):
        # Active desktop tokens win even if this Matugen configuration exports
        # only GTK/Qt and leaves old Waybar/Eww palette files on disk.
        colors.update({key: value for key, value in resolved.items()
                       if re.fullmatch(r'\w+', key) and isinstance(value, str)
                       and re.fullmatch(r'#[\da-fA-F]{6}', value)})
    text = '// Generated from active desktop tokens, with Waybar/Matugen fallback.\n'
    text += ''.join(f'${key}: {value};\n' for key, value in sorted(colors.items()))
    status = read(POWER / 'status.json')
    try:
        appearance = tomllib.loads((HOME / '.config/desktop-power/config.toml').read_text()).get('appearance', {})
    except (OSError, ValueError):
        appearance = {}
    level = status.get('level', 'normal')
    role = appearance.get(level, dict(high='primary', warning='tertiary', critical='error').get(level, 'on_surface'))
    if role not in colors:
        role = 'on_surface'
    if level in ('high', 'warning', 'critical'):
        text += f'$island_background: rgba(mix(${role}, $surface_container, 12%), .97);\n'
        text += f'$island_outline: rgba(${role}, .6);\n'
    else:
        text += '$island_background: rgba($surface_container, .97);\n$island_outline: rgba($outline_variant, .45);\n'
    path = CONFIG / '_palette.scss'
    if not path.exists() or path.read_text() != text:
        write(path, text)
    sync_popup_appearance(tokens, text)


def appearance_state(status=None):
    tokens = appearance_tokens()
    style = tokens.get('style', 'original')
    style = style if isinstance(style, str) and re.fullmatch(r'[\w-]+', style) else 'original'
    strict = tokens.get('strict') is True or style in ('ascii', 'monochrome', 'terminal', 'retro')
    factor = motion(read(POWER / 'status.json') if status is None else status)
    return dict(style=style, ascii=style == 'ascii', strict=strict,
                motion=factor > 0, duration=f'{round(240 * factor)}ms')


def listen_appearance():
    """Independent of the main menu's visibility; no timer or radio queries."""
    from raccon_events import FileEvents
    previous = None
    with FileEvents([HOME / '.config/desktop-style/current/tokens.json', POWER / 'status.json']) as changes:
        while True:
            palette()
            state = appearance_state()
            if state != previous:
                print(json.dumps(state), flush=True)
                previous = state
            changes.wait()


def mode_rows():
    try:
        config = tomllib.loads((HOME / '.config/desktop-power/config.toml').read_text())
    except (OSError, ValueError):
        config = {}
    rows = []
    for mode in MODES:
        profile = config.get('profiles', {}).get(mode, {})
        description = ('Follows battery and charger state.' if mode == 'auto'
                       else profile.get('description', 'Configure this mode in desktop-power/config.toml.'))
        description = ENGLISH_DESCRIPTIONS.get(description, description)
        rows.append(dict(id=mode, name=NAMES[mode], icon=ICONS[mode], description=description))
    return rows


def motion(status):
    # The user requested motion for the menu even while the PC stays in Power saver.
    # This is brief interaction feedback; no ambient loops or widget policy changes.
    factor = status.get('policy', {}).get('animation_factor', 1)
    factor = factor if isinstance(factor, (int, float)) else 1
    factor = max(.6, min(1, factor))
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        settings = Gtk.Settings.get_default()
        if settings and not settings.get_property('gtk-enable-animations'):
            return 0
    except (ImportError, RuntimeError):
        pass
    return factor


def snapshot(previous=None):
    previous = previous or {}
    status = read(POWER / 'status.json')
    preference = read(POWER / 'preference.json').get('mode', 'auto')
    now = dt.datetime.now()
    errors = status.get('errors', {})
    return dict(clock=now.strftime('%H:%M'), date=now.strftime('%A, %B %d').capitalize(),
        mode=status.get('mode', ''), source=status.get('source', ''), preference=preference,
        mode_name=NAMES.get(status.get('mode'), 'Loading mode'), applying=status.get('transition', False),
        has_errors=bool(errors), errors=' · '.join(f'{key}: {value}' for key, value in errors.items()),
        ready=bool(status.get('mode')), **appearance_state(status), **identity())


def listen():
    positioning.watch(RUNTIME)
    try:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'C')
    from filewatch import FileWatch
    with FileWatch([RUNTIME / 'visible']) as watch:
        previous, last = {}, None
        while True:
            if (RUNTIME / 'visible').exists() and (RUNTIME / 'visible').read_text().strip() == '0':
                watch.wait(5)
                continue
            palette()
            previous = snapshot(previous)
            line = json.dumps({k: v for k, v in previous.items() if not k.startswith('_')}, ensure_ascii=False)
            # Identical lines still make Eww re-evaluate every widget bound to `desktop`.
            if line != last:
                write(STATE / 'desktop.json', line)
                print(line, flush=True)
                last = line
            watch.wait(2)

def build_input_module():
    source = HERE / 'input.c'
    target = HOME / '.cache/raccon-menu/input.so'
    target.parent.mkdir(parents=True, exist_ok=True)
    # Menu and controls prewarm concurrently during Wayfire startup.
    with (target.parent / 'build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not target.exists() or target.stat().st_mtime_ns < int(source_revision(source)):
            flags = shlex.split(run(['pkg-config', '--cflags', '--libs', 'gtk+-3.0']))
            temp = target.with_name(f'.input-{os.getpid()}.so')
            try:
                run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter',
                     str(source), '-o', str(temp), *flags], timeout=30)
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
    return target


def geometry():
    try:
        import gi
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk
        display = Gdk.Display.get_default()
        if display:
            seat = display.get_default_seat()
            _, x, y = seat.get_pointer().get_position()
            monitor = display.get_monitor_at_point(x, y) or display.get_monitor(0)
            geo = monitor.get_geometry()
            index = next(i for i in range(display.get_n_monitors()) if display.get_monitor(i) == monitor)
            return index, max(280, min(420, geo.width - 260)), max(150, min(244, geo.height - 280))
    except (ImportError, AttributeError, RuntimeError, StopIteration):
        pass
    return 0, 420, 244


def close(super_key=False):
    if native_send('hide-super' if super_key else 'hide', str(RUNTIME)):
        return
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if super_key:
        write(RUNTIME / 'closed', str(time.monotonic()))
    update(revealed=False)
    time.sleep(0.12 if motion(read(POWER / 'status.json')) else 0)
    eww('close', WINDOW)


def initial_values(page, active):
    selected = read(POWER / 'preference.json').get('mode', 'auto')
    values = dict(page=PAGES.index(page or PAGES[0]), selected=selected if selected in MODES else 'auto',
                  confirmation='', error='', modes=mode_rows(), revealed=True)
    cached_desktop=read(STATE / 'desktop.json')
    if cached_desktop:values['desktop']=cached_desktop
    if not active:
        catalog = read(STATE / 'apps.json', [])
        values.update(catalogue=catalogue(catalog), apps_loading=False, busy=False)
    return values


def show(page=None, prewarm=False):
    if not prewarm and native_send('show ' + str(PAGES.index(page)) if page else 'toggle', str(RUNTIME)):
        return
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / 'toggle.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            stamp = float((RUNTIME / 'closed').read_text())
            if page is None and 0 <= time.monotonic() - stamp < 0.45:
                return
        except (OSError, ValueError):
            pass
        positioning.refresh(RUNTIME, force=True)
        module = build_input_module()
        palette()
        env = {**os.environ, 'LANGUAGE': 'en_US:en', 'LC_ALL': 'C.UTF-8', 'GTK_MODULES': str(module), 'RACCON_MENU_CONFIG': str(CONFIG),
               'RACCON_MENU_REVISION': source_revision(HERE / 'input.c'),
               'RACCON_MENU_BACKEND': str(BACKEND), 'RACCON_MENU_RUNTIME': RUNTIME.name,
               'RACCON_MENU_SIMPLE_PAGES': '1' if SIMPLE_PAGES else '0'}
        ensure_daemon(env)
        active = WINDOW + ':' in eww('active-windows')
        if active and prewarm:
            return
        if active and page is None:
            if eww('get', 'revealed').strip('"') != 'true':
                update(revealed=True)
                return
            close(super_key=True)
            return
        values = initial_values(page, active)
        values['prewarm'] = prewarm
        update(**values)
        if not active:
            monitor, width, height = geometry()
            try:
                eww('open', WINDOW, '--screen', str(monitor), '--arg', f'panel_width={width}',
                    '--arg', f'content_height={height}')
            except RuntimeError as exc:
                if not transient_ipc(str(exc)):
                    raise
                # The command was delivered; give GTK time to finish its first tree.
                time.sleep(.15)
            if prewarm:
                for _ in range(60):
                    if native_send('inspect', str(RUNTIME)):
                        return
                    time.sleep(.05)
                raise RuntimeError('Could not prepare the resident window.')
            update(revealed=True)
            # Eww 0.5 may exit a client successfully when its short IPC deadline
            # expires. Confirm the surface and its reveal state before reporting success.
            for _ in range(20):
                if native_send('show ' + str(PAGES.index(page or PAGES[0])), str(RUNTIME)):
                    time.sleep(.03)
                    if (RUNTIME / 'visible').read_text().strip() == '1':
                        return
                if WINDOW + ':' in eww('active-windows'):
                    visible = eww('get', 'revealed').strip('"')
                    if visible == 'true':
                        return
                    if visible == 'false':
                        update(revealed=True)
                time.sleep(0.05)
            raise RuntimeError('Eww did not confirm the menu is visible. Run desktop-menu diagnose.')


def prepare_resident():
    """Wait for the real GTK warmup, with retries for login-time startup races."""
    sys.path.insert(0, str(HERE.parent))
    from raccon_events import FileEvents
    ready = RUNTIME / 'ready'
    for attempt in range(3):
        try:
            if not (ready.exists() and ready.read_text().strip() == '1' and native_send('inspect', str(RUNTIME))):
                show(PAGES[0], prewarm=True)
            deadline = time.monotonic() + 3
            with FileEvents([ready]) as changes:
                while True:
                    if ready.exists() and ready.read_text().strip() == '1':
                        return
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError('Could not prepare the resident window before the warmup deadline.')
                    changes.wait(remaining)
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(.2 * (attempt + 1))


def apply_mode():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / 'apply.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        mode = eww('get', 'selected').strip('"')
        if mode not in MODES:
            raise ValueError('Select a valid mode.')
        update(busy=True, error='')
        try:
            run([BIN / 'desktop-power', 'set', mode], timeout=55)
            status = read(POWER / 'status.json')
            if status.get('source') != mode or status.get('transition'):
                raise RuntimeError('Mode saved and still applying. Check its status.')
            if status.get('errors'):
                raise RuntimeError('Mode saved with pending settings. Check the active mode notice.')
        finally:
            update(busy=False)


def launch_app(token):
    if not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('Invalid application.')
    item = next((app for app in read(STATE / 'apps.json', []) if app['token'] == token), None)
    if item is None:
        raise ValueError('App is no longer available. Reopen the menu.')
    from gi.repository import Gio
    app = Gio.DesktopAppInfo.new(item['id'])
    if app is None:
        raise ValueError('App is no longer installed.')
    close()
    if app.launch([], Gio.AppLaunchContext()):
        try:
            recent_apps.record(STATE, item['id'])
        except (OSError, ValueError) as exc:
            print('Raccon recent apps: ' + str(exc), file=sys.stderr)


def shortcut(name):
    commands = {'files': ['dolphin'], 'browser': ['brave'], 'terminal': ['kitty'],
        'audio': [str(BIN / 'desktop-panel'), 'audio'],
        'connections': [str(BIN / 'desktop-panel'), 'connections'],
        'calendar': [str(BIN / 'desktop-panel'), 'calendar'],
        'notifications': ['swaync-client', '-t', '-sw'], 'lock': [str(BIN / 'lock')]}
    if name not in commands:
        raise ValueError('Invalid shortcut.')
    close()
    subprocess.Popen(commands[name], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if 'shortcut:' + name in home_apps.SHORTCUTS:
        try:
            recent_apps.record(STATE, 'shortcut:' + name)
        except (OSError, ValueError) as exc:
            print('Raccon recent apps: ' + str(exc), file=sys.stderr)


def session_action(action):
    if action not in ('suspend', 'reboot', 'poweroff', 'logout'):
        raise ValueError('Invalid action.')
    if eww('get', 'confirmation').strip('"') != action:
        raise ValueError('Select the action to confirm first.')
    if action == 'logout':
        session = os.environ.get('XDG_SESSION_ID', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', session):
            raise ValueError('Could not identify this session.')
        argv = ['loginctl', 'terminate-session', session]
    else:
        argv = ['systemctl', action]
    run(argv, timeout=15)
    close()


def main(args):
    command = args[0] if args else 'toggle'
    if command == 'listen': listen()
    elif command == 'listen-appearance': listen_appearance()
    elif command == 'catalogue':
        catalog = cached_applications()
        print(json.dumps(catalogue(catalog), ensure_ascii=False))
    elif command == 'watch-catalogue': watch_catalogue()
    elif command == 'palette': palette()
    elif command == 'diagnose':
        print(WINDOW + ' · diagnostics')
        print('Config:', CONFIG)
        print('Session:', os.environ.get('XDG_SESSION_TYPE', 'unknown'))
        print('Wayland:', os.environ.get('WAYLAND_DISPLAY', 'unknown'))
        if native_send('inspect', str(RUNTIME)):
            time.sleep(.05)
            try: print((RUNTIME / 'inspect').read_text().strip())
            except OSError: pass
        native_state = RUNTIME / 'visible'
        if native_state.exists():
            print('Resident window:', 'visible' if native_state.read_text().strip() == '1' else 'hidden')
        for action in ('ping', 'active-windows', 'get'):
            names = [('get', 'revealed'), ('get', 'page')] if action == 'get' else [(action,)]
            for argv in names:
                try:
                    print(' '.join(argv) + ':', eww(*argv, timeout=1) or '(empty)')
                except Exception as exc:
                    print(' '.join(argv) + ':', str(exc))
        log = STATE / 'daemon.log'
        if log.exists():
            print('Recent log:')
            print(log.read_text()[-2500:])
    elif command == 'query':
        query = args[1] if len(args) > 1 else ''
        results = filter_search(query)
        update(apps=results, query_empty=not bool(results))
    elif command == 'apply': apply_mode()
    elif command == 'launch': launch_app(args[1])
    elif command == 'search-action':
        if len(args) != 2:
            raise ValueError('Invalid search action.')
        main(search_catalogue.resolve(args[1]))
    elif command == 'recent':
        if len(args) != 2:
            raise ValueError('Invalid recent applications arguments.')
        recent_apps.edit(STATE, args[1])
        try:
            update(error='')
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            pass
    elif command == 'favorite':
        home_apps.edit(STATE, cached_applications(), args[1:])
        try:
            update(error='')
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            pass
    elif command == 'launch-first':
        results = filter_search(args[1] if len(args) > 1 else '')
        if results:
            main([results[0]['action'], results[0]['value']])
    elif command == 'shortcut': shortcut(args[1])
    elif command == 'control-action':
        os.execv(sys.executable, [sys.executable, str(HERE / 'panels.py'), *args[1:]])
    elif command == 'session-action': session_action(args[1])
    elif command == 'close': close(super_key=len(args) > 1 and args[1] == 'super')
    elif command in ('toggle', *PAGES):
        try:
            show(None if command == 'toggle' else command)
        except Exception:
            # Keep a usable launcher if Eww fails to load after an upgrade or edit.
            subprocess.Popen([sys.executable, str(HERE / 'legacy_menu.py')], start_new_session=True)
            try:
                run(['notify-send', '-a', 'Raccon Menu', 'Fallback menu',
                     'Eww could not open the menu. The GTK fallback opened. Check the terminal or Eww log.'])
            except Exception:
                pass
            raise
    elif command == 'modes-data':
        print(json.dumps(mode_rows(), ensure_ascii=False))
    elif command == 'opened':
        positioning.refresh(RUNTIME, force=True)
        palette()
        selected = read(POWER / 'preference.json').get('mode', 'auto')
        values = dict(selected=selected if selected in MODES else 'auto', confirmation='', error='')
        # Rebuilding the mode rows mid-animation is wasted work unless desktop-power's config changed.
        rows = json.dumps(mode_rows(), ensure_ascii=False)
        cache = RUNTIME / 'modes.json'
        if not cache.exists() or cache.read_text() != rows:
            values['modes'] = json.loads(rows)
            write(cache, rows)
        update(**values)
    elif command == 'prepare':
        prepare_resident()
    elif command == 'tab':
        if args[1] not in PAGES: raise ValueError('Invalid section.')
        if not native_send('tab ' + str(PAGES.index(args[1])), str(RUNTIME)):
            update(page=PAGES.index(args[1]), confirmation='', error='')
    elif command == 'select':
        if args[1] not in MODES: raise ValueError('Invalid mode.')
        update(selected=args[1], error='')
    elif command == 'confirm':
        if args[1] not in ('suspend', 'reboot', 'poweroff', 'logout', 'cancel'):
            raise ValueError('Invalid action.')
        update(confirmation='' if args[1] == 'cancel' else args[1])
    elif command == '--legacy':
        os.execv(sys.executable, [sys.executable, str(HERE / 'legacy_menu.py')])
    else: raise ValueError('Uso: desktop-menu [home|apps|modes|session|close]')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    except Exception as exc:
        print(f'Raccon Menu: {exc}', file=sys.stderr)
        try: update(error=str(exc), busy=False)
        except Exception: pass
        raise SystemExit(1)
