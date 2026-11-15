"""Small geometric catalog preview reflecting the selected bar layout."""
from html import escape


def preview_svg(c, profile):
    position = profile['position']
    vertical = position in ('left', 'right')
    left, right = (46 if position == side else 0 for side in ('left', 'right'))
    top = 38 if position == 'top' else 0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280" viewBox="0 0 440 280"><rect width="440" height="280" rx="12" fill="{c["surface"]}"/>']

    def box(x, y, w, h, fill, small=8, large=24):
        parts.append(f'<path d="M{x+large} {y} H{x+w-small} Q{x+w} {y} {x+w} {y+small} V{y+h-large} Q{x+w} {y+h} {x+w-large} {y+h} H{x+small} Q{x} {y+h} {x} {y+h-small} V{y+large} Q{x} {y} {x+large} {y} Z" fill="{fill}"/>')

    def text(x, y, value, size=11, color=None, weight=500):
        parts.append(f'<text x="{x}" y="{y}" fill="{color or c["on_surface"]}" font-family="{escape(profile["font"])}" font-size="{size}" font-weight="{weight}">{escape(value)}</text>')

    x, y = left + 12, top + 16
    width = 440 - left - right - 24
    box(x, y, 116, 91, c['surface_container'])
    text(x + 12, y + 47, '10:24', 33, c['primary'], 800)
    text(x + 12, y + 70, 'My desktop', 11, c['on_surface_variant'])
    box(x, y + 103, 116, 68, c['secondary_container'])
    text(x + 12, y + 124, 'Music', 12, c['on_secondary_container'], 700)
    parts.append(f'<path d="M{x+18} {y+138} V{y+156} L{x+32} {y+147} Z" fill="{c["on_secondary_container"]}"/>')
    box(x + 45, y + 143, 56, 6, c['tertiary'], 3, 3)
    mx, mw = x + 128, width - 128
    box(mx, y, mw, 171, c['surface_container'])
    text(mx + 12, y + 28, 'Raccon Menu', 19, weight=800)
    box(mx + 12, y + 42, mw - 24, 28, c['surface_container_highest'], 14, 14)
    text(mx + 23, y + 60, 'Search apps', 10, c['on_surface_variant'])
    tile = (mw - 36) / 3
    for i, label in enumerate(('Apps', 'Files', 'Terminal')):
        tx = mx + 12 + i * (tile + 6)
        box(tx, y + 83, tile, 49, c['primary_container'], 5, 16)
        text(tx + 6, y + 113, label, 8, c['on_primary_container'], 600)
    box(mx + 12, y + 144, mw - 24, 17, c['tertiary_container'], 8, 8)
    text(mx + 23, y + 156, 'Apps     Settings', 9, c['on_tertiary_container'])

    if vertical:
        bx = 5 if position == 'left' else 397
        if profile.get('continuous'):
            box(bx, 0, 38, 280, c['surface_container'], 0, 0)
        else:
            box(bx, 10, 38, 48, c['surface_container'], 7, 18)
            box(bx, 78, 38, 116, c['surface_container'], 7, 18)
        for i in range(3):
            box(bx + 8, 87 + i * 34, 22, 24, c['primary'] if i == 1 else c['secondary_container'], 5, 10)
        box(bx, 216, 38, 54, c['primary'], 7, 18)
        text(bx + 7, 240, '10', 12, c['on_primary'], 800)
        text(bx + 7, 256, '24', 12, c['on_primary'], 800)
    else:
        by = 4 if position == 'top' else 240
        if profile.get('continuous'):
            box(0, by, 440, 36, c['surface_container'], 0, 0)
        else:
            for bx, bw in ((12, 95), (145, 150), (333, 95)):
                box(bx, by, bw, 36, c['surface_container'], 7, 18)
        text(25, by + 23, 'Raccon', 11, c['primary'], 700)
        for i in range(4):
            box(154 + i * 34, by + 5, 28, 26, c['primary'] if i == 1 else c['secondary_container'], 5, 12)
        box(341, by + 5, 78, 26, c['primary'], 13, 13)
        text(355, by + 23, '10:24', 13, c['on_primary'], 800)
    return ''.join(parts) + '</svg>'
