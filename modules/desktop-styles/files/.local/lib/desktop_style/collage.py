"""Maximalist Vocaloid/UTAU paper-cutout and multi-color collage palette."""
import colorsys

from desktop_style.main import contrast_ratio, contrasting_tone, hexcolor, luminance, rgb


def _hue_distance(a, b):
    diff = abs(a - b) % 1.0
    return min(diff, 1.0 - diff)


def _tone(color, lightness, saturation=None):
    hue, _, original = colorsys.rgb_to_hls(*rgb(color))
    return hexcolor(colorsys.hls_to_rgb(hue, lightness, original if saturation is None else saturation))


def _ensure_contrast(bg, fg, minimum=4.8):
    return fg if contrast_ratio(bg, fg) >= minimum else contrasting_tone(bg, fg)


def _wallpaper_accents(count=3):
    """Dominant, distinct, vivid colours of the current wallpaper (a still frame for videos), best first."""
    import os
    from pathlib import Path
    try:
        from PIL import Image
        cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
        image = Path((cache / 'current-wallpaper').read_text().strip())
        if image.suffix.lower() in ('.mp4', '.webm', '.mkv', '.mov', '.gif'):
            image = cache / 'wallpaper-frame.png'
        with Image.open(image) as img:
            img = img.convert('RGB')
            img.thumbnail((96, 96))
            quant = img.quantize(colors=24, method=Image.Quantize.MEDIANCUT)
            palette_rgb = quant.getpalette()
            counts = quant.getcolors() or []
    except Exception:
        return []
    scored = []
    for n, index in counts:
        r, g, b = (palette_rgb[index * 3 + k] / 255 for k in range(3))
        hue, light, sat = colorsys.rgb_to_hls(r, g, b)
        # Prefer colours that are both common and saturated; skip near-black, near-white and grey.
        if sat < .25 or not .16 < light < .86:
            continue
        scored.append((n ** .5 * sat, hue, hexcolor((r, g, b))))
    picked = []
    for _, hue, color in sorted(scored, reverse=True):
        if all(_hue_distance(hue, h) >= .07 for h, _ in picked):
            picked.append((hue, color))
        if len(picked) == count:
            break
    return [color for _, color in picked]


def _mat_seed(source, seed, seed_sat):
    src_surface = source.get('surface', '#121212')
    src_r, src_g, src_b = rgb(src_surface)
    seed_r, seed_g, seed_b = rgb(seed)
    blended = (.75 * src_r + .25 * seed_r, .75 * src_g + .25 * seed_g, .75 * src_b + .25 * seed_b)
    hue, _, blend_sat = colorsys.rgb_to_hls(*blended)
    _, src_l, _ = colorsys.rgb_to_hls(src_r, src_g, src_b)
    tint = min(.14, max(.04, blend_sat * .22)) if seed_sat > .02 else 0
    return hexcolor(colorsys.hls_to_rgb(hue, .5, tint)), src_l, tint


