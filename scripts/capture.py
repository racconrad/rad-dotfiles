#!/usr/bin/env python3
"""Capture only reviewed settings. Never copy a whole home or application profile."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
from capture_ai import capture_ai

ROOT = Path(__file__).resolve().parents[1]
# Neutral placeholder: the dots ship no wallpapers.
PUBLIC_WALLPAPER = '@RDOT_HOME@/Pictures/Wallpapers/wallpaper.png'
CONFIGS = {
    'base': [],
    'wayfire': ['wayfire.ini', 'wayfire-keys.md', 'xdg-desktop-portal'],
    'desktop': ['desktop-menu/style.css', 'raccon-menu', 'raccon-float', 'raccon-music', 'swayosd'],
    'power': ['desktop-power/config.toml'],
    'waybar': ['waybar/config.jsonc', 'waybar/style.css', 'waybar/colors.css',
               'waybar/islands.css', 'waybar/icons'],
    'themes': ['matugen/config.toml', 'matugen/templates', 'matugen/out/wayfire-colors.sh',
               'gtk-3.0/gtk.css', 'gtk-3.0/colors.css', 'gtk-3.0/settings.ini',
               'gtk-4.0/gtk.css', 'gtk-4.0/gtk-dark.css', 'gtk-4.0/colors.css',
               'gtk-4.0/settings.ini', 'qt5ct', 'qt6ct', 'rofi/clipboard.rasi', 'rofi/colors.rasi'],
    'wallpaper': ['waypaper/config.ini', 'rofi/wallpaper.rasi'],
    'kitty': ['kitty'], 'alacritty': ['alacritty'],
    'fuzzel': ['fuzzel'], 'rofi': [],
    'swaync': ['swaync'], 'mako': ['mako'],
    'gtklock': ['gtklock'], 'swaylock': ['swaylock'],
    'zsh': ['starship.toml'], 'fish': ['fish/config.fish'],
    'tools': ['btop/btop.conf', 'cava/config', 'cava/shaders', 'fastfetch', 'yazi', 'lazygit'],
    'nvim': ['nvim/init.lua', 'nvim/lua', 'nvim/lazy-lock.json', 'nvim/lazyvim.json',
             'nvim/stylua.toml', 'nvim/LICENSE'],
    'chat-theme': ['legcord/quickCss.css'], 'audio': [],
}
SCRIPTS = {
    'base': ['rdot'],
    'kitty': [],
    'desktop': ['desktop-menu', 'desktop-panel', 'desktop-login-sddm', 'desktop-input-recover', 'clip-pick', 'screenshot', 'raccon-float', 'raccon-music', 'waybar-music'],
    'wayfire': ['desktop-polkit', 'display-mode', 'wf-focus-fx', 'wf-tile', 'wf-tile-ctl', 'wf-ws', 'wf-ws-label', 'wf-ws-watch'],
    'power': ['desktop-power', 'idle-lock', 'idle-suspend', 'waybar-power-hold', 'waybar-power-menu'],
    'wallpaper': ['wallpaper-grid', 'wallpaper-pick', 'wallpaper-restore', 'wallpaper-scheme',
                  'wallpaper-set', 'wallpaper-theme', 'wayfire-theme-apply'],
    'waybar': ['waybar-player', 'waybar-toggle'], 'gtklock': ['lock'],
}


SECRET = re.compile(
    r'-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----|'
    r'\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|'
    r'gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|'
    r'AIza[0-9A-Za-z-_]{35}|AKIA[A-Z0-9]{16}|'
    r'xox[baprs]-[0-9A-Za-z]{10,})\b|'
    r'(?i:\bBearer\s+[A-Za-z0-9._-]{20,})|'
    r'(?i:(?:api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\'\"][A-Za-z0-9._-]{16,}[\'\"])'
)


def real_name():
    """The account's display name, which must never appear in captured files."""
    import pwd
    return pwd.getpwuid(os.getuid()).pw_gecos.split(',', 1)[0].strip()


def wallpaper_folder(home):
    """The owner's wallpaper folder, read from waypaper instead of hard-coding a mount."""
    try:
        text = (home / '.config/waypaper/config.ini').read_text()
    except OSError:
        return None
    match = re.search(r'^folder\s*=\s*(.+)$', text, re.M)
    folder = match and str(Path(match.group(1).strip()).expanduser())
    return folder if folder and folder not in ('/', str(home)) else None


