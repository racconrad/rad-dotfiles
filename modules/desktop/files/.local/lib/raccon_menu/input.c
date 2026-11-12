/* Local GTK input/visibility adapter for Raccon's own Eww instance. */
#include <gtk/gtk.h>
#include <gmodule.h>
#include "navigation.h"
#include "resident_surface.h"
#include "soft_icons.h"
#include "popup_geometry.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

static gchar *backend, *runtime_dir;
static gboolean super_down, super_used, visible, seen_window;
static guint hide_timer, focus_timer, current_page, result_count;
static gint64 filter_us, open_us, map_us;
static gboolean browsing_apps, simple_pages;
static gint64 shown_at, motion_started;
static guint motion_tick, motion_ms;
static gdouble motion_from, motion_target, motion_progress = 1;
static GtkWidget *animated_window;
static GtkWidget *menu_window;
static void focus_search(GtkWidget *window);
static void filter_current(void);
/* Eww links layer-shell; weak symbols keep this module usable on X11. */
extern void gtk_layer_set_keyboard_mode(GtkWindow *, gint) __attribute__((weak));
extern gboolean gtk_layer_is_layer_window(GtkWindow *) __attribute__((weak));
static void keyboard_mode(gint mode) {
    if (menu_window && gtk_layer_set_keyboard_mode && gtk_layer_is_layer_window &&
        gtk_layer_is_layer_window(GTK_WINDOW(menu_window)))
        gtk_layer_set_keyboard_mode(GTK_WINDOW(menu_window), mode);
}

static void dispatch(const gchar *action, const gchar *value) {
    gchar *argv[] = {"python3", backend, (gchar *)action, (gchar *)value, NULL};
    GError *error = NULL;
    if (!g_spawn_async(NULL, argv, NULL, G_SPAWN_SEARCH_PATH, NULL, NULL, NULL, &error)) {
        g_warning("Raccon input: %s", error->message);
        g_error_free(error);
    }
}
static void state(const gchar *name, const gchar *value) {
    gchar *path = g_build_filename(runtime_dir, name, NULL);
    g_file_set_contents(path, value, -1, NULL);
    g_free(path);
}
static gboolean has_class(GtkWidget *widget, const gchar *name) {
    if (!GTK_IS_WIDGET(widget)) return FALSE;
    return gtk_style_context_has_class(gtk_widget_get_style_context(widget), name);
}
static GtkWidget *find(GtkWidget *widget, const gchar *name) {
    if (has_class(widget, name)) return widget;
    if (!GTK_IS_CONTAINER(widget)) return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
    GtkWidget *found = NULL;
    for (GList *item = children; item && !found; item = item->next) found = find(item->data, name);
    g_list_free(children);
    return found;
}
/* Never block the GTK thread on compositor IPC; consume the background cache. */
extern void gtk_layer_set_exclusive_zone(GtkWindow *, gint) __attribute__((weak));
extern void gtk_layer_set_anchor(GtkWindow *, gint, gboolean) __attribute__((weak));
extern void gtk_layer_set_margin(GtkWindow *, gint, gint) __attribute__((weak));
extern void gtk_layer_set_monitor(GtkWindow *, GdkMonitor *) __attribute__((weak));
static gint dock_edge = 3, dock_body = 460;
static gint config_number(const gchar *text, const gchar *name, gint fallback) {
    gchar *pattern = g_strdup_printf("\"%s\"[[:space:]]*:[[:space:]]*([0-9]+)", name);
    GRegex *regex = g_regex_new(pattern, 0, 0, NULL); GMatchInfo *match = NULL;
    gint result = fallback;
    if (g_regex_match(regex, text, 0, &match)) {
        gchar *value = g_match_info_fetch(match, 1); result = atoi(value); g_free(value);
    }
    g_match_info_free(match); g_regex_unref(regex); g_free(pattern);
    return CLAMP(result, 0, 8192);
}
static void control_details(guint page) {
    GtkWidget *wifi = find(menu_window, "wifi-details");
    GtkWidget *bluetooth = find(menu_window, "bluetooth-details");
    if (GTK_IS_REVEALER(wifi)) gtk_revealer_set_reveal_child(GTK_REVEALER(wifi), page == 1);
    if (GTK_IS_REVEALER(bluetooth)) gtk_revealer_set_reveal_child(GTK_REVEALER(bluetooth), page == 2);
    GtkWidget *scroll = find(menu_window, "controls-scroll");
    if (scroll) gtk_widget_set_size_request(scroll, -1, page ? dock_body : MIN(260, dock_body));
}
static void dock_window(void) {
    if (!menu_window || !gtk_layer_set_anchor || !gtk_layer_set_margin || !gtk_layer_is_layer_window ||
        !gtk_layer_is_layer_window(GTK_WINDOW(menu_window))) return;
    gchar *path = g_build_filename(runtime_dir, "dock.ini", NULL);
    GKeyFile *data = g_key_file_new();
    gboolean cached = g_key_file_load_from_file(data, path, G_KEY_FILE_NONE, NULL);
    g_free(path);
    gchar *edge = cached ? g_key_file_get_string(data, "dock", "edge", NULL) : NULL;
    gint inset = cached ? g_key_file_get_integer(data, "dock", "inset", NULL) : 72;
    gint start = cached ? g_key_file_get_integer(data, "dock", "start", NULL) : 14;
    gint end = cached ? g_key_file_get_integer(data, "dock", "end", NULL) : 14;
    gint ow = cached ? g_key_file_get_integer(data, "dock", "ow", NULL) : 1920;
    gint oh = cached ? g_key_file_get_integer(data, "dock", "oh", NULL) : 1080;
    gchar *config_path = g_build_filename(g_get_home_dir(), ".config", "waybar", "config.jsonc", NULL);
    struct stat info;
    gint64 stamp = cached ? g_key_file_get_int64(data, "dock", "config_mtime", NULL) : 0;
    if (!cached || (stat(config_path, &info) == 0 && stamp != info.st_mtim.tv_sec * G_GINT64_CONSTANT(1000000000) + info.st_mtim.tv_nsec)) {
        gchar *text = NULL;
        if (g_file_get_contents(config_path, &text, NULL, NULL)) {
            GRegex *regex = g_regex_new("\"position\"[[:space:]]*:[[:space:]]*\"(top|bottom|left|right)\"", 0, 0, NULL);
            GMatchInfo *match = NULL;
            if (g_regex_match(regex, text, 0, &match)) { g_free(edge); edge = g_match_info_fetch(match, 1); }
            g_match_info_free(match); g_regex_unref(regex);
            gboolean vertical = g_strcmp0(edge, "left") == 0 || g_strcmp0(edge, "right") == 0;
            gchar *margin = g_strdup_printf("margin-%s", edge ? edge : "bottom");
            inset = config_number(text, vertical ? "width" : "height", vertical ? 48 : 32) + config_number(text, margin, 0) + 4;
            start = config_number(text, vertical ? "margin-top" : "margin-left", 8);
            end = config_number(text, vertical ? "margin-bottom" : "margin-right", 8);
            g_free(margin); g_free(text);
        }
    }
    g_free(config_path);
    dock_edge = g_strcmp0(edge, "left") == 0 ? 0 : g_strcmp0(edge, "right") == 0 ? 1 : g_strcmp0(edge, "top") == 0 ? 2 : 3;
    if (cached && gtk_layer_set_monitor) {
        GdkDisplay *display = gtk_widget_get_display(menu_window);
        gint ox = g_key_file_get_integer(data, "dock", "ox", NULL), oy = g_key_file_get_integer(data, "dock", "oy", NULL);
        for (gint i = 0; i < gdk_display_get_n_monitors(display); i++) {
            GdkMonitor *monitor = gdk_display_get_monitor(display, i); GdkRectangle rect;
            gdk_monitor_get_geometry(monitor, &rect);
            if (rect.x == ox && rect.y == oy && rect.width == ow && rect.height == oh) {
                gtk_layer_set_monitor(GTK_WINDOW(menu_window), monitor); break;
            }
        }
    }
    /* Anchor to the complete output, otherwise the compositor subtracts Waybar twice. */
    if (gtk_layer_set_exclusive_zone) gtk_layer_set_exclusive_zone(GTK_WINDOW(menu_window), -1);
    gint along = simple_pages ? end : start;
    gint other = dock_edge <= 1 ? (simple_pages ? 3 : 2) : (simple_pages ? 1 : 0);
    for (gint i = 0; i < 4; i++) {
        gtk_layer_set_anchor(GTK_WINDOW(menu_window), i, i == dock_edge || i == other);
        gtk_layer_set_margin(GTK_WINDOW(menu_window), i, i == dock_edge ? MAX(4, inset) : i == other ? MAX(4, along) : 0);
    }
    dock_body = MAX(140, MIN(460, oh - (dock_edge >= 2 ? inset : 4) - 120));
    GtkWidget *popup = find(menu_window, "popup");
    if (popup) {
        const gchar *names[] = {"dock-left", "dock-right", "dock-top", "dock-bottom"};
        GtkStyleContext *context = gtk_widget_get_style_context(popup);
        for (guint i = 0; i < 4; i++) {
            if (i == (guint)dock_edge) gtk_style_context_add_class(context, names[i]);
            else gtk_style_context_remove_class(context, names[i]);
        }
        GtkWidget *side = find(menu_window, "side-revealer");
        if (side) gtk_widget_set_valign(side, dock_edge == 2 ? GTK_ALIGN_START : GTK_ALIGN_END);
        if (!simple_pages && GTK_IS_BOX(popup) && side)
            gtk_box_reorder_child(GTK_BOX(popup), side, dock_edge == 1 ? 0 : -1);
    }
    if (simple_pages && find(menu_window, "unified-controls")) control_details(current_page);
    GtkWidget *side_pages = find(menu_window, "side-pages");
    if (GTK_IS_CONTAINER(side_pages)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(side_pages));
        for (GList *item = children; item; item = item->next) {
            GtkWidget *scroll = find(item->data, "service-scroll");
            if (scroll) {
                gint desired = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(scroll), "service-height"));
                if (!desired) {
                    gtk_widget_get_size_request(scroll, NULL, &desired);
                    if (desired < 1) desired = 280;
                    g_object_set_data(G_OBJECT(scroll), "service-height", GINT_TO_POINTER(desired));
                }
                gtk_widget_set_size_request(scroll, -1, MIN(desired, dock_body));
            }
        }
        g_list_free(children);
    }
    g_free(edge); g_key_file_unref(data);
}

