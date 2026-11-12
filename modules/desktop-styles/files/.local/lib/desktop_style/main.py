import colorsys
import fcntl
import hashlib
import configparser
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import threading
from xml.sax.saxutils import escape

HOME = Path.home()
CONFIG = HOME / '.config/desktop-style'
STATE = HOME / '.local/state/desktop-style'
CURRENT = CONFIG / 'current'
BIN = HOME / '.local/bin'
PROFILES = {
    'modern': dict(icon='view-grid-symbolic', widget_frame='none', name='Default', detail='Clean, rounded surfaces', font='Inter', radius=14, border=0, alpha=1, skin='minimal', position='bottom'),
    'glass': dict(icon='view-reveal-symbolic', widget_frame='none', name='Transparent', detail='Translucent surfaces', font='Inter', radius=20, border=1, alpha=.88, skin='glass', position='bottom'),
    'terminal': dict(icon='utilities-terminal-symbolic', widget_frame='terminal', name='Classic', detail='Monospaced type and fine borders', font='JetBrainsMono Nerd Font Mono', radius=0, border=1, alpha=1, skin='terminal', position='bottom'),
    'monochrome': dict(icon='format-text-code-symbolic', widget_frame='none', name='Mono', detail='Two colors from your wallpaper', font='JetBrainsMono Nerd Font Mono', radius=0, border=1, alpha=1, skin='monochrome', position='bottom'),
    'retro': dict(icon='applications-games-symbolic', widget_frame='retro', name='Retro', detail='Pixel type and a 16-color palette', font='Silkscreen', radius=0, border=2, alpha=1, skin='pixel', position='bottom'),
    'ascii': dict(icon='format-text-code-symbolic', widget_frame='ascii', name='Night', detail='Navy, ivory, coral and cyan', font='JetBrainsMono Nerd Font Mono', radius=0, border=1, alpha=1, skin='ascii', position='bottom'),
}
STYLE_ALIASES = {'gnome':'modern','windows':'modern','default':'modern','simple':'modern',
                 'transparent':'glass','classic':'terminal','mono':'monochrome','night':'ascii','ascii bloom':'ascii'}
WIDGET_FRAME_ICONS = dict(auto='insert-link-symbolic', none='window-minimize-symbolic', future='applications-engineering-symbolic',
                         gnome='preferences-desktop-symbolic', windows='preferences-system-windows-symbolic', **{k:v['icon'] for k,v in PROFILES.items()})

# Frame adopted by widgets set to «Heredar escritorio»; 'auto' follows the style.
WIDGET_FRAMES = {'auto': 'Follow theme', 'none': 'No frame', 'monochrome': 'Mono', 'terminal': 'Classic',
                 'retro': 'Retro', 'future': 'Future', 'glass': 'Transparent', 'modern': 'Default',
                 'gnome': 'Rounded', 'windows': 'Compact', 'ascii': 'Night'}


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def save(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def normalize_style(style):
    if not isinstance(style,str):return 'modern'
    return STYLE_ALIASES.get(style.lower(),style.lower())


def migrate_theme_state():
    """Keep old commands/selections and frame overrides useful after merging themes."""
    selection=read(STATE/'selection.json')
    if isinstance(selection,dict) and selection:
        old=selection.get('style','original');style=normalize_style(old)
        if style in PROFILES:
            selection.update(style=style,name=PROFILES[style]['name'])
            save(STATE/'selection.json',selection)
        frames=read(STATE/'widget-frame.json')
        choices=frames.get('styles',{}) if isinstance(frames,dict) else {}
        if isinstance(choices,dict):
            merged=dict(choices)
            for key in [old,*choices]:
                target=normalize_style(key)
                if key in choices and target in PROFILES and target not in merged:merged[target]=choices[key]
            if merged!=choices:frames['styles']=merged;save(STATE/'widget-frame.json',frames)


def bar_preferences():
    value=read(CONFIG/'waybar.json')
    if not isinstance(value,dict):value={}
    return dict(position=value.get('position') if value.get('position') in ('top','bottom','left','right') else 'bottom',
                layout=value.get('layout') if value.get('layout') in ('islands','continuous') else 'islands')


def bar_profile(style):
    prefs=bar_preferences()
    return dict(PROFILES[style],position=prefs['position'],continuous=prefs['layout']=='continuous')


def run(argv, check=True):
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=30, check=check)


def widgets_available():
    return os.access(BIN/'widgetctl',os.X_OK)


def validate_css(text):
    # The selector also works on desktops without a tinyWidgets installation.
    import gi
    gi.require_version('Gtk','3.0')
    from gi.repository import Gtk
    provider=Gtk.CssProvider()
    provider.load_from_data(text.encode())


def eww(*args, check=False):
    attempts=5 if args and args[0] in ('ping','update','get','active-windows') else 1
    for attempt in range(attempts):
        result=run(['eww','--no-daemonize','-c',CONFIG,*args],check=False)
        if not result.returncode:break
        message=result.stderr or result.stdout
        if not any(value in message for value in ('Resource temporarily unavailable','channel closed')):break
        time.sleep(.08*(attempt+1))
    if check and result.returncode:raise subprocess.CalledProcessError(result.returncode,result.args,result.stdout,result.stderr)
    return result


def update(_publish=True, _extra_action=None, **values):
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'ui.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=read(STATE/'ui.json')
        state.update(values)
        if _extra_action is not None:
            target='' if _extra_action=='close' or state.get('extra')==_extra_action else _extra_action
            state['extra']=target
            if target:state['extra_page']=target
            if target=='frames':state['frames_loaded']=True
        for key in ('selected','current'):
            if key in state:state[key]=normalize_style(state[key])
        state['bar'] = bar_preferences()
        state['motion'] = state.get('current') not in ('monochrome', 'terminal', 'retro', 'ascii')
        state['compact_motion'] = read(HOME/'.local/state/desktop-power/status.json').get('policy',{}).get('animation_factor',1) < 1
        save(STATE/'ui.json',state)
    # The resident deflisten receives this atomic write through FileEvents.
    # A second Eww IPC update rebuilt the same bindings twice per interaction.


def extra_action(name):
    if name not in ('bar','frames','close'):raise ValueError('Unknown extra options')
    update(_extra_action=name)


def initial_catalog():
    """Read existing previews only; never run Matugen/decoders before mapping."""
    cached=read(STATE/'preview-catalog.json').get('catalog',{})
    fallback=CONFIG/'previews/loading.svg'
    if not fallback.exists():
        write(fallback,'<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280"><text x="220" y="140" text-anchor="middle" fill="#888888" font-family="sans-serif" font-size="16">Loading preview…</text></svg>')
    catalog={}
    for key,profile in PROFILES.items():
        row=cached.get(key,{})
        raster=CONFIG/'previews'/f'{key}.png'
        preview_path=row.get('preview',str(raster if raster.is_file() else CONFIG/'previews'/f'{key}.svg'))
        swatches=row.get('swatches',str(CONFIG/'previews'/f'{key}-colors.svg'))
        catalog[key]=dict(id=key,**profile,preview=preview_path if Path(preview_path).is_file() else str(fallback),
                          swatches=swatches if Path(swatches).is_file() else str(fallback),count=row.get('count',0))
    return catalog


def preview_signature(source):
    return hashlib.sha256(json.dumps([source,PROFILES,bar_preferences()],sort_keys=True).encode()).hexdigest()


def preview_cache(source):
    cached=read(STATE/'preview-catalog.json')
    catalog=cached.get('catalog',{})
    if cached.get('signature')!=preview_signature(source) or set(catalog)!=set(PROFILES):return None
    if not all(Path(row.get(key,'')).is_file() for row in catalog.values() for key in ('preview','swatches')):return None
    return catalog


