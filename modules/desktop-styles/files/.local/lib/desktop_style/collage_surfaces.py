"""Editorial cutout geometry, crisp 0px slices, and understated tonal layers."""
from desktop_style.main import luminance, rgb


def decorate(outputs, c, tokens):
    primary, on_primary, secondary, on_secondary, tertiary, on_tertiary = [c[key] for key in
        ('primary', 'on_primary', 'secondary', 'on_secondary', 'tertiary', 'on_tertiary')]
    bg, lowest, raised, fg, muted, edge, edge_soft = [c[key] for key in
        ('surface_container', 'surface_container_lowest', 'surface_container_highest',
         'on_surface', 'on_surface_variant', 'outline', 'outline_variant')]
    pc, opc, sc, osc, tc, otc = [c[key] for key in
        ('primary_container', 'on_primary_container', 'secondary_container', 'on_secondary_container',
         'tertiary_container', 'on_tertiary_container')]
    err, oerr, ec, oec = c['error'], c['on_error'], c['error_container'], c['on_error_container']
    pr, pg, pb = [round(v * 255) for v in rgb(primary)]
    hover_tint = f'rgba({pr}, {pg}, {pb}, 0.10)'

    display_font = '"Fira Sans Compressed", "Inter Display", "JetBrainsMono Nerd Font Propo", sans-serif'
    tag_font = '"FantasqueSansM Nerd Font Mono", "JetBrainsMono Nerd Font Mono", monospace'
    cutout_panel = f'border-radius: 0px; border: 2px solid {edge}; box-shadow: 4px 4px 0 {primary};'
    cutout_sub = f'border-radius: 0px; border: 2px solid {edge}; box-shadow: 3px 3px 0 {secondary};'
    tile = f'border-radius: 0px; border: 1px solid {edge_soft}; box-shadow: none;'

    outputs['raccon'] += f'''
.popup .panel.panel {{ {cutout_panel} background: {bg}; }}
.popup .side-panel.side-panel {{ {cutout_sub} background: {bg}; }}
.popup .header {{ border-bottom: 2px solid {primary}; padding-bottom: 10px; }}
.popup.style-collage .title {{ font-family: {display_font}; font-size: 27px; font-weight: 800; letter-spacing: .2px; color: {primary}; }}
.popup .side-title {{ font-family: {display_font}; font-size: 20px; font-weight: 800; color: {secondary}; letter-spacing: .2px; }}
.popup .search-bar {{ border-radius: 0px; background: {lowest}; border: 1px solid {edge}; border-left: 3px solid {primary}; box-shadow: none; }}
.popup .daily-app {{ {tile} background: {raised}; color: {fg}; border-left: 2px solid {primary}; }}
.popup .daily-app label, .popup .daily-app image {{ color: {fg}; font-weight: 700; }}
.popup .quick {{ {tile} background: {lowest}; color: {fg}; border-left: 2px solid {secondary}; }}
.popup .quick label, .popup .quick image {{ color: {fg}; font-weight: 600; }}
.popup .nav-tab {{ {tile} background: {lowest}; color: {fg}; }}
.popup .nav-tab label, .popup .nav-tab image {{ color: {fg}; font-weight: 700; }}
.popup .daily-app:hover, .popup .daily-app:focus, .popup .quick:hover, .popup .quick:focus,
.popup .nav-tab:hover, .popup .nav-tab:focus, .popup .nav-tab.current {{ background: {primary}; border-color: {primary}; box-shadow: none; }}
.popup .daily-app:hover label, .popup .daily-app:focus label, .popup .daily-app:hover image, .popup .daily-app:focus image,
.popup .quick:hover label, .popup .quick:focus label, .popup .quick:hover image, .popup .quick:focus image,
.popup .nav-tab:hover label, .popup .nav-tab:focus label, .popup .nav-tab:hover image, .popup .nav-tab:focus image,
.popup .nav-tab.current label, .popup .nav-tab.current image {{ color: {on_primary}; }}
.popup .app-launch.app-launch, .popup .mode-row.mode-row, .popup .session-choice.session-choice,
.popup .key-row.key-row, .popup .shortcut-row.shortcut-row {{ border-radius: 0px; border: 1px solid {edge_soft}; background: {lowest}; color: {fg}; }}
.popup .app-launch.app-launch label, .popup .mode-row.mode-row label, .popup .session-choice.session-choice label,
.popup .key-row.key-row label, .popup .shortcut-row.shortcut-row label {{ color: {fg}; }}
.popup .app-launch.app-launch .muted, .popup .key-row.key-row .muted, .popup .shortcut-row.shortcut-row .muted {{ color: {muted}; }}
.popup .app-launch.app-launch:hover, .popup .app-launch.app-launch:focus, .popup .app-launch.app-launch.first-match,
.popup .mode-row.mode-row:hover, .popup .mode-row.mode-row:focus, .popup .mode-row.mode-row.selected,
.popup .session-choice.session-choice:hover, .popup .session-choice.session-choice:focus, .popup .session-choice.session-choice.selected,
.popup .key-row.key-row:hover, .popup .key-row.key-row:focus,
.popup .shortcut-row.shortcut-row:hover, .popup .shortcut-row.shortcut-row:focus {{ background: {primary}; color: {on_primary}; border-color: {primary}; box-shadow: none; }}
.popup .app-launch.app-launch:hover label, .popup .app-launch.app-launch:focus label, .popup .app-launch.app-launch.first-match label,
.popup .app-launch.app-launch:hover image, .popup .app-launch.app-launch:focus image, .popup .app-launch.app-launch.first-match image,
.popup .mode-row.mode-row:hover label, .popup .mode-row.mode-row:focus label, .popup .mode-row.mode-row.selected label,
.popup .mode-row.mode-row:hover image, .popup .mode-row.mode-row:focus image, .popup .mode-row.mode-row.selected image,
.popup .session-choice.session-choice:hover label, .popup .session-choice.session-choice:focus label, .popup .session-choice.session-choice.selected label,
.popup .session-choice.session-choice:hover image, .popup .session-choice.session-choice:focus image, .popup .session-choice.session-choice.selected image,
.popup .key-row.key-row:hover label:not(.key-cap), .popup .key-row.key-row:focus label:not(.key-cap),
.popup .shortcut-row.shortcut-row:hover label:not(.key-cap), .popup .shortcut-row.shortcut-row:focus label:not(.key-cap) {{ color: {on_primary}; }}
.popup .shortcuts-panel .key-cap {{ font-family: {tag_font}; border: 1px solid {secondary}; border-radius: 0px; background: {lowest}; color: {secondary}; box-shadow: none; }}
.popup .music-art {{ border-radius: 0px; border: 2px solid {edge}; box-shadow: none; }}
.popup .music-progress trough, .popup .music-progress progress {{ min-height: 6px; border-radius: 0px; }}
.popup .music-progress trough {{ border: 1px solid {edge_soft}; background: {lowest}; }}
.popup .music-progress progress {{ background: {primary}; }}
.popup .music-button {{ {tile} background: {lowest}; color: {fg}; }}
.popup .music-button image {{ color: {fg}; }}
.popup .music-button:hover, .popup .music-button:focus {{ background: {primary}; border-color: {primary}; box-shadow: none; }}
.popup .music-button:hover image, .popup .music-button:focus image {{ color: {on_primary}; }}
.popup .music-title {{ font-family: {display_font}; font-size: 19px; font-weight: 800; }}
.popup.float-popup.style-collage .panel.float-card {{ {cutout_panel} }}
.popup.float-popup.style-collage .float-title {{ font-family: {display_font}; font-size: 27px; font-weight: 800; color: {primary}; }}
.popup.float-popup.style-collage .float-badge {{ background: {pc}; color: {opc}; border: 1px solid {primary}; border-radius: 0px; box-shadow: none; }}
.popup.float-popup.style-collage .float-badge image {{ color: {opc}; }}
.popup.float-popup.style-collage .session-body {{ {tile} background: {raised}; border-top: 2px solid {secondary}; }}
.popup.float-popup.style-collage .session-body label {{ color: {fg}; font-weight: 700; }}
.popup.float-popup.style-collage .session-body .session-hint {{ color: {muted}; }}
.popup.float-popup.style-collage button.session-tile:hover .session-body,
.popup.float-popup.style-collage button.session-tile:focus .session-body,
.popup.float-popup.style-collage button.session-tile.armed .session-body {{ background: {primary}; border-color: {primary}; box-shadow: none; }}
.popup.float-popup.style-collage button.session-tile:hover label,
.popup.float-popup.style-collage button.session-tile:focus label,
.popup.float-popup.style-collage button.session-tile.armed label {{ color: {on_primary}; }}
.popup.float-popup.style-collage button.session-tile.danger.armed .session-body {{ background: {ec}; border-color: {err}; }}
.popup.float-popup.style-collage button.session-tile.danger.armed label {{ color: {oec}; }}
.popup.style-collage.motion:not(.still) button {{ transition: background-color 140ms ease-out, color 140ms ease-out, border-color 140ms ease-out; }}
.popup.still, .popup.still * {{ transition: none; animation: none; -gtk-icon-transform: none; }}
'''

    root = '.rw-desktop.wroot.rw-desktop.wroot'
    outputs['widgets'] += f'''
.rw-motion-space {root} .card.card, .rw-motion-space {root} .clock-card.clock-card {{ {cutout_panel} background: {bg}; }}
{root} .gen-icon, {root} .pl-icon, {root} .sys-chip {{ background: {raised}; color: {primary}; border: 1px solid {edge_soft}; border-radius: 0px; box-shadow: none; }}
{root} .gen-title, {root} .pl-title {{ font-family: {display_font}; font-size: 20px; font-weight: 800; color: {secondary}; }}
{root} .greeting {{ font-family: {display_font}; font-size: 24px; font-weight: 800; color: {primary}; }}
{root} .clock {{ font-family: {display_font}; font-weight: 800; color: {primary}; }}
{root} progress highlight {{ background: {primary}; }}
.rw-motion-space .rw-window-frame:not(.rw-frame-none) .rw-window-body > {root} .card.card,
.rw-motion-space .rw-window-frame:not(.rw-frame-none) .rw-window-body > {root} .clock-card.clock-card {{ background: transparent; border: none; border-radius: 0; box-shadow: none; }}
'''

    outputs['widget_editor'] += f'''
.tinywidgets-editor .panel {{ {cutout_panel} }}
.tinywidgets-editor .panel .panel-title {{ font-family: {display_font}; font-size: 24px; font-weight: 800; color: {primary}; }}
.tinywidgets-editor .panel .wcard {{ background: {lowest}; border: 1px solid {edge_soft}; border-left: 2px solid {primary}; border-radius: 0px; box-shadow: none; }}
.tinywidgets-editor .panel .wcard label {{ color: {fg}; font-weight: 700; }}
.tinywidgets-editor .panel .wcard:hover, .tinywidgets-editor .panel .wcard:focus {{ background: {primary}; border-color: {primary}; }}
.tinywidgets-editor .panel .wcard:hover label, .tinywidgets-editor .panel .wcard:focus label {{ color: {on_primary}; }}
'''

    outputs['panels'] += f'''
#desktop-menu .panel {{ {cutout_panel} }}
#desktop-menu .panel-title {{ font-family: {display_font}; font-size: 25px; font-weight: 800; color: {primary}; }}
#desktop-menu stackswitcher {{ background: {lowest}; border: 1px solid {edge_soft}; border-radius: 0px; }}
#desktop-menu stackswitcher button label {{ color: {fg}; font-weight: 700; }}
#desktop-menu stackswitcher button:hover label, #desktop-menu stackswitcher button:checked label {{ color: {on_primary}; }}
'''

    notif_font = '"Inter", "Noto Sans", "JetBrainsMono Nerd Font Propo", sans-serif'
    outputs['swaync'] += f'''
.control-center.control-center, .notification.notification {{ {cutout_panel} background: {bg}; color: {fg}; }}
.notification.notification.critical {{ border-color: {err}; box-shadow: 4px 4px 0 {err}; }}
.control-center .widget-title {{ font-family: {display_font}; color: {primary}; font-size: 22px; font-weight: 800; }}
.notification .summary {{ font-family: {notif_font}; color: {fg}; font-size: 14px; font-weight: 700; }}
.notification .body {{ font-family: {notif_font}; color: {fg}; font-size: 13px; font-weight: 400; }}
.notification .time {{ font-family: {notif_font}; color: {muted}; font-size: 11px; }}
.notification .notification-default-action {{ border-radius: 0px; color: {fg}; }}
.notification .notification-default-action:hover, .notification .notification-default-action:focus {{ background: {primary}; color: {on_primary}; border-radius: 0px; }}
.notification .notification-default-action:hover label, .notification .notification-default-action:focus label {{ color: {on_primary}; }}
.notification .close-button.close-button {{ border-radius: 0px; border: 1px solid {edge_soft}; background: {lowest}; color: {fg}; }}
.notification .close-button.close-button:hover {{ background: {ec}; color: {oec}; }}
.notification .notification-action {{ background: {raised}; color: {fg}; border: 1px solid {edge_soft}; border-radius: 0px; box-shadow: none; }}
.notification .notification-action label {{ color: {fg}; font-weight: 700; }}
.notification .notification-action:hover, .notification .notification-action:focus {{ background: {primary}; border-color: {primary}; }}
.notification .notification-action:hover label, .notification .notification-action:focus label {{ color: {on_primary}; }}
'''

    outputs['swayosd'] += f'''
window#osd #container {{ background: {bg}; border: 2px solid {edge}; border-radius: 0px; box-shadow: 3px 3px 0 {primary}; padding: 8px 12px; }}
window#osd label, window#osd image {{ color: {fg}; font-weight: 700; }}
window#osd progress, window#osd segment.active {{ background: {primary}; border-radius: 0px; }}
'''

    outputs['rofi'] += f'''
window {{ border-radius: 0px; border: 2px; border-color: @outline; }}
inputbar {{ background-color: @bg-alt; border: 1px; border-color: @accent; border-radius: 0px; padding: 12px; }}
element {{ border: 1px; border-color: @outline; border-radius: 0px; padding: 12px; }}
prompt {{ text-color: @accent; }}
'''

    bitmap_fg = max((fg, c['surface']), key=luminance)
    outputs['wlogout'] = f'''
window {{ background-color: {c['surface']}; }}
button {{ background-color: mix({pc}, #000000, .72); color: {bitmap_fg}; border: 2px solid {edge}; border-radius: 0px; box-shadow: 3px 3px 0 {lowest}; transition: background-color 140ms ease-out, border-color 140ms ease-out; }}
button label {{ color: {bitmap_fg}; font-family: {display_font}; font-weight: 800; }}
button:focus, button:hover {{ background-color: mix({tc}, #000000, .65); border-color: {secondary}; box-shadow: 3px 3px 0 {primary}; }}
#shutdown:focus, #shutdown:hover {{ background-color: mix({ec}, #000000, .72); border-color: {err}; box-shadow: 3px 3px 0 {err}; }}
'''

    outputs['gtklock'] = f'''
@keyframes lock-collage-in {{ 0% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}
window {{ background-color: {c['surface']}; color: {fg}; }}
#window-box {{ background: {bg}; {cutout_panel} padding: 30px 38px; animation: lock-collage-in 240ms ease-out 1; }}
#clock-label {{ font-family: {display_font}; color: {primary}; font-weight: 800; font-size: 62px; }}
#date-label {{ color: {secondary}; font-family: {tag_font}; }}
#user-image {{ border-radius: 0px; border: 2px solid {primary}; }}
#user-name {{ color: {fg}; font-family: {display_font}; font-weight: 800; }}
#input-field {{ background: {lowest}; color: {fg}; border-radius: 0px; border: 1px solid {edge}; box-shadow: none; }}
#input-field:focus {{ border-color: {primary}; }}
#unlock-button {{ background: {primary}; color: {on_primary}; border: 1px solid {edge}; border-radius: 0px; box-shadow: none; font-weight: 800; }}
#unlock-button:hover, #unlock-button:focus {{ background: {secondary}; color: {on_secondary}; border-color: {secondary}; }}
#powerbar-box button {{ background: {raised}; color: {fg}; border: 1px solid {edge_soft}; border-radius: 0px; }}
#powerbar-box button:hover, #powerbar-box button:focus {{ background: {primary}; color: {on_primary}; border-color: {primary}; }}
#powerbar-box #poweroff-button:hover, #powerbar-box #poweroff-button:focus {{ background: {err}; color: {oerr}; border-color: {err}; }}
'''
    return outputs