static guint duration(void) {
    gboolean animations = TRUE;
    GtkSettings *settings = gtk_settings_get_default();
    if (settings) g_object_get(settings, "gtk-enable-animations", &animations, NULL);
    if (!animations) return 0;
    gchar *path = g_build_filename(g_get_user_state_dir(), "desktop-power", "status.json", NULL);
    gchar *text = NULL;
    guint ms = 240;
    if (g_file_get_contents(path, &text, NULL, NULL)) {
        GRegex *regex = g_regex_new("\"animation_factor\"[[:space:]]*:[[:space:]]*([0-9.]+)", 0, 0, NULL);
        GMatchInfo *match = NULL;
        if (g_regex_match(regex, text, 0, &match)) {
            gchar *value = g_match_info_fetch(match, 1);
            gdouble factor = g_ascii_strtod(value, NULL);
            /* Keep the requested brief menu motion even in savings/Working;
               GTK's accessibility setting above remains authoritative. */
            if (factor < 1) ms = 140;
            g_free(value);
        }
        g_match_info_free(match);
        g_regex_unref(regex);
    }
    g_free(path); g_free(text);
    return ms;
}
static void stop_motion(void) {
    if (animated_window && motion_tick) gtk_widget_remove_tick_callback(animated_window, motion_tick);
    animated_window = NULL; motion_tick = 0;
}
static void motion_pose(gdouble progress) {
    motion_progress = progress;
    GtkWidget *stage = menu_window ? find(menu_window, "motion-stage") : NULL;
    if (!stage || !g_object_class_find_property(G_OBJECT_GET_CLASS(stage), "translate-y")) return;
    /* Translate the drawing inside a fixed, clipped surface; EGL never resizes
       per frame and the panel emerges from the edge occupied by Waybar. */
    gdouble offset = (1 - progress) * 100;
    gchar x[G_ASCII_DTOSTR_BUF_SIZE + 2], y[G_ASCII_DTOSTR_BUF_SIZE + 2];
    g_ascii_dtostr(x, sizeof(x)-1, dock_edge == 0 ? -offset : dock_edge == 1 ? offset : 0);
    g_ascii_dtostr(y, sizeof(y)-1, dock_edge == 2 ? -offset : dock_edge == 3 ? offset : 0);
    g_strlcat(x, "%", sizeof(x)); g_strlcat(y, "%", sizeof(y));
    g_object_set(stage, "translate-x", x, "translate-y", y, NULL);
}
static gboolean motion_frame(GtkWidget *window, GdkFrameClock *clock, gpointer data) {
    if (window != menu_window) { animated_window = NULL; motion_tick = 0; return G_SOURCE_REMOVE; }
    gint64 now = gdk_frame_clock_get_frame_time(clock);
    if (!motion_started) motion_started = now;
    gdouble t = MIN(1., (now - motion_started) / (motion_ms * 1000.));
    gdouble remaining = 1 - t;
    gdouble eased = motion_target > motion_from ? 1 - remaining * remaining * remaining : t * t;
    motion_pose(motion_from + (motion_target - motion_from) * eased);
    if (t < 1) return G_SOURCE_CONTINUE;
    motion_tick = 0; animated_window = NULL;
    if (!visible) resident_surface_park(window);
    return G_SOURCE_REMOVE;
}
static void slide_to(gdouble target, guint ms) {
    stop_motion();
    motion_from = motion_progress;
    motion_target = target; motion_ms = ms; motion_started = 0;
    if (!ms) {
        motion_pose(target);
        if (!visible) resident_surface_park(menu_window);
        return;
    }
    animated_window = menu_window;
    motion_tick = gtk_widget_add_tick_callback(menu_window, motion_frame, NULL, NULL);
}
static void animate_open(void) {
    if (!menu_window) return;
    guint ms = duration();
    /* One spatial entrance, with no per-control reveal delays. */
    GtkWidget *pages = find(menu_window, "pages");
    if (pages && GTK_IS_STACK(pages)) gtk_stack_set_transition_duration(GTK_STACK(pages), ms);
    GtkWidget *side = find(menu_window, "side-revealer");
    if (side && GTK_IS_REVEALER(side)) gtk_revealer_set_transition_duration(GTK_REVEALER(side), ms);
    GtkWidget *side_pages = find(menu_window, "side-pages");
    if (side_pages && GTK_IS_STACK(side_pages)) gtk_stack_set_transition_duration(GTK_STACK(side_pages), ms);
    /* Reveal layout immediately; the Transform only changes drawing coordinates. */
    GtkWidget *reveal = find(menu_window, "shell-revealer");
    if (GTK_IS_REVEALER(reveal)) {
        gtk_revealer_set_transition_type(GTK_REVEALER(reveal), GTK_REVEALER_TRANSITION_TYPE_NONE);
        gtk_revealer_set_transition_duration(GTK_REVEALER(reveal), 0);
        gtk_revealer_set_reveal_child(GTK_REVEALER(reveal), FALSE);
        gtk_revealer_set_reveal_child(GTK_REVEALER(reveal), TRUE);
    }
    gboolean interrupted = motion_tick != 0;
    stop_motion();
    if (!interrupted) motion_pose(ms ? 0 : 1);
    gtk_widget_set_opacity(menu_window, 1);
    slide_to(1, ms);
}
static void stack_index(GtkWidget *widget, guint index);
/* Warm common pages without publishing service activation or taking input. */
static gboolean prewarm_frame(GtkWidget *window, GdkFrameClock *clock, gpointer data) {
    if (window != menu_window) return G_SOURCE_REMOVE;
    if (visible) {
        stack_index(find(window, "pages"), current_page == 1 || browsing_apps ? 1 : 0);
        state("ready", "1");
        return G_SOURCE_REMOVE;
    }
    guint frames = GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window), "prewarm-frames")) + 1;
    g_object_set_data(G_OBJECT(window), "prewarm-frames", GUINT_TO_POINTER(frames));
    if (frames % 3) return G_SOURCE_CONTINUE;
    GtkWidget *pages = find(window, "pages");
    GtkWidget *side = find(window, "side-revealer");
    GtkWidget *side_pages = find(window, "side-pages");
    if (GTK_IS_STACK(pages)) gtk_stack_set_transition_duration(GTK_STACK(pages), 0);
    if (GTK_IS_STACK(side_pages)) gtk_stack_set_transition_duration(GTK_STACK(side_pages), 0);
    if (GTK_IS_REVEALER(side)) gtk_revealer_set_transition_duration(GTK_REVEALER(side), 0);
    if (frames == 3) stack_index(pages, 1);
    else if (frames == 6 || frames == 9) {
        stack_index(pages, 0);
        stack_index(side_pages, frames == 6 ? 2 : 3);
        if (GTK_IS_REVEALER(side)) gtk_revealer_set_reveal_child(GTK_REVEALER(side), TRUE);
    } else {
        stack_index(pages, 0);
        stack_index(side_pages, 0);
        if (GTK_IS_REVEALER(side)) gtk_revealer_set_reveal_child(GTK_REVEALER(side), FALSE);
    }
    if (frames < 12) return G_SOURCE_CONTINUE;
    resident_surface_park(window);
    state("ready", "1");
    return G_SOURCE_REMOVE;
}
static void hide_menu(gboolean stamp) {
    if (!menu_window) return;
    visible = FALSE;
    state("visible", "0");
    resident_surface_input(menu_window, FALSE);
    keyboard_mode(0);
    if (stamp) {
        gchar *now = g_strdup_printf("%.6f", g_get_monotonic_time() / 1000000.0);
        state("closed", now); g_free(now);
    }
    if (hide_timer) g_source_remove(hide_timer);
    GtkWidget *password = find(menu_window, "wifi-password");
    if (GTK_IS_ENTRY(password)) gtk_entry_set_text(GTK_ENTRY(password), "");
    slide_to(0, duration() * 2 / 3);
}
static void stack_index(GtkWidget *widget, guint index) {
    if (!GTK_IS_STACK(widget)) return;
    GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
    GtkWidget *child = g_list_nth_data(children, index);
    if (child) gtk_stack_set_visible_child(GTK_STACK(widget), child);
    g_list_free(children);
}
static guint count_class(GtkWidget *widget, const gchar *name) {
    if (!GTK_IS_WIDGET(widget)) return 0;
    guint count = has_class(widget, name) ? 1 : 0;
    if (GTK_IS_CONTAINER(widget)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
        for (GList *item = children; item; item = item->next) count += count_class(item->data, name);
        g_list_free(children);
    }
    return count;
}
static void inspect_bounds(GtkWidget *widget, GtkWidget *root, guint *overflow, guint *scrolls) {
    if (!gtk_widget_get_mapped(widget)) return;
    if (GTK_IS_SCROLLED_WINDOW(widget)) (*scrolls)++;
    gint x = 0, y = 0;
    if (gtk_widget_translate_coordinates(widget, root, 0, 0, &x, &y) &&
        (x < 0 || y < 0 || x + gtk_widget_get_allocated_width(widget) > gtk_widget_get_allocated_width(root) ||
         y + gtk_widget_get_allocated_height(widget) > gtk_widget_get_allocated_height(root))) (*overflow)++;
    if (GTK_IS_CONTAINER(widget)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
        for (GList *item = children; item; item = item->next) inspect_bounds(item->data, root, overflow, scrolls);
        g_list_free(children);
    }
}
static void inspect_menu(void) {
    if (!menu_window) { state("inspect", "visible=0\nerror=no GTK window\n"); return; }
    GtkWidget *entry = find(menu_window, "app-search");
    gint width, height;
    gtk_window_get_size(GTK_WINDOW(menu_window), &width, &height);
    GtkWidget *shell = find(menu_window, "shell-revealer");
    gboolean settled = shell && gtk_revealer_get_child_revealed(GTK_REVEALER(shell)) && !motion_tick && gtk_widget_get_opacity(menu_window) > .99;
    gchar *value = g_strdup_printf("opacity=%.2f\nmode_rows=%u\nsettled=%d\nvisible=%d\nwidth=%d\nheight=%d\npage=%u\nsearch_focus=%d\nresults=%u\nfilter_us=%" G_GINT64_FORMAT "\n",
        gtk_widget_get_opacity(menu_window), count_class(menu_window, "mode-row"), settled, visible, width, height, current_page, entry && gtk_widget_has_focus(entry), result_count, filter_us);
    GtkWidget *side_pages = find(menu_window, "side-pages");
    GtkWidget *service = GTK_IS_STACK(side_pages) ? gtk_stack_get_visible_child(GTK_STACK(side_pages)) : NULL;
    guint overflow = 0, scrolls = 0;
    if (current_page >= 5 && service) inspect_bounds(service, service, &overflow, &scrolls);
    GtkWidget *password = find(menu_window, "wifi-password");
    gchar *details = g_strdup_printf("%sservice_height=%d\nservice_overflow=%u\nservice_scrolls=%u\npassword_mapped=%d\npassword_visible=%d\npassword_parent_mapped=%d\nmapped=%d\nparked=%d\nopen_us=%" G_GINT64_FORMAT "\nmap_us=%" G_GINT64_FORMAT "\n",
        value, service ? gtk_widget_get_allocated_height(service) : 0, overflow, scrolls, password && gtk_widget_get_mapped(password), password && gtk_widget_get_visible(password), password && gtk_widget_get_mapped(gtk_widget_get_parent(password)),
        gtk_widget_get_mapped(menu_window), GPOINTER_TO_INT(g_object_get_data(G_OBJECT(menu_window), "raccon-parked")), open_us, map_us);
    state("inspect", details); g_free(details); g_free(value);
}
static void select_page(guint page) {
    if (!menu_window) return;
    current_page = page;
    GtkWidget *password = find(menu_window, "wifi-password");
    if (page != 5 && GTK_IS_ENTRY(password)) gtk_entry_set_text(GTK_ENTRY(password), "");
    gchar *page_text = g_strdup_printf("%u", page);
    state("page", page_text); g_free(page_text);
    GtkWidget *pages = find(menu_window, "pages");
    if (simple_pages && find(menu_window, "unified-controls")) control_details(page);
    else if (simple_pages || page <= 1) stack_index(pages, page);
    GtkWidget *side_pages = find(menu_window, "side-pages");
    stack_index(side_pages, page >= 2 ? page - 2 : 0);
    GtkWidget *side_panel = find(menu_window, "side-panel");
    if (side_panel) gtk_widget_set_size_request(side_panel, 292, -1);
    GtkWidget *side = find(menu_window, "side-revealer");
    if (side && GTK_IS_REVEALER(side)) {
        gtk_widget_set_valign(side, dock_edge == 2 ? GTK_ALIGN_START : GTK_ALIGN_END);
        gtk_revealer_set_reveal_child(GTK_REVEALER(side), page >= 2);
    }
    const gchar *classes[] = {"tab-home", "tab-apps", "tab-modes", "tab-session", "tab-audio", "tab-connections", "tab-bluetooth", "tab-calendar", "tab-shortcuts"};
    const gchar *panel_classes[] = {"tab-audio", "tab-connections", "tab-bluetooth", "tab-unused"};
    for (guint i = 0; i < (simple_pages ? 4u : 9u); i++) {
        GtkWidget *tab = find(menu_window, simple_pages ? panel_classes[i] : classes[i]);
        if (!tab) continue;
        GtkStyleContext *context = gtk_widget_get_style_context(tab);
        if (i == page) gtk_style_context_add_class(context, "current");
        else gtk_style_context_remove_class(context, "current");
    }
    if (page == 1 || page == 8) focus_search(menu_window);
}
static void show_menu(guint page) {
    if (!menu_window) return;
    gint64 started = g_get_monotonic_time();
    if (hide_timer) { g_source_remove(hide_timer); hide_timer = 0; }
    if (focus_timer) { g_source_remove(focus_timer); focus_timer = 0; }
    gboolean opening = !visible || !gtk_widget_get_mapped(menu_window);
    shown_at = g_get_monotonic_time();
    gtk_widget_set_opacity(menu_window, 1);
    visible = TRUE;
    super_down = super_used = FALSE;
    state("visible", "1");
    GtkWidget *entry = find(menu_window, "app-search");
    if (entry && GTK_IS_ENTRY(entry)) gtk_entry_set_text(GTK_ENTRY(entry), "");
    GtkWidget *confirmation = find(menu_window, "confirmation-reveal");
    if (confirmation && GTK_IS_REVEALER(confirmation))
        gtk_revealer_set_reveal_child(GTK_REVEALER(confirmation), FALSE);
    browsing_apps = page == 1;
    if (opening && !simple_pages) stack_index(find(menu_window, "pages"), browsing_apps ? 1 : 0);
    select_page(page);
    filter_current();
    GtkWidget *clock = find(menu_window, "clock");
    if (clock && GTK_IS_LABEL(clock)) {
        GDateTime *now = g_date_time_new_now_local();
        gchar *text = g_date_time_format(now, "%H:%M");
        gtk_label_set_text(GTK_LABEL(clock), text);
        g_free(text); g_date_time_unref(now);
    }
    dock_window();
    keyboard_mode(1);  /* Acquire focus on open, then permit clicking other apps. */
    gint64 mapping = g_get_monotonic_time();
    resident_surface_show(menu_window);
    map_us = g_get_monotonic_time() - mapping;
    if (opening) animate_open();
    focus_search(menu_window);
    if (gtk_window_is_active(GTK_WINDOW(menu_window))) keyboard_mode(2);
    gchar *value = g_strdup_printf("%u", page);
    dispatch("opened", value); g_free(value);
    open_us = g_get_monotonic_time() - started;
}
static gboolean control(GIOChannel *channel, GIOCondition condition, gpointer data) {
    gchar *line = NULL;
    while (g_io_channel_read_line(channel, &line, NULL, NULL, NULL) == G_IO_STATUS_NORMAL) {
        g_strstrip(line);
        if (g_str_equal(line, "toggle")) {
            if (visible) hide_menu(TRUE); else show_menu(0);
        } else if (g_str_equal(line, "hide")) hide_menu(FALSE);
        else if (g_str_equal(line, "hide-super")) hide_menu(TRUE);
        else if (g_str_has_prefix(line, "show ") && strlen(line) == 6 && line[5] >= '0' && line[5] <= '8')
            show_menu(line[5] - '0');
        else if (g_str_equal(line, "inspect")) inspect_menu();
        else if (g_str_equal(line, "dock")) dock_window();
        else if (!simple_pages && g_str_has_prefix(line, "service ") && strlen(line) == 9 && line[8] >= '4' && line[8] <= '7') {
            guint page = line[8] - '0';
            if (!visible) show_menu(page);
            else select_page(current_page == page ? 0 : page);
        }
        else if (simple_pages && g_str_has_prefix(line, "detail ") && strlen(line) == 8 && line[7] >= '0' && line[7] <= '2') {
            guint page = line[7] - '0';
            select_page(current_page == page ? 0 : page);
        }
        else if (simple_pages && g_str_has_prefix(line, "panel ") && strlen(line) == 7 && line[6] >= '0' && line[6] <= '2') {
            guint page = line[6] - '0';
            if (visible && current_page == page) hide_menu(FALSE);
            else show_menu(page);
        }
        else if (g_str_has_prefix(line, "tab ") && strlen(line) == 5 && line[4] >= '0' && line[4] <= '8') {
            guint page = line[4] - '0';
            if (current_page == page) page = 0;
            browsing_apps = page == 1;
            select_page(page);
            if (page == 0) {
                GtkWidget *entry = find(menu_window, "app-search");
                if (GTK_IS_ENTRY(entry)) gtk_entry_set_text(GTK_ENTRY(entry), "");
            }
        }
        g_free(line); line = NULL;
    }
    g_free(line);
    return TRUE;
}
/* Literal, accent-insensitive filtering. No shell, process or Eww update per key. */
static gchar *search_normalize(const gchar *text) {
    gchar *folded = g_utf8_casefold(text, -1);
    gchar *decomposed = g_utf8_normalize(folded, -1, G_NORMALIZE_NFKD);
    GString *result = g_string_new(NULL);
    for (const gchar *c = decomposed; c && *c; c = g_utf8_next_char(c)) {
        gunichar value = g_utf8_get_char(c);
        if (!g_unichar_combining_class(value)) g_string_append_unichar(result, value);
    }
    g_free(folded); g_free(decomposed);
    return g_string_free(result, FALSE);
}
static gboolean search_matches(const gchar *key, gchar **words) {
    for (guint i = 0; words[i]; i++)
        if (*words[i] && !strstr(key, words[i])) return FALSE;
    return TRUE;
}
static guint filter_rows(GtkWidget *widget, const gchar *row_class, gchar **words, gboolean *first) {
    if (GTK_IS_BUTTON(widget) && has_class(widget, row_class)) {
        GtkWidget *label = find(widget, "search-key");
        const gchar *key = GTK_IS_LABEL(label) ? gtk_label_get_text(GTK_LABEL(label)) : "";
        gboolean match = search_matches(key, words);
        gtk_widget_set_visible(widget, match);
        GtkStyleContext *context = gtk_widget_get_style_context(widget);
        if (match && !*first) {
            gtk_style_context_add_class(context, "first-match");
            *first = TRUE;
        } else gtk_style_context_remove_class(context, "first-match");
        return match ? 1 : 0;
    }
    if (!GTK_IS_CONTAINER(widget)) return 0;
    guint count = 0;
    GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
    for (GList *item = children; item; item = item->next)
        count += filter_rows(item->data, row_class, words, first);
    g_list_free(children);
    if (has_class(widget, "key-section") || has_class(widget, "app-row"))
        gtk_widget_set_visible(widget, count > 0);
    return count;
}
static void filter_current(void) {
    if (!menu_window) return;
    gint64 started = g_get_monotonic_time();
    GtkWidget *entry = find(menu_window, "app-search");
    GtkWidget *list = find(menu_window, "apps-list");
    if (!GTK_IS_ENTRY(entry) || !list) return;
    gchar *query = search_normalize(gtk_entry_get_text(GTK_ENTRY(entry)));
    gboolean searching = *g_strstrip(query) != '\0';
    const gchar *controls[] = {"utilities", "navigation"};
    for (guint i = 0; i < G_N_ELEMENTS(controls); i++) {
        GtkWidget *group = find(menu_window, controls[i]);
        if (group) gtk_widget_set_visible(group, !searching);
    }
    gchar **words = g_strsplit_set(query, " \t\r\n", -1);
    gboolean first = FALSE;
    guint count = filter_rows(list, "app-launch", words, &first);
    GtkWidget *empty = find(menu_window, "no-results");
    if (empty) gtk_widget_set_visible(empty, count == 0);
    g_strfreev(words); g_free(query);
    result_count = count;
    filter_us = g_get_monotonic_time() - started;
}
static void keys_changed(GtkEditable *entry, gpointer data) {
    GtkWidget *list = find(menu_window, "keys-list");
    if (!list) return;
    gchar *query = search_normalize(gtk_entry_get_text(GTK_ENTRY(entry)));
    gchar **words = g_strsplit_set(query, " \t\r\n", -1);
    gboolean first = FALSE;
    guint count = filter_rows(list, "key-row", words, &first);
    GtkWidget *empty = find(menu_window, "keys-empty");
    if (empty) gtk_widget_set_visible(empty, count == 0);
    g_strfreev(words); g_free(query);
}
static gboolean filter_idle(gpointer data) {
    filter_current();
    return G_SOURCE_REMOVE;
}
static void entry_changed(GtkEditable *entry, gpointer data) {
    const gchar *text = gtk_entry_get_text(GTK_ENTRY(entry));
    if (*text) select_page(1);
    else if (!browsing_apps) select_page(0);
    filter_current();
    GtkWidget *scroll = find(menu_window, "apps-scroll");
    if (GTK_IS_SCROLLED_WINDOW(scroll))
        gtk_adjustment_set_value(gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(scroll)), 0);
}
static void focus_search(GtkWidget *window) {
    GtkWidget *entry = find(window, current_page == 8 ? "keys-search" : "app-search");
    if (entry) gtk_widget_grab_focus(entry);
}
static GtkWidget *first_result(GtkWidget *widget) {
    if (GTK_IS_BUTTON(widget) && has_class(widget, "app-launch") && gtk_widget_get_visible(widget)) return widget;
    if (!GTK_IS_CONTAINER(widget)) return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
    GtkWidget *found = NULL;
    for (GList *item = children; item && !found; item = item->next) found = first_result(item->data);
    g_list_free(children);
    return found;
}
static void entry_accept(GtkEntry *entry, GtkWindow *window) {
    select_page(1);
    filter_current();
    GtkWidget *list = find(menu_window, "apps-list");
    GtkWidget *first = list ? first_result(list) : NULL;
    if (first) gtk_button_clicked(GTK_BUTTON(first));
}
static gboolean keyboard_page_focus(gpointer data) {
    guint requested=GPOINTER_TO_UINT(data);
    if(menu_window && current_page==requested && requested>=2) {
        GtkWidget *side=find(menu_window,"side-panel");if(side)nav_nth(side,NULL,0,FALSE);
    }
    return G_SOURCE_REMOVE;
}
static gboolean key_press(GtkWidget *window, GdkEventKey *event, gpointer data) {
    guint key = event->keyval;
    if ((event->state & GDK_CONTROL_MASK) && (key == GDK_KEY_w || key == GDK_KEY_W)) { hide_menu(FALSE); return TRUE; }
    if ((event->state & GDK_MOD1_MASK) && key >= GDK_KEY_1 && key <= GDK_KEY_9 && !simple_pages) {
        select_page(0); nav_nth(window, "daily-app", key - GDK_KEY_1, TRUE); return TRUE;
    }
    if (key == GDK_KEY_Down && !(event->state & (GDK_CONTROL_MASK|GDK_MOD1_MASK|GDK_SUPER_MASK))) {
        GtkWidget *focus = gtk_window_get_focus(GTK_WINDOW(window));
        if (focus && focus == find(window, current_page == 8 ? "keys-search" : "app-search")) {
            if (nav_nth(window, current_page == 8 ? "key-row" : current_page == 1 ? "app-launch" : "daily-app", 0, FALSE))
                return TRUE;
        }
    }
    if (nav_key(window, event)) return TRUE;
    if (key == GDK_KEY_Escape) {
        GtkWidget *entry = find(window, current_page == 8 ? "keys-search" : "app-search");
        if (GTK_IS_ENTRY(entry) && *gtk_entry_get_text(GTK_ENTRY(entry))) {
            gtk_entry_set_text(GTK_ENTRY(entry), "");
        } else if (nav_nth(window, "service-back", 0, TRUE)) {
            return TRUE;
        } else {
            GtkWidget *outputs = find(window, "output-choices");
            GtkWidget *inputs = find(window, "input-choices");
            if (GTK_IS_REVEALER(outputs) && gtk_revealer_get_reveal_child(GTK_REVEALER(outputs)))
                nav_nth(window, "device-toggle", 0, TRUE);
            else if (GTK_IS_REVEALER(inputs) && gtk_revealer_get_reveal_child(GTK_REVEALER(inputs)))
                nav_nth(window, "mic-choice", 0, TRUE);
            else if (current_page > 0) {
                browsing_apps = FALSE;
                select_page(0);
                nav_nth(window, simple_pages ? NULL : "daily-app", 0, FALSE);
            } else hide_menu(FALSE);
        }
        return TRUE;
    }
    if (key == GDK_KEY_Super_L || key == GDK_KEY_Super_R) {
        super_down = TRUE;
        super_used = !!(event->state & (GDK_CONTROL_MASK | GDK_MOD1_MASK | GDK_SHIFT_MASK));
        return FALSE;
    }
    if (super_down) super_used = TRUE;
    if (event->state & GDK_CONTROL_MASK) {
        if (key >= GDK_KEY_1 && key <= (simple_pages ? GDK_KEY_3 : GDK_KEY_9)) {
            browsing_apps = key == GDK_KEY_2;
            select_page(key - GDK_KEY_1);
            if (key == GDK_KEY_2) focus_search(window);
            else if (key == GDK_KEY_1) nav_nth(window,"daily-app",0,FALSE);
            else { g_timeout_add(250,keyboard_page_focus,GUINT_TO_POINTER(current_page)); }
            return TRUE;
        }
        if (key == GDK_KEY_f || key == GDK_KEY_l) {
            browsing_apps = TRUE; select_page(1); focus_search(window); return TRUE;
        }
    }
    gboolean keys_page = current_page == 8;
    GtkWidget *entry = find(window, keys_page ? "keys-search" : "app-search");
    gunichar character = gdk_keyval_to_unicode(key);
    if(GTK_IS_CALENDAR(gtk_window_get_focus(GTK_WINDOW(window))))return FALSE;
    if (GTK_IS_ENTRY(entry) && gtk_window_get_focus(GTK_WINDOW(window)) != entry &&
        !GTK_IS_EDITABLE(gtk_window_get_focus(GTK_WINDOW(window))) &&
        !(event->state & (GDK_CONTROL_MASK | GDK_MOD1_MASK | GDK_SUPER_MASK)) &&
        g_unichar_isprint(character)) {
        if (keys_page) gtk_widget_grab_focus(entry);
        else { select_page(1); focus_search(window); }
        gchar text[7] = {0};
        g_unichar_to_utf8(character, text);
        gint position = gtk_editable_get_position(GTK_EDITABLE(entry));
        gtk_editable_insert_text(GTK_EDITABLE(entry), text, -1, &position);
        gtk_editable_set_position(GTK_EDITABLE(entry), position);
        return TRUE;
    }
    return FALSE;
}
static gboolean key_release(GtkWidget *window, GdkEventKey *event, gpointer data) {
    if (nav_release(window,event)) return TRUE;
    if (event->keyval == GDK_KEY_Super_L || event->keyval == GDK_KEY_Super_R) {
        gboolean close = super_down && !super_used;
        super_down = FALSE;
        if (close) { hide_menu(TRUE); return TRUE; }
    }
    return FALSE;
}
static gboolean pointer_press(GtkWidget *widget, GdkEventButton *event, gpointer data) {
    if (super_down) super_used = TRUE;
    return FALSE;
}
static gboolean focus_in(GtkWidget *window, GdkEventFocus *event, gpointer data) {
    if (window != menu_window) return FALSE;
    if (focus_timer) { g_source_remove(focus_timer); focus_timer = 0; }
    keyboard_mode(2); /* ON_DEMAND retains focus and allows outside clicks. */
    return FALSE;
}
static gboolean lost_focus(gpointer data) {
    focus_timer = 0;
    if (visible && menu_window && !gtk_window_is_active(GTK_WINDOW(menu_window))) {
        if (g_get_monotonic_time() - shown_at < 200000) {
            focus_timer = g_timeout_add(120, lost_focus, NULL);
        } else hide_menu(FALSE);
    }
    return G_SOURCE_REMOVE;
}
static gboolean focus_out(GtkWidget *window, GdkEventFocus *event, gpointer data) {
    g_object_set_data(G_OBJECT(window),"nav-held",NULL);
    /* A theme reload destroys the previous window while mapping its replacement. */
    if (window == menu_window && visible) {
        if (focus_timer) g_source_remove(focus_timer);
        focus_timer = g_timeout_add(90, lost_focus, NULL);
    }
    return FALSE;
}
static void window_destroyed(GtkWidget *window, gpointer data) {
    /* A previous window's destruction must never clear its replacement. */
    if (animated_window == window) { animated_window = NULL; motion_tick = 0; }
    if (menu_window == window) {
        menu_window = NULL;
        state("ready", "0");
        gchar *path = g_build_filename(runtime_dir, "mapped", NULL);
        unlink(path); g_free(path);
    }
}
/* User changes are coalesced; provider updates cannot fight an ongoing drag. */
typedef struct { guint timer; gdouble value; gint64 changed; gboolean restoring; gint kind; } Volume;
static Volume volumes[2] = {{.kind = 0}, {.kind = 1}};
static gboolean volume_apply(gpointer data) {
    Volume *volume = data;
    volume->timer = 0;
    gchar *percent = g_strdup_printf("%.0f%%", volume->value);
    gchar *argv[] = {"pactl", volume->kind ? "set-source-volume" : "set-sink-volume",
                    volume->kind ? "@DEFAULT_SOURCE@" : "@DEFAULT_SINK@", percent, NULL};
    g_spawn_async(NULL, argv, NULL, G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL,
                  NULL, NULL, NULL, NULL);
    g_free(percent);
    return G_SOURCE_REMOVE;
}
static gboolean volume_change(GtkRange *range, GtkScrollType scroll, gdouble value, gpointer data) {
    Volume *volume = data;
    volume->value = CLAMP(value, 0, 100);
    volume->changed = g_get_monotonic_time();
    if (volume->timer) g_source_remove(volume->timer);
    volume->timer = g_timeout_add(75, volume_apply, volume);
    return FALSE;
}
static void volume_changed(GtkRange *range, gpointer data) {
    Volume *volume = data;
    if (!volume->restoring && g_get_monotonic_time() - volume->changed < 350000 &&
        ABS(gtk_range_get_value(range) - volume->value) > .5) {
        volume->restoring = TRUE;
        gtk_range_set_value(range, volume->value);
        volume->restoring = FALSE;
    }
}
static void password_done(GObject *object, GAsyncResult *result, gpointer data) {
    GError *error = NULL;
    g_subprocess_communicate_utf8_finish(G_SUBPROCESS(object), result, NULL, NULL, &error);
    g_clear_error(&error);
    gchar *secret = data;
    memset(secret, 0, strlen(secret)); g_free(secret);
    g_object_unref(object);
}
static void password_connect(GtkWidget *widget, gpointer data) {
    if (!menu_window) return;
    GtkWidget *entry = find(menu_window, "wifi-password");
    if (!GTK_IS_ENTRY(entry)) return;
    gchar *secret = g_strdup(gtk_entry_get_text(GTK_ENTRY(entry)));
    gtk_entry_set_text(GTK_ENTRY(entry), "");
    GSubprocess *child = g_subprocess_new(G_SUBPROCESS_FLAGS_STDIN_PIPE | G_SUBPROCESS_FLAGS_STDOUT_SILENCE |
        G_SUBPROCESS_FLAGS_STDERR_SILENCE, NULL, "python3", backend,
        simple_pages ? "wifi-connect" : "control-action", simple_pages ? NULL : "wifi-connect", NULL);
    if (child) g_subprocess_communicate_utf8_async(child, secret, NULL, password_done, secret);
    else { memset(secret, 0, strlen(secret)); g_free(secret); }
}
static void clear_password(GtkButton *button, gpointer data) {
    GtkWidget *entry = menu_window ? find(menu_window, "wifi-password") : NULL;
    if (GTK_IS_ENTRY(entry)) gtk_entry_set_text(GTK_ENTRY(entry), "");
}

