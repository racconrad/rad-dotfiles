"""Early Macintosh grayscale preview generator with simple hairline frames."""
from html import escape


def preview_svg(c, profile):
    position = profile['position']
    vertical = position in ('left', 'right')
    left, right = (46 if position == side else 0 for side in ('left', 'right'))
    top = 38 if position == 'top' else 0
    edge = c['outline']
    hi = c['surface_container_lowest']
    sh = c['outline_variant']
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280" viewBox="0 0 440 280">',
        '<defs>',
        '<pattern id="macdots" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="4" fill="#9e9e9e"/>'
        '<rect x="0" y="0" width="1" height="1" fill="#bdbdbd"/>'
        '<rect x="2" y="2" width="1" height="1" fill="#bdbdbd"/>'
        '</pattern>',
        f'<linearGradient id="macbar" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{hi}"/><stop offset="60%" stop-color="{c["surface_container"]}"/><stop offset="100%" stop-color="{c["surface_container_highest"]}"/></linearGradient>',
        '</defs>',
        '<rect width="440" height="280" fill="url(#macdots)"/>',
    ]

    def mac_window(x, y, w, h, title):
        parts.append(f'<rect x="{x+2}" y="{y+2}" width="{w}" height="{h}" rx="3" fill="#000000" fill-opacity=".22"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{c["surface_container"]}" stroke="{edge}" stroke-width="1.5"/>')
        parts.append(f'<rect x="{x+1}" y="{y+1}" width="{w-2}" height="20" rx="2" fill="url(#macbar)"/>')
        parts.append(f'<line x1="{x+1}" y1="{y+21}" x2="{x+w-1}" y2="{y+21}" stroke="{edge}" stroke-width="1"/>')
        for sy in (y + 5, y + 8, y + 11, y + 14):
            parts.append(f'<line x1="{x+22}" y1="{sy}" x2="{x+w-10}" y2="{sy}" stroke="{sh}" stroke-opacity=".45" stroke-width="1"/>')
        parts.append(f'<rect x="{x+7}" y="{y+5}" width="10" height="10" fill="{hi}" stroke="{edge}" stroke-width="1"/>')
        title_w = len(title) * 5.2 + 12
        tx = x + (w - title_w) / 2
        parts.append(f'<rect x="{tx}" y="{y+3}" width="{title_w}" height="14" fill="{c["surface_container"]}"/>')
        parts.append(f'<text x="{x + w/2}" y="{y+14}" text-anchor="middle" fill="{c["on_surface"]}" font-family="{escape(profile["font"])}" font-size="8.5" font-weight="700">{escape(title)}</text>')

    def flat_box(x, y, w, h, fill=None, stroke=edge):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{fill or c["surface_container_low"]}" stroke="{stroke}" stroke-width="1"/>')

    def text(x, y, value, size=11, color=None, weight=600):
        parts.append(f'<text x="{x}" y="{y}" fill="{color or c["on_surface"]}" font-family="{escape(profile["font"])}" font-size="{size}" font-weight="{weight}">{escape(value)}</text>')

    x, y = left + 12, top + 14
    width = 440 - left - right - 24

    mac_window(x, y, 120, 96, 'Macintosh')
    text(x + 12, y + 58, '10:24', 28, c['on_surface'], 700)
    text(x + 12, y + 78, 'System 7 Gray', 9, c['on_surface_variant'], 600)

    mac_window(x, y + 106, 120, 72, 'Sound')
    flat_box(x + 10, y + 132, 26, 26, hi)
    parts.append(f'<path d="M{x+18} {y+138} V{y+152} L{x+29} {y+145} Z" fill="{c["primary"]}"/>')
    flat_box(x + 44, y + 141, 62, 8, hi)
    parts.append(f'<rect x="{x+45}" y="{y+142}" width="38" height="6" fill="{c["primary"]}"/>')

    mx, mw = x + 130, width - 130
    mac_window(mx, y, mw, 178, 'Finder · Menu')
    flat_box(mx + 10, y + 32, mw - 20, 22, hi, sh)
    text(mx + 18, y + 47, 'Find applications…', 9, c['on_surface_variant'], 500)
    tile = (mw - 32) / 3
    for i, label in enumerate(('Apps', 'Files', 'Shell')):
        tx = mx + 10 + i * (tile + 6)
        flat_box(tx, y + 64, tile, 54, c['primary'] if i == 1 else hi, edge)
        text(tx + 8, y + 96, label, 10, c['on_primary'] if i == 1 else c['on_surface'], 700)
    flat_box(mx + 10, y + 128, mw - 20, 38, c['surface_container_low'], sh)
    flat_box(mx + 16, y + 135, 64, 24, c['primary'], edge)
    text(mx + 30, y + 151, 'Apply', 10, c['on_primary'], 700)
    text(mx + 92, y + 151, 'Preferences   Info', 9, c['on_surface'], 600)

    if vertical:
        bx = 4 if position == 'left' else 398
        parts.append(f'<rect x="{bx}" y="{0 if profile.get("continuous") else 8}" width="38" height="{280 if profile.get("continuous") else 264}" rx="3" fill="url(#macbar)" stroke="{edge}" stroke-width="1.5"/>')
        for i in range(3):
            flat_box(bx + 6, 80 + i * 32, 26, 24, c['primary'] if i == 1 else hi, edge)
        flat_box(bx + 3, 220, 32, 44, hi, sh)
        text(bx + 8, 240, '10', 11, c['on_surface'], 700)
        text(bx + 8, 255, '24', 11, c['on_surface'], 700)
    else:
        by = 4 if position == 'top' else 242
        parts.append(f'<rect x="{0 if profile.get("continuous") else 8}" y="{by}" width="{440 if profile.get("continuous") else 424}" height="34" rx="3" fill="url(#macbar)" stroke="{edge}" stroke-width="1.5"/>')
        text(22, by + 21, 'Menu', 10, c['on_surface'], 700)
        for i in range(3):
            flat_box(92 + i * 56, by + 5, 48, 24, c['primary'] if i == 1 else hi, edge)
        flat_box(348, by + 4, 78, 26, hi, sh)
        text(364, by + 21, '10:24', 11, c['on_surface'], 700)
    return ''.join(parts) + '</svg>'
