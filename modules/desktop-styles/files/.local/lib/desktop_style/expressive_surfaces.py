"""Solid color groups and shape feedback for the existing native controls."""
from desktop_style.main import luminance


def decorate(outputs, c, tokens):
    primary, on_primary, secondary, on_secondary, tertiary, on_tertiary = [c[key] for key in
        ('primary', 'on_primary', 'secondary', 'on_secondary', 'tertiary', 'on_tertiary')]
    bg, raised, fg, muted = [c[key] for key in
        ('surface_container', 'surface_container_highest', 'on_surface', 'on_surface_variant')]
    pc, opc, sc, osc, tc, otc = [c[key] for key in
        ('primary_container', 'on_primary_container', 'secondary_container', 'on_secondary_container',
         'tertiary_container', 'on_tertiary_container')]
    shape = 'border-radius: 32px 12px 32px 12px;'
    outputs['raccon'] += f'''
.popup .panel.panel, .popup .side-panel.side-panel {{ {shape} background: {bg}; }}
.popup.style-expressive .title {{ font-size: 28px; font-weight: 800; letter-spacing: -.5px; }}
.popup .side-title {{ font-size: 18px; font-weight: 700; }}
.popup .search-bar {{ border-radius: 24px; background: {raised}; border-color: {primary}; }}
.popup .daily-app {{ background: {pc}; border-radius: 24px 8px 24px 8px; }}
.popup .daily-app label, .popup .daily-app image {{ color: {opc}; }}
.popup .quick {{ background: {sc}; border-radius: 18px; }}
.popup .quick label, .popup .quick image {{ color: {osc}; }}
.popup .nav-tab {{ background: {tc}; border-radius: 20px; }}
.popup .nav-tab label, .popup .nav-tab image {{ color: {otc}; }}
.popup .daily-app:hover, .popup .daily-app:focus, .popup .quick:hover, .popup .quick:focus,
.popup .nav-tab:hover, .popup .nav-tab:focus, .popup .nav-tab.current {{ background: {primary}; }}
.popup .daily-app:hover label, .popup .daily-app:focus label, .popup .daily-app:hover image, .popup .daily-app:focus image,
.popup .quick:hover label, .popup .quick:focus label, .popup .quick:hover image, .popup .quick:focus image,
.popup .nav-tab:hover label, .popup .nav-tab:focus label, .popup .nav-tab:hover image, .popup .nav-tab:focus image,
.popup .nav-tab.current label, .popup .nav-tab.current image {{ color: {on_primary}; }}
.popup .music-art {{ border-radius: 28px 8px 28px 8px; }}
.popup .music-progress trough, .popup .music-progress progress {{ min-height: 6px; border-radius: 8px; }}
.popup .music-progress progress {{ background: {tertiary}; }}
.popup .music-button {{ background: {sc}; border-radius: 24px; }}
.popup .music-button image {{ color: {osc}; }}
.popup .music-button:hover, .popup .music-button:focus {{ background: {secondary}; }}
.popup .music-button:hover image, .popup .music-button:focus image {{ color: {on_secondary}; }}
.popup .music-title {{ font-size: 16px; font-weight: 700; }}
.popup.float-popup.style-expressive .panel.float-card {{ {shape} }}
.popup.float-popup.style-expressive .float-title {{ font-size: 28px; }}
.popup.float-popup.style-expressive .session-body {{ border-radius: 28px 8px 28px 8px; background: {sc}; }}
.popup.float-popup.style-expressive .session-body label {{ color: {osc}; }}
.popup.float-popup.style-expressive .session-body .session-hint {{ color: {osc}; }}
.popup.float-popup.style-expressive button.session-tile:hover .session-body,
.popup.float-popup.style-expressive button.session-tile:focus .session-body,
.popup.float-popup.style-expressive button.session-tile.armed .session-body {{ background: {pc}; }}
.popup.float-popup.style-expressive button.session-tile:hover label,
.popup.float-popup.style-expressive button.session-tile:focus label,
.popup.float-popup.style-expressive button.session-tile.armed label {{ color: {opc}; }}
.popup.float-popup.style-expressive button.session-tile.danger.armed .session-body {{ background: {c['error_container']}; }}
.popup.float-popup.style-expressive button.session-tile.danger.armed label {{ color: {c['on_error_container']}; }}
.popup.style-expressive.motion:not(.still) button {{ transition: background-color 200ms ease-out, color 200ms ease-out, border-radius 220ms cubic-bezier(.2,.8,.2,1); }}
.popup.motion .daily-app:active, .popup.motion .nav-tab:active {{ border-radius: 12px; }}
.popup.still, .popup.still * {{ transition: none; animation: none; -gtk-icon-transform: none; }}
'''
    outputs['selector'] += f'''
window .style-selector .selector-main, window .style-selector .selector-extra {{ {shape} }}
.style-selector .heading {{ font-size: 30px; font-weight: 800; }}
.style-selector.style-shell .style-emblem {{ background: {sc}; color: {osc}; border-radius: 24px 8px 24px 8px; }}
.style-selector .style-option {{ border-radius: 18px; }}
.style-selector .preview-title {{ color: {tertiary}; font-size: 21px; font-weight: 700; }}
.style-selector .apply {{ border-radius: 24px 8px 24px 8px; }}
.style-selector.motion:not(.reduce-motion):not(.still) .theme-choice {{ transition: background-color 200ms ease-out, border-radius 220ms ease-out; }}
.style-selector.motion.compact-motion:not(.reduce-motion):not(.still) .theme-choice {{ transition-duration: 140ms; }}
.style-selector.motion .theme-choice:active {{ border-radius: 8px; }}
.style-selector.still, .style-selector.still *, .style-selector.reduce-motion, .style-selector.reduce-motion * {{ transition: none; animation: none; -gtk-icon-transform: none; }}
'''
    if not tokens['continuous']:
        outputs['waybar'] += f'window#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar {{ {shape} }}\n'
    outputs['waybar'] += f'''
window#waybar #clock {{ background: {primary}; color: {on_primary}; font-weight: 800; border-radius: 24px; }}
window#waybar #custom-music-open {{ background: {sc}; color: {osc}; border-radius: 18px 6px 18px 6px; }}
window#waybar #network, window#waybar #wireplumber {{ background: {tc}; color: {otc}; border-radius: 16px; }}
window#waybar #taskbar button, window#waybar #taskbar button:hover,
window#waybar #taskbar button.active {{ min-height: 36px; padding: 4px 7px; border-radius: 22px 8px 22px 8px; }}
window#waybar #taskbar button:not(:disabled) {{ transition: background-color 180ms ease-out, border-radius 220ms ease-out; }}
window#waybar #taskbar button:active {{ border-radius: 12px; }}
window#waybar #taskbar button:focus {{ box-shadow: inset 0 0 0 2px {primary}; }}
window#waybar #taskbar button.active:focus {{ box-shadow: inset 0 0 0 2px {on_primary}; }}
window#waybar #taskbar.empty {{ background: transparent; border: none; padding: 0; min-height: 0; }}
'''
    root = '.rw-desktop.wroot.rw-desktop.wroot'
    outputs['widgets'] += f'''
.rw-motion-space {root} .card.card, .rw-motion-space {root} .clock-card.clock-card {{ {shape} background: {bg}; }}
{root} .gen-icon, {root} .pl-icon, {root} .sys-chip {{ background: {sc}; color: {osc}; border-radius: 24px 8px 24px 8px; }}
{root} .gen-title, {root} .pl-title {{ font-size: 18px; font-weight: 800; color: {tertiary}; }}
{root} .greeting {{ font-size: 24px; font-weight: 800; color: {primary}; }}
{root} .clock {{ font-weight: 800; color: {primary}; }}
{root} progress highlight {{ background: {tertiary}; }}
.rw-motion-space .rw-window-frame:not(.rw-frame-none) .rw-window-body > {root} .card.card,
.rw-motion-space .rw-window-frame:not(.rw-frame-none) .rw-window-body > {root} .clock-card.clock-card {{ background: transparent; border: none; border-radius: 0; box-shadow: none; }}
'''
    outputs['widget_editor'] += f'''
.tinywidgets-editor .panel {{ {shape} }}
.tinywidgets-editor .panel .panel-title {{ font-size: 24px; font-weight: 800; }}
.tinywidgets-editor .panel .wcard {{ background: {pc}; border-color: {pc}; border-radius: 20px 8px 20px 8px; }}
.tinywidgets-editor .panel .wcard label {{ color: {opc}; }}
.tinywidgets-editor .panel .wcard:hover, .tinywidgets-editor .panel .wcard:focus {{ background: {primary}; }}
.tinywidgets-editor .panel .wcard:hover label, .tinywidgets-editor .panel .wcard:focus label {{ color: {on_primary}; }}
'''
    outputs['panels'] += f'''
#desktop-menu .panel {{ {shape} }}
#desktop-menu .panel-title {{ font-size: 26px; font-weight: 800; color: {primary}; }}
#desktop-menu stackswitcher {{ background: {sc}; }}
#desktop-menu stackswitcher button label {{ color: {osc}; }}
#desktop-menu stackswitcher button:hover label, #desktop-menu stackswitcher button:checked label {{ color: {on_primary}; }}
'''
    outputs['swaync'] += f'''
.control-center.control-center, .notification.notification {{ {shape} }}
.control-center .widget-title {{ color: {primary}; font-size: 24px; font-weight: 800; }}
.notification .summary {{ color: {primary}; font-size: 16px; font-weight: 800; }}
.notification .notification-action {{ background: {sc}; color: {osc}; border-radius: 20px; }}
.notification .notification-action label {{ color: {osc}; }}
.notification .notification-action:hover, .notification .notification-action:focus {{ background: {secondary}; }}
.notification .notification-action:hover label, .notification .notification-action:focus label {{ color: {on_secondary}; }}
'''
    outputs['swayosd'] += f'''
window#osd #container {{ background: {pc}; border-radius: 24px 8px 24px 8px; padding: 8px 12px; }}
window#osd label, window#osd image {{ color: {opc}; }}
window#osd progress, window#osd segment.active {{ background: {primary}; border-radius: 6px; }}
'''
    outputs['rofi'] += f'''
inputbar {{ background-color: @bg-alt; border-radius: 24px; padding: 12px; }}
element {{ border-radius: 24px 8px 24px 8px; padding: 12px; }}
prompt {{ text-color: @accent; }}
'''
    # Wlogout's pale bitmap glyphs cannot inherit CSS color, even in light mode.
    bitmap_fg = max((fg, c['surface']), key=luminance)
    outputs['wlogout'] = f'''
window {{ background-color: {c['surface']}; }}
button {{ background-color: mix({sc}, #000000, .8); color: {bitmap_fg}; border: 2px solid transparent; {shape} transition: background-color 200ms ease-out, border-color 200ms ease-out, border-radius 220ms ease-out; }}
button label {{ color: {bitmap_fg}; }}
button:focus, button:hover {{ background-color: mix({pc}, #000000, .8); border-color: {primary}; }}
#shutdown:focus, #shutdown:hover {{ background-color: mix({c['error_container']}, #000000, .8); border-color: {c['error']}; }}
button:active {{ border-radius: 12px; }}
'''
    outputs['gtklock'] = f'''
window {{ background-color: {c['surface']}; color: {fg}; }}
#window-box {{ background: {bg}; border: none; box-shadow: none; {shape} }}
#clock-label {{ color: {primary}; font-weight: 800; }}
#date-label {{ color: {muted}; }}
#input-field {{ background: {raised}; color: {fg}; border-radius: 24px; border-color: {primary}; }}
#unlock-button {{ background: {primary}; color: {on_primary}; border-radius: 24px 8px 24px 8px; }}
#unlock-button:hover, #unlock-button:focus {{ background: {pc}; color: {opc}; }}
#powerbar-box button {{ background: {sc}; color: {osc}; border-radius: 18px; }}
#powerbar-box button:hover, #powerbar-box button:focus {{ background: {secondary}; color: {on_secondary}; }}
#powerbar-box #poweroff-button:hover, #powerbar-box #poweroff-button:focus {{ background: {c['error']}; color: {c['on_error']}; }}
'''
    return outputs