typedef struct { GtkWidget *entry; gchar *text; } CalendarAdd;
static void calendar_added(GObject *object,GAsyncResult *result,gpointer data) {
    CalendarAdd *pending=data;
    GError *error=NULL;
    g_subprocess_communicate_utf8_finish(G_SUBPROCESS(object),result,NULL,NULL,&error);
    GtkWidget *entry=pending->entry;
    if(!error&&g_subprocess_get_successful(G_SUBPROCESS(object))&&
       g_strcmp0(gtk_entry_get_text(GTK_ENTRY(entry)),pending->text)==0)gtk_entry_set_text(GTK_ENTRY(entry),"");
    g_object_set_data(G_OBJECT(entry),"calendar-pending",NULL);
    g_clear_error(&error);g_free(pending->text);g_object_unref(entry);g_free(pending);g_object_unref(object);
}
static void calendar_add(GtkWidget *widget,gpointer unused) {
    GtkWidget *entry=menu_window?find(menu_window,"calendar-entry"):NULL;
    if(!GTK_IS_ENTRY(entry)||!*gtk_entry_get_text(GTK_ENTRY(entry)))return;
    if(g_object_get_data(G_OBJECT(entry),"calendar-pending"))return;
    gchar *helper=g_build_filename(g_get_home_dir(),".local","lib","raccon_menu","calendar_data.py",NULL);
    GtkWidget *date=menu_window?find(menu_window,"calendar-date"):NULL;
    const gchar *iso=GTK_IS_LABEL(date)?gtk_label_get_text(GTK_LABEL(date)):NULL;
    if (!iso || !*iso) { g_free(helper); return; }
    GSubprocess *child=g_subprocess_new(G_SUBPROCESS_FLAGS_STDIN_PIPE|G_SUBPROCESS_FLAGS_STDOUT_SILENCE|
        G_SUBPROCESS_FLAGS_STDERR_SILENCE,NULL,"python3",helper,"add",iso,NULL);
    if(child) {
        CalendarAdd *pending=g_new0(CalendarAdd,1);
        pending->entry=g_object_ref(entry);pending->text=g_strdup(gtk_entry_get_text(GTK_ENTRY(entry)));
        g_object_set_data(G_OBJECT(entry),"calendar-pending",GINT_TO_POINTER(1));
        g_subprocess_communicate_utf8_async(child,pending->text,NULL,calendar_added,pending);
    }
    g_free(helper);
}