def sanitize(relative, text, home):
    if match := SECRET.search(text):
        raise ValueError(f'Posible credencial detectada en {relative} ({match.group(0)[:8]}...); captura cancelada por seguridad')
    if folder := wallpaper_folder(home):
        text = text.replace(folder, '@RDOT_HOME@/Pictures/Wallpapers')
    text = text.replace(str(home), '@RDOT_HOME@')
    if (owner := real_name()) and len(owner) > 2:
        text = re.sub(r'\b' + re.escape(owner) + r'\b', 'Raccon', text)  # case-sensitive: keeps runtime ids like randly-widgets
    # Personal wallpaper names never leave the machine; point to the bundled one.
    text = re.sub(r'@RDOT_HOME@/(?:Pictures/Wallpapers|\.local/share/wallpapers)/[^\s"\')]+', PUBLIC_WALLPAPER, text)
    if relative == '.config/gtklock/style.css':
        text = re.sub(r'  background-image: url\([^)]*\);\n(?:  background-(?:size|position): [^;]*;\n)*', '  background-color: @surface;\n', text)
    text = text.replace('Palette-Colors-Dark', 'Papirus-Dark')
    if relative == '.config/wayfire.ini':
        text = text.split('# >>> display-mode')[0].rstrip() + '\n'
        text = re.sub(r'\s+\S*liborbit\.so', '', text)
        text = re.sub(r'\n\[orbit\][\s\S]*?(?=\n\[|\Z)', '\n', text)
        # A copied laptop output layout can leave a new machine with no usable display.
    elif relative == '.config/wayfire-keys.md':
        text = '\n'.join(line for line in text.splitlines() if 'orbit' not in line.lower()) + '\n'
    elif relative == '.config/matugen/config.toml':
        text = re.sub(r'\n\[templates\.orbit\][\s\S]*?(?=\n\[|\Z)', '\n', text)
    elif relative == '.local/lib/desktop_power/effects.py':
        text = text.replace(", 'orbit')", ")")
        text = re.sub(r"    orbit_path = HOME / '.config/wayfire/orbit.conf'[\s\S]*?(?=\n\ndef widgets)", '', text)
        text = text.replace("def widgets(profile):\n", "def widgets(profile):\n    if not (HOME / '.local/bin/widgetctl').is_file():\n        return\n")
    elif relative == '.local/lib/desktop_power/controller.py':
        text = text.replace(", HOME / '.config/wayfire/orbit.conf'", '')
    elif relative in ('.local/bin/desktop-panel', '.local/lib/raccon_menu/legacy_panel.py'):
        text = text.replace('if date == dt.date.today():', 'if date == dt.date.today() and PLANNER.is_file():')
    elif relative == '.config/waybar/config.jsonc':
        data = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        for key in ('disk#me', 'disk#code'):
            data.pop(key, None)
            data['group/hardware']['modules'].remove(key)
        data['disk#home']['path'] = '@RDOT_HOME@'
        data['disk#home']['tooltip-format'] = 'Home · {used} usados / {total}'
        data['custom/updates']['on-click'] = 'kitty -e ~/.local/bin/raccon-update run'
        data['custom/updates']['exec'] = '~/.local/bin/raccon-update check'
        data['custom/updates']['return-type'] = 'json'
        text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    elif relative == '.config/fish/config.fish':
        text = ('if test -r /usr/share/cachyos-fish-config/cachyos-config.fish\n'
                '    source /usr/share/cachyos-fish-config/cachyos-config.fish\nend\n'
                'fish_add_path $HOME/.local/bin $HOME/go/bin\n'
                'set -gx EDITOR nvim\nset -gx VISUAL nvim\n'
                'if command -q starship\n    starship init fish | source\nend\n'
                'if command -q zoxide\n    zoxide init fish | source\nend\n')
    elif relative == '.config/alacritty/alacritty.toml':
        # TOML forbids appending [[tables]] to an already declared inline array.
        text = text.split('\n[[keyboard.bindings]]')[0]
        end = text.rfind(']')
        text = text[:end] + r'{ key = "Return", mods = "Shift", chars = "\u001B\r" },' + '\n' + text[end:]
    elif relative == '.config/gtklock/config.ini':
        # Module .so files are optional, the base locker works without them.
        text = re.sub(r'^modules=.*\n', '', text, flags=re.M)
    elif relative.startswith('.config/gtk-') and relative.endswith('settings.ini'):
        text = text.replace('gtk-modules=appmenu-gtk-module\n', '')
    if relative in ('.local/bin/wallpaper-grid', '.local/bin/wallpaper-pick'):
        text = text.replace('@RDOT_HOME@/Pictures/Wallpapers', '$HOME/Pictures/Wallpapers')
    if relative == '.config/waybar/launch.sh':
        text = text.replace('mkdir -p -- "$run_dir"', 'mkdir -p -- "$run_dir" "$(dirname -- "$log")"')
    return text


