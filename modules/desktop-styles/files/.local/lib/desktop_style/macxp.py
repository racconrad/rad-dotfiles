"""Early Macintosh grayscale palette: crisp monochrome grays and simple ink borders."""


def palette(source):
    colors = dict(source)
    # Neutral Platinum/System-7 grayscale so colorful wallpapers stand out cleanly.
    colors.update(
        surface='#dedede', surface_dim='#d2d2d2', background='#dedede',
        surface_bright='#ffffff', surface_container_lowest='#ffffff',
        surface_container_low='#f4f4f4', surface_container='#e8e8e8',
        surface_container_high='#dcdcdc', surface_container_highest='#cfcfcf',
        surface_variant='#d4d4d4', on_surface='#141414', on_background='#141414',
        on_surface_variant='#454545', outline='#1a1a1a', outline_variant='#6e6e6e',
        primary='#242424', on_primary='#ffffff', primary_container='#d4d4d4',
        on_primary_container='#111111', primary_fixed='#e2e2e2', primary_fixed_dim='#242424',
        on_primary_fixed='#111111', on_primary_fixed_variant='#2c2c2c',
        secondary='#3e3e3e', on_secondary='#ffffff', secondary_container='#dcdcdc',
        on_secondary_container='#141414', secondary_fixed='#e6e6e6', secondary_fixed_dim='#3e3e3e',
        on_secondary_fixed='#141414', on_secondary_fixed_variant='#3e3e3e',
        tertiary='#525252', on_tertiary='#ffffff', tertiary_container='#e2e2e2',
        on_tertiary_container='#1a1a1a', tertiary_fixed='#ebebeb', tertiary_fixed_dim='#525252',
        on_tertiary_fixed='#1a1a1a', on_tertiary_fixed_variant='#525252',
        error='#7a1c1c', on_error='#ffffff', error_container='#f2dede', on_error_container='#4d1010',
        inverse_surface='#1a1a1a', inverse_on_surface='#f4f4f4', inverse_primary='#d4d4d4',
        surface_tint='#242424', shadow='#000000', scrim='#000000',
    )
    return colors, [colors[k] for k in ('surface_container_lowest', 'surface_container', 'surface_container_highest', 'outline_variant', 'primary')]
