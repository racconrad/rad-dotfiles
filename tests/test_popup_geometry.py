"""Popup surfaces stay bounded when their content grows or shrinks."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'modules/desktop/files/.local/lib/raccon_menu'


class PopupGeometryTests(unittest.TestCase):
    def test_native_viewport_ignores_child_requisitions(self):
        self.assertTrue((LIB / 'popup_geometry.h').is_file())
        source = r'''
#include <gtk/gtk.h>
#include "popup_geometry.h"
static void settle(void) {
    for (int i=0;i<60;i++) {
        while (gtk_events_pending()) gtk_main_iteration();
        g_usleep(1000);
    }
}
int main(int argc, char **argv) {
    if (!gtk_init_check(&argc,&argv)) return 77;
    GtkWidget *window=gtk_offscreen_window_new();
    GtkWidget *body=gtk_box_new(GTK_ORIENTATION_VERTICAL,0);
    GtkWidget *label=gtk_label_new("Short");
    gtk_container_add(GTK_CONTAINER(body),label);
    gtk_container_add(GTK_CONTAINER(window),body);
    popup_geometry_bind(window,400,300);
    gtk_widget_show_all(window);settle();
    int width=gtk_widget_get_allocated_width(window),height=gtk_widget_get_allocated_height(window);
    g_assert_cmpint(width,==,400);g_assert_cmpint(height,==,300);
    gtk_widget_set_size_request(label,1200,900);settle();
    g_assert_cmpint(gtk_widget_get_allocated_width(window),==,width);
    g_assert_cmpint(gtk_widget_get_allocated_height(window),==,height);
    gtk_widget_hide(label);settle();
    g_assert_cmpint(gtk_widget_get_allocated_width(window),==,width);
    g_assert_cmpint(gtk_widget_get_allocated_height(window),==,height);
    popup_geometry_bind(window,400,300);settle();
    g_assert_true(gtk_bin_get_child(GTK_BIN(window))==g_object_get_data(G_OBJECT(window),"popup-viewport"));
    popup_geometry_bind(window,10000,10000);settle();
    GdkMonitor *monitor=gdk_display_get_monitor_at_window(gtk_widget_get_display(window),gtk_widget_get_window(window));
    if(monitor) {
        GdkRectangle bounds;gdk_monitor_get_workarea(monitor,&bounds);
        g_assert_cmpint(gtk_widget_get_allocated_width(window),<=,bounds.width-32);
        g_assert_cmpint(gtk_widget_get_allocated_height(window),<=,bounds.height-112);
    }
    GtkWidget *old=gtk_bin_get_child(GTK_BIN(window));
    g_object_ref(old);gtk_container_remove(GTK_CONTAINER(window),old);
    GtkWidget *replacement=gtk_label_new("Reloaded");
    gtk_container_add(GTK_CONTAINER(window),replacement);
    popup_geometry_bind(window,400,300);gtk_widget_show_all(window);settle();
    g_assert_true(gtk_bin_get_child(GTK_BIN(window))!=replacement);
    g_assert_true(gtk_bin_get_child(GTK_BIN(window))!=old);
    g_object_unref(old);
    gtk_widget_destroy(window);return 0;
}
'''
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'probe.c').write_text(source)
            subprocess.run(['cc', str(path / 'probe.c'), '-I', str(LIB), '-o', str(path / 'probe'), *flags], check=True)
            result = subprocess.run([str(path / 'probe')], capture_output=True, text=True, timeout=8)
            if result.returncode == 77:
                self.skipTest('No GTK display')
            self.assertEqual(result.returncode, 0, result.stderr)
