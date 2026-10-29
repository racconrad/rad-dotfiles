"""Pure battery policy: safe to test without changing a desktop."""
MODES = ('performance', 'balanced', 'complete', 'working')


def choose_mode(source, battery, settings, previous=None):
    if source in MODES:
        return source
    if battery.get('plugged') is True:
        return 'complete'
    if battery.get('plugged') is None or battery.get('percent') is None:
        return previous if previous in MODES else 'complete'
    percent = battery['percent']
    low = settings['low_battery']
    if percent < low:
        return 'performance'
    if previous == 'performance' and percent < low + settings['recovery_margin']:
        return 'performance'
    return 'balanced'


def should_suspend(battery, preference):
    return (preference.get("mode") != "working"
            and battery.get("plugged") is False and battery.get("batteries", 0) > 0)


def battery_level(percent, settings):
    if percent is None:
        return 'unknown'
    if percent <= settings['critical']:
        return 'critical'
    if percent <= settings['warning']:
        return 'warning'
    if percent >= settings['high']:
        return 'high'
    return 'normal'


def notifications(battery, flags, settings):
    flags = dict(flags)
    percent = battery.get('percent')
    if battery.get('plugged') is True:
        return [], {}
    if percent is None or battery.get('plugged') is None:
        return [], flags
    for key, threshold in (('warning', settings['warning']), ('critical', settings['critical'])):
        if percent >= threshold + settings['notification_reset']:
            flags.pop(key, None)
    if percent <= settings['critical'] and not flags.get('critical'):
        flags.update(critical=True, warning=True)
        return [('critical', f'Batería al {percent}%', 'Conecta el cargador. Puedes cambiar el modo desde Waybar.')], flags
    if percent <= settings['warning'] and not flags.get('warning'):
        flags['warning'] = True
        return [('normal', f'Batería al {percent}%', f"Ahorro automático por debajo del {settings['low_battery']}%. El modo manual se respeta.")], flags
    return [], flags