def capture(home, raccon_only=False, include_docs=True, modules=None, missing=None):
    copied = []

    def copy(module, source, relative):
        if (not include_docs and source.suffix.lower() == '.md') or source.name.startswith('test_'):
            return
        if relative in ('.config/raccon-menu/_desktop-style.scss', '.config/raccon-float/_desktop-style.scss', '.config/raccon-music/_desktop-style.scss'):
            return  # The styles module owns this generated file and seeds it empty.
        if not source.exists():
            if missing is not None:
                missing.append(relative)
                return
            raise RuntimeError(f'No existe: {source}')
        if source.is_symlink():
            raise RuntimeError(f'Revisar enlace antes de capturar: {source}')
        if source.is_dir():
            for child in sorted(source.iterdir()):
                if (child.name.startswith('.') or '.bak' in child.name or
                        child.name in ('__pycache__', 'orbit.conf.template') or
                        child.suffix in ('.log', '.pyc', '.lock')):
                    continue
                copy(module, child, relative + '/' + child.name)
            return
        dest = ROOT / 'modules' / module / 'files' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = source.read_text()
        except UnicodeDecodeError:
            shutil.copy2(source, dest)
        else:
            dest.write_text(sanitize(relative, text, home))
            dest.chmod(source.stat().st_mode & 0o777)
        copied.append({'module': module, 'path': relative})

    if modules is not None:
        selected = set(modules)
    elif raccon_only:
        selected = {'desktop','waybar','wayfire','power','themes','wallpaper','base','desktop-styles'}
    else:
        selected = set(CONFIGS) | set(SCRIPTS) | {'ai', 'desktop-styles'}
    for module, names in CONFIGS.items():
        if module not in selected: continue
        for name in names:
            copy(module, home / '.config' / name, '.config/' + name)
    for module, names in SCRIPTS.items():
        if module not in selected: continue
        for name in names:
            copy(module, home / '.local/bin' / name, '.local/bin/' + name)
    for module, relative in (
            ('waybar', '.config/waybar/launch.sh'),
            ('power', '.local/lib/desktop_power'),
            ('wayfire', '.local/lib/wf_tile'),
            ('desktop', '.local/lib/raccon_menu'),
            ('base', '.local/lib/raccon_events.py'),
            ('desktop', '.local/lib/raccon_music_status.py')):
        if module in selected:
            copy(module, home / relative, relative)
    if 'kitty' in selected:
        copy('kitty', home / '.local/lib/raccon_terminal.py', '.local/lib/raccon_terminal.py')
    if 'zsh' in selected:
        # .zshrc is a hand-kept base in the repo; the owner's copy holds personal settings.
        copy('zsh', home / '.zprofile', '.zprofile')
        theme = '.oh-my-zsh/custom/themes/raccon.zsh-theme'
        copy('zsh', home / theme, theme)
    if 'ai' in selected:
        copied.extend(capture_ai(home, ROOT))
    if 'desktop-styles' in selected:
        copied.extend(capture_styles(home, include_docs=include_docs, missing=missing))
    print(f'{len(copied)} archivos capturados; revisa el diff antes de publicar.')
    return copied


