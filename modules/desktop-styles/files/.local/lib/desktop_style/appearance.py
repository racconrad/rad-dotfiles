"""One resolved appearance contract, with adapters for each desktop surface."""
import json


def resolve(name, profile, colors):
    strict = name in ('monochrome', 'retro', 'terminal', 'ascii')
    widget_frame = profile.get('widget_frame', name)
    if widget_frame not in ('none','monochrome','terminal','retro','future','glass','modern','gnome','windows','ascii'):
        widget_frame = 'none'
    return dict(style=name, font=profile['font'], radius=profile['radius'],
                control_radius=min(profile['radius'], 10), border=profile['border'],
                opacity=profile['alpha'] if name == 'glass' else 1,
                panel_padding=16 if strict or name == 'windows' else 20,
                control_padding=8 if strict or name == 'windows' else 10,
                position=profile['position'], continuous=profile.get('continuous',False),
                strict=strict, colors=colors, widgets=dict(skin=profile['skin'], frame=widget_frame,
                    fx='none' if strict else 'focus', background='surface'))


def build(name, profile, colors):
    t=resolve(name,profile,colors)
    r,q,b,pad,cp,font=[t[k] for k in ('radius','control_radius','border','panel_padding','control_padding','font')]
    bg,fg,raised,accent,onaccent,edge,muted=[colors[k] for k in
        ('surface_container','on_surface','surface_container_highest','primary','on_primary','outline_variant','on_surface_variant')]
    # Solid colors in opaque profiles. Glass alone introduces translucency.
    def alpha(color):
        if t['opacity']==1:return color
        rgb=','.join(str(int(color[i:i+2],16)) for i in (1,3,5))
        return f'rgba({rgb},{t["opacity"]})'
    surface=alpha(bg)
    tooltip=f'''
tooltip, tooltip.background {{ background: {bg}; background-image: none; color: {fg}; border: {max(1,b)}px solid {edge}; border-radius: {q}px; padding: 8px; box-shadow: none; }}
tooltip, tooltip * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; font-size: 12px; color: {fg}; text-shadow: none; }}
tooltip label {{ padding: 0; }}
'''
    def panel(selector):
        return f'{selector} {{ background: {surface}; color: {fg}; border: {b}px solid {edge}; border-radius: {r}px; padding: {pad}px; box-shadow: none; transition: none; }}\n'
    def controls(scope):
        return f'''
{scope} button {{ background: transparent; background-image: none; color: {fg}; border-radius: {q}px; border: 1px solid transparent; box-shadow: none; text-shadow: none; padding: {cp}px; transition: none; }}
{scope} button:hover, {scope} button:focus, {scope} button:checked {{ background: {accent}; color: {onaccent}; border-color: {accent}; }}
{scope} button:hover label, {scope} button:focus label, {scope} button:checked label {{ color: {onaccent}; }}
{scope} button:focus {{ box-shadow: inset 0 0 0 2px {edge}; }}
{scope} entry, {scope} .search-bar {{ background: {raised}; color: {fg}; border: 1px solid {edge}; border-radius: {q}px; padding: {cp}px; caret-color: {accent}; }}
{scope} entry selection {{ background: {accent}; color: {onaccent}; }}
{scope} trough {{ background: {raised}; border-radius: {q}px; }}
{scope} highlight, {scope} progress {{ background: {accent}; border-radius: {q}px; }}
{scope} scrollbar slider {{ background: {muted}; border-radius: {q}px; }}
{scope} switch {{ background: {raised}; border: 1px solid {edge}; border-radius: {q}px; }}
{scope} switch slider {{ background: {fg}; border-radius: {q}px; }}
{scope} switch:checked {{ background: {accent}; }}
{scope} switch:checked slider {{ background: {onaccent}; }}
{scope} scale slider, {scope} check, {scope} radio {{ background: {fg}; background-image: none; border: 1px solid {edge}; border-radius: {q}px; box-shadow: none; min-width: 14px; min-height: 14px; }}
{scope} check, {scope} radio {{ background: {raised}; color: {fg}; }}
{scope} check:checked, {scope} radio:checked {{ background: {accent}; color: {onaccent}; }}
{scope} scale value {{ color: {muted}; }}
'''
    menu = f'.popup, .popup * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    menu += panel('.popup .panel.panel, .popup .side-panel.side-panel') + controls('.popup')
    menu += f'''
.popup .side-panel.side-panel {{ padding: {pad-4}px; }}
.popup .daily-app, .popup .app-launch, .popup .mode-row, .popup .session-choice, .popup .nav-tab, .popup .music-art, .popup .music-progress trough, .popup .music-progress progress {{ border-radius: {q}px; }}
.popup .daily-app {{ background: {raised}; color: {fg}; }}
.popup .daily-app label, .popup .daily-app image {{ color: {fg}; }}
.popup .mode-row.selected, .popup .session-choice.selected, .popup .nav-tab.current, .popup .app-launch.first-match, .popup button.apply {{ background: {accent}; color: {onaccent}; }}
.popup .mode-row.selected label, .popup .session-choice.selected label, .popup .nav-tab.current label, .popup button.apply label {{ color: {onaccent}; }}
.popup .muted {{ color: {muted}; }}
.popup .shortcuts-panel .key-cap {{ border-radius: {q}px; border-color: {edge}; }}
.popup button.destructive, .popup button.destructive:hover, .popup button.destructive:focus {{ background: {colors['error']}; color: {colors['on_error']}; }}
'''
    # Descendants must use the foreground of the actual selected/hover surface.
    menu += f"""
.popup .avatar {{ border-radius: {q}px; }}
.popup button:hover image, .popup button:focus image,
.popup .daily-app:hover label, .popup .daily-app:hover image,
.popup .daily-app:focus label, .popup .daily-app:focus image,
.popup .app-launch.first-match label, .popup .app-launch.first-match image,
.popup .nav-tab.current image, .popup .mode-row.selected image,
.popup .session-choice.selected image {{ color: {onaccent}; }}
.popup .daily-app:hover, .popup .daily-app:focus {{ background: {accent}; }}
.popup button.destructive label, .popup button.destructive:hover label,
.popup button.destructive:focus label {{ color: {colors['on_error']}; }}
"""
    if t['strict']:
        menu+=f'.popup .daily-app {{ border: {max(1,b)}px solid {edge}; }}\n'
    panels = f'#desktop-menu, #desktop-menu * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    panels += panel('#desktop-menu .panel') + controls('#desktop-menu')
    panels += f'#desktop-menu stackswitcher, #desktop-menu .music {{ background: {raised}; border-radius: {q}px; }}\n'
    panels += panel('menu, popover, window.popup')
    panels += f'menu, menu *, popover, popover * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; color: {fg}; }}\nmenuitem:hover, menuitem:selected {{ background: {accent}; color: {onaccent}; }}\n'

    selector = f'.style-selector, .style-selector * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    selector += panel('window .style-selector .selector-main, window .style-selector .selector-extra') + controls('.style-selector')
    selector += f'.style-selector .selector-extra {{ padding: 12px; margin-left: 4px; }}\n'
    selector += f'''
.style-selector .style-option, .style-selector .close, .style-selector .restore {{ border-radius: {q}px; }}
.style-selector .style-option.selected, .style-selector button.apply {{ background: {accent}; color: {onaccent}; border: 1px solid {accent}; }}
.style-selector .style-option.selected label, .style-selector button.apply label {{ color: {onaccent}; }}
.style-selector .option-status, .style-selector .subtitle, .style-selector .caption, .style-selector .notice {{ color: {muted}; }}
.style-selector .option-status {{ font-size: 11px; }}
.style-selector .style-option {{ padding: 6px 8px; }}
.style-selector .style-option:disabled {{ opacity: 1; }}
'''

    # This file is appended AFTER generated module/skin styles, not to the palette.
    root='.rw-desktop.wroot.rw-desktop.wroot'
    card=', '.join(f'.rw-motion-space {root} .{name}.{name}' for name in ('card','clock-card','mc-inventory'))
    widgets=f'{root}, {root} * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    widgets+=panel(card)+controls(root)
    media=', '.join(f'.rw-motion-space {root} .{key}.{key}' for key in ('photo-frame','image-frame'))
    # Longhand only: background shorthand resets cover/contain and the image itself.
    widgets+=f'{media} {{ background-color: {surface}; padding: 0; border-width: 0; border-radius: {r}px; box-shadow: inset 0 0 0 {b}px {edge}; background-position: center; background-repeat: no-repeat; transition: none; }}\n'
    chrome='.rw-motion-space .rw-window-frame:not(.rw-frame-none)'
    # Variant chrome owns its palette roles, geometry, and typography in shared
    # SCSS. A generic titlebar override would erase every style's identity.
    integrated=', '.join(f'{chrome} .rw-window-body > {root} .{key}' for key in ('card','clock-card'))
    widgets+=f'{integrated} {{ background: transparent; border: none; border-radius: 0; box-shadow: none; }}\n'
    framed_media=', '.join(f'{chrome} .rw-window-body > {root} .{key}.{key}' for key in ('photo-frame','image-frame'))
    widgets+=f'{framed_media} {{ padding: 0; border-width: 0; box-shadow: none; }}\n'
    if t['strict']:
        widgets+=f'{root} *, {chrome}, {chrome} * {{ animation: none; transition: none; text-shadow: none; }}\n'
    else:
        widgets+=f'{chrome} .rw-window-controls button {{ transition: background-color 120ms ease-out; }}\n'
        widgets+=f'{root}.fx-focus .card:hover, {root}.fx-focus .clock-card:hover {{ border-color: {accent}; }}\n'

    widgets+=f'''
{root} label {{ color: {fg}; text-shadow: none; }}
{root} .gen-sub, {root} .pl-sub, {root} .date {{ color: {muted}; }}
{root} .gen-icon, {root} .pl-icon, {root} .sys-chip {{ background: {raised}; color: {accent}; border-radius: {q}px; }}
{root} .gen-title, {root} .pl-title {{ color: {accent}; }}
'''

    bar=f'window#waybar, window#waybar * {{ font-family: "{font}", "Eva-Icons", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    bar+=panel('window#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar')
    bar+='window#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar { padding: 0 6px; }\n'
    chips=['clock','hardware','workspaces','custom-workspace-base','cpu','memory','temperature','disk','network','bluetooth','wireplumber','backlight','idle_inhibitor','custom-desktop-mode','custom-notification','custom-power','custom-updates','custom-hardware-toggle','tray','custom-music-open','custom-music-prev','custom-music-play','custom-music-next','battery','power-profiles-daemon']+[f'custom-ws{i}' for i in range(1,11)]
    allchips=', '.join('window#waybar #'+key for key in chips)
    bar+=f'{allchips} {{ border-radius: {q}px; color: {fg}; background: transparent; }}\n'
    bar+=f'window#waybar #clock, window#waybar #hardware, window#waybar #workspaces {{ background: {raised}; }}\n'
    active=', '.join('window#waybar #'+key+'.active' for key in chips if key.startswith('custom-ws'))
    bar+=f'{active}, window#waybar #workspaces button.active, window#waybar #taskbar button.active {{ background: {accent}; color: {onaccent}; border-radius: {q}px; }}\n'
    bar+=f'window#waybar #taskbar button, window#waybar #workspaces button {{ border-radius: {q}px; }}\n'
    bar+='window#waybar, window#waybar * { transition: none; animation: none; box-shadow: none; background-image: none; -gtk-icon-transform: none; }\n'
    bar+='window#waybar #taskbar button, window#waybar #taskbar button:hover { padding: 4px 7px; }\n'
    workspace=', '.join('window#waybar #custom-ws'+str(i)+state for i in range(1,11) for state in ('','.active',':hover'))
    bar+=f'{workspace}, window#waybar #workspaces button, window#waybar #workspaces button.active, window#waybar #workspaces button:hover {{ padding: 0 8px; }}\n'
    bar+=f'window#waybar #taskbar button:hover, window#waybar #workspaces button:hover {{ background: transparent; color: {fg}; }}\n'
    bar+=f'window#waybar #taskbar button.active:hover, window#waybar #workspaces button.active:hover {{ background: {accent}; color: {onaccent}; }}\n'
    # Allocate borders inside each island, with identical geometry for every state.
    bar+=f'window#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar {{ min-height: 44px; padding: 2px 6px; }}\n'
    bar+=f'{allchips} {{ margin: 4px 1px; padding: 0 7px; min-height: 24px; }}\n'
    bar+='window#waybar #hardware { margin: 4px 2px; padding: 0 2px; }\nwindow#waybar #hardware > * { margin-top: 0; margin-bottom: 0; }\n'
    bar+='window#waybar #taskbar button, window#waybar #taskbar button:hover, window#waybar #taskbar button.active { margin: 2px 1px; padding: 3px 6px; min-height: 30px; border: 1px solid transparent; }\n'
    bar+='window#waybar #taskbar.empty { background: transparent; border: none; min-height: 0; padding: 0; }\n'
    # Distinct workspace states without changing any allocation on hover.
    empty=', '.join(f'window#waybar #custom-ws{i}.empty' for i in range(1,11))
    occupied=', '.join(f'window#waybar #custom-ws{i}.occupied' for i in range(1,11))
    hover=', '.join(f'window#waybar #custom-ws{i}:hover' for i in range(1,11))
    bar+=f'{empty} {{ color: {muted}; }}\n{occupied} {{ color: {fg}; background: {raised}; }}\n'
    bar+=f'{hover}, window#waybar #taskbar button:not(.active):hover {{ background: {raised}; color: {fg}; }}\n'
    bar+=f'{active} {{ background: {accent}; color: {onaccent}; }}\n'
    if not t['strict']:
        interactive=allchips+', window#waybar #taskbar button'
        bar+=f'{interactive} {{ transition: background-color 150ms ease-out, color 150ms ease-out, border-color 150ms ease-out; }}\n'
    if t['continuous']:
        bar+=f'window#waybar {{ background: {surface}; }}\nwindow#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar {{ background: transparent; border: none; border-radius: 0; }}\nwindow#waybar > box {{ padding-top: 0; }}\n'
    else:
        bar+='window#waybar { background: transparent; }\n'
    inset=0 if t['continuous'] else 8
    padding=dict(top=f'0 0 {inset}px 0',bottom=f'{inset}px 0 0 0',left=f'0 {inset}px 0 0',right=f'0 0 0 {inset}px')[t['position']]
    bar+=f'window#waybar.{t["position"]} > box {{ padding: {padding}; }}\n'
    if t['strict']:
        bar+='window#waybar * { background-image: none; box-shadow: none; text-shadow: none; }\n'
    if name=='monochrome':
        bar+=f'{allchips} {{ opacity: 1; }}\n'
        widgets+=f'{root} .gen-title, {root} .pl-title {{ border-bottom: 1px solid {fg}; padding-bottom: 6px; margin-bottom: 6px; font-weight: bold; }}\n'
        selector+=f'.style-selector .header {{ border-bottom: 1px solid {fg}; padding-bottom: 12px; }}\n'
        widgets+=f'{root} .gen-icon, {root} .pl-icon {{ background: {bg}; color: {fg}; }}\n'

    rofi=f'''* {{ font: "{font} 11"; text-color: @fg; }}
window {{ border: {b}px; border-color: @outline; border-radius: {r}px; background-color: @bg; padding: {pad}px; }}
inputbar, element, message {{ border-radius: {q}px; }}
prompt, entry, element-text, textbox {{ font: "{font} 11"; }}
element {{ border: 1px; border-color: transparent; }}
element normal.normal, element alternate.normal {{ background-color: transparent; text-color: @fg; }}
element selected.normal {{ background-color: @accent; text-color: @on-accent; border-color: @accent; }}
element-text selected.normal {{ text-color: @on-accent; }}
'''
    rofi_colors='* {\n'+''.join(f'  {key}: {value};\n' for key,value in {
        'bg':bg+f'{round(t["opacity"]*255):02x}', 'bg-alt':raised,
        'accent':accent,'on-accent':onaccent,'accent-soft':raised,
        'outline':edge,'fg':fg,'fg-dim':muted}.items())+'}\n'
    swaync=f'* {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    swaync+=panel('.control-center.control-center, .notification.notification')
    swaync+=controls('.control-center')+controls('.notification')
    # Notification density is independent of the selected desktop style.
    swaync+=f'''.control-center.control-center {{ padding: 6px; }}
.notification.notification {{ padding: 0; }}
.notification .notification-default-action {{ padding: 0; border: none; }}
.notification .notification-action {{ padding: 4px 7px; }}
.notification .summary, .notification .body {{ color: {fg}; }}
.close-button.close-button {{ padding: 0; min-width: 18px; min-height: 18px; }}
'''

    # OSD is a compact floating indicator, never a full panel.
    osd=f'''window#osd {{ background: transparent; background-image: none; border: none; border-radius: 0; padding: 0; box-shadow: none; }}
window#osd * {{ font-family: "{font}"; color: {fg}; text-shadow: none; box-shadow: none; }}
window#osd #container {{ margin: 6px 8px; padding: 0; }}
window#osd image {{ -gtk-icon-transform: scale(.8); }}
window#osd label {{ font-size: 12px; }}
window#osd progressbar, window#osd segmentedprogress {{ min-height: 3px; min-width: 120px; background: transparent; border: none; padding: 0; }}
window#osd trough, window#osd segment {{ min-height: 3px; background: transparent; border: none; border-radius: 0; }}
window#osd progress, window#osd segment.active {{ min-height: 3px; background: {fg}; border: none; border-radius: 0; }}
'''
    editor_scope='.tinywidgets-editor .panel'
    editor=panel(editor_scope)+controls(editor_scope)
    editor+=f"""
{editor_scope}, {editor_scope} * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}
{editor_scope} label {{ color: {fg}; }}
{editor_scope} .panel-sub, {editor_scope} .wcard-desc, {editor_scope} .group-title {{ color: {muted}; }}
{editor_scope} .wcard {{ background: {raised}; border: {max(1,b)}px solid {edge}; border-radius: {q}px; padding: 4px 8px; }}
{editor_scope} .wcard:hover, {editor_scope} .wcard:focus {{ background: {accent}; border-color: {accent}; }}
{editor_scope} .wcard:hover label, {editor_scope} .wcard:focus label {{ color: {onaccent}; }}
{editor_scope} button {{ padding: 4px 8px; }}
{editor_scope} .pbtn.icon {{ padding: 0; }}
{editor_scope} .pbtn.primary, {editor_scope} .ws-pill:checked {{ background: {accent}; }}
{editor_scope} .pbtn.primary label, {editor_scope} .ws-pill:checked label {{ color: {onaccent}; }}
{editor_scope} .panel-icon, {editor_scope} .wcard-tag {{ background: {raised}; color: {fg}; border-radius: {q}px; }}
{editor_scope} .panel-icon, {editor_scope} .wcard-icon, {editor_scope} .pbtn.icon label, {editor_scope} .panel-grip {{ font-family: "JetBrainsMono Nerd Font Propo"; }}
{editor_scope} .section {{ border-color: {edge}; }}
{editor_scope} .textbox {{ border-color: {edge}; border-radius: {q}px; }}
"""
    if t['strict']:
        editor+=f'{editor_scope} * {{ transition: none; animation: none; }}\n'
        editor+=f'{editor_scope} .wcard:disabled {{ opacity: 1; }}\n'

    if name == 'ascii':
        cyan=colors['secondary']
        # Fine typographic rules, square controls, and color-coded text. No
        # raster overlays or ambient repaints on interactive desktop surfaces.
        menu+=f'''
.popup .header {{ border-bottom: 1px dashed {edge}; padding-bottom: 12px; }}
.popup .title, .popup .side-title {{ color: {cyan}; font-weight: 500; font-size: 14px; }}
.popup .search-bar {{ background: {bg}; border-style: dashed; }}
.popup .ascii-prompt {{ color: {accent}; }}
.popup .navigation {{ border-top: 1px dashed {edge}; padding-top: 8px; }}
.popup .daily-app {{ border-color: {edge}; }}
'''
        widgets+=f'''
{root} .gen-head, {root} .pl-head, {root} .music-head {{ border-bottom: 1px dashed {edge}; padding-bottom: 8px; }}
{root} .gen-title, {root} .pl-title, {root} .greeting {{ color: {cyan}; font-weight: 500; }}
{root} .gen-icon, {root} .pl-icon, {root} .sys-chip {{ background: transparent; color: {accent}; }}
{root} progress highlight {{ background: {cyan}; }}
'''
        selector+=f'.style-selector .header {{ border-bottom: 1px dashed {edge}; padding-bottom: 12px; }}\n.style-selector .preview-title {{ color: {cyan}; }}\n'
        panels+=f'#desktop-menu .panel-title {{ color: {cyan}; }}\n'
        editor+=f'{editor_scope} .panel-title, {editor_scope} .group-title {{ color: {cyan}; }}\n{editor_scope} .section {{ border-style: dashed; }}\n'
        bar+=f'window#waybar {{ border-bottom: 1px solid {edge}; }}\nwindow#waybar #clock {{ color: {cyan}; background: transparent; }}\n'
        swaync+=f'.notification .summary {{ color: {cyan}; }}\n'

    # gtk.css has USER priority, above each application's theme provider.
    # Mutable shape rules there would pin old radii in resident Eww processes.
    gtk='/* Global GTK files define color roles; shape and typography belong to the live application adapters. */\n'
    return dict(widget_editor=editor+tooltip,widgets=widgets+tooltip,raccon=menu+tooltip,panels=panels+tooltip,selector=selector+tooltip,
                waybar=bar+tooltip,rofi=rofi,rofi_colors=rofi_colors,swaync=swaync+tooltip,swayosd=osd+tooltip,gtk=gtk,
                tokens=json.dumps(t,ensure_ascii=False,indent=2)+'\n')
