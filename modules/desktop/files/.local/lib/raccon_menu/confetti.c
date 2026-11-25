/* Click-through Wayland confetti burst overlay rendered with GTK3 + Cairo. */
#include <gtk/gtk.h>
#include <gtk-layer-shell.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define PIECE_COUNT 84
#define DURATION_US 2500000

typedef struct {
    double x, y, vx, vy;
    double angle, spin, phase, tilt_speed;
    double w, h;
    double r, g, b;
} Piece;

static Piece pieces[PIECE_COUNT];
static double palette[5][3] = {
    {0.96, 0.56, 0.55},
    {0.65, 0.65, 0.87},
    {0.91, 0.79, 0.62},
    {0.95, 0.95, 0.95},
    {1.00, 0.71, 0.67},
};
static gint64 started_us;
static double elapsed_s;

static double randf(double lo, double hi) {
    return lo + ((double)rand() / (double)RAND_MAX) * (hi - lo);
}

static void parse_hex(const char *hex, double out[3]) {
    unsigned int r = 240, g = 140, b = 140;
    if (hex && hex[0] == '#' && strlen(hex) >= 7) {
        sscanf(hex + 1, "%02x%02x%02x", &r, &g, &b);
    }
    out[0] = r / 255.0;
    out[1] = g / 255.0;
    out[2] = b / 255.0;
}

static void load_palette(void) {
    const char *roles[] = {"primary", "secondary", "tertiary", "on_surface", "error"};
    gchar *path = g_build_filename(g_get_home_dir(), ".config", "waybar", "colors.css", NULL);
    gchar *text = NULL;
    if (g_file_get_contents(path, &text, NULL, NULL)) {
        for (int i = 0; i < 5; i++) {
            gchar *pat = g_strdup_printf("@define-color[[:space:]]+%s[[:space:]]+(#[0-9a-fA-F]{6})", roles[i]);
            GRegex *re = g_regex_new(pat, 0, 0, NULL);
            GMatchInfo *m = NULL;
            if (g_regex_match(re, text, 0, &m)) {
                gchar *hex = g_match_info_fetch(m, 1);
                parse_hex(hex, palette[i]);
                g_free(hex);
            }
            g_match_info_free(m);
            g_regex_unref(re);
            g_free(pat);
        }
        g_free(text);
    }
    g_free(path);
}

static void spawn_pieces(double origin_x, double origin_y) {
    srand((unsigned int)time(NULL) ^ (unsigned int)g_get_monotonic_time());
    for (int i = 0; i < PIECE_COUNT; i++) {
        double dir = randf(-M_PI * 0.12, M_PI * 1.12);
        double speed = randf(220.0, 740.0);
        int ci = rand() % 5;
        pieces[i].x = origin_x + randf(-24.0, 24.0);
        pieces[i].y = origin_y + randf(-10.0, 10.0);
        pieces[i].vx = cos(dir) * speed;
        pieces[i].vy = sin(dir) * speed - 180.0;
        pieces[i].angle = randf(0, 2.0 * M_PI);
        pieces[i].spin = randf(-8.0, 8.0);
        pieces[i].phase = randf(0, 2.0 * M_PI);
        pieces[i].tilt_speed = randf(4.0, 11.0);
        pieces[i].w = randf(6.0, 12.0);
        pieces[i].h = randf(4.0, 7.0);
        pieces[i].r = palette[ci][0];
        pieces[i].g = palette[ci][1];
        pieces[i].b = palette[ci][2];
    }
}

static gboolean on_draw(GtkWidget *w, cairo_t *cr, gpointer unused) {
    double alpha_global = elapsed_s > 1.75 ? CLAMP(1.0 - (elapsed_s - 1.75) / 0.75, 0.0, 1.0) : 1.0;
    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_set_source_rgba(cr, 0, 0, 0, 0);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);
    for (int i = 0; i < PIECE_COUNT; i++) {
        double tilt = fabs(cos(pieces[i].phase));
        cairo_save(cr);
        cairo_translate(cr, pieces[i].x, pieces[i].y);
        cairo_rotate(cr, pieces[i].angle);
        cairo_scale(cr, 1.0, MAX(0.22, tilt));
        cairo_set_source_rgba(cr, pieces[i].r, pieces[i].g, pieces[i].b, alpha_global * 0.94);
        cairo_rectangle(cr, -pieces[i].w * 0.5, -pieces[i].h * 0.5, pieces[i].w, pieces[i].h);
        cairo_fill(cr);
        cairo_restore(cr);
    }
    return FALSE;
}

