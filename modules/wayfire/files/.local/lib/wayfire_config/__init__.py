"""Compose managed Wayfire defaults with user-owned overrides."""
import configparser
import io
import os
from pathlib import Path
import re
import tempfile


def parse(data):
    config = configparser.ConfigParser(interpolation=None, strict=False, delimiters=('=',))
    config.optionxform = str
    try:
        config.read_string(data.decode('utf-8'))
    except (configparser.Error, UnicodeError) as error:
        raise ValueError(f'Invalid Wayfire configuration: {error}') from error
    if config.defaults():
        raise ValueError('DEFAULT sections are not supported in Wayfire layers')
    return config


def merge(base: bytes, user: bytes = b'') -> bytes:
    parse(base)
    custom = parse(user)
    pending = {section: dict(custom[section]) for section in custom.sections()}
    lines = []
    section = None

    def append_pending():
        for key, value in pending.get(section, {}).items():
            lines.append(f'{key} = {value}\n')
        pending.pop(section, None)

    for line in base.decode().splitlines(keepends=True):
        header = re.match(r'^\s*\[([^\]]+)\]', line)
        if header:
            append_pending()
            section = header[1]
        option = re.match(r'^\s*([^#;\s][^=]*?)\s*=', line)
        if option and custom.has_option(section or '', option[1].strip()):
            key = option[1].strip()
            value = custom[section][key].replace('\n', '\n\t')
            pending.get(section, {}).pop(key, None)
            line = f'{key} = {value}\n'
        lines.append(line if line.endswith('\n') else line + '\n')
    append_pending()
    for name, options in pending.items():
        lines.append(f'\n[{name}]\n')
        lines.extend(f'{key} = {value}\n' for key, value in options.items())
    return ''.join(lines).encode()


def overrides(base: bytes, current: bytes) -> bytes:
    managed, existing = parse(base), parse(current)
    result = configparser.ConfigParser(interpolation=None)
    result.optionxform = str
    for section in existing.sections():
        values = {key: value for key, value in existing[section].items()
                  if not managed.has_option(section, key) or managed[section][key] != value}
        if values:
            result[section] = values
    output = io.StringIO()
    result.write(output)
    return output.getvalue().encode()


def config_home() -> Path:
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))


def sync(root: Path) -> bool:
    layers = root / 'wayfire'
    user = layers / 'user.ini'
    data = merge((layers / 'raccon.ini').read_bytes(), user.read_bytes() if user.exists() else b'')
    target = root / 'wayfire.ini'
    if target.exists() and target.read_bytes() == data and target.stat().st_mode & 0o777 == 0o600:
        return False
    atomic_write(target, data)
    return True


def atomic_write(target: Path, data: bytes):
    fd, temporary = tempfile.mkstemp(prefix='.wayfire-', suffix='.ini', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def set_options(root: Path, section: str, values: dict) -> None:
    layers = root / 'wayfire'
    layers.mkdir(parents=True, exist_ok=True)
    target = layers / 'user.ini'
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config[section] = {key: str(value) for key, value in values.items()}
    output = io.StringIO()
    config.write(output)
    user = target.read_bytes() if target.exists() else b''
    data = merge(user, output.getvalue().encode())
    if user != data:
        atomic_write(target, data)
    sync(root)