def refresh_previews():
    # Run after the listener's first state. Merge only preview fields; a user's
    # selection must survive late results. The apply lock protects shared files.
    try:
        source=source_palette()
        signature=preview_signature(source)
        if preview_cache(source) is not None:return
        initial=read(STATE/'ui.json');current=initial.get('current')
        selected=initial.get('selected','modern')
        catalog=initial_catalog()
        order=([selected] if selected in PROFILES else [])+[k for k in PROFILES if k!=selected]
        for key in order:
            with (STATE/'apply.lock').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                state=read(STATE/'ui.json')
                if state.get('current')!=current or state.get('busy'):return
                if (STATE/'source.json').exists() and read(STATE/'source.json')!=source:return
                catalog[key]=preview(key,source)
                # Keep one publication for the visible preview and one for the
                # completed catalog, rather than rebuilding six choice lists.
                if key==order[0] or key==order[-1]:update(_publish=False,catalog=dict(catalog),choices=list(catalog.values()))
                if key==order[-1]:save(STATE/'preview-catalog.json',dict(signature=signature,catalog=catalog))
    except (OSError,ValueError,subprocess.SubprocessError):
        pass  # Existing previews/controls remain usable; next launch can retry.


def watch():
    from raccon_events import FileEvents
    previous=None;started=False
    with FileEvents([STATE/'ui.json']) as changes:
        while True:
            state=read(STATE/'ui.json')
            if state and state!=previous:
                print(json.dumps(state,ensure_ascii=False),flush=True)
                previous=state
                if not started:
                    started=True
                    threading.Thread(target=refresh_previews,daemon=True).start()
            changes.wait()


def selector_reload_source(state):
    # Eww recreates deflisten from :initial before its first script output.
    # Seed the same transaction so it cannot flash the shipped Modern data.
    state=dict(state, motion=state.get('current') not in ('monochrome','terminal','retro','ascii'), compact_motion=read(HOME/'.local/state/desktop-power/status.json').get('policy',{}).get('animation_factor',1)<1)
    text=(CONFIG/'eww.yuck').read_text()
    pattern=r'(\(deflisten ui :initial )("(?:[^"\\]|\\.)*")'
    match=re.search(pattern,text)
    if not match:raise ValueError('Selector initial state was not found.')
    initial=json.dumps(json.dumps(state,ensure_ascii=False),ensure_ascii=False)
    return text[:match.start(2)]+initial+text[match.end(2):]


def source_palette(refresh=False):
    """Read original wallpaper colors, never a palette already transformed by a style."""
    path=STATE/'source.json'; meta_path=STATE/'source-meta.json'
    raw_path=HOME/'.config/matugen/out/desktop-style-source.json'
    try: image=Path((HOME/'.cache/current-wallpaper').read_text().strip())
    except OSError: image=None
    scheme_path=HOME/'.config/matugen/scheme'
    scheme=scheme_path.read_text().strip() if scheme_path.exists() else 'scheme-tonal-spot'
    signature=None
    if image and image.is_file():
        stat=image.stat()
        signature=hashlib.sha256(f'{image}:{stat.st_size}:{stat.st_mtime_ns}:{scheme}'.encode()).hexdigest()
    def valid(value):
        return isinstance(value,dict) and {'primary','surface','on_surface'} <= value.keys() and all(re.fullmatch(r'#[0-9a-fA-F]{6}',str(v)) for v in value.values())
    meta=read(meta_path); raw=read(raw_path)
    raw_time=raw_path.stat().st_mtime_ns if raw_path.exists() else None
    cached=read(path)
    if valid(raw) and (raw_time != meta.get('raw_mtime') or signature == meta.get('wallpaper')):
        colors=raw
    elif signature and (signature!=meta.get('wallpaper') or refresh or not valid(cached)):
        still=image
        if image.suffix.lower() in ('.mp4','.webm','.mkv','.mov','.gif'):
            still=HOME/'.cache/wallpaper-frame.png'
        result=run(['matugen','image',still,'--dry-run','--json','hex','-m','dark','-t',scheme,'--source-color-index','0'])
        data=json.loads(result.stdout)['colors']
        if isinstance(data.get('dark'),dict):
            colors=data['dark']
        else:
            colors={key:value['dark']['color'] for key,value in data.items() if isinstance(value,dict) and 'dark' in value}
        if not valid(colors):raise ValueError('Matugen did not return a valid wallpaper palette.')
        save(raw_path,colors);raw_time=raw_path.stat().st_mtime_ns
    elif valid(cached):
        colors=cached
    elif read(STATE/'selection.json').get('style','original')=='original':
        colors=dict(re.findall(r'@define-color\s+(\w+)\s+(#[\da-fA-F]{6});',(HOME/'.config/waybar/colors.css').read_text()))
        if not valid(colors):raise ValueError('The original wallpaper palette is missing.')
    else:
        raise ValueError('Original palette not found. Reapply your wallpaper.')
    # Matugen may substitute a blue seed for a neutral photograph. Monochrome
    # follows the image itself, including gray wallpapers, rather than that seed.
    pair=meta.get('image_pair') if signature and signature==meta.get('wallpaper') and meta.get('image_pair_version')==1 else None
    if signature and not pair:
        try:
            from PIL import Image, ImageOps
            still=image if image.suffix.lower() not in ('.mp4','.webm','.mkv','.mov','.gif') else HOME/'.cache/wallpaper-frame.png'
            with Image.open(still) as opened:
                sample=ImageOps.exif_transpose(opened).convert('RGB');sample.thumbnail((160,160))
                indexed=sample.quantize(colors=24)
                table=indexed.getpalette()
                ranked=sorted(indexed.getcolors(),reverse=True)
                candidates=['#'+''.join(f'{v:02x}' for v in table[i*3:i*3+3]) for _,i in ranked]
                dominant=candidates[0]
                contrast=next((c for c in candidates[1:] if contrast_ratio(dominant,c)>=4.5),None)
                if contrast is None:
                    # Retain an image tone, adjusting only enough for readable
                    # text instead of replacing every neutral image with white.
                    contrast=contrasting_tone(dominant,max(candidates,key=lambda c:contrast_ratio(dominant,c)))
                pair=[dominant,contrast]
        except (OSError,ValueError,ImportError):
            pair=None
    colors=dict(colors)
    if pair:colors.update(wallpaper_dominant=pair[0],wallpaper_contrast=pair[1])
    save(path,colors)
    save(meta_path,dict(wallpaper=signature,raw_mtime=raw_time,image_pair=pair,image_pair_version=1))
    return colors


def rgb(color):
    return tuple(int(color[i:i+2], 16) / 255 for i in (1, 3, 5))


def hexcolor(values):
    return '#' + ''.join(f'{round(max(0,min(1,v))*255):02x}' for v in values)


def luminance(color):
    values = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb(color)]
    return sum(v*w for v,w in zip(values, (.2126,.7152,.0722)))


def contrast_ratio(a,b):
    low,high=sorted((luminance(a),luminance(b)))
    return (high+.05)/(low+.05)


def contrasting_tone(background,seed):
    hue,lightness,saturation=colorsys.rgb_to_hls(*rgb(seed))
    end=1 if contrast_ratio(background,'#ffffff')>contrast_ratio(background,'#000000') else 0
    low,high=0,1
    for _ in range(18):
        mid=(low+high)/2
        color=hexcolor(colorsys.hls_to_rgb(hue,lightness+(end-lightness)*mid,saturation))
        if contrast_ratio(background,color)>=4.8:high=mid
        else:low=mid
    return hexcolor(colorsys.hls_to_rgb(hue,lightness+(end-lightness)*high,saturation))