static gboolean on_tick(GtkWidget *w, GdkFrameClock *clock, gpointer unused) {
    static gint64 prev_us;
    gint64 now = g_get_monotonic_time();
    if (!started_us) { started_us = now; prev_us = now; }
    double dt = CLAMP((now - prev_us) / 1000000.0, 0.001, 0.05);
    prev_us = now;
    elapsed_s = (now - started_us) / 1000000.0;
    for (int i = 0; i < PIECE_COUNT; i++) {
        pieces[i].vy += 760.0 * dt;
        pieces[i].vx *= pow(0.32, dt);
        pieces[i].x += pieces[i].vx * dt;
        pieces[i].y += pieces[i].vy * dt;
        pieces[i].angle += pieces[i].spin * dt;
        pieces[i].phase += pieces[i].tilt_speed * dt;
    }
    gtk_widget_queue_draw(w);
    if (now - started_us >= DURATION_US) {
        gtk_main_quit();
        return G_SOURCE_REMOVE;
    }
    return G_SOURCE_CONTINUE;
}

static gboolean force_quit(gpointer unused) {
    gtk_main_quit();
    return G_SOURCE_REMOVE;
}

int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    load_palette();
    GdkDisplay *display = gdk_display_get_default();
    GdkMonitor *monitor = display ? (gdk_display_get_primary_monitor(display) ?: gdk_display_get_monitor(display, 0)) : NULL;
    GdkRectangle bounds = {0, 0, 1920, 1080};
    if (monitor) gdk_monitor_get_geometry(monitor, &bounds);

    double ox = bounds.width * 0.5;
    double oy = 64.0;
    gchar *pos_path = g_build_filename(g_get_user_state_dir(), "raccon-countdown", "pos.ini", NULL);
    GKeyFile *kf = g_key_file_new();
    if (g_key_file_load_from_file(kf, pos_path, G_KEY_FILE_NONE, NULL) &&
        g_key_file_has_key(kf, "pos", "x", NULL) && g_key_file_has_key(kf, "pos", "y", NULL)) {
        ox = g_key_file_get_integer(kf, "pos", "x", NULL) + 84.0;
        oy = g_key_file_get_integer(kf, "pos", "y", NULL) + 24.0;
    }
    g_key_file_unref(kf);
    g_free(pos_path);
    spawn_pieces(ox, oy);

    GtkWidget *win = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_layer_init_for_window(GTK_WINDOW(win));
    gtk_layer_set_layer(GTK_WINDOW(win), GTK_LAYER_SHELL_LAYER_OVERLAY);
    gtk_layer_set_keyboard_mode(GTK_WINDOW(win), GTK_LAYER_SHELL_KEYBOARD_MODE_NONE);
    gtk_layer_set_exclusive_zone(GTK_WINDOW(win), -1);
    for (int i = 0; i < 4; i++) gtk_layer_set_anchor(GTK_WINDOW(win), i, TRUE);
    gtk_layer_set_namespace(GTK_WINDOW(win), "raccon-confetti");

    GdkScreen *screen = gtk_widget_get_screen(win);
    GdkVisual *visual = gdk_screen_get_rgba_visual(screen);
    if (visual) gtk_widget_set_visual(win, visual);
    gtk_widget_set_app_paintable(win, TRUE);
    gtk_window_set_accept_focus(GTK_WINDOW(win), FALSE);

    GtkWidget *area = gtk_drawing_area_new();
    gtk_container_add(GTK_CONTAINER(win), area);
    g_signal_connect(area, "draw", G_CALLBACK(on_draw), NULL);
    gtk_widget_show_all(win);

    cairo_region_t *empty = cairo_region_create();
    gtk_widget_input_shape_combine_region(win, empty);
    if (gtk_widget_get_window(win)) gdk_window_input_shape_combine_region(gtk_widget_get_window(win), empty, 0, 0);
    cairo_region_destroy(empty);

    gtk_widget_add_tick_callback(area, on_tick, NULL, NULL);
    g_timeout_add(3200, force_quit, NULL);
    gtk_main();
    return 0;
}