def palette(source, accents=None):
    """`accents` are wallpaper colours, best first; None reads them from the current wallpaper, [] disables them."""
    colors = dict(source)
    dark = luminance(source.get('surface', '#121212')) < .5
    accents = _wallpaper_accents() if accents is None else accents
    seed = accents[0] if accents else source.get('primary', '#e5485d')
    p_h, _, seed_sat = colorsys.rgb_to_hls(*rgb(seed))
    mat_seed, src_l, tint = _mat_seed(source, seed, seed_sat)
    if accents:
        # Tint the surfaces with the wallpaper's own hue so the whole desktop reads as that image.
        mat_seed, tint = hexcolor(colorsys.hls_to_rgb(p_h, .5, .09)), .09
    base_l = max(.07, min(.11, src_l if src_l > .04 else .09)) if dark else min(.95, max(.90, src_l if src_l < .96 else .93))

    levels = (
        dict(
            surface=base_l, background=base_l, surface_dim=base_l,
            surface_container_lowest=max(.04, base_l - .03),
            surface_container_low=base_l + .025,
            surface_container=base_l + .05,
            surface_container_high=base_l + .085,
            surface_container_highest=base_l + .12,
            surface_variant=base_l + .12,
            surface_bright=base_l + .16,
        ) if dark else dict(
            surface=base_l, background=base_l, surface_dim=base_l,
            surface_container_lowest=min(.98, base_l + .035),
            surface_container_low=base_l - .025,
            surface_container=base_l - .05,
            surface_container_high=base_l - .085,
            surface_container_highest=base_l - .12,
            surface_variant=base_l - .12,
            surface_bright=min(.99, base_l + .04),
        )
    )
    for name, level in levels.items():
        colors[name] = _tone(mat_seed, level, tint)

    fg = _ensure_contrast(colors['surface_container_highest'], _tone(mat_seed, .95 if dark else .09, min(.08, tint)), 7.0)
    colors.update(on_surface=fg, on_background=fg, inverse_surface=fg, inverse_on_surface=colors['surface'])
    colors['on_surface_variant'] = _ensure_contrast(colors['surface_container'], _tone(mat_seed, .82 if dark else .24, min(.10, tint)), 7.0)
    colors['outline'] = _ensure_contrast(colors['surface_container_highest'], _tone(mat_seed, .68 if dark else .30, min(.22, tint + .06)), 3.2)
    colors['outline_variant'] = _tone(mat_seed, .34 if dark else .70, min(.18, tint + .04))

    # Coral+peach+teal style scheme: a warm neighbour and one soft complement, never a pure RGB triad
    if seed_sat <= .04:
        hues = {'primary': 0.50, 'secondary': 0.833, 'tertiary': 0.166}
        chroma = 0.80
    elif accents:
        def hue_of(color):
            return colorsys.rgb_to_hls(*rgb(color))[0]
        sec_h = hue_of(accents[1]) if len(accents) > 1 else (p_h + 30 / 360) % 1.0
        ter_h = hue_of(accents[2]) if len(accents) > 2 else (p_h + 150 / 360) % 1.0
        # Never let two roles collapse onto one hue.
        if _hue_distance(ter_h, p_h) < .07 or _hue_distance(ter_h, sec_h) < .07:
            ter_h = (p_h + 150 / 360) % 1.0 if _hue_distance((p_h + 150 / 360) % 1.0, sec_h) >= .07 else (p_h + 210 / 360) % 1.0
        hues = {'primary': p_h, 'secondary': sec_h, 'tertiary': ter_h}
        chroma = max(.55, min(.78, seed_sat * .95))
    else:
        hues = {
            'primary': p_h,
            'secondary': (p_h + 32 / 360) % 1.0,
            'tertiary': (p_h + 168 / 360) % 1.0,
        }
        chroma = max(0.42, min(0.62, seed_sat * 0.8))

    accent_l = 0.75 if dark else 0.35
    seeds = {
        role: hexcolor(colorsys.hls_to_rgb(h, accent_l, chroma))
        for role, h in hues.items()
    }
    seeds['error'] = source.get('error', '#ff6b6b')

    container_specs = {
        'primary': (.31 if dark else .88, .66),
        'secondary': (.30 if dark else .87, .64),
        'tertiary': (.32 if dark else .89, .62),
        'error': (.30 if dark else .88, .66),
    }

    for role, raw in seeds.items():
        _, _, sat = colorsys.rgb_to_hls(*rgb(raw))
        role_chroma = min(.88, max(.45, sat)) if sat > .01 else 0
        accent = raw if role == 'error' else _tone(raw, .76 if dark else .34, role_chroma)
        accent = _ensure_contrast(colors['surface_container'], accent, 4.8)
        accent = _ensure_contrast(colors['surface_container_highest'], accent, 6.0)
        on_accent = _ensure_contrast(accent, _tone(raw, .06 if dark else .98, .12), 4.8)

        c_l, c_scale = container_specs[role]
        # Lighter and more saturated than a muddy dark tint, so shadows and cards read against the surface.
        c_sat = min(.42, max(.28, role_chroma * c_scale * .7)) if sat > .01 else 0
        container_src = raw
        if role != 'error' and sat > .01:
            # Containers lean 25% toward the primary hue so every card shares one undertone (no muddy olive).
            role_h = colorsys.rgb_to_hls(*rgb(raw))[0]
            lean = (p_h + .25 * (((role_h - p_h + .5) % 1.0) - .5)) % 1.0
            container_src = hexcolor(colorsys.hls_to_rgb(lean, .5, .5))
        container = _tone(container_src, c_l, c_sat)
        on_container = _ensure_contrast(container, _tone(raw, .97 if dark else .05, min(.14, role_chroma * .22)), 7.0)

        colors.update({
            role: accent, 'on_' + role: on_accent,
            role + '_container': container, 'on_' + role + '_container': on_container,
            role + '_fixed': accent, role + '_fixed_dim': accent,
            'on_' + role + '_fixed': on_accent, 'on_' + role + '_fixed_variant': on_accent,
        })

    colors['surface_tint'] = colors['primary']
    colors['inverse_primary'] = _ensure_contrast(colors['surface_container_highest'], colors['on_primary'], 3.0)
    return colors, [colors[key] for key in ('surface', 'primary', 'secondary', 'tertiary', 'secondary_container')]
