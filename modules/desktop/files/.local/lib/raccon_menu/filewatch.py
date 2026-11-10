"""Bounded Linux file-event waits, including atomic replacements."""
import ctypes
import os
from pathlib import Path
import select
import struct
import time


class FileWatch:
    def __init__(self, paths=(), directories=()):
        self.paths = {Path(p) for p in paths}
        self.directories = {Path(p) for p in directories}
        self.watches = {}
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.fd = self.lib.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)

    def __enter__(self):
        self._subscribe()
        return self

    def __exit__(self, *_):
        self.close()

    def _subscribe(self):
        parents = {p.parent for p in self.paths} | self.directories
        for parent in parents - set(self.watches.values()):
            if self.fd >= 0:
                # Parent watches survive writers replacing the target inode.
                wd = self.lib.inotify_add_watch(self.fd, os.fsencode(parent), 0x00000FCC)
                if wd >= 0:
                    self.watches[wd] = parent
        return parents <= set(self.watches.values())

    def wait(self, timeout):
        complete = self._subscribe()
        if self.fd < 0 or not self.watches:
            time.sleep(min(timeout, .2))
            return
        deadline = time.monotonic() + (timeout if complete else min(timeout, .2))
        while True:
            ready, _, _ = select.select([self.fd], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                return
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                continue
            offset = 0
            changed = False
            while offset < len(data):
                wd, mask, _, size = struct.unpack_from('iIII', data, offset)
                name = os.fsdecode(data[offset+16:offset+16+size].split(b'\0', 1)[0])
                parent = self.watches.get(wd)
                if mask & 0x8000:
                    self.watches.pop(wd, None)
                if mask & 0x4000 or parent in self.directories or parent is not None and parent / name in self.paths:
                    changed = True
                offset += 16 + size
            if changed:
                return

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
