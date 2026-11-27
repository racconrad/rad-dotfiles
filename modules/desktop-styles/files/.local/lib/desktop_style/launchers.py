import configparser
import json
import os
from pathlib import Path
import re
from desktop_style.context import Context

HYPR_STYLE = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'hypr/desktop-style.lua'


def bar_profile(style, ctx=None):
    c = Context(ctx)
    return dict(c.PROFILES[style], position='bottom', continuous=False)


def managed_settings(ctx=None):
    c = Context(ctx)
    result = {}
    fuzzel = c.HOME / '.config/fuzzel/fuzzel.ini'
    if fuzzel.exists():
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(fuzzel)
        result['fuzzel'] = {sec: {key: parser.get(sec, key, fallback=None) for key in keys} for sec, keys in {'main': ['font'], 'border': ['radius', 'width']}.items()}
    return result


def set_managed(settings, ctx=None):
    c = Context(ctx)
    if settings.get('fuzzel'):
        path = c.HOME / '.config/fuzzel/fuzzel.ini'
        text = path.read_text()
        for section, values in settings['fuzzel'].items():
            def patch_section(match):
                block = match[0]
                for key, value in values.items():
                    pattern = r'(?m)^' + re.escape(key) + r'\s*=.*$'
                    if value is None:
                        block = re.sub(pattern + '\n?', '', block)
                    elif re.search(pattern, block):
                        block = re.sub(pattern, lambda m: key + '=' + value, block)
                    else:
                        block = block.rstrip() + '\n' + key + '=' + value + '\n\n'
                return block
            text = re.sub(r'(?ms)^\[' + re.escape(section) + r'\]\n.*?(?=^\[|\Z)', patch_section, text)
        c.write(path, text)


def configure_launchers(style, ctx=None):
    c = Context(ctx)
    settings = c.managed_settings()
    p = c.PROFILES[style]
    if settings.get('fuzzel'):
        fuzzel_font = 'Inter' if p['font'] in ('Inter Display', 'Fira Sans Compressed') else p['font']
        settings['fuzzel']['main']['font'] = fuzzel_font + ':size=12'
        settings['fuzzel']['border'].update(radius=str(p['radius']), width=str(p['border']))
    c.set_managed(settings)
