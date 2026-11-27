import fcntl
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from desktop_style.context import Context


def _sddm_background_mode(home):
    current = home / '.cache/current-wallpaper'
    image = Path(current.read_text().strip()) if current.is_file() else Path('/nonexistent')
    if image.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
        image = home / '.cache/wallpaper-frame.png'
    return 'wallpaper' if image.is_file() else 'solid'


def prepare_sddm_cache(ctx=None):
    c = Context(ctx)
    assets = c.HOME / '.local/share/raccon/sddm'
    prep = assets / 'prepare.py'
    if not prep.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(prep), '--home', str(c.HOME), '--output',
             str(c.HOME / '.local/share/sddm/themes/raccon'), '--background', _sddm_background_mode(c.HOME)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def apply_sddm(ctx=None):
    """Publish the active appearance only after interactive system authentication."""
    c = Context(ctx)
    c.STATE.mkdir(parents=True, exist_ok=True)
    with (c.STATE / 'apply.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        assets = c.HOME / '.local/share/raccon/sddm'
        tokens = c.read(c.CURRENT / 'tokens.json')
        if tokens.get('style') not in c.PROFILES:
            return
        if not all((assets / name).is_file() for name in ('prepare.py', 'apply.sh', 'raccon/Main.qml')):
            return
        shutil_which = getattr(c.shutil, 'which', shutil.which) if hasattr(c, 'shutil') else shutil.which
        if not shutil_which('pkexec'):
            return
        try:
            with tempfile.TemporaryDirectory(prefix='raccon-sddm-') as temp:
                theme = Path(temp) / 'theme'
                subprocess_run = getattr(c.subprocess, 'run', subprocess.run) if hasattr(c, 'subprocess') else subprocess.run
                subprocess_run([sys.executable, str(assets / 'prepare.py'), '--home', str(c.HOME),
                                '--output', str(theme), '--background', _sddm_background_mode(c.HOME)],
                               capture_output=True, text=True, timeout=30, check=True)
                result = subprocess_run(['pkexec', '/usr/bin/bash', str(assets / 'apply.sh'), str(theme)],
                                        capture_output=True, text=True, timeout=300)
                c.write(c.STATE / 'sddm.log', result.stdout + result.stderr)
        except (subprocess.TimeoutExpired, OSError, subprocess.CalledProcessError) as exc:
            c.write(c.STATE / 'sddm.log', str(exc) + '\n' + (getattr(exc, 'stderr', '') or ''))