def palette(style, source):
    style=normalize_style(style)
    colors = dict(source)
    if style == 'ascii':
        # An art-directed companion to ASCII Bloom, independent of the active
        # wallpaper. Keep the original source intact for every other profile.
        colors.update(surface='#091523', surface_dim='#091523', background='#091523',
            surface_bright='#253c50', surface_container_lowest='#060f1b',
            surface_container_low='#0c1b2b', surface_container='#102235',
            surface_container_high='#172e43', surface_container_highest='#203a50',
            surface_variant='#203a50', on_surface='#f3e9d2', on_background='#f3e9d2',
            on_surface_variant='#b2c4cc', outline='#7894a4', outline_variant='#526f82',
            primary='#ff9b91', on_primary='#29191e', primary_container='#51303b',
            on_primary_container='#ffe1d9', primary_fixed='#ffe1d9', primary_fixed_dim='#ff9b91',
            on_primary_fixed='#29191e', on_primary_fixed_variant='#51303b',
            secondary='#8bd6de', on_secondary='#082a33', secondary_container='#16414d',
            on_secondary_container='#c2f2f3', secondary_fixed='#c2f2f3', secondary_fixed_dim='#8bd6de',
            on_secondary_fixed='#082a33', on_secondary_fixed_variant='#16414d',
            tertiary='#dec0dc', on_tertiary='#332338', tertiary_container='#4c3750',
            on_tertiary_container='#f5def0', tertiary_fixed='#f5def0', tertiary_fixed_dim='#dec0dc',
            on_tertiary_fixed='#332338', on_tertiary_fixed_variant='#4c3750',
            error='#ffb4ab', on_error='#390e16', error_container='#59232b', on_error_container='#ffdad6',
            inverse_surface='#e4dece', inverse_on_surface='#102235', inverse_primary='#844c48',
            surface_tint='#8bd6de', shadow='#000000', scrim='#000000')
        return colors, [colors[k] for k in ('surface','surface_container','primary','secondary','on_surface')]
    for role in ('primary', 'secondary', 'tertiary'):
        colors.setdefault(role + '_fixed_dim', colors[role])
    h, _, _ = colorsys.rgb_to_hls(*rgb(colors['primary']))
    if style == 'monochrome':
        bg=colors.get('wallpaper_dominant',colors.get('source_color',colors['primary']))
        fg=colors.get('wallpaper_contrast',colors.get('on_primary',colors['on_surface']))
        if contrast_ratio(bg,fg)<4.5:
            fg=max(('#111111','#ffffff'),key=lambda c:contrast_ratio(bg,c))
        for key in colors:
            foreground = key.startswith('on_') or key in ('primary','secondary','tertiary','error','outline','outline_variant','inverse_surface','inverse_primary') or 'fixed_dim' in key
            if key in ('on_primary','on_secondary','on_tertiary','on_error','inverse_on_surface'):
                foreground = False
            colors[key] = fg if foreground else bg
        colors['primary_container']=fg
        colors['on_primary_container']=bg
        return colors, [bg,fg]
    if style == 'retro':
        # Four neutral steps plus twelve chromatic steps, shifted by wallpaper hue.
        swatches = [hexcolor(colorsys.hls_to_rgb(h,l,.16)) for l in (.07,.20,.69,.94)]
        swatches += [hexcolor(colorsys.hls_to_rgb((h+offset)%1,l,.60)) for l in (.32,.70) for offset in (0,1/6,2/6,3/6,4/6,5/6)]
        for key, color in colors.items():
            colors[key] = min(swatches, key=lambda s: sum((a-b)**2 for a,b in zip(rgb(s),rgb(color))))
        colors['surface'] = swatches[0]
        colors['on_surface'] = swatches[3]
        colors['on_surface_variant'] = swatches[2]
        for role in ('primary','secondary','tertiary','error'):
            if luminance(colors[role]) < .35: colors[role] = swatches[10]
            colors['on_'+role] = swatches[0]
            colors['on_'+role+'_container'] = swatches[3]
            colors[role+'_container']=swatches[1]
        return colors, swatches
    return colors, [colors[k] for k in ('surface','surface_container','primary','secondary','tertiary','on_surface')]


def templates():
    entries=tomllib.loads((HOME / '.config/matugen/config.toml').read_text())['templates']
    return {key:value for key,value in entries.items() if key!='desktop_style_source'}


def render(template, colors):
    def replace(match):
        expr = match[1].strip()
        if expr == 'image': return 'wallpaper / desktop-style'
        parts = expr.split('.')
        if len(parts) != 4 or parts[0] != 'colors' or parts[1] not in colors:
            raise ValueError('Unsupported template: ' + expr)
        color = colors[parts[1]]
        fmt = parts[3]
        if fmt == 'hex': return color
        if fmt == 'hex_stripped': return color[1:]
        if fmt in ('red','green','blue'): return str(round(rgb(color)[('red','green','blue').index(fmt)]*255))
        raise ValueError('Unsupported format: ' + fmt)
    return re.sub(r'\{\{(.*?)\}\}', replace, template)


def surfaces(style, colors):
    from desktop_style.appearance import build
    output=build(style,bar_profile(style),colors)
    return tuple(output[key] for key in ('widgets','raccon','waybar','rofi'))


def snapshot(paths):
    return {str(p): p.read_text() if p.exists() else None for p in paths}


def restore(files):
    for name, value in files.items():
        path = Path(name)
        if value is None: path.unlink(missing_ok=True)
        else: write(path, value)


def ensure_import(path, line):
    if not path.exists(): return
    # Read at write time; touch only our own import, preserving concurrent menu edits.
    text = path.read_text()
    if line not in text: write(path, text.rstrip() + '\n\n' + line + '\n')


def integrations(style=None):
    ensure_import(HOME/'.config/waybar/style.css', f'@import "{CURRENT}/waybar.css";')
    ensure_import(HOME/'.config/waybar/style.css', '@import "orientation.css";')
    menu=HOME/'.config/raccon-menu/eww.scss'
    old=f'@import "{CURRENT}/raccon.scss";'
    if menu.exists() and old in menu.read_text():
        write(menu,menu.read_text().replace(old,'@import "desktop-style";'))
    ensure_import(menu,'@import "desktop-style";')
    yuck=HOME/'.config/raccon-menu/eww.yuck'
    if yuck.exists():
        position=bar_preferences()['position']
        text=yuck.read_text().replace('(include "_desktop-layout.yuck")\n','')
        vertical=position in ('left','right')
        text=re.sub(r'(:geometry \(geometry [^\n]*:x )(?:"[^"]+"|\w+)',lambda m:m[1]+('"78px"' if vertical else '"4px"'),text)
        text=re.sub(r'(:geometry \(geometry [^\n]*:y )(?:"[^"]+"|\w+)',lambda m:m[1]+('"4px"' if vertical else '"78px"'),text)
        anchor='bottom '+position if vertical else position+' left'
        text=re.sub(r'(:geometry \(geometry [^\n]*:anchor )(?:"[^"]+"|\w+)',lambda m:m[1]+'"'+anchor+'"',text)
        transition=dict(top='slidedown',bottom='slideup',left='slideright',right='slideleft')[position]
        text=text.replace(':transition desktop_style_transition',':transition "'+transition+'"')
        text=re.sub(r'(:class "shell-revealer"[^\n]*:transition )"(?:slideup|slidedown|slideleft|slideright)"',lambda m:m[1]+'"'+transition+'"',text)
        write(yuck,text)
    for path in (HOME/'.config/rofi').glob('*.rasi'):
        if path.name != 'colors.rasi': ensure_import(path, f'@import "{CURRENT}/rofi.rasi"')
    ensure_import(CONFIG/'eww.scss',f'@import "{CURRENT}/selector.scss";')
    for name in ('swaync','swayosd'):
        ensure_import(HOME/'.config'/name/'style.css',f'@import "{CURRENT}/{name}.css";')


