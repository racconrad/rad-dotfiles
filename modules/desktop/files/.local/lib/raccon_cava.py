"""Shared Cava raw ASCII spectrum helper for Waybar and raccon-music."""
import os
from pathlib import Path
import subprocess

GLYPHS = '▁▂▃▄▅▆▇█'


def config_text(bars=8, framerate=22, max_range=7):
    return (
        f'[general]\n'
        f'framerate = {framerate}\n'
        f'bars = {bars}\n'
        f'autosens = 1\n'
        f'sleep_timer = 2\n'
        f'\n[input]\n'
        f'method = pulse\n'
        f'source = auto\n'
        f'\n[output]\n'
        f'method = raw\n'
        f'raw_target = /dev/stdout\n'
        f'data_format = ascii\n'
        f'ascii_max_range = {max_range}\n'
        f'bar_delimiter = 59\n'
    )


def parse_line(line, bars=8, max_range=7):
    """Parse one semicolon-delimited Cava ASCII line into clamped bar ints."""
    raw = [part for part in line.strip().split(';') if part]
    if not raw:
        return None
    values = []
    for part in raw[:bars]:
        try:
            values.append(max(0, min(max_range, int(part))))
        except ValueError:
            return None
    while len(values) < bars:
        values.append(0)
    return values


def energy_level(values, max_range=7):
    """Quantize overall spectrum energy into 0..3 for CSS reactivity."""
    if not values or max_range <= 0:
        return 0
    avg = sum(values) / len(values)
    peak = max(values)
    score = (avg * 0.65 + peak * 0.35) / max_range
    if score >= 0.62:
        return 3
    if score >= 0.36:
        return 2
    if score >= 0.12:
        return 1
    return 0


def bars_text(values):
    """Render clamped 0..7 bar values as crisp Unicode block glyphs."""
    return ''.join(GLYPHS[max(0, min(len(GLYPHS) - 1, v))] for v in values)


def spawn(conf_path, bars=8, framerate=22, max_range=7, nonblocking=False):
    """Write config and launch cava streaming raw ASCII bars to stdout."""
    path = Path(conf_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config_text(bars=bars, framerate=framerate, max_range=max_range))
    proc = subprocess.Popen(
        ['cava', '-p', str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if nonblocking and proc.stdout is not None:
        os.set_blocking(proc.stdout.fileno(), False)
    return proc


def stop(proc):
    """Terminate a running cava subprocess and close its stdout pipe."""
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
