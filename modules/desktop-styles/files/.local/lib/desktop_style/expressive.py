"""Emphatic tonal roles derived from the original wallpaper palette."""
import colorsys

from desktop_style.main import contrast_ratio, contrasting_tone, hexcolor, luminance, rgb


def palette(source):
    colors = dict(source)
    dark = luminance(source['surface']) < .5
    seed = source['primary']
    tint = min(.12, colorsys.rgb_to_hls(*rgb(seed))[2])

    def tone(color, lightness, saturation=None):
        hue, _, original = colorsys.rgb_to_hls(*rgb(color))
        return hexcolor(colorsys.hls_to_rgb(hue, lightness, original if saturation is None else saturation))

    for name, level in dict(surface=.06, background=.06, surface_dim=.06,
                            surface_container_lowest=.035, surface_container_low=.09,
                            surface_container=.115, surface_container_high=.15,
                            surface_container_highest=.19, surface_bright=.22, surface_variant=.19).items():
        colors[name] = tone(seed, level if dark else 1 - level * .65, tint)
    fg = tone(seed, .95 if dark else .08, tint)
    colors.update(on_surface=fg, on_background=fg, inverse_surface=fg,
                  inverse_on_surface=colors['surface'])
    colors['on_surface_variant'] = tone(seed, .78 if dark else .27, tint)
    colors['outline'] = tone(seed, .64 if dark else .38, tint)
    colors['outline_variant'] = tone(seed, .42 if dark else .62, tint)

    for role in ('primary', 'secondary', 'tertiary', 'error'):
        original = source.get(role, seed)
        saturation = colorsys.rgb_to_hls(*rgb(original))[2]
        # An achromatic wallpaper stays achromatic instead of inventing a red hue.
        saturation = min(.85, max(.60, saturation)) if saturation > .01 else 0
        accent = original if role == 'error' else tone(original, .78 if dark else .32, saturation)
        if contrast_ratio(colors['surface_container_highest'], accent) < 4.8:
            accent = contrasting_tone(colors['surface_container_highest'], accent)
        container = tone(original, .28 if dark else .84, saturation * .75)
        on_accent = tone(original, .06 if dark else .98, .12)
        if contrast_ratio(accent, on_accent) < 4.8:
            on_accent = contrasting_tone(accent, on_accent)
        on_container = fg
        if contrast_ratio(container, on_container) < 4.8:
            on_container = contrasting_tone(container, on_container)
        colors.update({role: accent, 'on_' + role: on_accent,
                       role + '_container': container, 'on_' + role + '_container': on_container,
                       role + '_fixed': accent, role + '_fixed_dim': accent,
                       'on_' + role + '_fixed': on_accent, 'on_' + role + '_fixed_variant': on_accent})
    colors['surface_tint'] = colors['primary']
    colors['inverse_primary'] = colors['on_primary']
    return colors, [colors[key] for key in ('surface', 'primary', 'secondary', 'tertiary', 'on_surface')]
