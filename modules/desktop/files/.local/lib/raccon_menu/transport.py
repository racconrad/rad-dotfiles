"""Nonblocking messages to the menu's own GTK process; no Eww client startup."""
import os
import stat
import time

PAGES = {'home': '0', 'apps': '1', 'modes': '2', 'session': '3', 'audio': '4', 'connections': '5', 'bluetooth': '6', 'calendar': '7', 'shortcuts': '8'}


def source_revision(source):
    directory = os.path.dirname(source)
    dependencies = [os.path.join(directory, name) for name in ('navigation.h', 'resident_surface.h', 'backend.py')]
    return str(max([os.stat(source).st_mtime_ns] + [os.stat(p).st_mtime_ns for p in dependencies if os.path.exists(p)]))


def send(command, runtime=None, source=None):
    root = runtime or os.path.join(os.environ.get('XDG_RUNTIME_DIR', os.path.expanduser('~/.cache')), 'raccon-menu')
    source = source or os.path.join(os.path.dirname(__file__), 'input.c')
    try:
        with open(os.path.join(root, 'revision')) as stream:
            if stream.read().strip() != source_revision(source):
                return False
        if not os.path.exists(os.path.join(root, 'mapped')):
            return False
        if command == 'toggle':
            try:
                with open(os.path.join(root, 'closed')) as stream:
                    elapsed = time.monotonic() - float(stream.read())
                if 0 <= elapsed < .35:
                    return True
            except (OSError, ValueError):
                pass
        fd = os.open(os.path.join(root, 'control'), os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if not stat.S_ISFIFO(info.st_mode) or info.st_uid != os.getuid():
                return False
            os.write(fd, (command + '\n').encode())
            return True
        finally:
            os.close(fd)
    except OSError:
        return False


def request(args):
    if not args or args == ['toggle']:
        return 'toggle'
    if len(args) == 1 and args[0] in PAGES:
        return 'show ' + PAGES[args[0]]
    if len(args) == 2 and args[0] == 'tab' and args[1] in PAGES:
        return 'tab ' + PAGES[args[1]]
    if args == ['close']:
        return 'hide'
    if args == ['close', 'super']:
        return 'hide-super'
    return None
