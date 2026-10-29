#!/usr/bin/env python3
"""Visual desktop home and application gallery for Wayfire (GTK layer shell)."""
import datetime
import getpass
import json
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

os.environ['LANGUAGE'] = 'en_US:en'
os.environ['LC_MESSAGES'] = 'en_US.UTF-8'

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell, Pango

HOME = Path.home()
CONFIG = HOME / '.config/desktop-menu'
BIN = HOME / '.local/bin'


def palette():
    colors = dict(primary='#a6c8ff', on_primary='#02315f', surface='#111318',
                  surface_container='#1d2024', surface_container_high='#282a2f',
                  surface_container_highest='#32353a', shadow='#000000',
                  primary_container='#234776', on_primary_container='#d5e3ff',
                  secondary='#bdc7dc', tertiary='#dabde2', tertiary_container='#553f5d',
                  outline_variant='#43474e', on_surface='#e1e2e9',
                  on_surface_variant='#c4c6cf', error='#ffb4ab')
    try:
        for key, value in re.findall(r'\$(\w+):\s*(#[\da-fA-F]{6})',
                                    (HOME / '.config/eww/_colors.scss').read_text()):
            colors[key] = value
    except OSError:
        pass
    # Waybar is the visual authority. Its palette may include roles absent in Eww.
    try:
        colors.update(re.findall(r'@define-color\s+(\w+)\s+(#[\da-fA-F]{6});',
                                 (HOME / '.config/waybar/colors.css').read_text()))
    except OSError:
        pass
    try:
        tokens=json.loads((HOME/'.config/desktop-style/current/tokens.json').read_text())
        resolved=tokens.get('colors',{}) if isinstance(tokens,dict) else {}
        if isinstance(resolved,dict):
            colors.update({k:v for k,v in resolved.items() if isinstance(v,str) and re.fullmatch(r'#[\da-fA-F]{6}',v)})
    except (OSError,ValueError):
        pass
    return colors


def close_stamp():
    return Path(os.environ.get('XDG_RUNTIME_DIR', str(HOME / '.cache'))) / 'desktop-menu-super-closed'


def recently_closed(path=None, now=None):
    try:
        elapsed = (time.monotonic() if now is None else now) - float((path or close_stamp()).read_text())
        return 0 <= elapsed < 0.45
    except (OSError, ValueError):
        return False


def label(text='', css=None):
    widget = Gtk.Label(label=text, xalign=0)
    if css:
        widget.get_style_context().add_class(css)
    return widget


def icon(name, size=24):
    image = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.DIALOG)
    image.set_pixel_size(size)
    return image


def box(vertical=False, spacing=0):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
                   spacing=spacing)


