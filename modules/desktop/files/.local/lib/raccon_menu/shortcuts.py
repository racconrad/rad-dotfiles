"""Shortcut sections for the menu's viewer, read from the human keys doc; prints one JSON line."""
import json
import os
import re
import subprocess
import sys
import textwrap
import unicodedata
from pathlib import Path

DOC = Path.home() / '.config/wayfire-keys.md'
MENU = ('Raccon Menu', [
    ('Ctrl+1…9', 'Home, Apps, Power, Session, Audio, Wi-Fi, Bluetooth, Calendar, Shortcuts'),
    ('Ctrl+F / Ctrl+L', 'Search apps'),
    ('Alt+1…9', 'Launch a Home app'),
    ('Esc', 'Back, clear search, then close'),
    ('Ctrl+W', 'Close the menu'),
])
CANVAS_OMIT_SECTIONS = {
    'Focus, move, resize (wf-tile)',
    'Advanced tiling',
    'Snapping (grid) — floating windows',
    'Workspaces',
    'Workspaces and overview',
    'Explicit Dwindle layout',
    'Experimental native Snap Tiling',
}
NORMAL_OMIT_SECTIONS = {'Canvas'}
CANVAS_OMIT_KEYS = {
    'Super+M',
    'Super+Shift+D',
    'Super+Shift+O',
    'Super+1..9, Super+0',
    'Super+Shift+1..9, Super+Shift+0',
    'Super+Ctrl+Arrows',
    'Super+Ctrl+Shift+Arrows',
    'Super+Backspace',
    'Super+S',
    'Super+Ctrl+Tab',
    'Super+Ctrl+LeftDrag, Super+MiddleDrag',
    'Super+MiddleDrag',
    '4-finger horizontal swipe',
}


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def parse(text):
    sections, title, rows = [], None, []
    for line in text.splitlines():
        if line.startswith('## '):
            if rows: sections.append((title, rows))
            title, rows = line[3:].strip(), []
        elif title and line.startswith('|') and not re.match(r'^\|[\s:|-]+\|$', line):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            cells = [c[1:-1] if len(c) >= 2 and c[0] == c[-1] == '`' else c for c in cells]
            if cells[0].lower().startswith('shortcut'): continue  # header row
            extra = [c for c in cells[1:] if c and c not in ('—', '-', 'same')]
            rows.append((cells[0], ' · '.join(extra)))
        elif title and (m := re.match(r'^- \*\*(.+?)\*\*:?\s*(.+)$', line)):
            rows.append((m[1], m[2].lstrip(': ').replace('**', '').replace('`', '')))
    if rows: sections.append((title, rows))
    return sections


def canvas_mode():
    base = DOC.parent.parent
    raccon_tool = base / '.local/bin/raccon-canvas-mode'
    wf_tool = base / '.local/bin/wf-canvas-mode'
    tool = raccon_tool if os.access(raccon_tool, os.X_OK) else wf_tool
    if not os.access(tool, os.X_OK):
        return False
    env = dict(os.environ)
    user_ini = base / '.config/wayfire/user.ini'
    if user_ini.is_file() and 'WF_CANVAS_INI' not in env:
        env['WF_CANVAS_INI'] = str(user_ini)
    try:
        return subprocess.run([str(tool), 'status'], env=env, capture_output=True, text=True, timeout=2).stdout.strip() == 'canvas'
    except (OSError, subprocess.SubprocessError):
        return False


def filter_sections(sections, is_canvas):
    if not is_canvas:
        return [(title, rows) for title, rows in sections if title not in NORMAL_OMIT_SECTIONS]
    kept = []
    for title, rows in sections:
        if title in CANVAS_OMIT_SECTIONS or 'workspace' in normalize(title):
            continue
        filtered = []
        for k, a in rows:
            if title != 'Canvas' and k in CANVAS_OMIT_KEYS:
                continue
            combined = normalize(f'{k} {a}')
            if any(term in combined for term in ('tinywidgets', 'widgetctl', 'workspace')):
                continue
            filtered.append((k, a))
        if filtered:
            kept.append((title, filtered))
    return kept


def payload():
    # Eww 0.5 labels ellipsize instead of wrapping; pre-break lines to fit the 292px side panel.
    try: sections = parse(DOC.read_text())
    except OSError: sections = []
    sections = filter_sections(sections, canvas_mode())
    return [dict(title=title, rows=[dict(keys=k, action=textwrap.fill(a, 36), search=normalize(f'{k} {a} {title}')) for k, a in rows])
            for title, rows in [MENU, *sections]]


if __name__ == '__main__':
    if sys.argv[1:] == ['test']:
        demo = parse('## A\n| Shortcut | Action |\n|---|---|\n| Super+Q | Close |\n'
                     '## B\n- **Super+F12**: slide panel\n| Super+T | Center | — |\n')
        assert demo == [('A', [('Super+Q', 'Close')]), ('B', [('Super+F12', 'slide panel'), ('Super+T', 'Center')])], demo
        assert normalize('Sesión') == 'sesion'
        print('ok')
    else: print(json.dumps(payload(), ensure_ascii=False))
