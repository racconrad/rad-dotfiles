"""Smoked metal surfaces and theme-tinted instrument accents for Raccon."""
import colorsys


def palette(source):
    colors = dict(source)

    def tone(seed, lightness, saturation):
        channels = [int(seed[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        hue = colorsys.rgb_to_hls(*channels)[0]
        return '#' + ''.join(f'{round(channel * 255):02x}' for channel in
                             colorsys.hls_to_rgb(hue, lightness, saturation))

    seed = colors['primary']
    graphite = tone(seed, .075, .08)
    silver = tone(seed, .94, .04)
    colors.update(surface=graphite, background=graphite, surface_dim=graphite,
                  surface_bright=tone(seed, .20, .06), surface_container_lowest=tone(seed, .055, .08),
                  surface_container_low=tone(seed, .09, .08), surface_container=tone(seed, .115, .08),
                  surface_container_high=tone(seed, .15, .07), surface_container_highest=tone(seed, .19, .06),
                  surface_variant=tone(seed, .19, .06), on_surface=silver, on_background=silver,
                  on_surface_variant=tone(seed, .77, .05), outline=tone(seed, .59, .08),
                  outline_variant=tone(seed, .39, .08), inverse_surface=silver,
                  inverse_on_surface=graphite)
    for role in ('primary', 'secondary', 'tertiary', 'error'):
        accent = tone(source.get(role, seed), .76, .62)
        colors.update({role: accent, 'on_' + role: graphite,
                       role + '_container': tone(source.get(role, seed), .23, .23),
                       'on_' + role + '_container': silver, role + '_fixed': accent,
                       role + '_fixed_dim': accent, 'on_' + role + '_fixed': graphite,
                       'on_' + role + '_fixed_variant': graphite})
    colors['surface_tint'] = colors['primary']
    colors['inverse_primary'] = tone(seed, .30, .6)
    return colors, [colors[key] for key in ('surface', 'surface_container', 'primary', 'secondary', 'on_surface')]


def decorate(outputs, colors):
    bg, raised, fg, edge, accent, signal = [colors[key] for key in
        ('surface_container', 'surface_container_highest', 'on_surface', 'outline_variant', 'primary', 'secondary')]
    # The top reflection describes the metal housing; controls stay flat and readable.
    smoked = 'rgba(' + ','.join(str(int(bg[i:i + 2], 16)) for i in (1, 3, 5)) + ',.96)'
    housing = (f'background-color: {smoked}; background-image: linear-gradient(to bottom, {raised}, {smoked} 48px); '
               f'border: 1px solid {edge}; box-shadow: inset 0 1px rgba(255,255,255,.16), 0 8px 20px rgba(0,0,0,.30);')
    outputs['raccon'] += f'''
.popup .panel.panel, .popup .side-panel.side-panel {{ {housing} }}
.popup .header {{ border-bottom: 1px solid {edge}; padding-bottom: 12px; }}
.popup .title {{ font-size: 24px; font-weight: 700; color: {fg}; }}
.popup .search-bar {{ background: {bg}; border-color: {accent}; box-shadow: inset 0 2px 4px rgba(0,0,0,.28); }}
.popup .daily-app {{ background: {raised}; border: 1px solid {edge}; }}
.popup .daily-app:hover, .popup .daily-app:focus {{ border-color: {accent}; }}
.popup .music-progress trough {{ min-height: 5px; background: {raised}; }}
.popup .music-progress progress {{ background-image: linear-gradient(to right, {accent}, {signal}); }}
.popup .music-art {{ border: 1px solid {edge}; box-shadow: 0 4px 12px rgba(0,0,0,.25); }}
.popup .music-time, .popup .service-status {{ font-family: "JetBrainsMono Nerd Font Mono"; color: {signal}; }}
.popup .nav-tab.current {{ box-shadow: inset 0 -2px {signal}; }}
.popup.motion button {{ transition: background-color 160ms ease-out, border-color 160ms ease-out; }}
.popup.motion .daily-app image {{ transition: -gtk-icon-transform 180ms ease-out; }}
.popup.motion .daily-app:hover image {{ -gtk-icon-transform: scale(1.06); }}
.popup.still, .popup.still * {{ transition: none; animation: none; -gtk-icon-transform: none; }}
'''
    outputs['waybar'] += f'''
window#waybar .modules-left, window#waybar .modules-right, window#waybar #taskbar {{ {housing} border-radius: 20px; }}
window#waybar #taskbar {{ padding: 3px 10px; }}
window#waybar #taskbar button, window#waybar #taskbar button:hover, window#waybar #taskbar button.active {{ min-height: 38px; padding: 4px 8px; margin: 3px 2px; border-radius: 13px; }}
window#waybar #taskbar button.active {{ background: {raised}; box-shadow: inset 0 -3px {accent}; color: {fg}; }}
window#waybar #taskbar button.active:hover {{ background: {raised}; color: {fg}; }}
window#waybar #taskbar button:hover {{ border-color: {accent}; }}
window#waybar #clock {{ color: {signal}; font-family: "JetBrainsMono Nerd Font Mono"; background: {bg}; border: 1px solid {edge}; }}
window#waybar #cpu, window#waybar #memory, window#waybar #temperature {{ font-family: "JetBrainsMono Nerd Font Mono"; }}
window#waybar #taskbar.empty {{ background: transparent; background-image: none; box-shadow: none; border: none; padding: 0; min-height: 0; }}
'''
    outputs['selector'] += f'''
.style-selector .panel.panel {{ {housing} }}
.style-selector .header {{ border-bottom: 1px solid {edge}; padding-bottom: 12px; }}
.style-selector .preview-title {{ color: {signal}; }}
'''
    outputs['panels'] += f'#desktop-menu .panel {{ {housing} }}\n'
    outputs['swaync'] += f'''
.control-center.control-center, .notification.notification {{ {housing} }}
.notification .summary {{ color: {fg}; font-weight: 700; }}
.notification .time {{ color: {signal}; font-family: "JetBrainsMono Nerd Font Mono"; }}
'''
    outputs['widgets'] += f'''
.rw-motion-space .rw-desktop.wroot .card.card, .rw-motion-space .rw-desktop.wroot .clock-card.clock-card {{ {housing} }}
.rw-desktop.wroot .gen-sub, .rw-desktop.wroot .date {{ font-family: "JetBrainsMono Nerd Font Mono"; }}
.rw-desktop.wroot .gen-title, .rw-desktop.wroot .pl-title {{ color: {signal}; }}
.rw-desktop.wroot progress highlight {{ background: {signal}; }}
.rw-motion-space .rw-window-frame .rw-window-body .card.card, .rw-motion-space .rw-window-frame .rw-window-body .clock-card.clock-card {{ background: transparent; background-image: none; box-shadow: none; border: none; }}
'''
    outputs['widget_editor'] += f'.tinywidgets-editor .panel {{ {housing} }}\n'
    return outputs


def preview_svg(colors, font):
    from html import escape
    bg, panel, raised, fg, edge, accent, signal = [colors[key] for key in
        ('surface', 'surface_container', 'surface_container_highest', 'on_surface', 'outline_variant', 'primary', 'secondary')]
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280" viewBox="0 0 440 280">
<defs><linearGradient id="metal" x2="0" y2="1"><stop stop-color="{colors['surface_bright']}"/><stop offset=".3" stop-color="{panel}"/><stop offset="1" stop-color="{bg}"/></linearGradient>
<filter id="depth" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dy="4" stdDeviation="4" flood-opacity=".5"/></filter></defs>
<rect width="440" height="280" rx="12" fill="{bg}"/>
<path d="M0 195 Q180 15 440 65" fill="none" stroke="{accent}" stroke-width="70" opacity=".08"/>
<path d="M0 250 Q220 80 440 120" fill="none" stroke="{signal}" stroke-width="32" opacity=".06"/>''']

    def box(x, y, width, height, fill='url(#metal)', radius=15, shadow=False):
        effect = ' filter="url(#depth)"' if shadow else ''
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{edge}"{effect}/>')

    def text(x, y, value, size=11, color=fg, mono=False):
        family = 'monospace' if mono else escape(font)
        parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" font-size="{size}">{escape(value)}</text>')

    box(14, 12, 412, 25, radius=10)
    text(27, 29, 'Raccon', 11, accent)
    text(89, 29, 'Desktop', 10)
    text(340, 29, '10:24', 11, signal, True)
    box(17, 54, 132, 81, shadow=True)
    text(30, 82, '10:24', 27, fg, True)
    text(31, 106, 'My desktop', 10, signal, True)
    box(17, 146, 132, 67, shadow=True)
    text(30, 164, 'Music', 11)
    box(29, 174, 27, 27, raised, 6)
    parts.append(f'<path d="M37 182 L37 194 L47 188 Z" fill="{signal}"/>')
    for index in range(10):
        parts.append(f'<rect x="{65 + index * 6}" y="187" width="4" height="8" rx="1" fill="{signal if index < 6 else edge}"/>')
    box(165, 54, 258, 160, shadow=True)
    text(181, 79, 'Raccon Menu', 17)
    parts.append(f'<path d="M181 89 H407" stroke="{signal}" opacity=".7"/>')
    box(180, 99, 228, 25, bg, 8)
    text(190, 116, 'Search apps', 10, colors['on_surface_variant'])
    for index, label in enumerate(('Apps', 'Files', 'Terminal')):
        x = 180 + index * 78
        box(x, 136, 70, 62, raised, 12)
        fill = accent if index == 0 else signal
        parts.append(f'<rect x="{x + 24}" y="147" width="22" height="22" rx="6" fill="{fill}"/>')
        text(x + 10, 187, label, 9)
    box(112, 231, 216, 41, shadow=True)
    for index in range(5):
        x = 122 + index * 40
        box(x, 236, 34, 30, raised, 9)
        parts.append(f'<rect x="{x + 9}" y="242" width="16" height="16" rx="4" fill="{accent if index == 2 else signal}" opacity=".9"/>')
        if index == 2:
            parts.append(f'<rect x="{x + 13}" y="269" width="8" height="2" rx="1" fill="{accent}"/>')
    return ''.join(parts) + '</svg>'
