"""One resolved appearance contract, with adapters for each desktop surface."""
import json


def resolve(name, profile, colors):
    return dict(style='collage', font=profile['font'], radius=profile['radius'],
                control_radius=min(profile['radius'], 10), border=profile['border'],
                opacity=1,
                panel_padding=16,
                control_padding=6,
                position=profile['position'], continuous=profile.get('continuous',False),
                strict=False, colors=colors, widgets=dict(skin=profile['skin'], frame='none',
                    fx='focus', background='surface'))


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
.popup .side-panel.side-panel {{ padding: {max(10, pad-4)}px; }}
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

    # This file is appended AFTER generated module/skin styles, not to the palette.
    root='.rw-desktop.wroot.rw-desktop.wroot'
    card=', '.join(f'.rw-motion-space {root} .{name}.{name}' for name in ('card','clock-card','mc-inventory'))
    widgets=f'{root}, {root} * {{ font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    widgets+=panel(card)+controls(root)
    media=', '.join(f'.rw-motion-space {root} .{key}.{key}' for key in ('photo-frame','image-frame'))
    widgets+=f'{media} {{ background-color: {surface}; padding: 0; border-width: 0; border-radius: {r}px; box-shadow: inset 0 0 0 {b}px {edge}; background-position: center; background-repeat: no-repeat; transition: none; }}\n'
    chrome='.rw-motion-space .rw-window-frame:not(.rw-frame-none)'
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
    notif_font = 'Inter' if font in ('Inter Display', 'Fira Sans Compressed') else font
    swaync=f'* {{ font-family: "{notif_font}", "Noto Sans", "JetBrainsMono Nerd Font Propo", sans-serif; }}\n'
    swaync+=panel('.control-center.control-center, .notification.notification')
    swaync+=controls('.control-center')+controls('.notification')
    # Notification density and readable font metrics are preserved across styles.
    swaync+=f'''.control-center.control-center {{ padding: 6px; }}
.notification.notification {{ padding: 0; }}
.notification .notification-default-action {{ padding: 0; border: none; }}
.notification .notification-action {{ padding: 4px 7px; }}
.notification .text-box label {{ opacity: 1; }}
.notification .summary {{ font-family: "{notif_font}", "Noto Sans", "JetBrainsMono Nerd Font Propo", sans-serif; font-size: 14px; font-weight: 700; color: {fg}; opacity: 1; }}
.notification .body {{ font-family: "{notif_font}", "Noto Sans", "JetBrainsMono Nerd Font Propo", sans-serif; font-size: 13px; font-weight: 400; color: {fg}; opacity: 1; }}
.notification .time {{ font-family: "{notif_font}", "Noto Sans", "JetBrainsMono Nerd Font Propo", sans-serif; font-size: 11px; color: {muted}; opacity: 1; }}
.close-button.close-button {{ padding: 0; min-width: 18px; min-height: 18px; }}
'''

    # OSD is a compact floating indicator that still respects the active style shape and readable type.
    osd=f'''window#osd {{ background: {surface}; background-image: none; border: {b}px solid {edge}; border-radius: {q}px; padding: 0; box-shadow: none; }}
window#osd * {{ font-family: "{notif_font}", "Noto Sans", sans-serif; color: {fg}; text-shadow: none; box-shadow: none; }}
window#osd #container {{ margin: 6px 10px; padding: 0; }}
window#osd image {{ -gtk-icon-transform: scale(.8); }}
window#osd label {{ font-size: 13px; }}
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

    # gtk.css has USER priority, above each application's theme provider.
    # Mutable shape rules there would pin old radii in resident Eww processes.
    gtk='/* Global GTK files define color roles; shape and typography belong to the live application adapters. */\n'
    gtklock = f'''
@keyframes lock-enter {{ 0% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}
window {{ background-color: {colors['surface']}; color: {fg}; font-family: "{font}", "JetBrainsMono Nerd Font Propo", sans-serif; }}
#window-box {{ background: {alpha(bg) if t['opacity'] < 1 else bg}; border: {max(1,b)}px solid {edge}; border-radius: {r}px; padding: 30px 38px; box-shadow: 0 16px 42px rgba(0,0,0,0.45); animation: lock-enter 240ms ease-out 1; }}
#clock-label {{ color: {accent}; font-weight: 700; font-size: 60px; }}
#date-label {{ color: {muted}; font-size: 14px; }}
#user-image {{ border-radius: {min(r, 999) if r > 0 else 0}px; border: {max(1,b)}px solid {accent}; }}
#user-name {{ color: {fg}; font-weight: 700; }}
#input-field {{ background: {raised}; color: {fg}; border: {max(1,b)}px solid {edge}; border-radius: {q}px; padding: 8px 14px; transition: border-color 150ms ease-out; }}
#input-field:focus {{ border-color: {accent}; }}
#unlock-button {{ background: {accent}; color: {onaccent}; border: none; border-radius: {q}px; font-weight: 700; transition: background-color 140ms ease-out; }}
#unlock-button:hover, #unlock-button:focus {{ background: {colors['primary_container']}; color: {colors['on_primary_container']}; }}
#powerbar-box button {{ background: {raised}; color: {fg}; border: {max(1,b)}px solid {edge}; border-radius: {q}px; transition: background-color 140ms ease-out, border-color 140ms ease-out; }}
#powerbar-box button:hover, #powerbar-box button:focus {{ background: {accent}; color: {onaccent}; border-color: {accent}; }}
#powerbar-box #poweroff-button:hover, #powerbar-box #poweroff-button:focus {{ background: {colors['error']}; color: {colors['on_error']}; border-color: {colors['error']}; }}
'''
    outputs = dict(widget_editor=editor+tooltip,widgets=widgets+tooltip,raccon=menu+tooltip,panels=panels+tooltip,
                rofi=rofi,rofi_colors=rofi_colors,swaync=swaync+tooltip,swayosd=osd+tooltip,gtk=gtk,
                wlogout='',gtklock=gtklock,tokens=json.dumps(t,ensure_ascii=False,indent=2)+'\n')

    from desktop_style.collage_surfaces import decorate
    return decorate(outputs, colors, t)
