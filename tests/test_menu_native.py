"""Exercise the shipped native search logic; optional GTK test never maps a window."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'modules/desktop/files/.local/lib/raccon_menu/input.c'


class NativeSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('cc') or not shutil.which('pkg-config'):
            raise unittest.SkipTest('C/GTK development tools unavailable')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True,
                               capture_output=True)
        if flags.returncode:
            raise unittest.SkipTest('GTK3 development files unavailable')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        harness = Path(cls.temp.name) / 'native.c'
        harness.write_text('#include "' + str(SOURCE) + '"\n' + r'''
static guint launches;
static void launched(GtkButton *button, gpointer data) { launches++; }
static GtkWidget *row(const gchar *text) {
    GtkWidget *button = gtk_button_new();
    gtk_style_context_add_class(gtk_widget_get_style_context(button), "app-launch");
    GtkWidget *label = gtk_label_new(text);
    gtk_style_context_add_class(gtk_widget_get_style_context(label), "search-key");
    gtk_container_add(GTK_CONTAINER(button), label);
    g_signal_connect(button, "clicked", G_CALLBACK(launched), NULL);
    return button;
}
int main(int argc, char **argv) {
    if (argc > 1 && g_str_equal(argv[1], "--gtk")) {
        gtk_init(&argc, &argv);
        runtime_dir = g_dir_make_tmp("raccon-native-test-XXXXXX", NULL);
        menu_window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
        GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
        gtk_container_add(GTK_CONTAINER(menu_window), root);
        GtkWidget *entry = gtk_entry_new();
        gtk_style_context_add_class(gtk_widget_get_style_context(entry), "app-search");
        gtk_container_add(GTK_CONTAINER(root), entry);
        GtkWidget *pages = gtk_stack_new();
        gtk_style_context_add_class(gtk_widget_get_style_context(pages), "pages");
        gtk_container_add(GTK_CONTAINER(root), pages);
        GtkWidget *home = gtk_label_new("Daily apps");
        gtk_stack_add_named(GTK_STACK(pages), home, "eww-home");
        GtkWidget *list = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
        gtk_style_context_add_class(gtk_widget_get_style_context(list), "apps-list");
        gtk_stack_add_named(GTK_STACK(pages), list, "eww-results");
        GtkWidget *audio = row("configuracion de audio");
        GtkWidget *brave = row("brave navegador");
        gtk_container_add(GTK_CONTAINER(list), audio);
        gtk_container_add(GTK_CONTAINER(list), brave);
        gtk_widget_show_all(root); /* The toplevel stays hidden throughout. */
        g_signal_connect(entry, "changed", G_CALLBACK(entry_changed), NULL);
        gtk_entry_set_text(GTK_ENTRY(entry), "AÚDIO configuración");
        g_assert_cmpuint(result_count, ==, 1);
        g_assert(gtk_widget_get_visible(audio));
        g_assert(!gtk_widget_get_visible(brave));
        g_assert(gtk_stack_get_visible_child(GTK_STACK(pages)) == list);
        entry_accept(GTK_ENTRY(entry), GTK_WINDOW(menu_window));
        g_assert_cmpuint(launches, ==, 1);
        gtk_entry_set_text(GTK_ENTRY(entry), "'; $(touch never) #");
        g_assert_cmpuint(result_count, ==, 0);
        entry_accept(GTK_ENTRY(entry), GTK_WINDOW(menu_window));
        g_assert_cmpuint(launches, ==, 1);
        gtk_entry_set_text(GTK_ENTRY(entry), "");
        g_assert(gtk_stack_get_visible_child(GTK_STACK(pages)) == home);
        gtk_window_set_focus(GTK_WINDOW(menu_window), brave);
        GdkEventKey event = {0}; event.keyval = GDK_KEY_b;
        g_assert(key_press(menu_window, &event, NULL));
        g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(entry)), ==, "b");
        g_assert_cmpuint(result_count, ==, 1);
        g_assert(gtk_stack_get_visible_child(GTK_STACK(pages)) == list);
        /* Services reuse the main window's attached side stack. */
        GtkWidget *side = gtk_revealer_new();
        gtk_style_context_add_class(gtk_widget_get_style_context(side), "side-revealer");
        gtk_container_add(GTK_CONTAINER(root), side);
        GtkWidget *side_pages = gtk_stack_new();
        gtk_style_context_add_class(gtk_widget_get_style_context(side_pages), "side-pages");
        gtk_container_add(GTK_CONTAINER(side), side_pages);
        GtkWidget *service_pages[5];
        for (guint i = 0; i < 5; i++) {
            service_pages[i] = gtk_label_new("Side page");
            gtk_container_add(GTK_CONTAINER(side_pages), service_pages[i]);
            gtk_widget_show(service_pages[i]);
        }
        for (guint page = 4; page <= 6; page++) {
            select_page(page);
            g_assert(gtk_revealer_get_reveal_child(GTK_REVEALER(side)));
            g_assert(gtk_stack_get_visible_child(GTK_STACK(side_pages)) == service_pages[page - 2]);
        }
        select_page(0);
        g_assert(!gtk_revealer_get_reveal_child(GTK_REVEALER(side)));
        /* User slider changes win over a stale provider value; never run pactl. */
        GtkWidget *slider = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, 0, 100, 1);
        Volume *volume = &volumes[0];
        volume_change(GTK_RANGE(slider), GTK_SCROLL_JUMP, 73, volume);
        gtk_range_set_value(GTK_RANGE(slider), 10);
        volume_changed(GTK_RANGE(slider), volume);
        g_assert_cmpfloat(gtk_range_get_value(GTK_RANGE(slider)), ==, 73);
        volume_change(GTK_RANGE(slider), GTK_SCROLL_JUMP, 64, volume);
        g_assert_cmpfloat(volume->value, ==, 64);
        g_source_remove(volume->timer); volume->timer = 0;
        gtk_widget_destroy(slider);
        GtkWidget *bt_page = gtk_label_new("Bluetooth");
        gtk_stack_add_named(GTK_STACK(pages), bt_page, "bt-controls");
        gtk_widget_show(bt_page);
        simple_pages = TRUE;
        select_page(2);
        g_assert(gtk_stack_get_visible_child(GTK_STACK(pages)) == bt_page);
        /* Unified controls reveal details without replacing the volume area. */
        GtkWidget *unified = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
        gtk_style_context_add_class(gtk_widget_get_style_context(unified), "unified-controls");
        gtk_container_add(GTK_CONTAINER(root), unified);
        GtkWidget *wifi = gtk_revealer_new();
        GtkWidget *bluetooth = gtk_revealer_new();
        gtk_style_context_add_class(gtk_widget_get_style_context(wifi), "wifi-details");
        gtk_style_context_add_class(gtk_widget_get_style_context(bluetooth), "bluetooth-details");
        gtk_container_add(GTK_CONTAINER(unified), wifi);
        gtk_container_add(GTK_CONTAINER(unified), bluetooth);
        select_page(1);
        g_assert(gtk_revealer_get_reveal_child(GTK_REVEALER(wifi)));
        g_assert(!gtk_revealer_get_reveal_child(GTK_REVEALER(bluetooth)));
        select_page(2);
        g_assert(!gtk_revealer_get_reveal_child(GTK_REVEALER(wifi)));
        g_assert(gtk_revealer_get_reveal_child(GTK_REVEALER(bluetooth)));
        select_page(0);
        g_assert(!gtk_revealer_get_reveal_child(GTK_REVEALER(wifi)));
        g_assert(!gtk_revealer_get_reveal_child(GTK_REVEALER(bluetooth)));
        /* Synthetic credentials traverse stdin only and the entry clears immediately. */
        GtkWidget *password = gtk_entry_new();
        gtk_style_context_add_class(gtk_widget_get_style_context(password), "wifi-password");
        gtk_container_add(GTK_CONTAINER(root), password);
        GValue password_value = G_VALUE_INIT;
        g_value_init(&password_value, GTK_TYPE_WIDGET);
        g_value_set_object(&password_value, password);
        mapped(NULL, 1, &password_value, NULL);
        g_assert(!gtk_entry_get_visibility(GTK_ENTRY(password)));
        backend = g_build_filename(runtime_dir, "fixture.py", NULL);
        const gchar *script = "import sys,json\nfrom pathlib import Path\nPath(__file__+'.json').write_text(json.dumps(dict(args=sys.argv[1:],secret=sys.stdin.read())))\n";
        g_file_set_contents(backend, script, -1, NULL);
        gtk_entry_set_text(GTK_ENTRY(password), "fixture ; $(never)");
        password_connect(password, NULL);
        g_assert_cmpstr(gtk_entry_get_text(GTK_ENTRY(password)), ==, "");
        gchar *receipt = g_strconcat(backend, ".json", NULL);
        gint64 deadline = g_get_monotonic_time() + 2000000;
        while (!g_file_test(receipt, G_FILE_TEST_EXISTS) && g_get_monotonic_time() < deadline) {
            g_main_context_iteration(NULL, FALSE); g_usleep(2000);
        }
        gtk_window_set_focus(GTK_WINDOW(menu_window), password);
        event.keyval = GDK_KEY_x;
        g_assert(!key_press(menu_window, &event, NULL));
        gchar *received = NULL;
        g_assert(g_file_get_contents(receipt, &received, NULL, NULL));
        g_assert(strstr(received, "[\"wifi-connect\"]") != NULL);
        g_assert(strstr(received, "fixture ; $(never)") != NULL);
        g_free(received); unlink(receipt);
        simple_pages = FALSE;
        gtk_entry_set_text(GTK_ENTRY(password), "second fixture");
        password_connect(password, NULL);
        deadline = g_get_monotonic_time() + 2000000;
        while (!g_file_test(receipt, G_FILE_TEST_EXISTS) && g_get_monotonic_time() < deadline) {
            g_main_context_iteration(NULL, FALSE); g_usleep(2000);
        }
        received = NULL;
        g_assert(g_file_get_contents(receipt, &received, NULL, NULL));
        g_assert(strstr(received, "control-action") != NULL);
        g_assert(strstr(received, "second fixture") != NULL);
        g_free(received); unlink(receipt); g_free(receipt); unlink(backend); g_free(backend); backend = NULL;
        g_value_unset(&password_value);
        simple_pages = FALSE;
        /* Eww maps a replacement before destroying the old theme window. */
        GtkWidget *previous = menu_window;
        g_signal_connect(previous, "destroy", G_CALLBACK(window_destroyed), NULL);
        GtkWidget *replacement = gtk_window_new(GTK_WINDOW_TOPLEVEL);
        GValue value = G_VALUE_INIT;
        g_value_init(&value, GTK_TYPE_WIDGET);
        g_value_set_object(&value, replacement);
        seen_window = TRUE; visible = FALSE;
        mapped(NULL, 1, &value, NULL);
        gtk_widget_destroy(previous);
        g_assert(menu_window == replacement);
        gtk_widget_destroy(replacement);
        g_value_unset(&value);
        g_assert(menu_window == NULL);
        gchar *mapped_file = g_build_filename(runtime_dir, "mapped", NULL);
        unlink(mapped_file); g_free(mapped_file);
        gchar *file = g_build_filename(runtime_dir, "page", NULL);
        unlink(file); rmdir(runtime_dir); g_free(file); g_free(runtime_dir);
        return 0;
    }
    if (argc != 3) return 2;
    gchar *query = search_normalize(argv[1]);
    gchar *key = search_normalize(argv[2]);
    gchar **words = g_strsplit_set(query, " \t\r\n", -1);
    gboolean result = search_matches(key, words);
    g_strfreev(words); g_free(query); g_free(key);
    return result ? 0 : 1;
}
''')
        cls.binary = Path(cls.temp.name) / 'native'
        subprocess.run(['cc', '-O2', '-Wno-unused-parameter', str(harness), '-o', str(cls.binary),
                        *shlex.split(flags.stdout)], check=True, capture_output=True, text=True)

    def test_native_words_accents_and_shell_characters(self):
        for query, value, match in (
            ('AÚDIO configuración', 'Configuración de audio', True),
            ("L'éditeur", "L'éditeur", True),
            ('配置', '系统配置', True),
            ('brave terminal', 'brave navegador', False),
            ('', 'anything', True),
            ("'; $(touch never) #", 'brave', False),
        ):
            with self.subTest(query=query):
                result = subprocess.run([str(self.binary), query, value], capture_output=True)
                self.assertEqual(result.returncode, 0 if match else 1, result.stderr)

    @unittest.skipUnless(os.environ.get('RACCON_MENU_GUI_TEST') == '1', 'opt-in GTK connection')
    def test_typeahead_filter_enter_and_stack_selection_without_a_mapped_window(self):
        result = subprocess.run([str(self.binary), '--gtk'], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
