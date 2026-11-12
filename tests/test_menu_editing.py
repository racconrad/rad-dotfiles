"""Exercise Eww loop reactivity on hidden, isolated menu trees."""
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / 'modules/desktop/files'
PROBE = r'''
#include <gtk/gtk.h>
#include <gmodule.h>
static GtkWidget *window;
static void count(GtkWidget *widget, guint *counts) {
    GtkStyleContext *style = gtk_widget_get_style_context(widget);
    if (gtk_style_context_has_class(style, "home-edit-controls")) {
        counts[0]++; counts[1] += gtk_widget_get_visible(widget);
    }
    if (gtk_style_context_has_class(style, "app-pin")) {
        counts[2]++; counts[3] += gtk_widget_get_visible(widget);
    }
    if (GTK_IS_CONTAINER(widget)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
        for (GList *item = children; item; item = item->next) count(item->data, counts);
        g_list_free(children);
    }
}
static gboolean inspect(gpointer unused) {
    if (!window) return G_SOURCE_CONTINUE;
    guint counts[4] = {0}; count(window, counts);
    gchar *data = g_strdup_printf("[%u,%u,%u,%u]", counts[0], counts[1], counts[2], counts[3]);
    gchar *path = g_build_filename(g_get_home_dir(), "editing-probe.json", NULL);
    g_file_set_contents(path, data, -1, NULL);
    g_free(path); g_free(data); return G_SOURCE_CONTINUE;
}
static gboolean mapped(GSignalInvocationHint *hint, guint n, const GValue *values, gpointer unused) {
    GtkWidget *widget = g_value_get_object(values);
    if (!window && GTK_IS_WINDOW(widget) && gtk_window_get_window_type(GTK_WINDOW(widget)) == GTK_WINDOW_TOPLEVEL) {
        window = widget;
        g_object_add_weak_pointer(G_OBJECT(widget), (gpointer *)&window);
    }
    return TRUE;
}
G_MODULE_EXPORT void gtk_module_init(gint *argc, gchar ***argv) {
    g_type_class_ref(GTK_TYPE_WIDGET);
    g_signal_add_emission_hook(g_signal_lookup("map", GTK_TYPE_WIDGET), 0, mapped, NULL, NULL);
    g_timeout_add(50, inspect, NULL);
}
'''


@unittest.skipUnless(os.environ.get('RACCON_MENU_GUI_TEST') == '1', 'opt-in isolated Eww connection')
class MenuEditingTests(unittest.TestCase):
    def setUp(self):
        if not all(shutil.which(name) for name in ('eww', 'cc', 'pkg-config')):
            self.skipTest('Eww/GTK development tools unavailable')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('GTK3 development files unavailable')
        temporary = tempfile.TemporaryDirectory(prefix='raccon-editing-test-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.config = self.home / '.config/raccon-menu'
        shutil.copytree(DESKTOP / '.config/raccon-menu', self.config)
        shutil.copy2(ROOT / 'modules/desktop-styles/files/.config/raccon-menu/_desktop-style.scss', self.config)
        self.library = self.home / '.local/lib/raccon_menu'
        shutil.copytree(DESKTOP / '.local/lib/raccon_menu', self.library, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'modules/base/files/.local/lib/raccon_events.py', self.library.parent)
        source = self.home / 'probe.c'
        source.write_text(PROBE)
        module = self.home / 'probe.so'
        subprocess.run(['cc', '-shared', '-fPIC', str(source), '-o', str(module), *shlex.split(flags.stdout)],
                       check=True, capture_output=True, text=True)
        backend = self.library / 'backend.py'
        original = backend.read_text()
        patched = original.replace("'GTK_MODULES': str(module)", "'GTK_MODULES': str(module) + ':' + " + repr(str(module)))
        self.assertNotEqual(original, patched, 'Native module launch boundary moved; update the probe injection.')
        backend.write_text(patched)
        binary = self.home / '.local/bin'
        binary.mkdir(parents=True)
        shutil.copy2(DESKTOP / '.local/bin/desktop-menu', binary)
        self.command = binary / 'desktop-menu'
        runtime = self.home / 'run'
        runtime.mkdir(mode=0o700)
        data = self.home / 'data/applications'
        data.mkdir(parents=True)
        (data / 'fixture.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true\nIcon=application-x-executable\n')
        display = os.environ.get('WAYLAND_DISPLAY', '')
        if display and not os.path.isabs(display):
            display = str(Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / display)
        self.env = {**os.environ, 'HOME': str(self.home), 'XDG_RUNTIME_DIR': str(runtime),
                    'XDG_CONFIG_HOME': str(self.home / '.config'), 'XDG_CACHE_HOME': str(self.home / '.cache'),
                    'XDG_STATE_HOME': str(self.home / 'state'), 'XDG_DATA_HOME': str(self.home / 'data'),
                    'XDG_DATA_DIRS': str(self.home / 'system'), 'PYTHONDONTWRITEBYTECODE': '1'}
        if display:
            self.env['WAYLAND_DISPLAY'] = display
        self.addCleanup(self.stop_menu)

    def stop_menu(self):
        subprocess.run(['eww', '--no-daemonize', '-c', str(self.config), 'kill'],
                       env=self.env, capture_output=True, timeout=5)
        # Only reap processes launched with this test's unique HOME.
        marker = os.fsencode('HOME=' + str(self.home)) + b'\0'
        for process in Path('/proc').glob('[0-9]*'):
            try:
                if marker in (process / 'environ').read_bytes().splitlines():
                    os.kill(int(process.name), signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass

    def run_command(self, *args):
        result = subprocess.run([str(arg) for arg in args], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result.stdout

    def await_controls(self, expected):
        deadline = time.monotonic() + 5
        current = None
        while time.monotonic() < deadline:
            try:
                current = json.loads((self.home / 'editing-probe.json').read_text())
            except (OSError, ValueError):
                pass
            if current == expected:
                return
            time.sleep(.05)
        self.assertEqual(current, expected)

    def test_edit_controls_toggle_without_rebuilding_the_catalogue(self):
        self.run_command(self.command, 'prepare')
        self.await_controls([3, 0, 1, 0])
        catalogue = self.run_command('eww', '-c', self.config, 'get', 'catalogue')
        for editing, expected in (('true', [3, 3, 1, 1]), ('false', [3, 0, 1, 0]), ('true', [3, 3, 1, 1])):
            self.run_command('eww', '-c', self.config, 'update', 'editing=' + editing)
            self.await_controls(expected)
            self.assertEqual(self.run_command('eww', '-c', self.config, 'get', 'catalogue'), catalogue)
        self.assertEqual((self.home / 'run/raccon-menu/visible').read_text().strip(), '0')
