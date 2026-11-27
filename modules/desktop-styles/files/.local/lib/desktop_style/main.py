import colorsys
import configparser
import fcntl
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from xml.sax.saxutils import escape

_lib_dir = Path(__file__).resolve().parent.parent
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))
import desktop_style
_pkg_dir = str(Path(__file__).resolve().parent)
if _pkg_dir not in desktop_style.__path__:
    desktop_style.__path__.insert(0, _pkg_dir)

HOME = Path.home()
CONFIG = HOME / '.config/desktop-style'
STATE = HOME / '.local/state/desktop-style'
CURRENT = CONFIG / 'current'
BIN = HOME / '.local/bin'

from desktop_style.helpers import (
    PROFILES, STYLE_ALIASES, WIDGET_FRAME_ICONS, WIDGET_FRAMES,
    read, write, save, normalize_style, validate_css,
)
from desktop_style.launchers import HYPR_STYLE
from desktop_style.colors import rgb, hexcolor, luminance, contrast_ratio, contrasting_tone
from desktop_style.pipeline import render, snapshot
from desktop_style.apply import companion_wallpaper
from desktop_style.sddm import _sddm_background_mode

from desktop_style import helpers as _helpers
from desktop_style import colors as _colors
from desktop_style import launchers as _launchers
from desktop_style import pipeline as _pipeline
from desktop_style import frames as _frames
from desktop_style import apply as _apply
from desktop_style import sddm as _sddm


def _wrap(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if 'ctx' not in kwargs:
            kwargs['ctx'] = globals()
        return fn(*args, **kwargs)
    return wrapper


migrate_theme_state = _wrap(_helpers.migrate_theme_state)
run = _wrap(_helpers.run)
widgets_available = _wrap(_helpers.widgets_available)
update = _wrap(_helpers.update)
extra_action = _wrap(_helpers.extra_action)

palette = _wrap(_colors.palette)
source_palette = _wrap(_colors.source_palette)

bar_profile = _wrap(_launchers.bar_profile)
managed_settings = _wrap(_launchers.managed_settings)
set_managed = _wrap(_launchers.set_managed)
configure_launchers = _wrap(_launchers.configure_launchers)

templates = _wrap(_pipeline.templates)
surfaces = _wrap(_pipeline.surfaces)
restore = _wrap(_pipeline.restore)
ensure_import = _wrap(_pipeline.ensure_import)
integrations = _wrap(_pipeline.integrations)
refresh_clients = _wrap(_pipeline.refresh_clients)
hypr_style = _wrap(_pipeline.hypr_style)

widget_frame = _wrap(_frames.widget_frame)
with_widget_frame = _wrap(_frames.with_widget_frame)
set_widget_frame = _wrap(_frames.set_widget_frame)

reset = _wrap(_apply.reset)
apply = _wrap(_apply.apply)

prepare_sddm_cache = _wrap(_sddm.prepare_sddm_cache)
apply_sddm = _wrap(_sddm.apply_sddm)


def main():
    args = sys.argv[1:] or ['apply', 'collage']
    command = args[0]
    migrate_theme_state()
    try:
        if command == 'apply':
            target = args[1] if len(args) > 1 else 'collage'
            apply(target)
        elif command == 'wallpaper':
            source_palette(refresh=True)
            original = read(STATE / 'original.json')
            if original:
                for entry in templates().values():
                    path = Path(entry['output_path']).expanduser()
                    if path.name == 'desktop-style-source.json':
                        continue
                    if path.exists():
                        original[str(path)] = path.read_text()
                save(STATE / 'original.json', original)
            apply('collage', wallpaper=True)
            write(CONFIG / '_palette.scss', ''.join(f'${k}: {v};\n' for k, v in source_palette().items()))
            prepare_sddm_cache()
        elif command == 'frame':
            set_widget_frame(args[1], args[2] if len(args) > 2 else None)
        elif command == 'extra':
            extra_action(args[1])
        elif command == 'background':
            companion_wallpaper(normalize_style(args[1]))
        elif command == 'sddm':
            apply_sddm()
        elif command == 'reset':
            reset()
        elif command == 'status':
            print(json.dumps(read(STATE / 'selection.json', {'style': 'collage', 'name': 'Collage'}), ensure_ascii=False))
        elif command == 'list':
            print(json.dumps(PROFILES, ensure_ascii=False, indent=2))
        else:
            raise ValueError('Usage: desktop-style apply [collage]|wallpaper|sddm|reset|status|list')
    except Exception as exc:
        message = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(message, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