def configure_bar(style):
    from desktop_style.waybar import Document, compact
    path = HOME/'.config/waybar/config.jsonc'
    text = path.read_text()
    original_text = text
    previous = re.search(r'"position"\s*:\s*"(\w+)"',text)[1]
    prefs=bar_preferences();continuous=prefs['layout']=='continuous'
    position=prefs['position']
    vertical=position in ('left','right')
    horizontal=STATE/'waybar-horizontal.json'
    text,saved=compact(text,vertical,read(horizontal,[]))
    values=dict(position=position)
    for edge in ('top','bottom','left','right'):
        along=edge in (('top','bottom') if vertical else ('left','right'))
        values['margin-'+edge]=0 if continuous else 14 if along else 10 if edge==position else 0
    for key,value in values.items():
        text=Document(text).patch((key,),value)
    write(path,text)
    if saved:save(horizontal,saved)
    else:horizontal.unlink(missing_ok=True)
    return previous != position or text != original_text


def set_bar(key, value):
    if key not in ('position','layout') or value not in ({'top','bottom','left','right'} if key=='position' else {'islands','continuous'}):
        raise ValueError('Use bar position top|bottom|left|right or bar layout islands|continuous')
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'apply.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        prefs=bar_preferences();prefs[key]=value
        paths=[CONFIG/'waybar.json',HOME/'.config/waybar/config.jsonc',CURRENT/'waybar.css',CURRENT/'tokens.json',STATE/'waybar-horizontal.json']
        previous=snapshot(paths)
        try:
            save(CONFIG/'waybar.json',prefs)
            style=read(STATE/'selection.json').get('style','modern')
            if style not in PROFILES:style='modern'
            tokens=read(CURRENT/'tokens.json')
            colors=tokens.get('colors') or palette(style,source_palette())[0]
            from desktop_style.appearance import build
            appearance=build(style,bar_profile(style),colors)
            write(CURRENT/'waybar.css',appearance['waybar'])
            if tokens:
                tokens.update(position=prefs['position'],continuous=prefs['layout']=='continuous')
                save(CURRENT/'tokens.json',tokens)
            configure_bar(style)
            reload_bar_style()
            # An explicit preference action also loads edits made on disk since
            # Waybar started, even when the saved value already matches.
            restart_bar()
        except Exception:
            restore(previous)
            reload_bar_style()
            raise
        update(notice='Bar preferences saved')
    refresh_previews()


BAR_KEYS = ('position','margin-top','margin-left','margin-right','margin-bottom')
WINDOW_KEYS = ('rounded_corner_radius','border_size','shadow_radius','title_font')


def managed_settings():
    bar=(HOME/'.config/waybar/config.jsonc').read_text()
    ini=(HOME/'.config/wayfire.ini').read_text()
    section=re.search(r'(?ms)^\[pixdecor\]\n(.*?)(?=^\[|\Z)',ini)[1]
    result=dict(bar={k:json.loads(re.search(r'"'+k+r'"\s*:\s*("[^"]*"|\d+)',bar)[1]) for k in BAR_KEYS},
                window={k:re.search(r'(?m)^'+k+r'\s*=\s*(.*)$',section)[1] for k in WINDOW_KEYS})
    fuzzel=HOME/'.config/fuzzel/fuzzel.ini'
    if fuzzel.exists():
        parser=configparser.ConfigParser(interpolation=None);parser.read(fuzzel)
        result['fuzzel']={sec:{key:parser.get(sec,key,fallback=None) for key in keys} for sec,keys in {'main':['font'],'border':['radius','width']}.items()}
    return result


def set_managed(settings):
    path=HOME/'.config/waybar/config.jsonc'; text=path.read_text(); old=text
    for key,value in settings['bar'].items():
        text=re.sub(r'("'+key+r'"\s*:\s*)("[^"]*"|\d+)',lambda m:m[1]+json.dumps(value),text,count=1)
    write(path,text)
    bar_changed=text!=old
    if (HOME/'.config/wayfire/raccon.ini').exists():
        from wayfire_config import set_options
        set_options(HOME/'.config', 'pixdecor', settings['window'])
    else:
        path=HOME/'.config/wayfire.ini'; ini=path.read_text()
        def change(match):
            section=match[0]
            for key,value in settings['window'].items():
                section=re.sub(r'(?m)^('+key+r'\s*=\s*).*$',lambda m:m[1]+str(value),section,count=1)
            return section
        write(path,re.sub(r'(?ms)^\[pixdecor\]\n.*?(?=^\[|\Z)',change,ini))
    if settings.get('fuzzel'):
        path=HOME/'.config/fuzzel/fuzzel.ini';text=path.read_text()
        for section,values in settings['fuzzel'].items():
            def patch_section(match):
                block=match[0]
                for key,value in values.items():
                    pattern=r'(?m)^'+re.escape(key)+r'\s*=.*$'
                    if value is None:block=re.sub(pattern+'\n?','',block)
                    elif re.search(pattern,block):block=re.sub(pattern,lambda m:key+'='+value,block)
                    else:block=block.rstrip()+'\n'+key+'='+value+'\n\n'
                return block
            text=re.sub(r'(?ms)^\['+re.escape(section)+r'\]\n.*?(?=^\[|\Z)',patch_section,text)
        write(path,text)
    return bar_changed


def configure_windows(style):
    settings=managed_settings(); p=PROFILES[style]
    settings['window'].update(rounded_corner_radius=str(p['radius']),border_size=str(p['border']),
                              shadow_radius='24' if style=='glass' else '0',title_font=p['font']+' 10')
    if settings.get('fuzzel'):
        settings['fuzzel']['main']['font']=p['font']+':size=12'
        settings['fuzzel']['border'].update(radius=str(p['radius']),width=str(p['border']))
    set_managed(settings)


