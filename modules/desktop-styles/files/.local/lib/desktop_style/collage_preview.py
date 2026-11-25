"""Sharp angular Vocaloid/UTAU cutout collage preview generator."""
from html import escape


def preview_svg(c, profile):
    position = profile['position']
    vertical = position in ('left', 'right')
    left, right = (46 if position == side else 0 for side in ('left', 'right'))
    top = 38 if position == 'top' else 0
    edge = c['outline']
    ink = c['surface_container_lowest']
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280" viewBox="0 0 440 280">',
        f'<rect width="440" height="280" fill="{c["surface"]}"/>',
    ]
    for gx in range(24, 440, 32):
        parts.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="280" stroke="{c["outline_variant"]}" stroke-opacity=".28" stroke-width="1"/>')
    for gy in range(24, 280, 32):
        parts.append(f'<line x1="0" y1="{gy}" x2="440" y2="{gy}" stroke="{c["outline_variant"]}" stroke-opacity=".28" stroke-width="1"/>')
    parts.append(f'<polygon points="0,24 196,4 162,154 0,180" fill="{c["primary_container"]}" stroke="{edge}" stroke-width="1"/>')
    parts.append(f'<polygon points="248,162 440,126 440,280 214,280" fill="{c["secondary_container"]}" stroke="{edge}" stroke-width="1"/>')
    parts.append(f'<polygon points="154,12 232,12 204,70 138,70" fill="{c["primary"]}" opacity=".22"/>')

    def cutout(x, y, w, h, fill, shadow=None, stroke=edge, sw=1.5, chamfer=0):
        if chamfer:
            pts = f'{x},{y} {x+w-chamfer},{y} {x+w},{y+chamfer} {x+w},{y+h} {x},{y+h}'
            if shadow:
                spts = f'{x+3},{y+3} {x+w-chamfer+3},{y+3} {x+w+3},{y+chamfer+3} {x+w+3},{y+h+3} {x+3},{y+h+3}'
                parts.append(f'<polygon points="{spts}" fill="{shadow}"/>')
            parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        else:
            if shadow:
                parts.append(f'<rect x="{x+3}" y="{y+3}" width="{w}" height="{h}" fill="{shadow}"/>')
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def text(x, y, value, size=11, color=None, weight=800, font=None):
        parts.append(f'<text x="{x}" y="{y}" fill="{color or c["on_surface"]}" font-family="{escape(font or profile["font"])}" font-size="{size}" font-weight="{weight}">{escape(value)}</text>')

    x, y = left + 12, top + 14
    width = 440 - left - right - 24

    cutout(x, y + 8, 122, 90, c['surface_container'], shadow=c['primary'], sw=2)
    cutout(x - 2, y, 68, 18, c['primary'], sw=1)
    text(x + 5, y + 13, 'CUT // 09', 8, c['on_primary'], 800, 'JetBrainsMono Nerd Font Mono')
    text(x + 10, y + 58, '10:24', 34, c['primary'], 800, 'Fira Sans Compressed')
    text(x + 10, y + 78, 'PAPER / CUT', 9, c['on_surface_variant'], 700, 'JetBrainsMono Nerd Font Mono')

    cutout(x, y + 109, 122, 68, c['surface_container'], shadow=c['secondary'], sw=2)
    parts.append(f'<rect x="{x}" y="{y+109}" width="122" height="2" fill="{c["primary"]}"/>')
    text(x + 9, y + 125, 'Virtual Player', 8, c['on_surface_variant'], 700, 'JetBrainsMono Nerd Font Mono')
    cutout(x + 9, y + 134, 24, 24, c['surface_container_highest'], stroke=c['outline_variant'], sw=1)
    parts.append(f'<path d="M{x+17} {y+139} V{y+153} L{x+27} {y+146} Z" fill="{c["primary"]}"/>')
    for bi, bh in enumerate((12, 24, 16, 26, 9, 20)):
        parts.append(f'<rect x="{x+43+bi*11}" y="{y+160-bh}" width="7" height="{bh}" fill="{c["primary"] if bi % 2 == 0 else c["secondary"]}"/>')

    mx, mw = x + 132, width - 132
    cutout(mx, y + 4, mw, 173, c['surface_container'], shadow=c['primary'], sw=2)
    parts.append(f'<line x1="{mx}" y1="{y+36}" x2="{mx+mw}" y2="{y+36}" stroke="{c["primary"]}" stroke-width="2"/>')
    text(mx + 12, y + 27, 'RACCON // CUT', 18, c['primary'], 800, 'Fira Sans Compressed')
    cutout(mx + mw - 78, y + 10, 62, 18, c['primary_container'], stroke=c['primary'], sw=1)
    text(mx + mw - 71, y + 22, 'COLLAGE', 8, c['on_primary_container'], 800, 'JetBrainsMono Nerd Font Mono')
    cutout(mx + 12, y + 44, mw - 24, 22, ink, stroke=c['outline_variant'], sw=1)
    parts.append(f'<rect x="{mx+12}" y="{y+44}" width="3" height="22" fill="{c["primary"]}"/>')
    text(mx + 22, y + 59, '> Search apps_', 9, c['on_surface_variant'], 700, 'JetBrainsMono Nerd Font Mono')

    tile = (mw - 36) / 3
    fills = [
        (c['surface_container_highest'], c['on_surface'], c['primary']),
        (c['primary'], c['on_primary'], c['primary']),
        (c['surface_container_highest'], c['on_surface'], c['secondary']),
    ]
    for i, label in enumerate(('Apps', 'Files', 'Term')):
        tx = mx + 12 + i * (tile + 6)
        fill, tcol, bar_col = fills[i]
        cutout(tx, y + 76, tile, 50, fill, stroke=c['outline_variant'], sw=1)
        parts.append(f'<rect x="{tx}" y="{y+76}" width="2" height="50" fill="{bar_col}"/>')
        text(tx + 9, y + 105, label, 10, tcol, 700)

    cutout(mx + 12, y + 138, mw - 24, 24, ink, stroke=c['outline_variant'], sw=1)
    text(mx + 20, y + 153, '[SYS]  WIFI   BT   THEME', 8, c['secondary'], 700, 'JetBrainsMono Nerd Font Mono')

    if vertical:
        bx = 5 if position == 'left' else 397
        if profile.get('continuous'):
            cutout(bx, 0, 38, 280, c['surface_container'], sw=1)
        else:
            cutout(bx, 10, 38, 48, c['surface_container'], shadow=c['primary_container'], sw=1)
            cutout(bx, 78, 38, 116, c['surface_container'], shadow=c['primary_container'], sw=1)
            cutout(bx, 216, 38, 54, c['surface_container'], shadow=c['primary_container'], sw=1)
        for i in range(3):
            parts.append(f'<rect x="{bx+10}" y="{90+i*32}" width="18" height="18" fill="none" stroke="{c["primary"] if i == 1 else c["outline_variant"]}" stroke-width="1"/>')
        text(bx + 7, 240, '10', 12, c['primary'], 800)
        text(bx + 7, 256, '24', 12, c['primary'], 800)
    else:
        by = 4 if position == 'top' else 238
        if profile.get('continuous'):
            cutout(0, by, 440, 38, c['surface_container'], sw=1)
        else:
            for bx, bw in ((12, 96), (144, 152), (332, 96)):
                cutout(bx, by, bw, 34, c['surface_container'], shadow=c['primary_container'], sw=1)
        text(26, by + 21, '1   2   3', 10, c['primary'], 700)
        for i in range(4):
            cx = 158 + i * 34
            parts.append(f'<rect x="{cx}" y="{by+9}" width="16" height="16" fill="{c["surface_container_highest"]}"/>')
            if i == 1:
                parts.append(f'<rect x="{cx}" y="{by+27}" width="16" height="2" fill="{c["primary"]}"/>')
        text(344, by + 21, '73%', 10, c['on_surface_variant'], 700)
        text(380, by + 21, '10:24', 11, c['primary'], 800, 'Fira Sans Compressed')
    return ''.join(parts) + '</svg>'
