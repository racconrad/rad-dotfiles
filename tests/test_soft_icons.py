"""Exercise the shipped icon adapter with GTK, including live icon changes."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'modules/desktop/files/.local/lib/raccon_menu'
ICONS = ROOT / 'modules/desktop/files/.config/raccon-menu/assets/icons'


class SoftIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        source = Path(cls.temp.name) / 'icons.c'
        cls.binary = Path(cls.temp.name) / 'icons'
        source.write_text('#include "' + str(LIB / 'soft_icons.h') + '"\n' + r'''
int main(int argc, char **argv) {
    g_assert_cmpstr(soft_icon_name("window-close-symbolic"), ==, "raccon-close-symbolic");
    g_assert_cmpstr(soft_icon_name("network-wireless-symbolic"), ==, "raccon-wifi-symbolic");
    g_assert_null(soft_icon_name("org.mozilla.firefox"));
    if (argc < 2) return 0;
    gtk_init(&argc, &argv);
    gtk_icon_theme_prepend_search_path(gtk_icon_theme_get_default(), argv[1]);
    GtkWidget *row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    GtkWidget *image = gtk_image_new_from_icon_name("window-close-symbolic", GTK_ICON_SIZE_BUTTON);
    gtk_container_add(GTK_CONTAINER(row), image);
    soft_icons_apply(image);
    const gchar *name;
    GtkIconSize size;
    gtk_image_get_icon_name(GTK_IMAGE(image), &name, &size);
    g_assert_cmpstr(name, ==, "raccon-close-symbolic");
    g_assert_cmpint(gtk_image_get_pixel_size(GTK_IMAGE(image)), ==, 20);
    /* Eww updates an already-mapped GtkImage when a service changes state. */
    gtk_image_set_from_icon_name(GTK_IMAGE(image), "media-playback-pause-symbolic", GTK_ICON_SIZE_BUTTON);
    gtk_image_get_icon_name(GTK_IMAGE(image), &name, &size);
    g_assert_cmpstr(name, ==, "raccon-pause-symbolic");
    gtk_style_context_add_class(gtk_widget_get_style_context(image), "app-icon");
    gtk_image_set_from_icon_name(GTK_IMAGE(image), "org.mozilla.firefox", GTK_ICON_SIZE_DND);
    soft_icons_apply(image);
    gtk_image_get_icon_name(GTK_IMAGE(image), &name, &size);
    g_assert_cmpstr(name, ==, "org.mozilla.firefox");
    g_assert_cmpint(gtk_image_get_pixel_size(GTK_IMAGE(image)), ==, 24);
    gtk_style_context_remove_class(gtk_widget_get_style_context(image), "app-icon");
    gtk_style_context_add_class(gtk_widget_get_style_context(row), "daily-app");
    soft_icons_apply(image);
    g_assert_cmpint(gtk_image_get_pixel_size(GTK_IMAGE(image)), ==, 32);
    /* A private symbolic asset resolves and renders at the requested size. */
    GtkIconInfo *info = gtk_icon_theme_lookup_icon(gtk_icon_theme_get_default(), "raccon-close-symbolic", 20, GTK_ICON_LOOKUP_FORCE_SIZE);
    g_assert_nonnull(info);
    GdkRGBA foreground = { .red = .2, .green = .6, .blue = .8, .alpha = 1 };
    GError *error = NULL;
    gboolean symbolic = FALSE;
    GdkPixbuf *pixels = gtk_icon_info_load_symbolic(info, &foreground, NULL, NULL, NULL, &symbolic, &error);
    g_assert_no_error(error); g_assert_nonnull(pixels); g_assert_true(symbolic);
    g_assert_cmpint(gdk_pixbuf_get_width(pixels), ==, 20);
    g_assert_cmpint(gdk_pixbuf_get_height(pixels), ==, 20);
    g_object_unref(pixels); g_object_unref(info);
    gchar *asset_path = g_build_filename(argv[1], "hicolor", "scalable", "actions", NULL);
    GDir *assets = g_dir_open(asset_path, 0, &error);
    g_assert_no_error(error); g_assert_nonnull(assets);
    const gchar *asset;
    guint rendered = 0;
    while ((asset = g_dir_read_name(assets))) {
        if (!g_str_has_suffix(asset, ".svg")) continue;
        gchar *icon_name = g_strndup(asset, strlen(asset) - 4);
        info = gtk_icon_theme_lookup_icon(gtk_icon_theme_get_default(), icon_name, 20, GTK_ICON_LOOKUP_FORCE_SIZE);
        g_assert_nonnull(info);
        pixels = gtk_icon_info_load_symbolic(info, &foreground, NULL, NULL, NULL, &symbolic, &error);
        g_assert_no_error(error); g_assert_nonnull(pixels); g_assert_true(symbolic);
        g_assert_cmpint(gdk_pixbuf_get_width(pixels), ==, 20);
        g_assert_cmpint(gdk_pixbuf_get_height(pixels), ==, 20);
        const guchar *data = gdk_pixbuf_read_pixels(pixels);
        gint stride = gdk_pixbuf_get_rowstride(pixels);
        gint channels = gdk_pixbuf_get_n_channels(pixels);
        g_assert_true(gdk_pixbuf_get_has_alpha(pixels));
        if (g_str_equal(icon_name, "raccon-folder-symbolic") ||
                g_str_equal(icon_name, "raccon-prompt-symbolic") ||
                g_str_equal(icon_name, "raccon-monitor-symbolic"))
            g_assert_cmpuint(data[10 * stride + 10 * channels + 3], ==, 0);
        if (g_str_equal(icon_name, "raccon-close-symbolic")) {
            const guchar *center = data + 10 * stride + 10 * channels;
            g_assert_cmpuint(center[3], >, 100);
            g_assert_cmpint(ABS(center[0] - 51), <, 5);
            g_assert_cmpint(ABS(center[1] - 153), <, 5);
            g_assert_cmpint(ABS(center[2] - 204), <, 5);
        }
        g_object_unref(pixels); g_object_unref(info); g_free(icon_name);
        rendered++;
    }
    g_assert_cmpuint(rendered, >, 0);
    g_dir_close(assets); g_free(asset_path);
    gtk_widget_destroy(row);
}
''')
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True))
        result = subprocess.run(['cc', str(source), '-o', str(cls.binary), *flags], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_control_mapping_preserves_application_identity(self):
        subprocess.run([str(self.binary)], check=True, capture_output=True)

    @unittest.skipUnless(os.environ.get('RACCON_MENU_GUI_TEST') == '1', 'opt-in GTK connection')
    def test_fixed_sizes_dynamic_icons_and_symbolic_assets(self):
        result = subprocess.run([str(self.binary), str(ICONS)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_mapping_has_an_asset_and_style_icons_are_mapped(self):
        import re
        header = (LIB / 'soft_icons.h').read_text()
        mapped = dict(re.findall(r'\{"([\w.-]+)", "(raccon-[\w-]+)"\}', header))
        assets = ICONS / 'hicolor/scalable/actions'
        self.assertEqual([g for g in set(mapped.values()) if not (assets / f'{g}.svg').is_file()], [])
        styles = (ROOT / 'modules/desktop-styles/files/.local/lib/desktop_style/main.py').read_text()
        used = set(re.findall(r"'([a-z-]+-symbolic)'", styles))
        self.assertEqual(sorted(used - set(mapped)), [])
