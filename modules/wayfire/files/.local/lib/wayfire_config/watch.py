"""Event-driven layer updates, including atomic editor saves."""
import ctypes
import os
from pathlib import Path
import select
import struct
import sys

from wayfire_config import sync


def watch(root: Path):
    library = ctypes.CDLL(None, use_errno=True)
    library.inotify_init1.argtypes = [ctypes.c_int]
    library.inotify_init1.restype = ctypes.c_int
    library.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    library.inotify_add_watch.restype = ctypes.c_int
    fd = library.inotify_init1(os.O_CLOEXEC | os.O_NONBLOCK)
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'Cannot initialize configuration watcher')
    layers = root / 'wayfire'
    layers.mkdir(parents=True, exist_ok=True)
    mask = 0x00000008 | 0x00000080 | 0x00000100 | 0x00000200 | 0x00000400 | 0x00000800

    def add(path):
        watch_id = library.inotify_add_watch(fd, os.fsencode(path), mask)
        if watch_id < 0:
            raise OSError(ctypes.get_errno(), f'Cannot watch {path}')
        return watch_id

    def refresh():
        try:
            sync(root)
        except (OSError, ValueError) as error:
            print(error, file=sys.stderr, flush=True)

    try:
        parent = add(root)
        child = add(layers)
        refresh()
        while True:
            select.select([fd], [], [])
            events = os.read(fd, 65536)
            offset = 0
            changed = False
            while offset + 16 <= len(events):
                wd, flags, _, length = struct.unpack_from('iIII', events, offset)
                name = events[offset + 16:offset + 16 + length].split(b'\0', 1)[0]
                offset += 16 + length
                if wd == parent and name == b'wayfire' and layers.is_dir():
                    child = add(layers)
                    changed = True
                if wd == child and name in (b'raccon.ini', b'user.ini'):
                    changed = True
                if flags & 0x00004000:  # Overflow requires rereading the source files.
                    changed = True
            if changed:
                refresh()
    finally:
        os.close(fd)
