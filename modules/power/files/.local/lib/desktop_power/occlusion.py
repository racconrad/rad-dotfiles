"""Suspend complete-mode desktop surfaces only with verified full coverage."""
from pathlib import Path
from . import effects


def covers(area, rectangles):
    x, y, width, height = (area[k] for k in ('x', 'y', 'width', 'height'))
    if width <= 0 or height <= 0:
        return False
    right, bottom = x + width, y + height
    xs = sorted({x, right} | {max(x, min(right, r[k])) for r in rectangles for k in (0, 2)})
    for left, end in zip(xs, xs[1:]):
        intervals = sorted((max(y, r[1]), min(bottom, r[3])) for r in rectangles if r[0] <= left and r[2] >= end)
        reached = y
        for top, stop in intervals:
            if top > reached:
                break
            reached = max(reached, stop)
        if reached < bottom:
            return False
    return True


def covered(outputs, views):
    if not isinstance(outputs, list) or not outputs or not isinstance(views, list):
        return False
    try:
        for out in outputs:
            rectangles = []
            for view in views:
                if (view.get('role') != 'toplevel' or not view.get('mapped') or view.get('minimized')
                        or view.get('output-id') != out['id'] or view.get('wset-index') != out['wset-index']
                        or not (view.get('fullscreen') or view.get('tiled-edges'))):
                    continue
                g = view['geometry']
                rectangles.append((g['x'], g['y'], g['x'] + g['width'], g['y'] + g['height']))
            if not covers(out['workarea'], rectangles):
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def suspended():
    try:
        return covered(effects.ipc('window-rules/list-outputs'), effects.ipc('window-rules/list-views'))
    except (OSError, RuntimeError, ValueError):
        return False
