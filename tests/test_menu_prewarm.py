"""Run the production warmup callback without mapping a compositor surface."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'modules/desktop/files/.local/lib/raccon_menu/input.c'


class MenuPrewarmTests(unittest.TestCase):
    def test_warms_common_pages_without_service_requests_and_parks(self):
        callback = SOURCE.read_text().split('static gboolean prewarm_frame(', 1)[1].split('\nstatic void hide_menu', 1)[0]
        fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef unsigned guint;
typedef int gboolean;
typedef void GdkFrameClock;
typedef void *gpointer;
typedef struct { guint frames, index, duration; int revealed; } GtkWidget;
#define G_SOURCE_REMOVE 0
#define G_SOURCE_CONTINUE 1
#define G_OBJECT(w) (w)
#define GPOINTER_TO_UINT(p) ((guint)(uintptr_t)(p))
#define GUINT_TO_POINTER(n) ((void *)(uintptr_t)(n))
#define GTK_IS_STACK(w) ((w) != 0)
#define GTK_STACK(w) (w)
#define GTK_IS_REVEALER(w) ((w) != 0)
#define GTK_REVEALER(w) (w)
static GtkWidget window, pages, side, side_pages;
static GtkWidget *menu_window = &window;
static gboolean visible, browsing_apps;
static guint parked, ready, current_page;
static void *g_object_get_data(GtkWidget *w, const char *key) { return GUINT_TO_POINTER(w->frames); }
static void g_object_set_data(GtkWidget *w, const char *key, void *value) { w->frames = GPOINTER_TO_UINT(value); }
static GtkWidget *find(GtkWidget *w, const char *name) {
    if (!strcmp(name, "pages")) return &pages;
    if (!strcmp(name, "side-revealer")) return &side;
    if (!strcmp(name, "side-pages")) return &side_pages;
    return 0;
}
static void stack_index(GtkWidget *w, guint index) { w->index = index; }
static void gtk_stack_set_transition_duration(GtkWidget *w, guint duration) { w->duration = duration; }
static void gtk_revealer_set_transition_duration(GtkWidget *w, guint duration) { w->duration = duration; }
static void gtk_revealer_set_reveal_child(GtkWidget *w, gboolean reveal) { w->revealed = reveal; }
static void resident_surface_park(GtkWidget *w) { parked++; }
static void state(const char *key, const char *value) {
    /* A warmup must never publish a service-page activation. */
    assert(!strcmp(key, "ready")); assert(!strcmp(value, "1")); ready++;
}
#define TRUE 1
#define FALSE 0
static gboolean prewarm_frame(CALLBACK
int main(void) {
    for (guint frame = 1; frame <= 12; frame++) {
        gboolean result = prewarm_frame(&window, 0, 0);
        assert(result == (frame < 12 ? G_SOURCE_CONTINUE : G_SOURCE_REMOVE));
        assert(parked == (frame == 12));
        if (frame == 3) assert(pages.index == 1);
        if (frame == 6) assert(pages.index == 0 && side.revealed && side_pages.index == 2);
        if (frame == 9) assert(side.revealed && side_pages.index == 3);
    }
    assert(ready == 1 && pages.index == 0 && side_pages.index == 0 && !side.revealed);
    /* Opening a service during the Apps warm stage must restore Home. */
    window.frames = 0;
    for (guint frame = 0; frame < 3; frame++) prewarm_frame(&window, 0, 0);
    assert(pages.index == 1);
    visible = 1;
    side.revealed = 1; side_pages.index = 2;
    assert(prewarm_frame(&window, 0, 0) == G_SOURCE_REMOVE);
    assert(pages.index == 0 && side.revealed && side_pages.index == 2);
    assert(parked == 1 && ready == 2);
    /* A user explicitly opening Apps must keep their selection. */
    browsing_apps = 1;
    prewarm_frame(&window, 0, 0);
    assert(pages.index == 1 && parked == 1);
    GtkWidget other = {0};
    assert(prewarm_frame(&other, 0, 0) == G_SOURCE_REMOVE);
    assert(ready == 3);
}
'''.replace('CALLBACK', callback)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'warm.c'
            binary = Path(temp) / 'warm'
            source.write_text(fixture)
            subprocess.run(['cc', '-std=c11', str(source), '-o', str(binary)], check=True, capture_output=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
