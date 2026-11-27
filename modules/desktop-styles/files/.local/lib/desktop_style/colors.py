import colorsys
import hashlib
from pathlib import Path
import re
from desktop_style.context import Context


def rgb(color):
    return tuple(int(color[i:i+2], 16) / 255 for i in (1, 3, 5))


def hexcolor(values):
    return '#' + ''.join(f'{round(max(0,min(1,v))*255):02x}' for v in values)


def luminance(color):
    values = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb(color)]
    return sum(v*w for v,w in zip(values, (.2126,.7152,.0722)))


def contrast_ratio(a, b):
    low, high = sorted((luminance(a), luminance(b)))
    return (high + .05) / (low + .05)


def contrasting_tone(background, seed):
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb(seed))
    end = 1 if contrast_ratio(background, '#ffffff') > contrast_ratio(background, '#000000') else 0
    low, high = 0, 1
    for _ in range(18):
        mid = (low + high) / 2
        color = hexcolor(colorsys.hls_to_rgb(hue, lightness + (end - lightness) * mid, saturation))
        if contrast_ratio(background, color) >= 4.8:
            high = mid
        else:
            low = mid
    return hexcolor(colorsys.hls_to_rgb(hue, lightness + (end - lightness) * high, saturation))


def palette(style, source, ctx=None):
    from desktop_style.collage import palette as collage_palette
    return collage_palette(source)


def source_palette(refresh=False, ctx=None):
    """Read original wallpaper colors, never a palette already transformed by a style."""
    c = Context(ctx)
    path = c.STATE / 'source.json'
    meta_path = c.STATE / 'source-meta.json'
    raw_path = c.HOME / '.config/matugen/out/desktop-style-source.json'
    try:
        image = Path((c.HOME / '.cache/current-wallpaper').read_text().strip())
    except OSError:
        image = None
    scheme_path = c.HOME / '.config/matugen/scheme'
    scheme = scheme_path.read_text().strip() if scheme_path.exists() else 'scheme-tonal-spot'
    signature = None
    if image and image.is_file():
        stat = image.stat()
        signature = hashlib.sha256(f'{image}:{stat.st_size}:{stat.st_mtime_ns}:{scheme}'.encode()).hexdigest()

    def valid(value):
        return isinstance(value, dict) and {'primary','surface','on_surface'} <= value.keys() and all(re.fullmatch(r'#[0-9a-fA-F]{6}', str(v)) for v in value.values())

    meta = c.read(meta_path)
    raw = c.read(raw_path)
    raw_time = raw_path.stat().st_mtime_ns if raw_path.exists() else None
    cached = c.read(path)
    if valid(raw) and (raw_time != meta.get('raw_mtime') or signature == meta.get('wallpaper')):
        colors = raw
    elif signature and (signature != meta.get('wallpaper') or refresh or not valid(cached)):
        still = image
        if image.suffix.lower() in ('.mp4', '.webm', '.mkv', '.mov', '.gif'):
            still = c.HOME / '.cache/wallpaper-frame.png'
        result = c.run(['matugen', 'image', still, '--dry-run', '--json', 'hex', '-m', 'dark', '-t', scheme, '--source-color-index', '0'])
        import json
        data = json.loads(result.stdout)['colors']
        if isinstance(data.get('dark'), dict):
            colors = data['dark']
        else:
            colors = {key: value['dark']['color'] for key, value in data.items() if isinstance(value, dict) and 'dark' in value}
        if not valid(colors):
            raise ValueError('Matugen did not return a valid wallpaper palette.')
        c.save(raw_path, colors)
        raw_time = raw_path.stat().st_mtime_ns
    elif valid(cached):
        colors = cached
    else:
        # Matugen renders the full Material palette into these per-app colors.css files.
        colors = {}
        for app in ('swayosd', 'wlogout', 'swaync', 'gtklock'):
            path = c.HOME / '.config' / app / 'colors.css'
            if path.is_file():
                colors = dict(re.findall(r'@define-color\s+(\w+)\s+(#[\da-fA-F]{6});', path.read_text()))
                if valid(colors):
                    break
        if not valid(colors):
            raise ValueError('Original palette not found. Reapply your wallpaper.')

    cached_meta = bool(signature and signature == meta.get('wallpaper') and meta.get('image_pair_version') == 2)
    pair = meta.get('image_pair') if cached_meta else None
    accents = list(meta.get('image_accents') or []) if cached_meta else []
    if signature and not pair:
        try:
            from PIL import Image, ImageOps
            still = image if image.suffix.lower() not in ('.mp4', '.webm', '.mkv', '.mov', '.gif') else c.HOME / '.cache/wallpaper-frame.png'
            with Image.open(still) as opened:
                sample = ImageOps.exif_transpose(opened).convert('RGB')
                sample.thumbnail((160, 160))
                indexed = sample.quantize(colors=24)
                table = indexed.getpalette()
                ranked = sorted(indexed.getcolors(), reverse=True)
                candidates = ['#' + ''.join(f'{v:02x}' for v in table[i*3:i*3+3]) for _, i in ranked]
                dominant = candidates[0]
                contrast = next((cand for cand in candidates[1:] if contrast_ratio(dominant, cand) >= 4.5), None)
                if contrast is None:
                    contrast = contrasting_tone(dominant, max(candidates, key=lambda cand: contrast_ratio(dominant, cand)))
                pair = [dominant, contrast]
                accents = []
                for min_sat, lo_l, hi_l in ((0.15, 0.12, 0.88), (0.06, 0.08, 0.92)):
                    for cand in candidates:
                        if len(accents) >= 3:
                            break
                        ch, cl, cs = colorsys.rgb_to_hls(*rgb(cand))
                        if cs < min_sat or not (lo_l <= cl <= hi_l):
                            continue
                        if any(min(abs(ch - ah) % 1.0, 1.0 - abs(ch - ah) % 1.0) < 0.08 for ah in (colorsys.rgb_to_hls(*rgb(a))[0] for a in accents)):
                            continue
                        accents.append(cand)
        except (OSError, ValueError, ImportError):
            pair = None
            accents = []
    colors = dict(colors)
    if pair:
        colors.update(wallpaper_dominant=pair[0], wallpaper_contrast=pair[1])
        for idx, accent in enumerate(accents[:3], 1):
            colors[f'wallpaper_accent_{idx}'] = accent
    c.save(path, colors)
    c.save(meta_path, dict(wallpaper=signature, raw_mtime=raw_time, image_pair=pair, image_accents=accents[:3], image_pair_version=2))
    return colors
