#!/usr/bin/env python3
"""Stream live Cava spectrum bars as JSON lines while the music card is visible and playing."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import raccon_cava

BARS = 12
MAX_RANGE = 24
BASE_PX = 4
IDLE = {'active': False, 'level': 0, **{f'b{i}': BASE_PX for i in range(BARS)}}


def frame_payload(values):
    payload = {
        'active': True,
        'level': raccon_cava.energy_level(values, max_range=MAX_RANGE),
    }
    for index in range(BARS):
        payload[f'b{index}'] = BASE_PX + values[index]
    return payload


def emit(value):
    print(json.dumps(value), flush=True)


def stop_proc(proc):
    if proc is None:
        return None
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    if proc.stdout is not None:
        proc.stdout.close()
    return None


def main():
    from raccon_events import FileEvents

    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))
    flag = runtime / 'raccon-music.open'
    conf = runtime / 'raccon-music-cava.conf'

    def stop(_signal, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    status_proc = None
    cava_proc = None
    playing = False
    status_buf = b''
    cava_buf = b''
    last = None

    def send(value):
        nonlocal last
        if value != last:
            emit(value)
            last = value

    with FileEvents([flag]) as changes:
        send(IDLE)
        try:
            while True:
                if not flag.exists():
                    cava_proc = stop_proc(cava_proc)
                    status_proc = stop_proc(status_proc)
                    playing = False
                    status_buf = cava_buf = b''
                    send(IDLE)
                    changes.wait()
                    continue

                if status_proc is None:
                    try:
                        status_proc = subprocess.Popen(
                            ['playerctl', '--follow', 'status'],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                        )
                        os.set_blocking(status_proc.stdout.fileno(), False)
                        status_buf = b''
                    except FileNotFoundError:
                        changes.wait(60)
                        continue

                if playing and cava_proc is None:
                    try:
                        cava_proc = raccon_cava.spawn(
                            conf, bars=BARS, framerate=24, max_range=MAX_RANGE, nonblocking=True
                        )
                        cava_buf = b''
                    except OSError:
                        cava_proc = stop_proc(cava_proc)
                elif not playing and cava_proc is not None:
                    cava_proc = stop_proc(cava_proc)
                    cava_buf = b''
                    send(IDLE)

                fds = [changes, status_proc.stdout]
                if cava_proc is not None and cava_proc.stdout is not None:
                    fds.append(cava_proc.stdout)

                ready, _, _ = select.select(fds, [], [])
                if changes in ready:
                    changes.drain()
                    if not flag.exists():
                        continue

                if status_proc.stdout in ready:
                    chunk = os.read(status_proc.stdout.fileno(), 65536)
                    if not chunk:
                        status_proc = stop_proc(status_proc)
                        cava_proc = stop_proc(cava_proc)
                        playing = False
                        send(IDLE)
                        changes.wait(2)
                        continue
                    status_buf += chunk
                    while b'\n' in status_buf:
                        line, status_buf = status_buf.split(b'\n', 1)
                        playing = line.decode(errors='replace').strip() == 'Playing'
                    if not playing:
                        cava_proc = stop_proc(cava_proc)
                        cava_buf = b''
                        send(IDLE)

                if cava_proc is not None and cava_proc.stdout in ready:
                    chunk = os.read(cava_proc.stdout.fileno(), 65536)
                    if not chunk:
                        cava_proc = stop_proc(cava_proc)
                        send(IDLE)
                        continue
                    cava_buf += chunk
                    if b'\n' in cava_buf:
                        lines = cava_buf.split(b'\n')
                        cava_buf = lines[-1]
                        for raw in reversed(lines[:-1]):
                            vals = raccon_cava.parse_line(raw.decode(errors='replace'), bars=BARS, max_range=MAX_RANGE)
                            if vals is not None:
                                send(frame_payload(vals))
                                break
        finally:
            cava_proc = stop_proc(cava_proc)
            status_proc = stop_proc(status_proc)


if __name__ == '__main__':
    main()