static gboolean mapped(GSignalInvocationHint *hint, guint n, const GValue *values, gpointer data) {
    GtkWidget *widget = g_value_get_object(&values[0]);
    soft_icons_apply(widget);
    if (GTK_IS_BUTTON(widget) && !g_object_get_data(G_OBJECT(widget), "raccon-pointer-input")) {
        g_signal_connect(widget, "button-press-event", G_CALLBACK(pointer_press), NULL);
        g_object_set_data(G_OBJECT(widget), "raccon-pointer-input", GINT_TO_POINTER(1));
    }
    if (!g_object_get_data(G_OBJECT(widget), "panel-input")) {
        if (GTK_IS_STACK(widget) && (has_class(widget, "wifi-views") || has_class(widget, "bluetooth-views")))
            gtk_stack_set_transition_duration(GTK_STACK(widget), 140);
        gboolean output = has_class(widget, "output-volume");
        gboolean input = has_class(widget, "input-volume");
        if (GTK_IS_RANGE(widget) && (output || input)) {
            Volume *volume = &volumes[input ? 1 : 0];
            g_signal_connect(widget, "change-value", G_CALLBACK(volume_change), volume);
            g_signal_connect(widget, "value-changed", G_CALLBACK(volume_changed), volume);
        }
        if (GTK_IS_ENTRY(widget) && has_class(widget, "wifi-password")) {
            gtk_entry_set_visibility(GTK_ENTRY(widget), FALSE);
            gtk_entry_set_placeholder_text(GTK_ENTRY(widget), "Password (optional)");
            gtk_entry_set_max_length(GTK_ENTRY(widget), 256);
            gtk_widget_grab_focus(widget);
            g_signal_connect(widget, "activate", G_CALLBACK(password_connect), NULL);
        }
        if (GTK_IS_BUTTON(widget) && has_class(widget, "wifi-connect"))
            g_signal_connect(widget, "clicked", G_CALLBACK(password_connect), NULL);
        if (GTK_IS_BUTTON(widget) && (has_class(widget, "network-row") || has_class(widget, "cancel-wifi")))
            g_signal_connect(widget, "clicked", G_CALLBACK(clear_password), NULL);
        if (GTK_IS_ENTRY(widget) && has_class(widget,"calendar-entry")) {
            gtk_entry_set_placeholder_text(GTK_ENTRY(widget),"Add event…");
            gtk_entry_set_max_length(GTK_ENTRY(widget),500);
            gtk_entry_set_width_chars(GTK_ENTRY(widget),12);
            g_signal_connect(widget,"activate",G_CALLBACK(calendar_add),NULL);
        }
        if (GTK_IS_BUTTON(widget) && has_class(widget,"calendar-add"))
            g_signal_connect(widget,"clicked",G_CALLBACK(calendar_add),NULL);
        g_object_set_data(G_OBJECT(widget), "panel-input", GINT_TO_POINTER(1));
    }
    if (GTK_IS_IMAGE(widget) && (has_class(widget, "app-icon") || has_class(widget, "daily-icon")) &&
        !g_object_get_data(G_OBJECT(widget), "file-icon")) {
        GtkWidget *row = gtk_widget_get_parent(widget);
        while (row && !has_class(row, "app-launch") && !has_class(row, "daily-app") && !has_class(row, "recent-launch"))
            row = gtk_widget_get_parent(row);
        GtkWidget *key = row ? find(row, "file-key") : NULL;
        if (GTK_IS_LABEL(key) && *gtk_label_get_text(GTK_LABEL(key))) {
            GError *error = NULL;
            gint pixels = has_class(widget, "daily-icon") ? 32 : 24;
            GdkPixbuf *icon = gdk_pixbuf_new_from_file_at_scale(gtk_label_get_text(GTK_LABEL(key)), pixels, pixels, TRUE, &error);
            if (icon) { gtk_image_set_from_pixbuf(GTK_IMAGE(widget), icon); g_object_unref(icon); }
            g_clear_error(&error);
        }
        g_object_set_data(G_OBJECT(widget), "file-icon", GINT_TO_POINTER(1));
    }
    /* Catalogue refreshes can finish after the user has started typing. */
    if (GTK_IS_BUTTON(widget) && has_class(widget, "app-launch")) {
        static guint pending_filter;
        if (pending_filter && g_main_context_find_source_by_id(NULL, pending_filter))
            g_source_remove(pending_filter);
        pending_filter = g_idle_add(filter_idle, NULL);
    }
    if (GTK_IS_WINDOW(widget) && gtk_window_get_window_type(GTK_WINDOW(widget)) == GTK_WINDOW_TOPLEVEL &&
            !g_object_get_data(G_OBJECT(widget), "raccon-keys")) {
        menu_window = widget;
        g_signal_connect(widget, "destroy", G_CALLBACK(window_destroyed), NULL);
        g_object_set_data(G_OBJECT(widget), "raccon-keys", GINT_TO_POINTER(1));
        super_down = super_used = FALSE;
        g_signal_connect(widget, "key-press-event", G_CALLBACK(key_press), NULL);
        g_signal_connect(widget, "key-release-event", G_CALLBACK(key_release), NULL);
        g_signal_connect(widget, "focus-in-event", G_CALLBACK(focus_in), NULL);
        g_signal_connect(widget, "focus-out-event", G_CALLBACK(focus_out), NULL);
        dock_window();
        popup_geometry_bind(widget, simple_pages ? 380 : 760, 560);
        state("mapped", "1");
        GtkWidget *hidden = find(widget, "initial-hidden");
        gboolean prewarm = !seen_window && GTK_IS_LABEL(hidden) && g_str_equal(gtk_label_get_text(GTK_LABEL(hidden)), "true");
        if ((seen_window && !visible) || prewarm) {
            visible = FALSE; state("visible", "0");
            gtk_widget_set_opacity(widget, 0);
            resident_surface_input(widget, FALSE);
            state("ready", "0");
            keyboard_mode(0);
            gtk_widget_add_tick_callback(widget, prewarm_frame, NULL, NULL);
        } else {
            shown_at = g_get_monotonic_time();
            visible = TRUE; state("visible", "1");
            GtkWidget *initial = find(widget, "initial-page");
            guint page = GTK_IS_LABEL(initial) ? (guint)g_ascii_strtoull(gtk_label_get_text(GTK_LABEL(initial)), NULL, 10) : 0;
            browsing_apps = page == 1;
            select_page(page); filter_current(); animate_open(); focus_search(widget);
            state("ready", "1");
        }
        seen_window = TRUE;
    }
    if (GTK_IS_ENTRY(widget) && has_class(widget, "keys-search") && !g_object_get_data(G_OBJECT(widget), "raccon-search")) {
        g_object_set_data(G_OBJECT(widget), "raccon-search", GINT_TO_POINTER(1));
        g_signal_connect(widget, "changed", G_CALLBACK(keys_changed), NULL);
        gtk_entry_set_placeholder_text(GTK_ENTRY(widget), "Search shortcuts…");
    }
    if (GTK_IS_ENTRY(widget) && has_class(widget, "app-search")) {
        if (!g_object_get_data(G_OBJECT(widget), "raccon-search")) {
            g_object_set_data(G_OBJECT(widget), "raccon-search", GINT_TO_POINTER(1));
            g_signal_connect(widget, "changed", G_CALLBACK(entry_changed), NULL);
            g_signal_connect(widget, "activate", G_CALLBACK(entry_accept), gtk_widget_get_toplevel(widget));
            gtk_entry_set_placeholder_text(GTK_ENTRY(widget), "Search apps…");
        }
        gtk_widget_grab_focus(widget);
    }
    return TRUE;
}
G_MODULE_EXPORT void gtk_module_init(gint *argc, gchar ***argv) {
    if (!g_getenv("RACCON_MENU_CONFIG")) return;
    /* GTK_MODULES is inherited by providers/helpers. Only Eww owns this FIFO. */
    gchar *executable = g_file_read_link("/proc/self/exe", NULL);
    gchar *program = executable ? g_path_get_basename(executable) : NULL;
    gboolean owner = program && g_str_equal(program, "eww");
    g_free(executable); g_free(program);
    if (!owner) return;
    backend = g_getenv("RACCON_MENU_BACKEND") ? g_strdup(g_getenv("RACCON_MENU_BACKEND")) :
        g_build_filename(g_get_home_dir(), ".local", "lib", "raccon_menu", "backend.py", NULL);
    simple_pages = g_strcmp0(g_getenv("RACCON_MENU_SIMPLE_PAGES"), "1") == 0;
    const gchar *base = g_getenv("XDG_RUNTIME_DIR");
    gchar *fallback = g_build_filename(g_get_home_dir(), ".cache", NULL);
    runtime_dir = g_build_filename(base ? base : fallback, g_getenv("RACCON_MENU_RUNTIME") ? g_getenv("RACCON_MENU_RUNTIME") : "raccon-menu", NULL);
    g_free(fallback);
    g_mkdir_with_parents(runtime_dir, 0700);
    gchar *pipe_path = g_build_filename(runtime_dir, "control", NULL);
    struct stat info;
    if (lstat(pipe_path, &info) < 0) mkfifo(pipe_path, 0600);
    if (lstat(pipe_path, &info) == 0 && S_ISFIFO(info.st_mode) && info.st_uid == getuid()) {
        int fd = open(pipe_path, O_RDWR | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
        if (fd >= 0) {
            GIOChannel *channel = g_io_channel_unix_new(fd);
            g_io_channel_set_encoding(channel, NULL, NULL);
            g_io_channel_set_close_on_unref(channel, TRUE);
            g_io_add_watch(channel, G_IO_IN, control, NULL);
            g_io_channel_unref(channel);
        }
    }
    g_free(pipe_path);
    state("revision", g_getenv("RACCON_MENU_REVISION") ? g_getenv("RACCON_MENU_REVISION") : "");
    gchar *mapped_path = g_build_filename(runtime_dir, "mapped", NULL);
    unlink(mapped_path); g_free(mapped_path);
    state("ready", "0");
    g_type_class_ref(GTK_TYPE_WIDGET);
    g_signal_add_emission_hook(g_signal_lookup("map", GTK_TYPE_WIDGET), 0, mapped, NULL, NULL);
}
