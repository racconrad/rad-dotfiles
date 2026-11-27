import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
from desktop_style.context import Context

HOME = Path.home()
CONFIG = HOME / '.config/desktop-style'
STATE = HOME / '.local/state/desktop-style'
CURRENT = CONFIG / 'current'
BIN = HOME / '.local/bin'
PROFILES = {
    'collage': dict(icon='applications-multimedia-symbolic', widget_frame='none', name='Collage', detail='Sharp Vocaloid/UTAU paper-cutout layers and bold ink slices', font='Inter Display', radius=0, border=2, alpha=1, skin='minimal', position='bottom'),
}
STYLE_ALIASES = {'gnome':'collage','windows':'collage','default':'collage','simple':'collage',
                 'transparent':'collage','glass':'collage',
                 'classic':'collage','mono':'collage','monochrome':'collage',
                 'retro':'collage','night':'collage','ascii':'collage','ascii bloom':'collage',
                 'retrofuture':'collage','raccon retrofuture':'collage',
                 'dynamic':'collage','expressive':'collage','raccon expressive':'collage',
                 'modern':'collage','terminal':'collage',
                 'vocaloid':'collage','utau':'collage','utauloid':'collage',
                 'maximalist':'collage','maximalism':'collage','maximal':'collage',
                 'papel mache':'collage','papier-mache':'collage',
                 'vintage':'collage','macxp':'collage','mac':'collage','macintosh':'collage','windows xp':'collage','xp':'collage',
                 'luna':'collage','platinum':'collage','classic os':'collage','retro os':'collage'}
WIDGET_FRAME_ICONS = dict(auto='insert-link-symbolic', none='window-minimize-symbolic', future='applications-engineering-symbolic',
                         gnome='preferences-desktop-symbolic', windows='preferences-system-windows-symbolic',
                         monochrome='format-text-code-symbolic', retro='applications-games-symbolic',
                         glass='view-reveal-symbolic', ascii='format-text-code-symbolic',
                         collage='applications-multimedia-symbolic')
WIDGET_FRAMES = {'auto': 'Follow theme', 'none': 'No frame', 'monochrome': 'Mono', 'terminal': 'Classic',
                 'retro': 'Retro', 'future': 'Future', 'glass': 'Transparent', 'modern': 'Default',
                 'gnome': 'Rounded', 'windows': 'Compact', 'ascii': 'Night'}


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def save(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def normalize_style(style):
    return 'collage'


def migrate_theme_state(ctx=None):
    """Keep old commands/selections and frame overrides useful after fixing to Collage."""
    c = Context(ctx)
    selection = c.read(c.STATE / 'selection.json')
    if isinstance(selection, dict) and selection:
        selection.update(style='collage', name='Collage')
        c.save(c.STATE / 'selection.json', selection)
    frames = c.read(c.STATE / 'widget-frame.json')
    if isinstance(frames, dict):
        frames['styles'] = {'collage': 'none'}
        c.save(c.STATE / 'widget-frame.json', frames)


def run(argv, check=True, ctx=None):
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=30, check=check)


def canvas_mode_active(ctx=None):
    c = Context(ctx)
    tool = c.BIN / 'raccon-canvas-mode'
    if not os.access(tool, os.X_OK):
        tool = c.BIN / 'wf-canvas-mode'
    if not os.access(tool, os.X_OK):
        return False
    env = dict(os.environ)
    user_ini = c.HOME / '.config/wayfire/user.ini'
    if user_ini.is_file() and 'WF_CANVAS_INI' not in env:
        env['WF_CANVAS_INI'] = str(user_ini)
    try:
        return subprocess.run([str(tool), 'status'], env=env, capture_output=True, text=True, timeout=2).stdout.strip() == 'canvas'
    except (OSError, subprocess.SubprocessError):
        return False


def widgets_available(ctx=None):
    c = Context(ctx)
    return os.access(c.BIN / 'widgetctl', os.X_OK) and not c.canvas_mode_active()


def validate_css(text):
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    provider = Gtk.CssProvider()
    provider.load_from_data(text.encode())


def update(_extra_action=None, ctx=None, **values):
    c = Context(ctx)
    c.STATE.mkdir(parents=True, exist_ok=True)
    with (c.STATE / 'ui.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = c.read(c.STATE / 'ui.json')
        state.update(values)
        state['selected'] = 'collage'
        state['current'] = 'collage'
        state['motion'] = True
        state['compact_motion'] = c.read(c.HOME / '.local/state/desktop-power/status.json').get('policy', {}).get('animation_factor', 1) < 1
        c.save(c.STATE / 'ui.json', state)


def extra_action(name, ctx=None):
    c = Context(ctx)
    if name not in ('frames', 'close'):
        raise ValueError('Unknown extra options')
    c.update(_extra_action=name)
