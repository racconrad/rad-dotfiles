"""Wait for a floating GTK tree to finish its hidden first-frame warmup."""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from raccon_events import FileEvents


def wait_ready(name, timeout=3):
    path = Path(os.environ.get('XDG_RUNTIME_DIR', Path.home() / '.cache')) / name
    deadline = time.monotonic() + timeout
    with FileEvents([path]) as changes:
        while True:
            try:
                if path.read_text().strip() == '1':
                    return
            except OSError:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Floating card did not finish its hidden warmup.')
            changes.wait(remaining)


if __name__ == '__main__':
    wait_ready(sys.argv[1])
