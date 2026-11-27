import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import tomllib
from desktop_style.context import Context


def templates(ctx=None):
    c = Context(ctx)
    entries = tomllib.loads((c.HOME / '.config/matugen/config.toml').read_text())['templates']
    return {key: value for key, value in entries.items() if key != 'desktop_style_source'}


def render(template, colors):
    def replace(match):
        expr = match[1].strip()
        if expr == 'image':
            return 'wallpaper / desktop-style'
        parts = expr.split('.')
        if len(parts) != 4 or parts[0] != 'colors' or parts[1] not in colors:
            raise ValueError('Unsupported template: ' + expr)
        color = colors[parts[1]]
        fmt = parts[3]
        if fmt == 'hex':
            return color
        if fmt == 'hex_stripped':
            return color[1:]
        if fmt in ('red', 'green', 'blue'):
            from desktop_style.colors import rgb
            return str(round(rgb(color)[('red', 'green', 'blue').index(fmt)] * 255))
        raise ValueError('Unsupported format: ' + fmt)
    return re.sub(r'\{\{(.*?)\}\}', replace, template)


def surfaces(style, colors, ctx=None):
    c = Context(ctx)
    from desktop_style.appearance import build
    output = build(style, c.bar_profile(style), colors)
    return tuple(output[key] for key in ('widgets', 'raccon', 'rofi'))


def snapshot(paths):
    return {str(p): p.read_text() if p.exists() else None for p in paths}


def restore(files, ctx=None):
    c = Context(ctx)
    for name, value in files.items():
        path = Path(name)
        if value is None:
            path.unlink(missing_ok=True)
        else:
            c.write(path, value)


def ensure_import(path, line, ctx=None):
    c = Context(ctx)
    if not path.exists():
        return
    text = path.read_text()
    if line not in text:
        c.write(path, text.rstrip() + '\n\n' + line + '\n')


def integrations(style=None, ctx=None):
    c = Context(ctx)
    for path in (c.HOME / '.config/rofi').glob('*.rasi'):
        if path.name != 'colors.rasi':
            c.ensure_import(path, f'@import "{c.CURRENT}/rofi.rasi"')
    for name in ('swaync', 'swayosd', 'wlogout', 'gtklock'):
        c.ensure_import(c.HOME / '.config' / name / 'style.css', f'@import "{c.CURRENT}/{name}.css";')


def refresh_clients(ctx=None):
    c = Context(ctx)
    warnings = []
    commands = []
    if (c.BIN / 'hyprland-theme-apply').is_file():
        commands.append([c.BIN / 'hyprland-theme-apply'])
    if c.widgets_available():
        commands.append([c.BIN / 'widgetctl', 'theme'])
    if shutil.which('swaync-client'):
        commands.append(['swaync-client', '-rs'])
    for command in commands:
        try:
            result = c.run(command, False)
            if result.returncode:
                warnings.append(str(command[0]) + ': ' + result.stderr.strip()[:160])
        except (OSError, subprocess.TimeoutExpired) as exc:
            warnings.append(str(exc))
    c.run(['pkill', '-SIGUSR1', '-u', str(os.getuid()), '-x', 'kitty'], False)
    servers = []
    for proc in list(Path('/proc').iterdir()):
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = [v.decode() for v in (proc / 'cmdline').read_bytes().split(b'\0') if v]
            if not args or Path(args[0]).name != 'swayosd-server':
                continue
            env = dict(v.decode().split('=', 1) for v in (proc / 'environ').read_bytes().split(b'\0') if b'=' in v)
            if env.get('WAYLAND_DISPLAY') == os.environ.get('WAYLAND_DISPLAY'):
                servers.append((int(proc.name), args, env))
        except (OSError, ValueError):
            continue
    if servers:
        for pid, _, _ in servers:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass
        time.sleep(.1)
        with (c.STATE / 'osd.log').open('ab') as log:
            subprocess.Popen(servers[0][1], env=servers[0][2], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    if c.canvas_mode_active():
        canvas_tool = c.BIN / 'raccon-canvas-mode'
        if not os.access(canvas_tool, os.X_OK):
            canvas_tool = c.BIN / 'wf-canvas-mode'
        if os.access(canvas_tool, os.X_OK):
            try:
                result = c.run([canvas_tool, 'refresh'], False)
                if result.returncode:
                    warnings.append(str(canvas_tool) + ': ' + result.stderr.strip()[:160])
            except (OSError, subprocess.TimeoutExpired) as exc:
                warnings.append(str(exc))
    return warnings


def hypr_style(style, ctx=None):
    c = Context(ctx)
    profile = c.PROFILES[style]
    shadow = 18 if style == 'collage' else 0
    return ('hl.config({ general = { border_size = %d }, decoration = { rounding = %d, shadow = { range = %d } } })\n'
            % (profile['border'], profile['radius'], shadow))
