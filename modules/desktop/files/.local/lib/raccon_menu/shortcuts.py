"""Shortcut sections for the menu's viewer, read from the human keys doc; prints one JSON line."""
import json
import re
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


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def parse(text):
    sections, title, rows = [], None, []
    for line in text.splitlines():
        if line.startswith('## '):
            if rows: sections.append((title, rows))
            title, rows = line[3:].strip(), []
        elif title and line.startswith('|') and not re.match(r'^\|[\s:|-]+\|$', line):
            cells = [c.strip().strip('`') for c in line.strip().strip('|').split('|')]
            if cells[0].lower().startswith('shortcut'): continue  # header row
            extra = [c for c in cells[1:] if c and c not in ('—', '-', 'same')]
            rows.append((cells[0], ' · '.join(extra)))
        elif title and (m := re.match(r'^- \*\*(.+?)\*\*:?\s*(.+)$', line)):
            rows.append((m[1], m[2].lstrip(': ').replace('**', '').replace('`', '')))
    if rows: sections.append((title, rows))
    return sections


def payload():
    # Eww 0.5 labels ellipsize instead of wrapping; pre-break lines to fit the 292px side panel.
    try: sections = parse(DOC.read_text())
    except OSError: sections = []
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
