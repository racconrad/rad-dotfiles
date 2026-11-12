"""Static search targets resolve only through the menu's existing allowlists."""
TARGETS = {
    'audio': ('Audio settings', 'audio-volume-high-symbolic', 'Setting', 'tab', 'audio', 'sound volume microphone sonido volumen microfono'),
    'connections': ('Network settings', 'network-wireless-symbolic', 'Setting', 'tab', 'connections', 'wifi internet redes conexiones'),
    'bluetooth': ('Bluetooth settings', 'bluetooth-symbolic', 'Setting', 'tab', 'bluetooth', 'devices dispositivos'),
    'calendar': ('Calendar', 'x-office-calendar-symbolic', 'Setting', 'tab', 'calendar', 'date calendario fecha'),
    'modes': ('Power modes', 'preferences-system-symbolic', 'Setting', 'tab', 'modes', 'battery performance energia bateria rendimiento'),
    'shortcuts': ('Keyboard shortcuts', 'input-keyboard-symbolic', 'Setting', 'tab', 'shortcuts', 'keys hotkeys teclado atajos'),
    'notifications': ('Notifications', 'preferences-system-notifications-symbolic', 'Action', 'shortcut', 'notifications', 'notificaciones avisos'),
    'lock': ('Lock screen', 'system-lock-screen-symbolic', 'Action', 'shortcut', 'lock', 'bloquear pantalla'),
}


def rows(apps):
    result = [dict(app, category='Application', action='launch', value=app['token'], pinnable=True) for app in apps]
    for key, (name, icon, category, _command, _value, aliases) in TARGETS.items():
        result.append(dict(name=name, icon=icon, category=category, action='search-action', value=key,
                           search=(name + ' ' + category + ' ' + aliases).casefold(),
                           has_file=False, file='', pinned=False, pinnable=False, ref=key))
    return result


def resolve(key):
    if key not in TARGETS:
        raise ValueError('Invalid search action.')
    return list(TARGETS[key][3:5])
