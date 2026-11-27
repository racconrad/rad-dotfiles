from __future__ import annotations

import json
from pathlib import Path
import re

TEMPLATE_OWNERS = {
    'swaync': 'swaync', 'wlogout': 'desktop', 'swayosd': 'desktop',
    'kitty': 'kitty', 'fuzzel': 'fuzzel', 'swaylock': 'swaylock',
    'gtk3': 'themes', 'gtk4': 'themes', 'hyprland': 'hyprland', 'quickshell': 'quickshell',
    'starship': 'shell', 'cava': 'tools', 'fastfetch': 'tools', 'rofi': 'wallpaper',
    'qt5ct': 'themes', 'qt6ct': 'themes', 'yazi': 'tools', 'nvim': 'nvim',
    'gtklock': 'gtklock', 'legcord': 'chat-theme',
    'desktop_style_source': 'desktop-styles',
}
ZSH_PERSONAL = '# >>> personal (kept on reinstall, never captured)'


def render(relative, content, home, modules, choices, ctx=None):
    try:
        text = content.decode()
    except UnicodeDecodeError:
        return content
    terminal = choices['terminal']
    text = text.replace('@RDOT_HOME@', str(home)).replace('@RDOT_TERMINAL@', terminal)
    if relative == '.zshrc':
        try:
            current = (home / '.zshrc').read_text()
        except (OSError, UnicodeDecodeError):
            current = ''
        if ZSH_PERSONAL in current and ZSH_PERSONAL in text:
            text = text.split(ZSH_PERSONAL)[0] + ZSH_PERSONAL + current.split(ZSH_PERSONAL, 1)[1]
    if relative == '.config/matugen/config.toml':
        blocks = re.split(r'(?=^\[templates\.)', text, flags=re.M)
        kept = [blocks[0]]
        for block in blocks[1:]:
            name = re.match(r'\[templates\.([^\]]+)\]', block)[1]
            owner = TEMPLATE_OWNERS.get(name)
            if owner == 'shell':
                enabled = bool({'zsh', 'fish'}.intersection(modules))
            elif name == 'rofi':
                enabled = bool({'wallpaper', 'rofi', 'desktop'}.intersection(modules))
            else:
                enabled = owner in modules
            if enabled:
                kept.append(block)
        text = ''.join(kept)
    if relative == '.config/hypr/conf/programs.lua':
        text = text.replace('terminal = "kitty"', 'terminal = "' + terminal + '"')
    if relative == '.config/fuzzel/fuzzel.ini':
        text = re.sub(r'^terminal=.*$', 'terminal=' + terminal, text, flags=re.M)
    style_import = None
    if relative.startswith('.config/rofi/') and relative.endswith('.rasi') and not relative.endswith('/colors.rasi'):
        style_import = f'@import "{home}/.config/desktop-style/current/rofi.rasi"'
    elif relative in ('.config/swaync/style.css', '.config/swayosd/style.css',
                      '.config/wlogout/style.css', '.config/gtklock/style.css'):
        name = relative.split('/')[1]
        style_import = f'@import "{home}/.config/desktop-style/current/{name}.css";'
    if style_import is not None:
        text = '\n'.join(line for line in text.splitlines()
                         if not ('@import' in line and 'desktop-style/current/' in line)) + '\n'
        if 'desktop-styles' in modules:
            text += '\n' + style_import + '\n'
    if relative == '.local/bin/wallpaper-theme' and 'desktop-styles' not in modules:
        text = re.sub(r'\nif \[\[ -x "\$HOME/\.local/bin/desktop-style" \]\]; then\n.*?\nfi\n', '\n', text, flags=re.S)
    shell_enabled = choices['shell'] in modules
    if relative == '.config/kitty/kitty.conf' and shell_enabled:
        text += '\nshell ' + choices['shell'] + '\n'
    elif relative == '.config/alacritty/alacritty.toml' and shell_enabled:
        text += '\n[terminal.shell]\nprogram = "' + choices['shell'] + '"\n'
    elif relative == '.config/Code/User/settings.json' and shell_enabled:
        settings = json.loads(text)
        shell = choices['shell']
        settings['terminal.integrated.defaultProfile.linux'] = shell
        settings['terminal.integrated.profiles.linux'] = {shell: {'path': '/usr/bin/' + shell}}
        text = json.dumps(settings, ensure_ascii=False, indent=2) + '\n'
    if '@RDOT_' in text:
        raise ValueError(f'Unresolved variable: {relative}')
    return text.encode()
