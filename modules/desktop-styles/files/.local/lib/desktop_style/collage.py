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


def _mat_seed(source, seed, seed_sat):
    src_surface = source.get('surface', '#121212')
    src_r, src_g, src_b = rgb(src_surface)
    seed_r, seed_g, seed_b = rgb(seed)
    blended = (.72 * src_r + .28 * seed_r,
               .72 * src_g + .28 * seed_g,
               .72 * src_b + .28 * seed_b)
    hue, _, blend_sat = colorsys.rgb_to_hls(*blended)
    _, src_l, _ = colorsys.rgb_to_hls(src_r, src_g, src_b)
    if seed_sat > .02 or blend_sat > .02:
        tint = min(.16, max(.05, blend_sat * .24))
    else:
        tint = 0
    return hexcolor(colorsys.hls_to_rgb(hue, .5, tint)), src_l, tint


def palette(source):
    colors = dict(source)
    dark = luminance(source.get('surface', '#121212')) < .5
    seed = source.get('primary', '#e5485d')
    _, _, seed_sat = colorsys.rgb_to_hls(*rgb(seed))
    mat_seed, src_l, tint = _mat_seed(source, seed, seed_sat)
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
        )
        if dark else
        dict(
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

    fg = _ensure_contrast(colors['surface_container_highest'],
                          _tone(mat_seed, .95 if dark else .09, min(.08, tint)), 4.8)
    colors.update(on_surface=fg, on_background=fg, inverse_surface=fg,
                  inverse_on_surface=colors['surface'])
    colors['on_surface_variant'] = _ensure_contrast(
        colors['surface_container'], _tone(mat_seed, .76 if dark else .28, min(.10, tint)), 4.8)
    outline_sat = min(.22, tint + .06) if tint > 0 else 0
    colors['outline'] = _ensure_contrast(colors['surface_container_highest'],
                                         _tone(mat_seed, .68 if dark else .30, outline_sat), 3.2)
    colors['outline_variant'] = _tone(mat_seed, .34 if dark else .70, min(.18, tint + .04) if tint > 0 else 0)

    accents = [source[k] for k in ('wallpaper_accent_1', 'wallpaper_accent_2', 'wallpaper_accent_3') if source.get(k)]
    first_chromatic = next((a for a in accents if colorsys.rgb_to_hls(*rgb(a))[2] > .04), None)
    pri_raw = seed if seed_sat > .02 else (first_chromatic or '#ff5b73')
    p_hue = colorsys.rgb_to_hls(*rgb(pri_raw))[0]

    def _distinct_accent(excluded_hues, min_diff=.05):
        for cand in accents:
            ch, _, cs = colorsys.rgb_to_hls(*rgb(cand))
            if cs > .04 and all(_hue_distance(ch, eh) >= min_diff for eh in excluded_hues):
                return cand
        return None

    sec_src = source.get('secondary', pri_raw)
    sec_hue, _, sec_sat = colorsys.rgb_to_hls(*rgb(sec_src))
    ter_src = source.get('tertiary', pri_raw)
    ter_hue, _, ter_sat = colorsys.rgb_to_hls(*rgb(ter_src))

    single_seed = (
        seed_sat <= .02
        or (
            sec_src.lower() == seed.lower()
            and ter_src.lower() == seed.lower()
            and _distinct_accent((p_hue,)) is None
        )
    )

    if sec_sat > .02 and _hue_distance(sec_hue, p_hue) >= .05:
        sec_raw = sec_src
    elif (real_sec := _distinct_accent((p_hue,))) is not None:
        sec_raw = real_sec
    elif not single_seed and sec_sat > .02 and sec_src.lower() != seed.lower():
        sec_raw = sec_src
    elif not single_seed and ter_sat > .02 and _hue_distance(ter_hue, p_hue) >= .05:
        sec_raw = ter_src
    else:
        sec_raw = hexcolor(colorsys.hls_to_rgb((p_hue + .18) % 1.0, .64, .76))
    s_hue = colorsys.rgb_to_hls(*rgb(sec_raw))[0]

    if ter_sat > .02 and _hue_distance(ter_hue, p_hue) >= .05 and _hue_distance(ter_hue, s_hue) >= .05:
        ter_raw = ter_src
    elif (real_ter := _distinct_accent((p_hue, s_hue))) is not None:
        ter_raw = real_ter
    elif not single_seed and ter_sat > .02 and ter_src.lower() != seed.lower():
        ter_raw = ter_src
    else:
        t_hue = (p_hue + .34) % 1.0
        if _hue_distance(t_hue, s_hue) < .10:
            t_hue = (p_hue + .82) % 1.0
        ter_raw = hexcolor(colorsys.hls_to_rgb(t_hue, .68, .76))

    seeds = {
        'primary': pri_raw,
        'secondary': sec_raw,
        'tertiary': ter_raw,
        'error': source.get('error', '#ff6b6b'),
    }

    container_specs = {
        'primary': (.21 if dark else .88, .66),
        'secondary': (.20 if dark else .87, .64),
        'tertiary': (.22 if dark else .89, .62),
        'error': (.22 if dark else .88, .66),
    }

    for role, raw in seeds.items():
        _, _, sat = colorsys.rgb_to_hls(*rgb(raw))
        chroma = min(.86, max(.45, sat)) if sat > .01 else 0
        accent = raw if role == 'error' else _tone(raw, .76 if dark else .34, chroma)
        accent = _ensure_contrast(colors['surface_container_highest'], accent, 4.8)

        on_accent = _ensure_contrast(accent, _tone(raw, .06 if dark else .98, .12), 4.8)

        c_lightness, c_chroma_scale = container_specs[role]
        c_sat = min(.56, max(.40, chroma * c_chroma_scale)) if sat > .01 else 0
        container = _tone(raw, c_lightness, c_sat)
        on_container = _ensure_contrast(container, _tone(raw, .95 if dark else .08, min(.14, chroma * .22)), 4.8)

        colors.update({
            role: accent, 'on_' + role: on_accent,
            role + '_container': container, 'on_' + role + '_container': on_container,
            role + '_fixed': accent, role + '_fixed_dim': accent,
            'on_' + role + '_fixed': on_accent, 'on_' + role + '_fixed_variant': on_accent,
        })

    colors['surface_tint'] = colors['primary']
    colors['inverse_primary'] = _ensure_contrast(colors['surface_container_highest'], colors['on_primary'], 3.0)
    return colors, [colors[key] for key in ('surface', 'primary', 'secondary', 'tertiary', 'secondary_container')]
