#!/usr/bin/env python3
"""Small visual controls sharing desktop-menu's theme and keyboard shell."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import threading
import uuid

CORE = runpy.run_path(str(Path.home() / '.local/lib/raccon_menu/legacy_menu.py'), run_name='menu_core')
Menu, Gtk, GLib, Gio = (CORE[name] for name in ('Menu', 'Gtk', 'GLib', 'Gio'))
box, label = CORE['box'], CORE['label']
HOME = Path.home()
PLANNER = HOME / '.config/eww/scripts/planner'
EVENTS = HOME / '.local/share/desktop-menu/events.json'


def command(argv, stdin=None):
    result = subprocess.run(argv, input=stdin, text=True, capture_output=True, timeout=35,
                            env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'The operation did not complete.')
    return result.stdout.strip()


def nm_fields(line):
    fields, value, escaped = [], '', False
    for char in line:
        if escaped:
            value += char
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == ':':
            fields.append(value)
            value = ''
        else:
            value += char
    fields.append(value)
    return fields


def read_events():
    try:
        data = json.loads(EVENTS.read_text())
        return [item for item in data if isinstance(item, dict) and
                all(isinstance(item.get(key), str) for key in ('id', 'date', 'title'))]
    except (OSError, ValueError, TypeError):
        return []


def save_events(events):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    tmp = EVENTS.with_suffix('.tmp')
    tmp.write_text(json.dumps(events, ensure_ascii=False, indent=2))
    tmp.replace(EVENTS)


class Panel(Menu):
    def __init__(self, surface, preview=False):
        super().__init__(preview=preview)
        self.surface = surface
        self.panel_title = {'audio': 'Audio', 'connections': 'Connections', 'calendar': 'Calendar'}[surface]
        self.set_application_id('org.raccon.DesktopPanel.' + surface.capitalize())
        self.pending = set()
        self.queued = {}
        self.volume_timers = {}

    def work(self, key, function, callback=None):
        if key in self.pending:
            operation = (function, callback)
            if key == 'refresh' or key.startswith(('volume-', 'mute-', 'device-', 'wifi-toggle', 'profile')):
                # State setters keep the last requested value, even on a slow service.
                self.queued[key] = [operation]
            else:
                # Actions such as two different task toggles must both run.
                self.queued.setdefault(key, []).append(operation)
            return
        self.pending.add(key)
        self.activity.set_text('Refreshing…' if key == 'refresh' else 'Applying…')

        def deliver(result, error):
            self.pending.discard(key)
            self.activity.set_text('' if not self.pending else 'Applying…')
            if error:
                self.show_error(error)
            elif callback:
                self.error.hide()
                callback(result)
            waiting = self.queued.get(key, [])
            if waiting:
                next_function, next_callback = waiting.pop(0)
                if not waiting:
                    self.queued.pop(key, None)
                self.work(key, next_function, next_callback)
            return False

        def run():
            try:
                result, error = function(), None
            except Exception as exc:
                result, error = None, str(exc)
            GLib.idle_add(deliver, result, error)
        threading.Thread(target=run, daemon=True).start()

    def button(self, text, callback):
        widget = Gtk.Button(label=text)
        widget.get_child().set_xalign(0)
        widget.get_child().set_max_width_chars(48)
        widget.get_child().set_ellipsize(CORE['Pango'].EllipsizeMode.END)
        widget.connect('clicked', lambda *_: callback())
        return widget

    def run_command(self, key, argv, refresh=False, stdin=None):
        self.work(key, lambda: command(argv, stdin), (lambda _: self.refresh()) if refresh else None)

    def build_panel(self, width):
        root = box(vertical=True, spacing=14)
        toolbar = box(spacing=8)
        self.activity = label('', 'muted')
        toolbar.pack_start(self.activity, True, True, 0)
        toolbar.pack_end(self.button('Refresh', self.refresh), False, False, 0)
        root.pack_start(toolbar, False, False, 0)
        self.body = box(vertical=True, spacing=14)
        root.pack_start(self.body, True, True, 0)
        if self.surface == 'calendar':
            self.build_calendar()
        else:
            GLib.idle_add(self.refresh)
        return root

    def clear(self, container):
        for child in container.get_children():
            container.remove(child)

    def refresh(self):
        if self.surface == 'audio':
            def snapshot():
                return (json.loads(command(['pactl', '-f', 'json', 'info'])),
                        json.loads(command(['pactl', '-f', 'json', 'list', 'sinks'])),
                        json.loads(command(['pactl', '-f', 'json', 'list', 'sources'])))
            self.work('refresh', snapshot, self.audio_ready)
        elif self.surface == 'connections':
            self.work('refresh', self.connections_snapshot, self.connections_ready)
        else:
            self.render_agenda()
        return False

    def audio_ready(self, data):
        self.clear(self.body)
        info, sinks, sources = data
        for title, kind, devices, default in (
            ('Output', 'sink', sinks, info.get('default_sink_name', info.get('default_sink'))),
            ('Microphone', 'source', [x for x in sources if not x['name'].endswith('.monitor')],
             info.get('default_source_name', info.get('default_source'))),
        ):
            self.body.pack_start(label(title, 'section'), False, False, 0)
            if not devices:
                self.body.pack_start(label('No devices available.', 'muted'), False, False, 0)
                continue
            selected = next((x for x in devices if x['name'] == default), devices[0])
            combo = Gtk.ComboBoxText()
            for device in devices:
                combo.append(device['name'], device.get('description') or device['name'])
            combo.set_active_id(selected['name'])
            combo.connect('changed', lambda c, k=kind: self.run_command('device-' + k,
                ['pactl', 'set-default-' + k, c.get_active_id()], refresh=True))
            self.body.pack_start(combo, False, False, 0)
            channels = selected.get('volume', {}).values()
            percentages = [int(re.search(r'\d+', x.get('value_percent', '0')).group()) for x in channels]
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            scale.set_value(sum(percentages) / len(percentages) if percentages else 0)
            scale.set_digits(0)
            scale.set_value_pos(Gtk.PositionType.RIGHT)
            scale.set_hexpand(True)
            device_name = selected['name']
            scale.connect('value-changed', lambda s, k=kind, n=device_name: self.volume_changed(k, n, s.get_value()))
            self.body.pack_start(scale, False, False, 0)
            toggle = Gtk.CheckButton(label='Mute' if kind == 'sink' else 'Mute microphone')
            toggle.set_active(selected.get('mute', False))
            toggle.connect('toggled', lambda t, k=kind, n=device_name: self.run_command('mute-' + k,
                ['pactl', 'set-' + k + '-mute', n, '1' if t.get_active() else '0']))
            self.body.pack_start(toggle, False, False, 0)
        self.body.pack_start(self.action('App mixer', 'audio-card-symbolic', ['pavucontrol']), False, False, 0)
        self.body.show_all()

    def volume_changed(self, kind, name, value):
        if kind in self.volume_timers:
            GLib.source_remove(self.volume_timers[kind])
        def apply():
            self.volume_timers.pop(kind, None)
            self.work('volume-' + kind, lambda: command(['pactl', 'set-' + kind + '-volume', name, f'{round(value)}%']))
            return False
        self.volume_timers[kind] = GLib.timeout_add(180, apply)

    def bluez(self, path, interface, method, parameters=None, timeout=20000):
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        return bus.call_sync('org.bluez', path, interface, method, parameters, None,
                             Gio.DBusCallFlags.NONE, timeout, None).unpack()

    def connections_snapshot(self):
        result = {}
        try:
            result['wifi'] = command(['nmcli', 'radio', 'wifi']) == 'enabled'
            rows = command(['nmcli', '-t', '-f', 'IN-USE,SSID,BSSID,SIGNAL,SECURITY,DEVICE',
                            'device', 'wifi', 'list', '--rescan', 'auto'])
            networks = {}
            for row in rows.splitlines():
                parts = nm_fields(row)
                if len(parts) != 6 or not parts[1]:
                    continue
                active, ssid, bssid, strength, security, device = parts
                item = dict(active=active == '*', ssid=ssid, bssid=bssid,
                            strength=int(strength or 0), security=security, device=device)
                if ssid not in networks or item['active'] or item['strength'] > networks[ssid]['strength'] and not networks[ssid]['active']:
                    networks[ssid] = item
            result['networks'] = sorted(networks.values(), key=lambda x: (not x['active'], -x['strength']))
        except Exception as exc:
            result['wifi_error'] = str(exc)
        try:
            objects = self.bluez('/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects', timeout=5000)[0]
            result['adapters'] = [(path, props['org.bluez.Adapter1']) for path, props in objects.items()
                                  if 'org.bluez.Adapter1' in props]
            result['devices'] = [(path, props['org.bluez.Device1'], props.get('org.bluez.Battery1', {}))
                                 for path, props in objects.items() if 'org.bluez.Device1' in props
                                 and props['org.bluez.Device1'].get('Paired')]
        except Exception as exc:
            result['bluetooth_error'] = str(exc)
        return result

    def connections_ready(self, data):
        self.clear(self.body)
        wifi_header = box(spacing=10)
        wifi_header.pack_start(label('Wi-Fi', 'section'), True, True, 0)
        wifi_switch = Gtk.Switch(active=data.get('wifi', False))
        wifi_switch.set_sensitive('wifi_error' not in data)
        wifi_switch.connect('notify::active', lambda s, _: self.run_command('wifi-toggle',
            ['nmcli', 'radio', 'wifi', 'on' if s.get_active() else 'off'], refresh=True))
        wifi_header.pack_end(wifi_switch, False, False, 0)
        self.body.pack_start(wifi_header, False, False, 0)
        if data.get('wifi_error'):
            self.body.pack_start(label('Could not query NetworkManager.', 'muted'), False, False, 0)
        elif not data.get('networks'):
            self.body.pack_start(label('No networks available.' if data['wifi'] else 'Wi-Fi is off.', 'muted'), False, False, 0)
        for network in data.get('networks', [])[:10]:
            title = f'{network["ssid"]}   {network["strength"]}%'
            if network['active']:
                title += ' · disconnect'
            self.body.pack_start(self.button(title, lambda n=network: self.choose_wifi(n)), False, False, 0)
        self.wifi_form = box(vertical=True, spacing=8)
        self.body.pack_start(self.wifi_form, False, False, 0)
        self.body.pack_start(label('Bluetooth', 'section'), False, False, 0)
        for path, props in data.get('adapters', []):
            powered = props.get('Powered', False)
            def toggle(p=path, value=not powered):
                args = GLib.Variant('(ssv)', ('org.bluez.Adapter1', 'Powered', GLib.Variant('b', value)))
                self.work('bt-power', lambda: self.bluez(p, 'org.freedesktop.DBus.Properties', 'Set', args), lambda _: self.refresh())
            self.body.pack_start(self.button('Turn off Bluetooth' if powered else 'Turn on Bluetooth', toggle), False, False, 0)
        for path, props, battery in data.get('devices', []):
            connected = props.get('Connected', False)
            title = props.get('Alias') or props.get('Address', 'Device')
            if 'Percentage' in battery:
                title += f' · {battery["Percentage"]}%'
            title += ' · disconnect' if connected else ' · connect'
            self.body.pack_start(self.button(title, lambda p=path, c=connected: self.work('bt-device',
                lambda: self.bluez(p, 'org.bluez.Device1', 'Disconnect' if c else 'Connect'), lambda _: self.refresh())), False, False, 0)
        if not data.get('devices'):
            self.body.pack_start(label('No paired devices.' if not data.get('bluetooth_error')
                                       else 'Bluetooth is unavailable.', 'muted'), False, False, 0)
        self.body.show_all()

    def choose_wifi(self, network):
        if network['active']:
            self.work('wifi-connect', lambda: command(['nmcli', 'device', 'disconnect', network['device']]), lambda _: self.refresh())
            return
        self.clear(self.wifi_form)
        self.wifi_form.pack_start(label('Connect to ' + network['ssid'], 'section'), False, False, 0)
        password = Gtk.Entry(placeholder_text='Password (leave blank if saved)')
        password.set_visibility(False)
        secured = network['security'] not in ('', '--')
        if secured:
            self.wifi_form.pack_start(password, False, False, 0)
        def connect():
            secret = password.get_text()
            password.set_text('')
            argv = ['nmcli', '--wait', '25']
            if secret:
                argv += ['--ask']
            argv += ['device', 'wifi', 'connect', network['bssid']]
            # Password travels over stdin, never in process arguments or a file.
            self.work('wifi-connect', lambda: command(argv, secret + '\n' if secret else None), lambda _: self.refresh())
        password.connect('activate', lambda *_: connect())
        self.wifi_form.pack_start(self.button('Connect', connect), False, False, 0)
        self.wifi_form.show_all()
        if secured:
            password.grab_focus()

    def build_calendar(self):
        self.calendar = Gtk.Calendar()
        self.calendar.connect('day-selected', lambda *_: self.render_agenda())
        self.calendar.connect('month-changed', lambda *_: self.render_agenda())
        self.body.pack_start(self.calendar, False, False, 0)
        entry_row = box(spacing=8)
        self.event_entry = Gtk.Entry(placeholder_text='Add an event for the selected day')
        self.event_entry.set_hexpand(True)
        self.event_entry.connect('activate', lambda *_: self.add_event())
        entry_row.pack_start(self.event_entry, True, True, 0)
        entry_row.pack_end(self.button('Add', self.add_event), False, False, 0)
        self.body.pack_start(entry_row, False, False, 0)
        self.agenda = box(vertical=True, spacing=8)
        self.body.pack_start(self.agenda, False, False, 0)
        GLib.idle_add(self.render_agenda)

    def selected_date(self):
        year, month, day = self.calendar.get_date()
        return dt.date(year, month + 1, day)

    def add_event(self):
        title = self.event_entry.get_text().strip()
        if not title:
            return
        events = read_events()
        events.append(dict(id=uuid.uuid4().hex, date=self.selected_date().isoformat(), title=title))
        try:
            save_events(events)
        except OSError as exc:
            self.show_error(str(exc))
            return
        self.event_entry.set_text('')
        self.render_agenda()

    def remove_event(self, event_id):
        try:
            save_events([item for item in read_events() if item['id'] != event_id])
            self.render_agenda()
        except OSError as exc:
            self.show_error(str(exc))

    def render_agenda(self):
        if not hasattr(self, 'agenda'):
            return False
        self.clear(self.agenda)
        date = self.selected_date()
        events = read_events()
        self.calendar.clear_marks()
        for item in events:
            try:
                day = dt.date.fromisoformat(item['date'])
                if (day.year, day.month) == (date.year, date.month):
                    self.calendar.mark_day(day.day)
            except ValueError:
                pass
        self.agenda.pack_start(label(date.strftime('%d/%m/%Y'), 'section'), False, False, 0)
        selected = [item for item in events if item['date'] == date.isoformat()]
        for item in selected:
            row = box(spacing=8)
            title = label(item['title'])
            title.set_line_wrap(True)
            title.set_hexpand(True)
            row.pack_start(title, True, True, 0)
            row.pack_end(self.button('Remove', lambda i=item['id']: self.remove_event(i)), False, False, 0)
            self.agenda.pack_start(row, False, False, 0)
        if not selected:
            self.agenda.pack_start(label('No events for this day.', 'muted'), False, False, 0)
        upcoming = sorted((item for item in events if item['date'] > date.isoformat()), key=lambda item: item['date'])[:4]
        if upcoming:
            self.agenda.pack_start(label('Upcoming', 'section'), False, False, 0)
            for item in upcoming:
                upcoming_label = label(item['date'] + '  ' + item['title'])
                upcoming_label.set_line_wrap(True)
                upcoming_label.set_max_width_chars(48)
                self.agenda.pack_start(upcoming_label, False, False, 0)
        if date == dt.date.today() and PLANNER.is_file():
            self.work('tasks', lambda: json.loads(command([str(PLANNER), '--once', 'tasks'])), self.tasks_ready)
        self.agenda.show_all()
        return False

    def tasks_ready(self, data):
        if self.selected_date() != dt.date.today():
            return
        self.agenda.pack_start(label('Today’s tasks', 'section'), False, False, 0)
        for group in data.get('groups', []):
            for item in group['items']:
                check = Gtk.CheckButton(label=item['text'])
                check.get_child().set_line_wrap(True)
                check.get_child().set_max_width_chars(48)
                check.set_active(item['done'])
                check.connect('toggled', lambda _, i=item['id']: self.work('task-toggle',
                    lambda: command([str(PLANNER), 'task', i]), lambda _: self.render_agenda()))
                self.agenda.pack_start(check, False, False, 0)
        self.agenda.show_all()


if __name__ == '__main__':
    surface = sys.argv[1] if len(sys.argv) > 1 else 'audio'
    if surface not in ('audio', 'connections', 'calendar'):
        raise SystemExit('Usage: desktop-panel audio|connections|calendar [--preview]')
    raise SystemExit(Panel(surface, preview='--preview' in sys.argv).run([sys.argv[0]]))