def capture_styles(home, include_docs=True, missing=None):
    """Export the selector's reviewed code/assets, never selections or backups."""
    base = ROOT / 'modules/desktop-styles/files'
    paths = [
        '.local/bin/desktop-style',
        '.local/lib/desktop_style/__init__.py', '.local/lib/desktop_style/main.py',
        '.local/lib/desktop_style/cli.py',
        '.local/lib/desktop_style/appearance.py', '.local/lib/desktop_style/transition.py',
        '.local/lib/desktop_style/selector_input.c',
        '.local/share/applications/desktop-style.desktop',
        '.local/share/fonts/Silkscreen/Silkscreen-Regular.ttf',
        '.local/share/fonts/Silkscreen/OFL.txt',
        '.config/desktop-style/eww.yuck', '.config/desktop-style/eww.scss',
        '.config/desktop-style/_palette.scss', '.config/desktop-style/README.md',
        '.config/desktop-style/source-colors.json',
        '.config/desktop-style/waybar.json',
    ]
    for name in ('modern','glass','terminal','monochrome','retro','ascii'):
        paths += [f'.config/desktop-style/previews/{name}.svg',
                  f'.config/desktop-style/previews/{name}-colors.svg',
                  f'.config/desktop-style/previews/{name}.png']
    copied = []
    for relative in paths:
        if not include_docs and relative.endswith('.md'): continue
        source = home / relative
        if not source.exists() and missing is not None:
            missing.append(relative)
            continue
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f'Revisar recurso de estilos: {source}')
        data = source.read_bytes()
        try:
            text = data.decode()
        except UnicodeDecodeError:
            pass
        else:
            if relative == '.config/desktop-style/eww.yuck':
                pattern = r'(\(deflisten ui :initial )("(?:[^"\\]|\\.)*")'
                match = re.search(pattern, text)
                initial = json.loads(json.loads(match[2]))
                initial.update(selected='modern', current='original', busy=False, notice='')
                text = text[:match.start(2)] + json.dumps(json.dumps(initial,ensure_ascii=False),ensure_ascii=False) + text[match.end(2):]
            elif relative.endswith('desktop-style.desktop'):
                text = re.sub(r'^Exec=.*$', 'Exec="@RDOT_HOME@/.local/bin/desktop-style" open', text, flags=re.M)
            elif relative == '.config/desktop-style/README.md':
                text = text.replace('`widgetctl`, librsvg,', 'librsvg,')
                text = text.replace('`python3 ~/.config/desktop-style/test_styles.py`.',
                                    '`python3 -m unittest discover -s tests -p test_desktop_styles.py` desde Raccon Dots.')
            data = sanitize(relative, text, home).encode()
        destination = base / relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(source.stat().st_mode & 0o777)
        copied.append({'module':'desktop-styles','path':relative})
    if not copied:
        return copied
    # Seed inert overrides. Applying a profile generates these locally.
    for relative in ['.config/desktop-style/current/'+name for name in ('waybar.css','raccon.scss','rofi.rasi','widgets.css','panels.css','selector.scss','swaync.css','swayosd.css')] + ['.config/raccon-menu/_desktop-style.scss']:
        destination=base/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text('/* Original appearance; generated by desktop-style after applying a profile. */\n')
        copied.append({'module':'desktop-styles','path':relative})
    return copied


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-home', type=Path, required=True)
    parser.add_argument('--styles-only', action='store_true', help='Capture only global style code and public assets')
    parser.add_argument('--ai-only', action='store_true', help='Capture AI preferences and skills without credentials or sessions')
    parser.add_argument('--raccon-only', action='store_true')
    parser.add_argument('--no-docs', action='store_true')
    args = parser.parse_args()
    if sum((args.styles_only, args.ai_only, args.raccon_only)) > 1:
        parser.error('Choose only one capture scope')
    if args.ai_only:
        result = capture_ai(args.from_home.resolve(), ROOT)
        print(f'{len(result)} archivos de IA capturados; sin credenciales ni sesiones.')
    elif args.styles_only:
        result=capture_styles(args.from_home.resolve(), include_docs=not args.no_docs)
        print(f'{len(result)} archivos de estilos capturados; sin estado personal.')
    else:
        capture(args.from_home.resolve(), raccon_only=args.raccon_only, include_docs=not args.no_docs)
