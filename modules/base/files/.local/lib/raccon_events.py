"""Linux file notifications, including atomic replacements, without idle polling."""
import ctypes
import os
from pathlib import Path
import select
import struct
import time


class FileEvents:
    # Watch parent directories: watching an inode loses atomic JSON replacements.
    MASK = 0x00000008 | 0x00000080 | 0x00000100 | 0x00000200 | 0x00000040 | 0x00000004

    def __init__(self, paths):
        self.fd = -1
        self.reader = self.writer = -1
        self.targets = {}
        libc = ctypes.CDLL(None, use_errno=True)
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), 'inotify_init1')
        try:
            parents = {}
            for item in paths:
                path = Path(item).absolute()
                path.parent.mkdir(parents=True, exist_ok=True)
                parents.setdefault(path.parent, set()).add(path.name)
            for parent, names in parents.items():
                wd = libc.inotify_add_watch(self.fd, os.fsencode(parent), self.MASK)
                if wd < 0:
                    raise OSError(ctypes.get_errno(), 'inotify_add_watch', str(parent))
                self.targets[wd] = (parent, names)
            self.reader, self.writer = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        except BaseException:
            self.close()
            raise

    def fileno(self):
        return self.fd

    def wake(self, _future=None):
        """Decoder completion can interrupt the same blocking wait as file changes."""
        try:
            os.write(self.writer, b'1')
        except (BlockingIOError, OSError):
            pass

    def drain(self):
        changed = set()
        while True:
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                return changed
            offset = 0
            while offset < len(data):
                wd, mask, _, length = struct.unpack_from('iIII', data, offset)
                name = os.fsdecode(data[offset + 16:offset + 16 + length].split(b'\0', 1)[0])
                offset += 16 + length
                if mask & 0x00004000:  # IN_Q_OVERFLOW: reconcile every watched file.
                    changed.update(parent / name for parent, names in self.targets.values() for name in names)
                elif wd in self.targets:
                    parent, names = self.targets[wd]
                    if name in names:
                        changed.add(parent / name)

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + max(0, timeout)
        while True:
            remaining = None if deadline is None else max(0, deadline - time.monotonic())
            ready, _, _ = select.select([self.fd, self.reader], [], [], remaining)
            changed = self.drain() if self.fd in ready else set()
            if self.reader in ready:
                while True:
                    try:
                        os.read(self.reader, 65536)
                    except BlockingIOError:
                        break
                return changed
            if changed or not ready:
                return changed
            # Ignore unrelated files in a shared runtime/cache directory.

    def close(self):
        for name in ('fd', 'reader', 'writer'):
            fd = getattr(self, name)
            if fd >= 0:
                os.close(fd)
                setattr(self, name, -1)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