def restart_bar():
    groups = {}
    # Snapshot first: iterating /proc while spawning can visit our own new bar
    # again. Restart once per configuration/display, also removing duplicates.
    for proc in list(Path('/proc').iterdir()):
        if not proc.name.isdigit(): continue
        try:
            if proc.stat().st_uid != os.getuid(): continue
            args = [v.decode() for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
            if not args or Path(args[0]).name != 'waybar': continue
            env = dict(v.decode().split('=',1) for v in (proc/'environ').read_bytes().split(b'\0') if b'=' in v)
            if env.get('WAYLAND_DISPLAY') != os.environ.get('WAYLAND_DISPLAY'): continue
            key=(tuple(args),env.get('WAYLAND_DISPLAY'))
            group=groups.setdefault(key,dict(args=args,env=env,pids=[]))
            group['pids'].append(int(proc.name))
        except (FileNotFoundError,ProcessLookupError): pass
    launcher=HOME/'.config/waybar/launch.sh'
    if groups and launcher.is_file():
        # Use the existing supervisor's own replacement protocol. Killing only
        # its child would make it respawn alongside our replacement.
        group=next(iter(groups.values()))
        with (STATE/'waybar.log').open('ab') as log:
            child=subprocess.Popen([str(launcher)],env=group['env'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        if isinstance(child.pid,int):
            deadline=time.monotonic()+5
            status_log=Path(group['env'].get('XDG_CACHE_HOME',str(HOME/'.cache')))/'waybar.log'
            while time.monotonic()<deadline:
                try:
                    children=Path(f'/proc/{child.pid}/task/{child.pid}/children').read_text().split()
                    ready=any(Path(f'/proc/{pid}/comm').read_text().strip()=='waybar' for pid in children)
                    if ready and 'Bar configured' in status_log.read_text():break
                except OSError:pass
                time.sleep(.1)
        return
    for group in groups.values():
        for pid in group['pids']:
            try: os.kill(pid,15)
            except ProcessLookupError: pass
        deadline=time.monotonic()+2
        while any(Path(f'/proc/{pid}').exists() for pid in group['pids']) and time.monotonic()<deadline:
            time.sleep(.025)
        with (STATE/'waybar.log').open('ab') as log:
            subprocess.Popen(group['args'],env=group['env'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)


def reload_bar_style():
    # Gio's file monitor needs a write/close event on a stable entrypoint inode.
    entry=HOME/'.config/waybar/style.css'
    if entry.exists():
        content=entry.read_bytes()
        with entry.open('wb') as stream:stream.write(content)


def refresh_clients(bar_restart=False):
    warnings = []
    commands=[[BIN/'wayfire-theme-apply']]
    if (BIN/'raccon-float').is_file(): commands.append([BIN/'raccon-float','refresh'])
    if widgets_available():commands.append([BIN/'widgetctl','theme'])
    if shutil.which('swaync-client'):commands.append(['swaync-client','-rs'])
    for command in commands:
        try:
            result = run(command,False)
            if result.returncode: warnings.append(str(command[0])+': '+result.stderr.strip()[:160])
        except (OSError,subprocess.TimeoutExpired) as exc: warnings.append(str(exc))
    # Kitty reads generated colors on SIGUSR1; Eww and Waybar watch their CSS.
    run(['pkill','-SIGUSR1','-u',str(os.getuid()),'-x','kitty'],False)
    # Waybar accepts CHANGES_DONE_HINT, not an mtime/attribute event. Keep the
    # entrypoint inode and close a real write after every generated import lands.
    reload_bar_style()
    if bar_restart: restart_bar()
    # SwayOSD loads CSS at process startup; refresh just its existing instance.
    servers=[]
    for proc in list(Path('/proc').iterdir()):
        if not proc.name.isdigit():continue
        try:
            if proc.stat().st_uid!=os.getuid():continue
            args=[v.decode() for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
            if not args or Path(args[0]).name!='swayosd-server':continue
            env=dict(v.decode().split('=',1) for v in (proc/'environ').read_bytes().split(b'\0') if b'=' in v)
            if env.get('WAYLAND_DISPLAY')==os.environ.get('WAYLAND_DISPLAY'):servers.append((int(proc.name),args,env))
        except (OSError,ValueError):continue
    if servers:
        for pid,_,_ in servers:
            try:os.kill(pid,15)
            except ProcessLookupError:pass
        time.sleep(.1)
        with (STATE/'osd.log').open('ab') as log:
            subprocess.Popen(servers[0][1],env=servers[0][2],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    return warnings


def apply(style, wallpaper=False):
    style=normalize_style(style)
    if style not in PROFILES: raise ValueError('Unknown style: '+style)
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'apply.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        update(busy=True,notice='Applying style…')
        source = source_palette(refresh=wallpaper)
        catalog=preview_catalog(source)
        if not (STATE/'geometry.json').exists(): save(STATE/'geometry.json',managed_settings())
        before_settings=managed_settings()
        original_geometry=read(STATE/'geometry.json')
        for key,value in before_settings.items():original_geometry.setdefault(key,value)
        save(STATE/'geometry.json',original_geometry)
        before_widget_style=read(HOME/'.config/eww/style.json')
        colors, swatches = palette(style,source)
        outputs = {}
        for name, entry in templates().items():
            if name=='desktop_style_source':continue
            src = Path(entry['input_path']).expanduser()
            dst = Path(entry['output_path']).expanduser()
            outputs[dst] = render(src.read_text(),colors)
        from desktop_style.appearance import build
        appearance=build(style,bar_profile(style),colors)
        widgets,menu,bar,rofi=(appearance[k] for k in ('widgets','raccon','waybar','rofi'))
        widget_palette = HOME/'.local/state/randly-widgets/palette.scss'
        if widgets_available():
            outputs.setdefault(widget_palette,''.join(f'${key}: {value};\n' for key,value in colors.items()))
            try:native=json.loads(run([BIN/'widgetctl','manager-status']).stdout).get('global_style',False)
            except (OSError,ValueError,subprocess.SubprocessError):native=False
            if not native:
                # Compatibility for an older installed manager. New managers
                # load the same overrides after the generated module defaults.
                outputs[widget_palette]+='\n'+widgets
        if style in ('monochrome','retro'):
            # Constrain fixed ANSI colors and opacity suffixes as well as semantic roles.
            def nearest(match):
                value=match[0][:7]
                chosen=min(swatches,key=lambda s:sum((a-b)**2 for a,b in zip(rgb(s),rgb(value))))
                return chosen+('ff' if len(match[0])==9 else '')
            for path in outputs:
                outputs[path]=re.sub(r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b',nearest,outputs[path])
            if HOME/'.config/cava/config' in outputs:
                outputs[HOME/'.config/cava/config']=outputs[HOME/'.config/cava/config'].replace('gradient = 1','gradient = 0')+f"\nforeground = '{colors['primary']}'\n"
        outputs.update({CURRENT/'raccon.scss':menu,CURRENT/'waybar.css':bar,CURRENT/'rofi.rasi':rofi})
        for name in ('widgets','panels','swaync','swayosd'):
            outputs[CURRENT/(name+'.css')]=appearance[name]
        outputs[CURRENT/'selector.scss']=appearance['selector']
        outputs[CURRENT/'tokens.json']=with_widget_frame(appearance['tokens'])
        outputs[CURRENT/'widget-editor.css']=appearance['widget_editor']
        outputs[HOME/'.config/rofi/colors.rasi']=appearance['rofi_colors']
        outputs[HOME/'.config/raccon-menu/_desktop-style.scss']=menu
        outputs[CONFIG/'_palette.scss']=''.join(f'${key}: {value};\n' for key,value in colors.items())
        kitty=HOME/'.config/kitty/colors.conf'
        if kitty in outputs:
            outputs[kitty]+=f'\n# Shared desktop appearance\nfont_family {PROFILES[style]["font"]}\nbackground_opacity {PROFILES[style]["alpha"]}\n'
            if style=='monochrome':
                outputs[kitty]=re.sub(r'(?m)^(color\d+)\s+.*$',lambda m:m[1]+' '+(colors['surface'] if m[1]=='color0' else colors['on_surface']),outputs[kitty])
        fuzzel=HOME/'.config/fuzzel/colors.ini'
        if fuzzel in outputs:
            tokens=json.loads(appearance['tokens']);opacity=f'{round(tokens["opacity"]*255):02x}'
            mappings={'background':colors['surface_container']+opacity,'text':colors['on_surface']+'ff',
                'prompt':colors['primary']+'ff','placeholder':colors['on_surface_variant']+'ff',
                'input':colors['on_surface']+'ff','match':colors['primary']+'ff',
                'selection':colors['primary']+'ff','selection-text':colors['on_primary']+'ff',
                'selection-match':colors['on_primary']+'ff','counter':colors['on_surface_variant']+'ff','border':colors['outline_variant']+'ff'}
            outputs[fuzzel]='[colors]\n'+''.join(f'{k}={v[1:]}\n' for k,v in mappings.items())
        # Every application shares the same shape/font through its native stylesheet.
        for gtk in ('gtk-3.0','gtk-4.0'):
            path=HOME/'.config'/gtk/'colors.css'
            if path in outputs:outputs[path]+='\n'+appearance['gtk']
        initial=read(STATE/'ui.json')
        initial.update(catalog=catalog,choices=list(catalog.values()),current=style,selected=style,frame=widget_frame(style),busy=True,notice='Applying style…')
        outputs[CONFIG/'eww.yuck']=selector_reload_source(initial)
        previous = snapshot(outputs)
        original=read(STATE/'original.json')
        # The selector program evolves independently of appearance backups.
        # Restoring an older Yuck tree can remove its card and prewarm guard.
        original.pop(str(CONFIG/'eww.yuck'),None)
        for key,value in previous.items():
            if key!=str(CONFIG/'eww.yuck'):original.setdefault(key,value)
        save(STATE/'original.json',original)
        previous.update(snapshot([HOME/'.config/waybar/config.jsonc', STATE/'waybar-horizontal.json']))
        # Validate standalone GTK styles before publishing any outputs.
        for name in ('raccon','waybar','selector','widgets','panels','swaync','swayosd','gtk','widget_editor'):
            validate_css(appearance[name])
        with tempfile.TemporaryDirectory() as tmp:
            for index, text in enumerate([outputs[widget_palette]] if widgets_available() else []):
                src=Path(tmp)/f'{index}.scss'; src.write_text(text)
                run([BIN/'widgetctl','compile-css',src,Path(tmp)/f'{index}.css'])
        from desktop_style.transition import ShellTransition
        with ShellTransition(enabled=os.environ.get('DESKTOP_STYLE_NO_TRANSITION') != '1'):
            try:
                # Eww reloads the whole window on a stylesheet event. Publish its
                # palette and overrides together, after the other application files.
                menu_root=HOME/'.config/raccon-menu'
                eww_outputs={p:t for p,t in outputs.items() if p.is_relative_to(CONFIG) or p.is_relative_to(menu_root)}
                for path,text in outputs.items():
                    if path not in eww_outputs:write(path,text)
                for path,text in eww_outputs.items():write(path,text)
                # The menu palette resolves current/tokens.json. Publish the
                # new contract before asking resident popups to adopt it.
                backend=HOME/'.local/lib/raccon_menu/backend.py'
                if backend.is_file():run([sys.executable,backend,'palette'])
                integrations(style)
                # Keep the preview/current label synchronized with the palette,
                # while slower client refreshes finish behind the applying state.
                update(catalog=catalog,choices=list(catalog.values()),current=style,selected=style,frame=widget_frame(style),busy=True,notice='Applying style…')
                # Style options are managed through the existing widget API/lock.
                if widgets_available():
                    widget_style=json.loads(with_widget_frame(appearance['tokens']))['widgets']
                    run([BIN/'widgetctl','style',widget_style['skin'],widget_style['fx'],widget_style['background'],widget_style['frame']])
                restart=configure_bar(style)
                configure_windows(style)
                warnings=refresh_clients(restart)
                save(STATE/'selection.json',dict(style=style,name=PROFILES[style]['name'],swatches=swatches,warnings=warnings))
                update(catalog=catalog,choices=list(catalog.values()),current=style,selected=style,frame=widget_frame(style),busy=False,notice='Style applied' if not warnings else 'Applied; check desktop-style status for details.')
            except Exception:
                restore(previous)
                set_managed(before_settings)
                if widgets_available() and before_widget_style:
                    run([BIN/'widgetctl','style',before_widget_style['skin'],before_widget_style['fx'],before_widget_style['background'],before_widget_style.get('frame','none')],False)
                refresh_clients()
                update(current=read(STATE/'selection.json').get('style','original'),busy=False,notice='Could not apply. Color files were restored.')
                raise


def preview(style, source):
    c,swatches=palette(style,source)
    p=bar_profile(style); r=p['radius']; bg=c['surface']; panel=c['surface_container']; fg=c['on_surface']; accent=c['primary']; edge=c['outline_variant']
    ybar=0 if p['position']=='top' else 234
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280" viewBox="0 0 440 280"><rect width="440" height="280" rx="12" fill="{bg}"/>']
    if style=='glass':
        svg.append(f'<path d="M0 120 L440 20 V200 L0 280 Z" fill="{accent}" opacity=".42"/>')
    def rect(x,y,w,h,fill,rad=r): svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rad}" fill="{fill}" fill-opacity="{p["alpha"]}" stroke="{edge}" stroke-width="{p["border"]}"/>')
    def label(x,y,text,size=12,color=fg): svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="{escape(p["font"])}" font-size="{size}">{escape(text)}</text>')
    rect(18,48,130,88,panel); label(30,78,'10:24',25); label(30,105,'My desktop',10)
    rect(166,48,254,158,panel); label(182,76,'Raccon Menu',14)
    for i,name in enumerate(('Apps','Files','Terminal')):
        rect(180+i*76,94,66,64,bg,min(r,8)); label(185+i*76,134,name,9)
    rect(180,173,226,19,bg,min(r,5)); label(188,186,'Search apps',9)
    if p['continuous']:
        rect(0,ybar,440,34,panel,0)
    else:
        rect(14,ybar,94,32,panel); rect(162,ybar,116,32,panel); rect(318,ybar,108,32,panel)
    label(25,ybar+21,'Apps',11); label(180,ybar+21,'1   2   3',11,accent); label(334,ybar+21,'73%  10:24',10)
    if style=='terminal': label(24,170,'> working_',12,accent)
    if style=='ascii':
        label(24,160,'+--[ night ]--+',11,c['secondary'])
        label(28,178,': * + # + * :',11,fg)
        label(28,194,'  + @ # @ +',11,accent)
        label(182,65,'[ raccon / menu ]',10,c['secondary'])
    if style=='retro':
        for x,y in ((26,156),(34,156),(50,156),(58,156),(26,164),(34,164),(42,164),(50,164),(58,164),(34,172),(50,172)):
            rect(x,y,8,8,accent,0)
    svg.append('</svg>')
    path=CONFIG/'previews'/f'{style}.svg';write(path,''.join(svg))
    # Decode a small cached raster when opening the picker. SVG/font rendering
    # belongs to this background preparation, once per palette/layout change.
    image_path=path.with_suffix('.png')
    if not image_path.is_file() or image_path.stat().st_mtime_ns<path.stat().st_mtime_ns:
        run(['rsvg-convert',path,'-o',image_path])
    path=image_path
    swatch=CONFIG/'previews'/f'{style}-colors.svg'
    write(swatch,'<svg xmlns="http://www.w3.org/2000/svg" width="440" height="20">'+''.join(f'<rect x="{i*440/len(swatches)}" width="{440/len(swatches)+.1}" height="20" fill="{s}"/>' for i,s in enumerate(swatches))+'</svg>')
    return dict(id=style,**p,preview=str(path),swatches=str(swatch),count=len(swatches))


def preview_catalog(source):
    cached=preview_cache(source)
    if cached is not None:return cached
    catalog={key:preview(key,source) for key in PROFILES}
    save(STATE/'preview-catalog.json',dict(signature=preview_signature(source),catalog=catalog))
    return catalog


def safe_selector_enabled():
    return read(CONFIG/'selector.json').get('backend') == 'rofi'


def open_safe_selector():
    # Temporary alternate UI for hosts where mapping the Eww selector ends the
    # compositor session. Merely opening/cancelling must not touch that daemon.
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'selector.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        current = read(STATE/'selection.json').get('style', 'original')
        keys = list(PROFILES) + ['original']
        labels = [PROFILES[key]['name'] for key in PROFILES] + ['Restore original']
        labels = [label + (' — Active' if key == current else '')
                  for key, label in zip(keys, labels)]
        env = dict(os.environ)
        env.pop('GTK_MODULES', None)
        result = subprocess.run(
            ['rofi', '-no-config', '-dmenu', '-i', '-no-custom', '-format', 'i',
             '-p', 'Desktop style', '-mesg', 'Enter to apply · Esc to cancel',
             '-selected-row', str(keys.index(current) if current in keys else 0),
             '-theme-str', 'window { width: 480px; } listview { lines: 8; }'],
            input='\n'.join(labels)+'\n', capture_output=True, text=True, env=env)
        if result.returncode == 1:  # Escape / dismiss
            return
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'Could not open the style selector')
        choice = result.stdout.strip()
        if not choice.isdecimal() or not 0 <= int(choice) < len(keys):
            return
        style = keys[int(choice)]
        if style == current:
            return
        if style == 'original':
            reset()
        else:
            if not (STATE/'settings.json').exists():
                save(STATE/'settings.json', read(HOME/'.config/eww/style.json'))
            apply(style)


def widget_frame(style=None):
    style=normalize_style(style or read(STATE/'selection.json').get('style','modern'))
    state=read(STATE/'widget-frame.json',{})
    choices=state.get('styles',{})
    frame=choices.get(style,'auto') if isinstance(choices,dict) and 'styles' in state else state.get('frame','auto')
    return frame if frame in WIDGET_FRAMES else 'auto'


def with_widget_frame(tokens):
    data=json.loads(tokens)
    frame=widget_frame(data.get('style'))
    if frame!='auto':data['widgets']['frame']=frame
    return json.dumps(data,ensure_ascii=False,indent=2)+'\n'


def set_widget_frame(frame, style=None):
    if frame not in WIDGET_FRAMES: raise ValueError('Unknown frame')
    current=read(STATE/'selection.json').get('style')
    style=normalize_style(style or (current if current in PROFILES else 'modern'))
    if style not in PROFILES:raise ValueError('Unknown style')
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'widget-frame.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=read(STATE/'widget-frame.json',{})
        if isinstance(previous.get('styles'),dict):
            choices={k:v for k,v in previous['styles'].items() if k in PROFILES and v in WIDGET_FRAMES}
        else:
            # Preserve an older global override for every other theme on migration.
            legacy=previous.get('frame','auto')
            choices={k:legacy for k in PROFILES} if legacy in WIDGET_FRAMES and legacy!='auto' else {}
        choices[style]=frame
        save(STATE/'widget-frame.json',dict(version=2,styles=choices))
    tokens=CURRENT/'tokens.json'
    if current==style and tokens.exists():
        from desktop_style.appearance import resolve
        data=json.loads(tokens.read_text())
        data['widgets']['frame']=resolve(current,PROFILES[current],data['colors'])['widgets']['frame']
        # Publish just the inherited frame; never rewrite per-widget choices.
        write(tokens,with_widget_frame(json.dumps(data)))
        if widgets_available():
            general=json.loads(run([BIN/'widgetctl','style']).stdout)
            if isinstance(general,dict) and 'frame' in general:
                resolved=json.loads(with_widget_frame(json.dumps(data)))['widgets']['frame']
                run([BIN/'widgetctl','style','--frame',resolved])
    suffix='' if current==style else ' · saved for this theme'
    update(frame=frame,notice=PROFILES[style]['name']+': '+WIDGET_FRAMES[frame]+suffix)


def selector_module():
    """Own GTK adapter; never replace another Eww project's resident daemon."""
    import shlex
    here=Path(__file__).resolve().parent
    target=HOME/'.cache/desktop-style/selector.so'
    target.parent.mkdir(parents=True,exist_ok=True)
    sources=(here/'selector_input.c',here.parent/'raccon_menu/navigation.h',here.parent/'raccon_menu/resident_surface.h',here.parent/'raccon_menu/soft_icons.h',here.parent/'raccon_menu/popup_geometry.h')
    with (target.parent/'build.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not target.exists() or target.stat().st_mtime_ns < max(p.stat().st_mtime_ns for p in sources):
            flags=shlex.split(run(['pkg-config','--cflags','--libs','gtk+-3.0']).stdout)
            temp=target.with_name(f'selector-{os.getpid()}.so')
            try:
                run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-Wno-unused-parameter','-I',here.parent/'raccon_menu',sources[0],'-o',temp,*flags])
                temp.replace(target)
            finally:temp.unlink(missing_ok=True)
    return target


def selector_revision():
    here=Path(__file__).resolve().parent
    sources=[here/'selector_input.c',here.parent/'raccon_menu/navigation.h']
    # The resident only loads this native module. Python runs in separate
    # commands/listeners; changing a name or renderer must not restart GTK.
    sources.extend(p for p in (here.parent/'raccon_menu/resident_surface.h',here.parent/'raccon_menu/soft_icons.h',here.parent/'raccon_menu/popup_geometry.h') if p.is_file())
    return str(max(p.stat().st_mtime_ns for p in sources))


def selector_send(command):
    """Use the resident GTK window without starting an Eww IPC client."""
    root=Path(os.environ.get('XDG_RUNTIME_DIR',HOME/'.cache'))/'desktop-style'
    try:
        if (root/'revision').read_text().strip()!=selector_revision() or not (root/'mapped').exists():return False
        fd=os.open(root/'control',os.O_WRONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
        try:
            info=os.fstat(fd)
            if not stat.S_ISFIFO(info.st_mode) or info.st_uid!=os.getuid():return False
            os.write(fd,(command+'\n').encode())
            return True
        finally:os.close(fd)
    except OSError:return False


def selector_daemon_running():
    # An absent Eww daemon otherwise costs ~1 second for every attempted IPC.
    try:
        return subprocess.run(['eww','--no-daemonize','-c',str(CONFIG),'ping'],
                              capture_output=True,timeout=.15).returncode==0
    except subprocess.TimeoutExpired:return False


def close_selector():
    if selector_send('hide'):return
    if not selector_daemon_running():return
    if 'styles:' not in eww('active-windows').stdout:return
    eww('update','selector_closing=true')
    time.sleep(.16)
    eww('close','styles')


def open_selector(prewarm=False):
    if safe_selector_enabled():
        return open_safe_selector()
    if selector_send('ping' if prewarm else 'show'):return
    STATE.mkdir(parents=True,exist_ok=True)
    catalog=initial_catalog()
    current=read(STATE/'selection.json').get('style','original')
    update(_publish=False,catalog=catalog,choices=list(catalog.values()),selected=current if current in PROFILES else 'modern',current=current,busy=False,notice='',
           extra='',extra_page='bar',frames_loaded=False,
           frame=widget_frame(current if current in PROFILES else 'modern'),frames=[[dict(id=k,name=WIDGET_FRAMES[k],icon=WIDGET_FRAME_ICONS[k]) for k in list(WIDGET_FRAMES)[i:i+5]] for i in range(0,len(WIDGET_FRAMES),5)])
    # Seed once before launch so neither the window nor its listener flashes old data.
    write(CONFIG/'eww.yuck',selector_reload_source(read(STATE/'ui.json')))
    module=selector_module()
    revision=str(max(module.stat().st_mtime_ns,int(selector_revision())))
    loaded=STATE/'selector-revision'
    running=selector_daemon_running()
    if running and read(loaded,{}).get('revision')!=revision:
        eww('kill');running=False
    if not running:
        env=dict(os.environ,GTK_MODULES=str(module),RACCON_STYLE_KEYS='1',RACCON_STYLE_REVISION=selector_revision(),LANGUAGE='en_US:en',LC_MESSAGES='en_US.UTF-8')
        with (STATE/'eww.log').open('ab') as log:
            subprocess.Popen(['eww','-c',str(CONFIG),'daemon','--no-daemonize'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        for _ in range(40):
            if selector_daemon_running(): break
            time.sleep(.05)
        else: raise RuntimeError('Eww did not start. Check ~/.local/state/desktop-style/eww.log')
        save(loaded,dict(revision=revision))
    # The seeded config and FileEvents listener already contain the UI state.
    eww('update','selector_closing=false',f'selector_prewarm={str(prewarm).lower()}')
    result=eww('open','styles')
    if result.returncode:
        # The short Eww IPC deadline can expire after GTK has already mapped
        # the window. Confirm ownership before ever issuing a second open.
        if 'styles:' not in eww('active-windows').stdout:
            time.sleep(.15)
            eww('open','styles',check=True)
    if not prewarm:
        # A recreated resident may still be completing its invisible warmup.
        # Deliver the actual user's show intent after the new adapter binds.
        for _ in range(20):
            if selector_send('show'):break
            time.sleep(.01)


def toggle_selector():
    if safe_selector_enabled():
        return open_safe_selector()
    if selector_send('toggle'):return
    # A stale/missing adapter must recover directly. Querying and closing its
    # old window first consumed an extra click and several synchronous IPCs.
    open_selector()


def reset():
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'apply.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        original=read(STATE/'original.json')
        if not original: return
        # Also ignore the UI program in backups made by previous releases.
        restore({key:value for key,value in original.items() if key!=str(CONFIG/'eww.yuck')})
        for name in ('raccon.scss','waybar.css','rofi.rasi','widgets.css','panels.css','selector.scss','swaync.css','swayosd.css','widget-editor.css'):
            write(CURRENT/name,'/* Original appearance */\n')
        (CURRENT/'tokens.json').unlink(missing_ok=True)
        write(HOME/'.config/raccon-menu/_desktop-style.scss','/* Original appearance */\n')
        backend=HOME/'.local/lib/raccon_menu/backend.py'
        if backend.is_file():run([sys.executable,backend,'palette'])
        integrations('original')
        write(CONFIG/'_palette.scss',''.join(f'${k}: {v};\n' for k,v in source_palette().items()))
        settings=read(STATE/'settings.json')
        if widgets_available() and settings:
            run([BIN/'widgetctl','style',settings['skin'],settings['fx'],settings['background'],settings.get('frame','none')])
        geometry=read(STATE/'geometry.json')
        restart=set_managed(geometry) if geometry else False
        restart=configure_bar('modern') or restart
        if bar_preferences()['layout']=='continuous':
            write(CURRENT/'waybar.css','window#waybar { background: @surface_container; }\nwindow#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar { background: transparent; border: none; border-radius: 0; }\n')
        prefs=bar_preferences();inset=0 if prefs['layout']=='continuous' else 8
        padding=dict(top=f'0 0 {inset}px 0',bottom=f'{inset}px 0 0 0',left=f'0 {inset}px 0 0',right=f'0 0 0 {inset}px')[prefs['position']]
        write(CURRENT/'waybar.css',(CURRENT/'waybar.css').read_text()+f'window#waybar.{prefs["position"]} > box {{ padding: {padding}; }}\n')
        save(STATE/'selection.json',dict(style='original',name='Original'))
        refresh_clients(restart)
        update(current='original',notice='Original appearance restored',busy=False)


def companion_wallpaper(style):
    if style != 'ascii':
        raise ValueError('This style has no companion wallpaper')
    path = HOME / '.local/share/wallpapers/raccon/ascii-bloom.png'
    if not path.is_file():
        raise ValueError('No Night wallpaper: put your own image at ~/.local/share/wallpapers/raccon/ascii-bloom.png')
    # Reuse the guarded transaction, including duplicate detection and palette
    # refresh. Never call the wallpaper backend directly from the selector.
    subprocess.run([str(BIN/'wallpaper-set'), str(path)], capture_output=True,
                   text=True, timeout=90, check=True)
    update(notice='Night wallpaper selected')


def apply_sddm():
    """Publish the active appearance only after interactive system authentication."""
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'apply.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        assets = HOME/'.local/share/raccon/sddm'
        tokens = read(CURRENT/'tokens.json')
        if tokens.get('style') not in PROFILES:
            update(notice='Apply a desktop style before updating SDDM')
            return
        if not all((assets/name).is_file() for name in ('prepare.py', 'apply.sh', 'raccon/Main.qml')):
            update(notice='SDDM theme files are missing; reinstall desktop-styles')
            return
        if not shutil.which('pkexec'):
            update(notice='Install polkit to authenticate the SDDM update')
            return
        runtime = Path(os.environ.get('XDG_RUNTIME_DIR', HOME/'.cache'))/'desktop-style'
        try:
            was_visible = (runtime/'visible').read_text().strip() == '1'
        except OSError:
            was_visible = False
        notice = 'Could not update SDDM; try again'
        update(busy=True, sddm_busy=True, notice='Preparing login screen…')
        try:
            # Prepare as the user. Elevate only the existing system installer,
            # with a private, fresh snapshot that cannot race another preview.
            with tempfile.TemporaryDirectory(prefix='raccon-sddm-') as temp:
                theme = Path(temp)/'theme'
                subprocess.run([sys.executable, str(assets/'prepare.py'), '--home', str(HOME),
                                '--output', str(theme)], capture_output=True, text=True,
                               timeout=30, check=True)
                update(notice='Authenticate to update the login screen')
                # The overlay must yield focus to the desktop's polkit agent.
                if was_visible:
                    close_selector()
                result = subprocess.run(['pkexec', '/usr/bin/bash', str(assets/'apply.sh'), str(theme)],
                                        capture_output=True, text=True, timeout=300)
                write(STATE/'sddm.log', result.stdout + result.stderr)
                if result.returncode == 0:
                    notice = 'SDDM updated · visible at next login'
                elif result.returncode == 126:
                    notice = 'SDDM update canceled'
                elif result.returncode == 127:
                    notice = 'Authentication failed; retry with the polkit agent running'
                else:
                    notice = 'Could not update SDDM; see ~/.local/state/desktop-style/sddm.log'
        except subprocess.TimeoutExpired:
            notice = 'SDDM update timed out; try again'
        except (OSError, subprocess.CalledProcessError) as exc:
            write(STATE/'sddm.log', str(exc) + '\n' + (getattr(exc, 'stderr', '') or ''))
            notice = 'Could not update SDDM; see ~/.local/state/desktop-style/sddm.log'
        finally:
            update(busy=False, sddm_busy=False, notice=notice)
            if was_visible:
                open_selector()
                update(notice=notice)


def main():
    args=sys.argv[1:] or ['open']; command=args[0]
    migrate_theme_state()
    selector_lock=None
    if command in ('open','toggle','close','prewarm'):
        STATE.mkdir(parents=True,exist_ok=True)
        selector_lock=(STATE/'visibility.lock').open('w')
        fcntl.flock(selector_lock,fcntl.LOCK_EX)
    try:
        if command=='open': open_selector()
        elif command=='prewarm':
            if not safe_selector_enabled():open_selector(prewarm=True)
        elif command=='toggle':toggle_selector()
        elif command=='close': close_selector()
        elif command=='select':
            style=normalize_style(args[1])
            if style not in PROFILES: raise ValueError('Unknown style')
            update(selected=style,frame=widget_frame(style),notice='')
        elif command=='apply':
            if not (STATE/'settings.json').exists(): save(STATE/'settings.json',read(HOME/'.config/eww/style.json'))
            apply(args[1])
        elif command=='wallpaper':
            style=read(STATE/'selection.json').get('style')
            source_palette(refresh=True)
            original=read(STATE/'original.json')
            if original:
                for entry in templates().values():
                    path=Path(entry['output_path']).expanduser()
                    if path.name=='desktop-style-source.json':continue
                    if path.exists():original[str(path)]=path.read_text()
                save(STATE/'original.json',original)
            if style in PROFILES: apply(style)
            else:
                source=source_palette();catalog=preview_catalog(source)
                write(CONFIG/'_palette.scss',''.join(f'${k}: {v};\n' for k,v in source.items()))
                update(catalog=catalog,choices=list(catalog.values()))
        elif command=='frame': set_widget_frame(args[1],args[2] if len(args)>2 else None)
        elif command=='extra': extra_action(args[1])
        elif command=='bar': set_bar(args[1],args[2])
        elif command=='background': companion_wallpaper(normalize_style(args[1]))
        elif command=='sddm': apply_sddm()
        elif command=='watch': watch()
        elif command=='reset': reset()
        elif command=='status': print(json.dumps(read(STATE/'selection.json',{'style':'original','name':'Original'}),ensure_ascii=False))
        elif command=='list': print(json.dumps(PROFILES,ensure_ascii=False,indent=2))
        else: raise ValueError('Usage: desktop-style open|toggle|prewarm|apply STYLE|sddm|bar position top|bottom|left|right|bar layout islands|continuous|frame FRAME|background STYLE|reset|status|list')
    except Exception as exc:
        message=exc.stderr.strip() if isinstance(exc,subprocess.CalledProcessError) else str(exc)
        update(busy=False,notice='Could not apply: '+message[:180])
        print(message,file=sys.stderr)
        sys.exit(1)
