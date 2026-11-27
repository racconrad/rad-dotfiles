import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
from desktop_style.context import Context


def reset(ctx=None):
    c = Context(ctx)
    c.STATE.mkdir(parents=True, exist_ok=True)
    with (c.STATE / 'apply.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = c.read(c.STATE / 'original.json')
        if not original:
            return
        destinations = {Path(entry['output_path']).expanduser() for entry in c.templates().values()}
        destinations.update((c.HYPR_STYLE, c.CONFIG / '_palette.scss',
                             c.HOME / '.config/rofi/colors.rasi', c.HOME / '.local/state/randly-widgets/palette.scss'))
        c.restore({key: value for key, value in original.items()
                   if Path(key) in destinations or Path(key).is_relative_to(c.CURRENT)})
        for name in ('raccon.scss', 'rofi.rasi', 'widgets.css', 'panels.css', 'swaync.css', 'swayosd.css', 'widget-editor.css'):
            c.write(c.CURRENT / name, '/* Original appearance */\n')
        (c.CURRENT / 'tokens.json').unlink(missing_ok=True)
        c.integrations('original')
        c.write(c.CONFIG / '_palette.scss', ''.join(f'${k}: {v};\n' for k, v in c.source_palette().items()))
        settings = c.read(c.STATE / 'settings.json')
        if c.widgets_available() and settings:
            c.run([c.BIN / 'widgetctl', 'style', settings['skin'], settings['fx'], settings['background'], settings.get('frame', 'none')])
        geometry = c.read(c.STATE / 'geometry.json')
        if geometry:
            c.set_managed(geometry)
        c.save(c.STATE / 'selection.json', dict(style='original', name='Original'))
        c.refresh_clients()


def companion_wallpaper(style):
    raise ValueError('This style has no companion wallpaper')


def apply(style='collage', wallpaper=False, ctx=None):
    c = Context(ctx)
    style = 'collage'
    c.STATE.mkdir(parents=True, exist_ok=True)
    with (c.STATE / 'apply.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        source = c.source_palette(refresh=wallpaper)
        if not (c.STATE / 'geometry.json').exists():
            c.save(c.STATE / 'geometry.json', c.managed_settings())
        before_settings = c.managed_settings()
        original_geometry = c.read(c.STATE / 'geometry.json')
        for key, value in before_settings.items():
            original_geometry.setdefault(key, value)
        c.save(c.STATE / 'geometry.json', original_geometry)
        before_widget_style = c.read(c.HOME / '.config/eww/style.json')
        colors, swatches = c.palette(style, source)
        outputs = {}
        for name, entry in c.templates().items():
            if name == 'desktop_style_source':
                continue
            src = Path(entry['input_path']).expanduser()
            dst = Path(entry['output_path']).expanduser()
            outputs[dst] = c.render(src.read_text(), colors)
        from desktop_style.appearance import build
        appearance = build(style, c.bar_profile(style), colors)
        widgets, menu, rofi = (appearance[k] for k in ('widgets', 'raccon', 'rofi'))
        widget_palette = c.HOME / '.local/state/randly-widgets/palette.scss'
        if c.widgets_available():
            outputs.setdefault(widget_palette, ''.join(f'${key}: {value};\n' for key, value in colors.items()))
            try:
                native = json.loads(c.run([c.BIN / 'widgetctl', 'manager-status']).stdout).get('global_style', False)
            except (OSError, ValueError, subprocess.SubprocessError):
                native = False
            if not native:
                outputs[widget_palette] += '\n' + widgets
        outputs.update({c.CURRENT / 'raccon.scss': menu, c.CURRENT / 'rofi.rasi': rofi})
        for name in ('widgets', 'panels', 'swaync', 'swayosd', 'wlogout', 'gtklock'):
            outputs[c.CURRENT / (name + '.css')] = appearance[name]
        outputs[c.CURRENT / 'tokens.json'] = c.with_widget_frame(appearance['tokens'])
        outputs[c.CURRENT / 'widget-editor.css'] = appearance['widget_editor']
        outputs[c.HOME / '.config/rofi/colors.rasi'] = appearance['rofi_colors']
        outputs[c.CONFIG / '_palette.scss'] = ''.join(f'${key}: {value};\n' for key, value in colors.items())
        outputs[c.HYPR_STYLE] = c.hypr_style(style)
        kitty = c.HOME / '.config/kitty/colors.conf'
        if kitty in outputs:
            outputs[kitty] += f'\n# Shared desktop appearance\nfont_family {c.PROFILES[style]["font"]}\nbackground_opacity {c.PROFILES[style]["alpha"]}\n'
        fuzzel = c.HOME / '.config/fuzzel/colors.ini'
        if fuzzel in outputs:
            tokens = json.loads(appearance['tokens'])
            opacity = f'{round(tokens["opacity"] * 255):02x}'
            mappings = {'background': colors['surface_container'] + opacity, 'text': colors['on_surface'] + 'ff',
                        'prompt': colors['primary'] + 'ff', 'placeholder': colors['on_surface_variant'] + 'ff',
                        'input': colors['on_surface'] + 'ff', 'match': colors['primary'] + 'ff',
                        'selection': colors['primary'] + 'ff', 'selection-text': colors['on_primary'] + 'ff',
                        'selection-match': colors['on_primary'] + 'ff', 'counter': colors['on_surface_variant'] + 'ff', 'border': colors['outline_variant'] + 'ff'}
            outputs[fuzzel] = '[colors]\n' + ''.join(f'{k}={v[1:]}\n' for k, v in mappings.items())
        for gtk in ('gtk-3.0', 'gtk-4.0'):
            path = c.HOME / '.config' / gtk / 'colors.css'
            if path in outputs:
                outputs[path] += '\n' + appearance['gtk']
        previous = c.snapshot(outputs)
        original = c.read(c.STATE / 'original.json')
        for key, value in previous.items():
            original.setdefault(key, value)
        c.save(c.STATE / 'original.json', original)
        for name in ('raccon', 'widgets', 'panels', 'swaync', 'swayosd', 'gtk', 'widget_editor', 'wlogout', 'gtklock'):
            c.validate_css(appearance[name])
        with tempfile.TemporaryDirectory() as tmp:
            for index, text in enumerate([outputs[widget_palette]] if c.widgets_available() else []):
                src = Path(tmp) / f'{index}.scss'
                src.write_text(text)
                c.run([c.BIN / 'widgetctl', 'compile-css', src, Path(tmp) / f'{index}.css'])
        try:
            for path, text in outputs.items():
                c.write(path, text)
            c.integrations(style)
            if c.widgets_available():
                widget_style = json.loads(c.with_widget_frame(appearance['tokens']))['widgets']
                c.run([c.BIN / 'widgetctl', 'style', widget_style['skin'], widget_style['fx'], widget_style['background'], widget_style['frame']])
            c.configure_launchers(style)
            warnings = c.refresh_clients()
            c.prepare_sddm_cache()
            c.save(c.STATE / 'selection.json', dict(style=style, name=c.PROFILES[style]['name'], swatches=swatches, warnings=warnings))
        except Exception:
            c.restore(previous)
            c.set_managed(before_settings)
            if c.widgets_available() and before_widget_style:
                c.run([c.BIN / 'widgetctl', 'style', before_widget_style['skin'], before_widget_style['fx'], before_widget_style['background'], before_widget_style.get('frame', 'none')], False)
            c.refresh_clients()
            raise