class Menu(Gtk.Application):
    def __init__(self, preview=False):
        super().__init__(application_id='org.raccon.DesktopMenu',
                         flags=Gio.ApplicationFlags.NON_UNIQUE if preview else Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.preview = preview
        self.apps_loaded = False
        self.cpu_previous = None
        self.music_pending = False
        self.super_pressed = False
        self.super_used = False
        self.theme_timer = None
        self.theme_monitors = []

    def do_activate(self):
        # Gtk.Application forwards another Super/click invocation over session D-Bus.
        if self.window:
            self.close_from_super()
            return
        self.window = Gtk.ApplicationWindow(application=self, title='Home')
        self.window.set_name('desktop-menu')
        self.window.set_decorated(False)
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        self.window.connect('key-press-event', self.key)
        self.window.connect('key-release-event', self.key_released)
        self.window.connect('destroy', lambda *_: self.quit())

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if GtkLayerShell.is_supported() and not self.preview:
            GtkLayerShell.init_for_window(self.window)
            GtkLayerShell.set_namespace(self.window, 'desktop-menu')
            GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
            # Keyboard navigation works immediately, without first clicking.
            # Bare Super closes on RELEASE; a short guard absorbs duplicate activation.
            GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            # Use the monitor under the pointer when the menu is opened.
            seat = display.get_default_seat()
            if seat and seat.get_pointer():
                _, px, py = seat.get_pointer().get_position()
                monitor = display.get_monitor_at_point(px, py) or monitor
            GtkLayerShell.set_monitor(self.window, monitor)
            for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                         GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self.window, edge, True)
            GtkLayerShell.set_exclusive_zone(self.window, -1)
        else:
            self.window.set_default_size(790, 680)

        self.provider = Gtk.CssProvider()
        self.reload_theme()
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), self.provider,
                                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        backdrop = Gtk.EventBox()
        backdrop.get_style_context().add_class('backdrop')
        backdrop.connect('button-press-event', self.outside_click)
        overlay = Gtk.Overlay()
        backdrop.add(overlay)
        overlay.add(Gtk.Box())
        self.window.add(backdrop)

        geo = monitor.get_geometry()
        width = min(660, max(320, geo.width - 28))
        panel = box(vertical=True, spacing=16)
        panel.get_style_context().add_class('panel')
        panel.set_halign(Gtk.Align.START)
        panel.set_valign(Gtk.Align.END)
        panel.set_margin_start(14)
        panel.set_margin_end(14)
        panel.set_margin_bottom(80)
        panel.set_margin_top(14)
        panel.set_size_request(width, -1)
        self.panel = panel
        overlay.add_overlay(panel)

        header = box(spacing=12)
        title_area = box(vertical=True, spacing=2)
        title_area.set_hexpand(True)
        title_area.pack_start(label(getattr(self, 'panel_title', getpass.getuser().capitalize()), 'title'), False, False, 0)
        self.power_badge = label('', 'muted')
        title_area.pack_start(self.power_badge, False, False, 0)
        header.pack_start(title_area, True, True, 0)
        close = Gtk.Button()
        close.get_style_context().add_class('quiet')
        close.add(icon('window-close-symbolic', 20))
        close.set_tooltip_text('Close · Esc')
        close.connect('clicked', lambda *_: self.quit())
        header.pack_end(close, False, False, 0)
        panel.pack_start(header, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        settings = Gtk.Settings.get_default()
        self.stack.set_transition_duration(150 if settings.get_property('gtk-enable-animations') else 0)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        switcher.set_halign(Gtk.Align.START)
        panel.pack_start(switcher, False, False, 0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(True)
        # Reserve room for the header, tabs, footer, padding and bottom dock.
        # The application gallery must scroll instead of growing past a laptop screen.
        available_height = min(geo.height, 680) if self.preview else geo.height
        content_height = max(100, min(520, available_height - 380))
        scroller.set_min_content_height(min(360, content_height))
        scroller.set_max_content_height(content_height)
        scroller.add(self.stack)
        panel.pack_start(scroller, True, True, 0)
        if hasattr(self, 'build_panel'):
            self.stack.add_titled(self.build_panel(width), 'panel', self.panel_title)
            switcher.set_no_show_all(True)
            switcher.hide()
        else:
            self.stack.add_titled(self.home_view(width), 'home', 'Home')
            self.stack.add_titled(self.apps_view(width), 'apps', 'Applications')
            self.stack.connect('notify::visible-child-name', self.tab_changed)
        self.error = label('', 'error')
        self.error.set_line_wrap(True)
        self.error.set_no_show_all(True)
        panel.pack_start(self.error, False, False, 0)
        footer = box(spacing=12)
        hints = 'Tab · Arrows · Enter     Ctrl+1 Home · Ctrl+2 Apps'
        footer.pack_start(label(hints if not hasattr(self, 'build_panel') else 'Esc to close', 'muted'), True, True, 0)
        footer.pack_end(self.action('Lock', 'system-lock-screen-symbolic',
                                    [str(BIN / 'lock')], compact=True), False, False, 0)
        panel.pack_start(footer, False, False, 0)
        self.reload_theme()
        self.window.show_all()
        self.window.present()
        self.refresh_power_state()
        self.watch_theme()
        if not hasattr(self, 'build_panel'):
            self.update_status()
            GLib.timeout_add_seconds(1, self.update_status)
            GLib.timeout_add_seconds(3, self.update_music)
            self.update_music()
            self.shortcuts.get_child_at_index(0).get_child().grab_focus()

    def reload_theme(self):
        css = (CONFIG / 'style.css').read_text()
        for name, value in palette().items():
            css = css.replace('@' + name + ';', value + ';')
        shared=HOME / ".config/desktop-style/current/panels.css"
        if shared.exists():
            css+="\n"+shared.read_text()
        try:
            self.provider.load_from_data(css.encode())
        except GLib.Error as exc:
            print(f'desktop-menu theme: {exc.message}', file=sys.stderr)
        if hasattr(self, 'panel'):
            try:
                tokens=json.loads((HOME / '.config/desktop-style/current/tokens.json').read_text())
            except (OSError, ValueError):
                tokens={}
            top=tokens.get('position')=='top'
            self.panel.set_valign(Gtk.Align.START if top else Gtk.Align.END)
            self.panel.set_margin_top(78 if top else 14)
            self.panel.set_margin_bottom(14 if top else 80)
        self.theme_timer = None
        return False

    def watch_theme(self):
        # Monitor directories because Matugen and editors may replace files atomically.
        state_directory = Path(os.environ.get('XDG_STATE_HOME', str(HOME / '.local/state'))) / 'desktop-power'
        for directory in (HOME / '.config/waybar', HOME / '.config/eww', CONFIG, state_directory, HOME / ".config/desktop-style/current"):
            try:
                monitor = Gio.File.new_for_path(str(directory)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
                monitor.connect('changed', self.theme_changed)
                self.theme_monitors.append(monitor)
            except GLib.Error:
                pass

    def theme_changed(self, monitor, file, other_file, event):
        names = {f.get_basename() for f in (file, other_file) if f}
        if 'status.json' in names:
            self.refresh_power_state()
        if not names.intersection({'colors.css', '_colors.scss', 'style.css', 'panels.css', 'tokens.json'}):
            return
        if self.theme_timer:
            GLib.source_remove(self.theme_timer)
        self.theme_timer = GLib.timeout_add(120, self.reload_theme)

    def refresh_power_state(self):
        path = Path(os.environ.get('XDG_STATE_HOME', str(HOME / '.local/state'))) / 'desktop-power/status.json'
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        if not data:
            self.power_badge.set_text('')
            return
        if not data.get('mode'):
            self.power_badge.set_text('Mode pending · check settings')
            return
        self.power_badge.set_text({'performance':'Power saver','balanced':'Balanced','complete':'Full','working':'Working'}.get(data.get('mode'), '') + (' · Auto' if data.get('source') == 'auto' else ' · Manual'))
        context = self.window.get_style_context()
        for mode in ('performance', 'balanced', 'complete', 'working'):
            context.remove_class('power-' + mode)
        context.add_class('power-' + data.get('mode', 'complete'))
        factor = data.get('policy', {}).get('animation_factor', 1)
        self.stack.set_transition_duration(round(150 * factor))
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE if factor == 0 else Gtk.StackTransitionType.CROSSFADE)

    def close_from_super(self):
        # GTK and the compositor can both see the same modifier release.
        # The next process must not reopen the menu for that same gesture.
        try:
            close_stamp().write_text(str(time.monotonic()))
        except OSError:
            pass
        self.quit()

    def outside_click(self, widget, event):
        allocation = self.panel.get_allocation()
        # Events bubble from content: only clicks outside the panel dismiss it.
        x, y = widget.translate_coordinates(self.window, int(event.x), int(event.y)) or (0, 0)
        pos = self.panel.translate_coordinates(self.window, 0, 0)
        if pos and not (pos[0] <= x < pos[0] + allocation.width and
                        pos[1] <= y < pos[1] + allocation.height):
            self.quit()
            return True
        return False

    def key(self, widget, event):
        if event.keyval in (Gdk.KEY_Super_L, Gdk.KEY_Super_R):
            self.super_pressed = True
            self.super_used = bool(event.state & (Gdk.ModifierType.CONTROL_MASK |
                                                  Gdk.ModifierType.MOD1_MASK |
                                                  Gdk.ModifierType.SHIFT_MASK))
            return False
        if self.super_pressed:
            self.super_used = True
        if event.keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        if hasattr(self, 'build_panel'):
            return False
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and event.keyval in (Gdk.KEY_1, Gdk.KEY_2, Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            if event.keyval == Gdk.KEY_1:
                target = 'home'
            elif event.keyval == Gdk.KEY_2:
                target = 'apps'
            else:
                target = 'home' if self.stack.get_visible_child_name() == 'apps' else 'apps'
            self.stack.set_visible_child_name(target)
            if target == 'home':
                self.shortcuts.get_child_at_index(0).get_child().grab_focus()
            else:
                self.search.grab_focus()
            return True
        if ctrl and event.keyval in (Gdk.KEY_f, Gdk.KEY_l):
            self.stack.set_visible_child_name('apps')
            self.search.grab_focus()
            return True
        if ctrl or event.state & (Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.SUPER_MASK):
            return False
        grid = self.app_grid if self.stack.get_visible_child_name() == 'apps' else self.shortcuts
        focus = self.window.get_focus()
        in_search = focus == self.search
        if in_search and event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Home, Gdk.KEY_End):
            return False  # Preserve text editing inside the search field.
        navigation = {Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Home, Gdk.KEY_End}
        if event.keyval in navigation and (in_search or self.within(focus, grid)):
            self.navigate(grid, event.keyval)
            return True
        if in_search and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            children = self.visible_children(grid)
            if children:
                children[0].get_child().clicked()
            return True
        if not in_search and self.within(focus, grid) and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            current = next((child for child in self.visible_children(grid) if self.within(focus, child)), None)
            if current:
                current.get_child().clicked()
                return True
        return False

    def key_released(self, widget, event):
        if event.keyval in (Gdk.KEY_Super_L, Gdk.KEY_Super_R):
            close = self.super_pressed and not self.super_used
            self.super_pressed = False
            if close:
                self.close_from_super()
                return True
        return False

    @staticmethod
    def within(widget, container):
        return widget is not None and (widget == container or widget.is_ancestor(container))

    def visible_children(self, grid):
        if grid is self.app_grid:
            query = self.search.get_text().casefold()
            return [child for child in grid.get_children() if query in child.search_text]
        return grid.get_children()

    def navigate(self, grid, key):
        children = self.visible_children(grid)
        if not children:
            return
        focus = self.window.get_focus()
        current = next((i for i, child in enumerate(children) if self.within(focus, child)), None)
        if current is None:
            target = len(children) - 1 if key == Gdk.KEY_Up else 0
        elif key in (Gdk.KEY_Home, Gdk.KEY_End):
            target = 0 if key == Gdk.KEY_Home else len(children) - 1
        elif key in (Gdk.KEY_Left, Gdk.KEY_Right):
            target = max(0, min(len(children) - 1, current + (1 if key == Gdk.KEY_Right else -1)))
        else:
            rect = children[current].get_allocation()
            rows = [i for i, child in enumerate(children)
                    if (child.get_allocation().y > rect.y if key == Gdk.KEY_Down else child.get_allocation().y < rect.y)]
            if not rows:
                return
            row_y = min((children[i].get_allocation().y for i in rows), key=lambda y: abs(y - rect.y))
            target = min((i for i in rows if children[i].get_allocation().y == row_y),
                         key=lambda i: abs(children[i].get_allocation().x - rect.x))
        grid.select_child(children[target])
        children[target].get_child().grab_focus()

    def launch(self, command):
        try:
            subprocess.Popen(command, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            self.show_error(f'Could not open: {exc.strerror}')
            return
        self.quit()

    def show_error(self, message):
        self.error.set_text(message)
        self.error.show()

    def action(self, title, image, command, compact=False):
        button = Gtk.Button()
        button.get_style_context().add_class('shortcut' if not compact else 'compact')
        row = box(spacing=10)
        row.pack_start(icon(image, 18 if compact else 24), False, False, 0)
        row.pack_start(label(title), True, True, 0)
        button.add(row)
        button.connect('clicked', lambda *_: self.launch(command))
        return button

    def home_view(self, width):
        content = box(vertical=True, spacing=18)
        hero = box(spacing=22)
        hero.get_style_context().add_class('hero')
        time_box = box(vertical=True, spacing=0)
        time_box.set_hexpand(True)
        self.clock = label('', 'clock')
        self.date = label('', 'muted')
        time_box.pack_start(self.clock, False, False, 0)
        time_box.pack_start(self.date, False, False, 0)
        hero.pack_start(time_box, True, True, 0)
        self.stats = label('', 'status')
        hero.pack_end(self.stats, False, False, 0)
        content.pack_start(hero, False, False, 0)

        shortcuts = Gtk.FlowBox()
        self.shortcuts = shortcuts
        shortcuts.get_style_context().add_class('shortcuts')
        shortcuts.set_selection_mode(Gtk.SelectionMode.SINGLE)
        shortcuts.set_activate_on_single_click(False)
        shortcuts.set_max_children_per_line(3 if width >= 600 else 2)
        shortcuts.set_min_children_per_line(2)
        shortcuts.set_column_spacing(8)
        shortcuts.set_row_spacing(8)
        for index, (title, image, command) in enumerate((
            ('Files', 'system-file-manager', ['dolphin']),
            ('Browser', 'web-browser', ['brave']),
            ('Terminal', 'utilities-terminal', ['kitty']),
            ('Editor', 'accessories-text-editor', ['code', '--ozone-platform-hint=wayland']),
            ('Wallpapers', 'preferences-desktop-wallpaper', ['waypaper']),
            ('Widgets', 'preferences-desktop', [str(HOME / '.local/bin/widgetctl'), 'editor']),
        )):
            button = self.action(title, image, command)
            button.get_style_context().add_class(('primary', 'secondary', 'tertiary')[index % 3])
            shortcuts.add(button)
        content.pack_start(shortcuts, False, False, 0)

        music = box(vertical=True, spacing=8)
        music.get_style_context().add_class('music')
        self.track = label('Nothing playing', 'section')
        self.track.set_ellipsize(Pango.EllipsizeMode.END)
        self.track.set_max_width_chars(48)
        self.artist = label('Open your player to listen', 'muted')
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        music.pack_start(self.track, False, False, 0)
        music.pack_start(self.artist, False, False, 0)
        controls = box(spacing=8)
        for name, image, action in (('Previous', 'media-skip-backward-symbolic', 'previous'),
                                    ('Play / pause', 'media-playback-start-symbolic', 'play-pause'),
                                    ('Next', 'media-skip-forward-symbolic', 'next')):
            button = Gtk.Button()
            button.add(icon(image, 20))
            button.set_tooltip_text(name)
            button.connect('clicked', lambda _, a=action: self.media(a))
            controls.pack_start(button, False, False, 0)
        music.pack_start(controls, False, False, 0)
        content.pack_start(music, False, False, 0)
        settings_row = box(spacing=8)
        for title, image, command in (
            ('Network', 'network-wireless-symbolic', [str(BIN / 'desktop-panel'), 'connections']),
            ('Audio', 'audio-volume-high-symbolic', [str(BIN / 'desktop-panel'), 'audio']),
            ('Notifications', 'preferences-system-notifications-symbolic', ['swaync-client', '-t', '-sw']),
        ):
            settings_row.pack_start(self.action(title, image, command, compact=True), True, True, 0)
        content.pack_start(settings_row, False, False, 0)
        return content

    def apps_view(self, width):
        content = box(vertical=True, spacing=14)
        self.search = Gtk.SearchEntry(placeholder_text='Search your apps')
        self.search.connect('search-changed', lambda *_: self.app_grid.invalidate_filter())
        content.pack_start(self.search, False, False, 0)
        self.app_grid = Gtk.FlowBox()
        self.app_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.app_grid.set_activate_on_single_click(False)
        self.app_grid.set_min_children_per_line(2)
        self.app_grid.set_max_children_per_line(5 if width >= 600 else 3)
        self.app_grid.set_homogeneous(True)
        self.app_grid.set_column_spacing(6)
        self.app_grid.set_row_spacing(6)
        self.app_grid.set_filter_func(lambda child: self.search.get_text().casefold() in child.search_text)
        self.empty_apps = label('No matching apps.', 'muted')
        self.empty_apps.set_no_show_all(True)
        self.search.connect('search-changed', self.filter_status)
        content.pack_start(self.empty_apps, False, False, 0)
        content.pack_start(self.app_grid, False, False, 0)
        return content

    def filter_status(self, *_):
        query = self.search.get_text().casefold()
        self.empty_apps.set_visible(not any(query in child.search_text
                                           for child in self.app_grid.get_children()))

    def tab_changed(self, *_):
        if self.stack.get_visible_child_name() != 'apps' or self.apps_loaded:
            return
        self.apps_loaded = True
        apps = sorted((app for app in Gio.AppInfo.get_all() if app.should_show()),
                      key=lambda app: locale.strxfrm(app.get_display_name().casefold()))
        for app in apps:
            child = Gtk.FlowBoxChild()
            child.search_text = (app.get_display_name() + ' ' + (app.get_description() or '')).casefold()
            button = Gtk.Button()
            button.get_style_context().add_class('app')
            button.set_tooltip_text(app.get_description() or app.get_display_name())
            col = box(vertical=True, spacing=8)
            app_icon = app.get_icon()
            image = Gtk.Image.new_from_gicon(app_icon, Gtk.IconSize.DIALOG) if app_icon else icon('application-x-executable')
            image.set_pixel_size(40)
            col.pack_start(image, False, False, 0)
            name = Gtk.Label(label=app.get_display_name(), max_width_chars=12)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            col.pack_start(name, False, False, 0)
            button.add(col)
            button.connect('clicked', lambda _, a=app: self.launch_app(a))
            child.add(button)
            self.app_grid.add(child)
        self.app_grid.show_all()
        self.filter_status()
        self.search.grab_focus()
        self.app_grid.select_child(self.app_grid.get_child_at_index(0))

    def launch_app(self, app):
        try:
            app.launch([], self.window.get_display().get_app_launch_context())
            self.quit()
        except GLib.Error as exc:
            self.show_error(f'Could not open {app.get_display_name()}: {exc.message}')

    def media(self, action):
        try:
            proc = Gio.Subprocess.new(['playerctl', action], Gio.SubprocessFlags.STDOUT_SILENCE |
                                      Gio.SubprocessFlags.STDERR_SILENCE)
            proc.wait_async(None, lambda p, result: (p.wait_finish(result), self.update_music()))
        except GLib.Error:
            self.show_error('No player is available.')

    def update_music(self):
        if self.music_pending or not shutil.which('playerctl'):
            return True
        self.music_pending = True
        try:
            proc = Gio.Subprocess.new(['playerctl', 'metadata', '--format', '{{title}}\n{{artist}}'],
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
            proc.communicate_utf8_async(None, None, self.music_ready)
        except GLib.Error:
            self.music_pending = False
        return True

    def music_ready(self, proc, result):
        self.music_pending = False
        try:
            _, output, _ = proc.communicate_utf8_finish(result)
            parts = (output or '').strip().split('\n', 1)
            self.track.set_text(parts[0] or 'Nothing playing')
            self.artist.set_text(parts[1] if len(parts) > 1 else 'Open your player to listen')
        except GLib.Error:
            pass

    def update_status(self):
        now = datetime.datetime.now()
        self.clock.set_text(now.strftime('%H:%M'))
        self.date.set_text(now.strftime('%A, %B %d').capitalize())
        stats = []
        try:
            cpu = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
            total, idle = sum(cpu[:8]), sum(cpu[3:5])
            if self.cpu_previous:
                dt, di = total - self.cpu_previous[0], idle - self.cpu_previous[1]
                stats.append(f'CPU  {100 * (1 - di / dt):.0f}%' if dt else 'CPU  0%')
            self.cpu_previous = (total, idle)
            mem = dict(re.findall(r'^(\w+):\s+(\d+)', Path('/proc/meminfo').read_text(), re.M))
            stats.append(f'RAM  {(int(mem["MemTotal"]) - int(mem["MemAvailable"])) / 1048576:.1f} GB')
            for battery in Path('/sys/class/power_supply').glob('*'):
                if (battery / 'type').read_text().strip() == 'Battery':
                    capacity = (battery / 'capacity').read_text().strip()
                    charging = (battery / 'status').read_text().strip() == 'Charging'
                    stats.append(f'Battery  {capacity}%' + (' · charging' if charging else ''))
                    break
        except (OSError, ValueError, KeyError):
            pass
        self.stats.set_text('\n'.join(stats))
        return True


if __name__ == '__main__':
    try:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'C')
    preview = '--preview' in sys.argv
    if not preview and recently_closed():
        raise SystemExit(0)
    raise SystemExit(Menu(preview=preview).run([sys.argv[0]]))
