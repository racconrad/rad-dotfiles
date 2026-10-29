"""Resident Eww controls. Service work runs outside GTK; secrets use stdin only."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import backend as shell
import positioning
from transport import send

HOME = Path.home()
ROOT = Path(os.environ.get('XDG_RUNTIME_DIR', HOME / '.cache')) / 'raccon-menu'
STATE = HOME / '.local/state/desktop-panel'
PAGES = ('audio', 'connections', 'bluetooth', 'calendar')
CONFIG = HOME / '.config/raccon-menu'
SERVICE_PAGES = dict(audio=4, connections=5, bluetooth=6, calendar=7)
_bus = None
PAGE_SIZE = 4


def command(argv, timeout=3, stdin=None):
    result = subprocess.run([str(x) for x in argv], input=stdin, capture_output=True, text=True,
                            timeout=timeout, env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Could not complete the operation.')
    return result.stdout.strip()


def fields(line):
    result, value, escaped = [], '', False
    for char in line:
        if escaped:
            value += char
            escaped = False
        elif char == '\\': escaped = True
        elif char == ':': result.append(value); value = ''
        else: value += char
    result.append(value)
    return result


def token(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def defaults(kind):
    base = dict(available=False, ready=False, error='', title='Loading…')
    if kind == 'audio':
        device = dict(name='', title='No device', token='', volume=0, mute=False)
        base.update(outputs=[], inputs=[], output=device.copy(), input=device.copy())
    elif kind == 'connections': base.update(enabled=False, networks=[], empty=True)
    else: base.update(enabled=False, scanning=False, adapters=[], devices=[], empty=True)
    return base


def audio_snapshot():
    commands = [['pactl', '-f', 'json', *args] for args in (['info'], ['list', 'sinks'], ['list', 'sources'])]
    with ThreadPoolExecutor(max_workers=3) as pool:
        info, outputs, inputs = list(pool.map(lambda args: json.loads(command(args)), commands))
    result = defaults('audio')
    for key, devices, default_key in (('output', outputs, 'default_sink_name'),
                                      ('input', [x for x in inputs if not x['name'].endswith('.monitor')], 'default_source_name')):
        rows = []
        for device in devices:
            percentages = [int(re.search(r'\d+', channel.get('value_percent', '0')).group())
                           for channel in device.get('volume', {}).values()]
            rows.append(dict(name=device['name'], token=token(device['name']),
                             title=device.get('description') or device['name'], mute=device.get('mute', False),
                             volume=round(sum(percentages) / len(percentages)) if percentages else 0,
                             active=device['name'] == info.get(default_key, info.get(default_key.replace('_name', '')))))
        result[key+'s'] = rows
        result[key] = next((x for x in rows if x['active']), rows[0] if rows else result[key])
    result.update(available=True, ready=True)
    return result


def wifi_snapshot():
    with ThreadPoolExecutor(max_workers=2) as pool:
        enabled = pool.submit(command, ['nmcli', 'radio', 'wifi'])
        rows = pool.submit(command, ['nmcli', '-t', '-f', 'IN-USE,SSID,BSSID,SIGNAL,SECURITY,DEVICE',
                                     'device', 'wifi', 'list', '--rescan', 'no'])
        networks = {}
        for line in rows.result().splitlines():
            parts = fields(line)
            if len(parts) != 6 or not parts[1]: continue
            active, ssid, bssid, signal, security, device = parts
            item = dict(active=active == '*', title=ssid, bssid=bssid, device=device,
                        token=token(bssid+'|'+device), signal=int(signal or 0), secured=security not in ('', '--'),
                        security=security if security not in ('', '--') else 'Open')
            old = networks.get(ssid)
            if old is None or item['active'] or not old['active'] and item['signal'] > old['signal']:
                networks[ssid] = item
        is_enabled = enabled.result() == 'enabled'
        title = next((item['title'] for item in networks.values() if item['active']), 'Disconnected' if is_enabled else 'Off')
        return dict(available=True, ready=True, error='', title=title, enabled=is_enabled,
                    networks=sorted(networks.values(), key=lambda x: (not x['active'], -x['signal'])), empty=not bool(networks))


def bluez(path, interface, method, parameters=None, timeout=2500):
    global _bus
    from gi.repository import Gio
    if _bus is None: _bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    return _bus.call_sync('org.bluez', path, interface, method, parameters, None,
                         Gio.DBusCallFlags.NONE, timeout, None).unpack()


def bluetooth_snapshot():
    objects = bluez('/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects')[0]
    adapters, devices = [], []
    for path, interfaces in objects.items():
        props = interfaces.get('org.bluez.Adapter1')
        if props is not None:
            adapters.append(dict(path=path, token=token(path), enabled=props.get('Powered', False),
                                 scanning=props.get('Discovering', False)))
        props = interfaces.get('org.bluez.Device1')
        if props is not None:
            battery = interfaces.get('org.bluez.Battery1', {}).get('Percentage')
            devices.append(dict(path=path, token=token(path), title=props.get('Alias') or props.get('Address', 'Device'),
                                connected=props.get('Connected', False), paired=props.get('Paired', False),
                                battery=f'{battery}%' if isinstance(battery, int) and 0 <= battery <= 100 else '',
                                address=props.get('Address', ''), trusted=props.get('Trusted', False),
                                kind={'audio-headset':'Headphones', 'audio-headphones':'Headphones',
                                      'audio-card':'Audio', 'input-keyboard':'Keyboard', 'input-mouse':'Mouse',
                                      'input-gaming':'Controller', 'phone':'Phone', 'computer':'Computer'}.get(props.get('Icon'), 'Device'),
                                icon=props.get('Icon') or 'bluetooth-symbolic',
                                signal=f"{props['RSSI']} dBm" if 'RSSI' in props else 'No data'))
    devices.sort(key=lambda x: (not x['connected'], not x['paired'], x['title'].casefold()))
    enabled = any(x['enabled'] for x in adapters)
    title = next((device['title'] for device in devices if device['connected']), 'Disconnected' if enabled else 'Off')
    return dict(ready=True, available=bool(adapters), title=title, enabled=enabled,
                scanning=any(x['scanning'] for x in adapters), adapters=adapters, devices=devices, empty=not bool(devices),
                error='' if adapters else 'No Bluetooth adapter found.')


def refresh(kind):
    try:
        data = {'audio': audio_snapshot, 'connections': wifi_snapshot, 'bluetooth': bluetooth_snapshot}[kind]()
    except Exception:
        data = defaults(kind)
        data.update(ready=True, title='Unavailable', error={'audio':'Audio service is not responding.',
            'connections':'Could not query NetworkManager.', 'bluetooth':'Bluetooth is unavailable.'}[kind])
    shell.write(STATE / (kind+'.json'), json.dumps(data, ensure_ascii=False))
    return data


def active(kind):
    try:
        return (ROOT/'visible').read_text().strip() == '1' and (ROOT/'page').read_text().strip() == str(SERVICE_PAGES[kind])
    except OSError: return False


def wake(kind):
    shell.write(ROOT / ('refresh-'+kind), str(time.time_ns()))


def empty_wifi():
    return dict(token='', title='', secured=False, active=False, signal=0, security='')


def device_info(row=None):
    return dict(dict(token='', title='', icon='bluetooth-symbolic', connected=False,
                     paired=False, battery='', address='', trusted=False, kind='Device', signal='No data'), **(row or {}))


def presentation(kind, data):
    """Paginate the cached snapshot without rescans or nested scrolling."""
    if kind == 'audio': return data
    group = 'networks' if kind == 'connections' else 'devices'
    rows = data.get(group, [])
    count = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    try: page = int((ROOT / ('list-page-'+kind)).read_text())
    except (OSError, ValueError): page = 0
    page = max(0, min(page, count - 1))
    result = dict(data, rows=rows[page*PAGE_SIZE:(page+1)*PAGE_SIZE], list_page=page,
                  page_count=count, total=len(rows), detail=device_info())
    if kind == 'bluetooth':
        try: chosen = (ROOT/'bt-selected').read_text().strip()
        except OSError: chosen = ''
        result['rows'] = [device_info(row) for row in result['rows']]
        result['detail'] = device_info(next((x for x in rows if x['token'] == chosen), None))
    return result


def listen(kind):
    data = {**defaults(kind), **shell.read(STATE / (kind+'.json'), {})}
    shown = presentation(kind, data)
    print(json.dumps(shown, ensure_ascii=False), flush=True)
    deadline, previous, discovery = 0, '', set()
    while True:
        if active(kind):
            try: marker = (ROOT / ('refresh-'+kind)).read_text()
            except OSError: marker = ''
            now = time.monotonic()
            if now >= deadline or marker != previous:
                if kind == 'bluetooth':
                    try: scanning = float((ROOT/'scan-until').read_text()) > time.time()
                    except (OSError, ValueError): scanning = False
                    for path in discovery.copy():
                        if not scanning:
                            try: bluez(path, 'org.bluez.Adapter1', 'StopDiscovery')
                            except Exception: pass
                            discovery.discard(path)
                    if scanning:
                        for adapter in data.get('adapters', []):
                            if adapter['enabled'] and adapter['path'] not in discovery:
                                try:
                                    bluez(adapter['path'], 'org.bluez.Adapter1', 'StartDiscovery')
                                    discovery.add(adapter['path'])
                                except Exception: pass
                fresh = refresh(kind)
                frame = presentation(kind, fresh)
                if frame != shown:
                    print(json.dumps(frame, ensure_ascii=False), flush=True)
                    shown = frame
                data = fresh
                previous = marker
                deadline = now + (1 if kind == 'audio' else 2)
            # UI navigation uses the current snapshot; it must never trigger a radio query.
            frame = presentation(kind, data)
            if frame != shown:
                print(json.dumps(frame, ensure_ascii=False), flush=True)
                shown = frame
        elif discovery:
            for path in discovery:
                try: bluez(path, 'org.bluez.Adapter1', 'StopDiscovery')
                except Exception: pass
            discovery.clear()
        time.sleep(.25)


def selected(kind, value, group):
    if not re.fullmatch(r'[0-9a-f]{24}', value): raise ValueError('Invalid selection.')
    row = next((x for x in shell.read(STATE/(kind+'.json'), {}).get(group, []) if x['token'] == value), None)
    if row is None: raise ValueError('Device changed. Refresh the list.')
    return row


def sync_appearance():
    for filename in ('_palette.scss', '_desktop-style.scss'):
        source = HOME / '.config/raccon-menu' / filename
        destination = CONFIG / filename
        text = source.read_text() if source.exists() else '/* No global override */\n'
        if not destination.exists() or destination.read_text() != text:
            shell.write(destination, text)


def pair_device(path):
    """Register an agent scoped to this explicit pairing request, without replacing others."""
    from gi.repository import Gio, GLib
    global _bus
    if _bus is None: _bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    xml = '<node><interface name="org.bluez.Agent1">' + ''.join(
        '<method name="'+name+'">'+arguments+'</method>' for name, arguments in (
            ('Release',''), ('Cancel',''),
            ('RequestConfirmation','<arg type="o" direction="in"/><arg type="u" direction="in"/>'),
            ('RequestAuthorization','<arg type="o" direction="in"/>'),
            ('AuthorizeService','<arg type="o" direction="in"/><arg type="s" direction="in"/>'),
            ('RequestPinCode','<arg type="o" direction="in"/><arg type="s" direction="out"/>'),
            ('RequestPasskey','<arg type="o" direction="in"/><arg type="u" direction="out"/>'),
            ('DisplayPinCode','<arg type="o" direction="in"/><arg type="s" direction="in"/>'),
            ('DisplayPasskey','<arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/>'),
        )) + '</interface></node>'
    def handle(connection, sender, object_path, interface, method, parameters, invocation):
        values = parameters.unpack()
        if method in ('RequestPinCode','RequestPasskey'):
            invocation.return_dbus_error('org.bluez.Error.Rejected','This device requires a PIN or passkey.')
        elif values and values[0] != path:
            invocation.return_dbus_error('org.bluez.Error.Rejected','Device not selected.')
        else: invocation.return_value(GLib.Variant('()',()))
    agent = '/org/raccon/DesktopPanel/Agent'
    registration = _bus.register_object(agent,Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],handle,None,None)
    registered = False
    try:
        bluez('/org/bluez','org.bluez.AgentManager1','RegisterAgent',GLib.Variant('(os)',(agent,'NoInputNoOutput')))
        registered = True
        loop, result = GLib.MainLoop(), []
        def done(bus, answer, data):
            try: bus.call_finish(answer)
            except Exception as exc: result.append(exc)
            loop.quit()
        _bus.call('org.bluez',path,'org.bluez.Device1','Pair',None,None,Gio.DBusCallFlags.NONE,30000,None,done,None)
        loop.run()
        if result: raise RuntimeError('Could not pair. If a PIN is required, use a compatible pairing tool.')
    finally:
        if registered:
            try: bluez('/org/bluez','org.bluez.AgentManager1','UnregisterAgent',GLib.Variant('(o)',(agent,)))
            except Exception: pass
        _bus.unregister_object(registration)


def configure():
    # Service actions and providers target the same resident menu instance.
    shell.CONFIG, shell.RUNTIME = CONFIG, ROOT



def action(args):
    from gi.repository import GLib
    operation = args[0]
    if operation in ('wifi-page', 'bt-page'):
        kind = 'connections' if operation == 'wifi-page' else 'bluetooth'
        if args[1] not in ('next', 'previous'): raise ValueError('Invalid page.')
        frame = presentation(kind, shell.read(STATE/(kind+'.json'), defaults(kind)))
        page = max(0, min(frame['list_page'] + (1 if args[1] == 'next' else -1), frame['page_count'] - 1))
        shell.write(ROOT/('list-page-'+kind), str(page))
    elif operation == 'bt-select':
        row = selected('bluetooth', args[1], 'devices')
        shell.write(ROOT/'bt-selected', row['token'])
    elif operation == 'bt-back':
        shell.write(ROOT/'bt-selected', '')
    elif operation == 'wifi-select':
        row = selected('connections', args[1], 'networks')
        shell.update(wifi_selected=dict(token=row['token'], title=row['title'], secured=row['secured'], active=row['active'],
                                        signal=row.get('signal', 0), security=row.get('security', 'Secured' if row['secured'] else 'Open')))
    elif operation == 'wifi-connect':
        value = shell.eww('get', 'wifi_selected')
        row = selected('connections', json.loads(value)['token'], 'networks')
        secret = sys.stdin.read(1025)
        if len(secret) > 1024 or '\n' in secret or '\r' in secret: raise ValueError('Invalid password.')
        shell.update(wifi_busy=True, error='')
        try:
            argv = ['nmcli', '--wait', '20'] + (['--ask'] if secret else [])
            argv += ['device', 'wifi', 'connect', row['bssid'], 'ifname', row['device']]
            command(argv, timeout=25, stdin=secret+'\n' if secret else None)
            shell.update(wifi_selected=empty_wifi())
        finally: shell.update(wifi_busy=False)
        wake('connections')
    elif operation == 'wifi-disconnect':
        row = selected('connections', args[1], 'networks')
        if not row['active']: raise ValueError('Network is already disconnected.')
        command(['nmcli', '--wait', '8', 'device', 'disconnect', row['device']], timeout=10)
        shell.update(wifi_selected=empty_wifi());wake('connections')
    elif operation == 'wifi-power':
        if args[1] not in ('on','off'): raise ValueError('Invalid Wi-Fi state.')
        command(['nmcli', 'radio', 'wifi', args[1]]);wake('connections')
    elif operation == 'wifi-scan':
        shell.update(wifi_busy=True, error='')
        try: command(['nmcli', '--wait', '8', 'device', 'wifi', 'rescan'], timeout=10)
        finally: shell.update(wifi_busy=False);wake('connections')
    elif operation in ('audio-device', 'audio-mute'):
        kind = args[1]
        if kind not in ('output','input'): raise ValueError('Invalid audio device.')
        row = selected('audio', args[2], kind+'s')
        target = 'sink' if kind == 'output' else 'source'
        argv = ['pactl', 'set-default-'+target, row['name']] if operation == 'audio-device' else ['pactl', 'set-'+target+'-mute', row['name'], 'toggle']
        command(argv);wake('audio')
    elif operation == 'bt-power':
        if args[1] not in ('on','off'): raise ValueError('Invalid Bluetooth state.')
        for adapter in shell.read(STATE/'bluetooth.json', {}).get('adapters', []):
            if not re.fullmatch(r'/org/bluez/hci\d+', adapter['path']): continue
            bluez(adapter['path'], 'org.freedesktop.DBus.Properties', 'Set',
                  GLib.Variant('(ssv)', ('org.bluez.Adapter1','Powered',GLib.Variant('b',args[1]=='on'))))
        wake('bluetooth')
    elif operation == 'bt-scan':
        shell.write(ROOT/'scan-until', str(time.time()+20));wake('bluetooth')
    elif operation == 'bt-device':
        row = selected('bluetooth', args[1], 'devices')
        if not re.fullmatch(r'/org/bluez/hci\d+/dev_[0-9A-Fa-f_]+', row['path']): raise ValueError('Invalid device.')
        shell.update(bt_busy=True, error='')
        try:
            if not row['paired']:
                pair_device(row['path'])
            bluez(row['path'], 'org.bluez.Device1', 'Disconnect' if row['connected'] else 'Connect', timeout=20000)
        finally: shell.update(bt_busy=False);wake('bluetooth')
    elif operation == 'advanced':
        if args[1] != 'audio': raise ValueError('Invalid panel.')
        shell.close()
        subprocess.Popen(['pavucontrol'],start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    elif operation == 'cancel-wifi': shell.update(wifi_selected=empty_wifi())
    else: raise ValueError('Invalid action.')


def main(args):
    configure()
    operation = args[0] if args else 'audio'
    if operation == 'listen': listen(args[1]);return
    if operation == 'diagnose': shell.main(['diagnose']);return
    if operation == 'prepare': shell.show('home', prewarm=True);return
    if operation == 'close': shell.close();return
    if operation == 'opened':
        positioning.refresh(ROOT, force=True)
        for kind in PAGES:
            if kind != 'calendar': wake(kind)
        shell.update(error='');return
    if operation in PAGES:
        if not send('service '+str(SERVICE_PAGES[operation]), str(ROOT)):
            shell.show(operation)
        return
    if operation == 'tab':
        if args[1] not in PAGES: raise ValueError('Invalid panel.')
        if not send('service '+str(SERVICE_PAGES[args[1]]), str(ROOT)): shell.show(args[1])
        return
    ROOT.mkdir(parents=True,exist_ok=True)
    kind = 'bluetooth' if operation.startswith('bt-') else 'audio' if operation.startswith('audio-') else 'connections'
    with (ROOT/('action-'+kind+'.lock')).open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        shell.update(error='')
        action(args)


if __name__ == '__main__':
    try: main(sys.argv[1:])
    except (KeyboardInterrupt, BrokenPipeError): pass
    except Exception as exc:
        # Command failures can contain SSIDs/device names, never log input secrets.
        message = str(exc)
        if sys.argv[1:2] == ['wifi-connect']:
            message = 'Could not connect. Check the password and try again.'
        try:
            resets = dict(error=message)
            if sys.argv[1:2] and sys.argv[1].startswith('wifi-'): resets['wifi_busy'] = False
            if sys.argv[1:2] and sys.argv[1].startswith('bt-'): resets['bt_busy'] = False
            shell.update(**resets)
        except Exception: pass
        print('Panel:',message,file=sys.stderr)
        raise SystemExit(1)
