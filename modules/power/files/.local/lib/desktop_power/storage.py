import json
import os
from pathlib import Path
import tempfile
import tomllib

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'desktop-power'
STATE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'desktop-power'


def read_json(path, default=None):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else (default or {})
    except (OSError, ValueError):
        return default or {}


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def load_config():
    with (CONFIG / 'config.toml').open('rb') as stream:
        config = tomllib.load(stream)
    auto = config['automation']
    if not 0 < auto['critical'] < auto['warning'] < auto['high'] <= 100:
        raise ValueError('Se requiere 0 < critical < warning < high <= 100')
    if not 0 < auto['low_battery'] <= 100 or not 0 <= auto['recovery_margin'] <= 10:
        raise ValueError('Umbrales de cambio automático no válidos')
    if auto['poll_seconds'] < 1 or auto.get('stable_ac_poll_seconds',15) < 1 or auto['notification_reset'] < 1:
        raise ValueError('Los intervalos y el margen de notificación deben ser positivos')
    for name in ('performance', 'balanced', 'complete', 'working'):
        profile = config['profiles'][name]
        if not 0 <= profile['animation_factor'] <= 1:
            raise ValueError('animation_factor debe estar entre 0 y 1')
        if any(plugin not in {'animate', 'extra-animations', 'blur', 'wobbly', 'winshadows', 'focus-change'}
               for plugin in profile['disable_plugins']):
            raise ValueError('Solo se permite desactivar los efectos opcionales documentados')
    for value in config['appearance'].values():
        if value not in {'primary', 'secondary', 'tertiary', 'error', 'on_surface', 'on_surface_variant'}:
            raise ValueError('Usa roles semánticos documentados en appearance')
    return config
