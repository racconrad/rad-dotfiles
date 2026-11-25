"""Early Macintosh grayscale frames, subtle silver shading, and simple borders."""


def decorate(outputs, c, tokens):
    primary, on_primary, secondary, on_secondary, tertiary = [c[key] for key in
        ('primary', 'on_primary', 'secondary', 'on_secondary', 'tertiary')]
    bg, lowest, low, raised, fg, muted, edge, edge_soft = [c[key] for key in
        ('surface_container', 'surface_container_lowest', 'surface_container_low',
         'surface_container_highest', 'on_surface', 'on_surface_variant', 'outline', 'outline_variant')]
    err, oerr, ec, oec = c['error'], c['on_error'], c['error_container'], c['on_error_container']

    win_box = f'background: {bg}; border: 2px solid {edge}; border-radius: 4px; box-shadow: 2px 2px 0 rgba(0, 0, 0, 0.24), inset 1px 1px 0 {lowest};'
    title_grad = f'background: linear-gradient(to bottom, {lowest} 0%, {bg} 55%, {raised} 100%); color: {fg}; border-bottom: 1px solid {edge};'
    btn_mac = f'background: linear-gradient(to bottom, {lowest} 0%, {low} 70%, {raised} 100%); color: {fg}; border: 1px solid {edge}; border-radius: 3px; box-shadow: inset 1px 1px 0 {lowest};'
    btn_primary = f'background: {primary}; color: {on_primary}; border: 1px solid {edge}; border-radius: 3px; font-weight: 700;'
    groove = f'background: {lowest}; border: 1px solid {edge_soft}; border-radius: 2px; box-shadow: inset 1px 1px 0 {raised};'

    outputs['raccon'] += f'''
.popup .panel.panel, .popup .side-panel.side-panel {{ {win_box} padding: 12px; }}
.popup .header {{ {title_grad} border-radius: 2px 2px 0px 0px; padding: 6px 10px; }}
.popup .header label, .popup.style-macxp .title {{ color: {fg}; font-weight: 700; font-size: 16px; }}
.popup .side-title {{ {title_grad} border-radius: 2px 2px 0px 0px; padding: 5px 8px; font-weight: 700; font-size: 14px; color: {fg}; }}
.popup .search-bar {{ {groove} }}
.popup .daily-app, .popup .nav-tab, .popup .quick {{ {btn_mac} }}
.popup .daily-app label, .popup .daily-app image, .popup .nav-tab label, .popup .nav-tab image,
.popup .quick label, .popup .quick image {{ color: {fg}; }}
.popup .daily-app:hover, .popup .daily-app:focus, .popup .quick:hover, .popup .quick:focus,
.popup .nav-tab:hover, .popup .nav-tab:focus, .popup .nav-tab.current {{ background: {primary}; color: {on_primary}; border-color: {edge}; }}
.popup .daily-app:hover label, .popup .daily-app:focus label, .popup .daily-app:hover image, .popup .daily-app:focus image,
.popup .quick:hover label, .popup .quick:focus label, .popup .quick:hover image, .popup .quick:focus image,
.popup .nav-tab:hover label, .popup .nav-tab:focus label, .popup .nav-tab:hover image, .popup .nav-tab:focus image,
.popup .nav-tab.current label, .popup .nav-tab.current image {{ color: {on_primary}; }}
.popup button.apply {{ {btn_primary} }}
.popup button.apply label {{ color: {on_primary}; }}
.popup .shortcuts-panel .key-cap {{ {btn_mac} color: {fg}; font-family: "JetBrainsMono Nerd Font Mono", monospace; }}
.popup .music-art {{ {groove} border: 1px solid {edge}; border-radius: 2px; }}
.popup .music-progress trough {{ {groove} min-height: 6px; }}
.popup .music-progress progress {{ background: {primary}; border-radius: 1px; }}
.popup .music-button {{ {btn_mac} }}
.popup .music-button image {{ color: {fg}; }}
.popup .music-button:hover, .popup .music-button:focus {{ background: {primary}; }}
.popup .music-button:hover image, .popup .music-button:focus image {{ color: {on_primary}; }}
.popup.float-popup.style-macxp .panel.float-card {{ {win_box} }}
.popup.float-popup.style-macxp .float-head {{ {title_grad} padding: 6px 10px; border-radius: 2px 2px 0px 0px; }}
.popup.float-popup.style-macxp .float-title {{ color: {fg}; font-size: 17px; font-weight: 700; }}
.popup.float-popup.style-macxp .float-badge {{ {btn_mac} padding: 2px 6px; }}
.popup.float-popup.style-macxp .session-body {{ {btn_mac} }}
.popup.float-popup.style-macxp .session-body label,
.popup.float-popup.style-macxp .session-body .session-hint {{ color: {fg}; }}
.popup.float-popup.style-macxp button.session-tile:hover .session-body,
.popup.float-popup.style-macxp button.session-tile:focus .session-body,
.popup.float-popup.style-macxp button.session-tile.armed .session-body {{ background: {primary}; border-color: {edge}; }}
.popup.float-popup.style-macxp button.session-tile:hover label,
.popup.float-popup.style-macxp button.session-tile:focus label,
.popup.float-popup.style-macxp button.session-tile.armed label {{ color: {on_primary}; }}
.popup.float-popup.style-macxp button.session-tile.danger.armed .session-body {{ background: {ec}; }}
.popup.float-popup.style-macxp button.session-tile.danger.armed label {{ color: {oec}; }}
.popup.still, .popup.still * {{ transition: none; animation: none; -gtk-icon-transform: none; }}
'''

    outputs['selector'] += f'''
window .style-selector .selector-main, window .style-selector .selector-extra {{ {win_box} }}
.style-selector .header {{ {title_grad} padding: 7px 10px; border-radius: 2px 2px 0px 0px; }}
.style-selector .heading {{ color: {fg}; font-size: 18px; font-weight: 700; }}
.style-selector.style-shell .style-emblem {{ background: {lowest}; color: {fg}; border: 1px solid {edge}; border-radius: 2px; }}
.style-selector button.close {{ {btn_mac} }}
.style-selector button.close:hover {{ background: {err}; color: {oerr}; border-color: {err}; }}
.style-selector button.close:hover image {{ color: {oerr}; }}
.style-selector .style-option {{ {btn_mac} }}
.style-selector .style-option.selected {{ background: {primary}; color: {on_primary}; border-color: {edge}; }}
.style-selector .style-option.selected label, .style-selector .style-option.selected image {{ color: {on_primary}; }}
.style-selector .preview-title {{ color: {fg}; font-size: 17px; font-weight: 700; }}
.style-selector .apply {{ {btn_primary} }}
.style-selector .apply label {{ color: {on_primary}; }}
.style-selector.still, .style-selector.still *, .style-selector.reduce-motion, .style-selector.reduce-motion * {{ transition: none; animation: none; -gtk-icon-transform: none; }}
'''

    bar_mac = f'background: linear-gradient(to bottom, {lowest} 0%, {bg} 60%, {raised} 100%); border: 1px solid {edge}; box-shadow: inset 0 1px 0 {lowest};'
    if not tokens['continuous']:
        outputs['waybar'] += f'window#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar {{ {bar_mac} border-radius: 4px; }}\n'
    else:
        outputs['waybar'] += f'window#waybar {{ {bar_mac} }}\n'
    outputs['waybar'] += f'''
window#waybar .modules-left label, window#waybar .modules-right label,
window#waybar .modules-left image, window#waybar .modules-right image,
window#waybar #taskbar button label {{ color: {fg}; }}
window#waybar #custom-workspace-base {{ color: {fg}; font-weight: 700; padding: 0 9px; border-right: 1px solid {edge_soft}; }}
window#waybar #clock {{ background: {lowest}; color: {fg}; border: 1px solid {edge_soft}; border-radius: 2px; font-weight: 700; padding: 0 10px; }}
window#waybar #custom-power {{ color: {err}; background: transparent; }}
window#waybar #custom-power:hover {{ background: {err}; color: {oerr}; }}
window#waybar #taskbar button {{ background: transparent; border: 1px solid transparent; border-radius: 2px; min-height: 30px; color: {fg}; }}
window#waybar #taskbar button.active {{ background: {primary}; color: {on_primary}; border: 1px solid {edge}; }}
window#waybar #taskbar button.active label {{ color: {on_primary}; }}
window#waybar #taskbar button:not(.active):hover {{ background: {raised}; border-color: {edge_soft}; }}
window#waybar #taskbar.empty {{ background: transparent; border: none; min-height: 0; padding: 0; box-shadow: none; }}
'''

    root = '.rw-desktop.wroot.rw-desktop.wroot'
    outputs['widgets'] += f'''
.rw-motion-space {root} .card.card, .rw-motion-space {root} .clock-card.clock-card {{ {win_box} }}
{root} .gen-head, {root} .pl-head, {root} .music-head {{ {title_grad} padding: 5px 8px; border-radius: 2px 2px 0px 0px; margin-bottom: 6px; }}
{root} .gen-title, {root} .pl-title {{ color: {fg}; font-weight: 700; }}
{root} .gen-icon, {root} .pl-icon, {root} .sys-chip {{ {btn_mac} color: {fg}; }}
{root} .clock {{ color: {fg}; font-weight: 700; }}
{root} .greeting {{ color: {fg}; font-weight: 700; }}
{root} progress trough {{ {groove} }}
{root} progress highlight {{ background: {primary}; }}
.rw-motion-space .rw-window-frame:not(.rw-frame-none) .rw-window-body > {root} .card.card,
.rw-motion-space .rw-window-frame:not(.rw-frame-none) .rw-window-body > {root} .clock-card.clock-card {{ background: transparent; border: none; border-radius: 0; box-shadow: none; }}
'''

    outputs['widget_editor'] += f'''
.tinywidgets-editor .panel {{ {win_box} }}
.tinywidgets-editor .panel .panel-title {{ {title_grad} padding: 6px 10px; border-radius: 2px; color: {fg}; }}
.tinywidgets-editor .panel .wcard {{ {btn_mac} }}
.tinywidgets-editor .panel .wcard label {{ color: {fg}; }}
.tinywidgets-editor .panel .wcard:hover, .tinywidgets-editor .panel .wcard:focus {{ background: {primary}; color: {on_primary}; }}
.tinywidgets-editor .panel .wcard:hover label, .tinywidgets-editor .panel .wcard:focus label {{ color: {on_primary}; }}
'''

    outputs['panels'] += f'''
#desktop-menu .panel {{ {win_box} }}
#desktop-menu .panel-title {{ {title_grad} padding: 6px 10px; border-radius: 2px; color: {fg}; }}
#desktop-menu stackswitcher {{ {groove} }}
#desktop-menu stackswitcher button label {{ color: {fg}; }}
#desktop-menu stackswitcher button:hover label, #desktop-menu stackswitcher button:checked label {{ color: {on_primary}; }}
'''

    outputs['swaync'] += f'''
.control-center.control-center, .notification.notification {{ {win_box} }}
.control-center .widget-title {{ {title_grad} padding: 5px 8px; border-radius: 2px; color: {fg}; }}
.notification .summary {{ color: {fg}; font-weight: 700; }}
.notification .notification-action {{ {btn_mac} }}
.notification .notification-action label {{ color: {fg}; }}
.notification .notification-action:hover, .notification .notification-action:focus {{ background: {primary}; }}
.notification .notification-action:hover label, .notification .notification-action:focus label {{ color: {on_primary}; }}
'''

    outputs['swayosd'] += f'''
window#osd #container {{ {win_box} padding: 8px 12px; }}
window#osd label, window#osd image {{ color: {fg}; font-weight: 700; }}
window#osd progress, window#osd segment.active {{ background: {primary}; border-radius: 1px; }}
'''

    outputs['rofi'] += f'''
window {{ border-radius: 4px; border: 2px; border-color: @outline; }}
inputbar {{ background-color: @bg-alt; border: 1px; border-color: @outline; border-radius: 2px; padding: 10px; }}
element {{ border: 1px; border-color: transparent; border-radius: 2px; padding: 10px; }}
prompt {{ text-color: @accent; }}
'''

    outputs['wlogout'] = f'''
window {{ background-color: {c['surface']}; }}
button {{ {btn_mac} border: 2px solid {edge}; border-radius: 4px; color: {fg}; }}
button label {{ color: {fg}; font-weight: 700; }}
button:focus, button:hover {{ background: {primary}; color: {on_primary}; border-color: {edge}; }}
button:focus label, button:hover label {{ color: {on_primary}; }}
#shutdown:focus, #shutdown:hover {{ background: {err}; color: {oerr}; border-color: {err}; }}
#shutdown:focus label, #shutdown:hover label {{ color: {oerr}; }}
'''

    outputs['gtklock'] = f'''
@keyframes lock-mac-in {{ 0% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}
window {{ background-color: {c['surface']}; color: {fg}; }}
#window-box {{ {win_box} padding: 28px 36px; animation: lock-mac-in 220ms ease-out 1; }}
#clock-label {{ color: {fg}; font-weight: 700; font-size: 60px; }}
#date-label {{ color: {muted}; }}
#user-image {{ border-radius: 4px; border: 2px solid {edge}; }}
#user-name {{ color: {fg}; font-weight: 700; }}
#input-field {{ {groove} color: {fg}; }}
#input-field:focus {{ border-color: {edge}; }}
#unlock-button {{ {btn_primary} }}
#unlock-button:hover, #unlock-button:focus {{ background: {secondary}; color: {on_secondary}; }}
#powerbar-box button {{ {btn_mac} }}
#powerbar-box button:hover, #powerbar-box button:focus {{ background: {primary}; color: {on_primary}; }}
#powerbar-box #poweroff-button:hover, #powerbar-box #poweroff-button:focus {{ background: {err}; color: {oerr}; }}
'''
    return outputs
