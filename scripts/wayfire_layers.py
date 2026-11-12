"""Plan managed Wayfire defaults while preserving user-owned overrides."""
import sys


def layer_plan(home, plan, root):
    effective = '.config/wayfire.ini'
    if effective not in plan:
        return
    library = str(root / 'modules/wayfire/files/.local/lib')
    if library not in sys.path:
        sys.path.insert(0, library)
    from wayfire_config import merge, overrides

    base, mode = plan[effective]
    user_path = '.config/wayfire/user.ini'
    user = home / user_path
    if user.exists():
        content = user.read_bytes()
    else:
        current = home / effective
        previous_base = home / '.config/wayfire/raccon.ini'
        baseline = previous_base.read_bytes() if previous_base.exists() else base
        content = overrides(baseline, current.read_bytes()) if current.exists() else b''
        plan[user_path] = (content, 0o600)
    plan['.config/wayfire/raccon.ini'] = (base, mode)
    plan[effective] = (merge(base, content), 0o600)


def generated_is_current(home):
    base = home / '.config/wayfire/raccon.ini'
    user = home / '.config/wayfire/user.ini'
    effective = home / '.config/wayfire.ini'
    if not base.exists() or not effective.exists():
        return False
    from wayfire_config import merge
    try:
        return effective.read_bytes() == merge(base.read_bytes(), user.read_bytes() if user.exists() else b'')
    except (OSError, ValueError):
        return False
