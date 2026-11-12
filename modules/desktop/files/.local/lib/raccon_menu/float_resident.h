#ifndef RACCON_FLOAT_RESIDENT_H
#define RACCON_FLOAT_RESIDENT_H
#include "resident_surface.h"

static void resident_ready(gboolean ready) {
    const gchar *name = g_strcmp0(g_getenv("RACCON_KEYS_COMMAND"), "raccon-music") == 0 ? "raccon-music.ready" : "raccon-float-session.ready";
    gchar *path = g_build_filename(g_get_user_runtime_dir(), name, NULL);
    g_file_set_contents(path, ready ? "1" : "0", -1, NULL);
    g_free(path);
}

static void resident_changed(GObject *metadata, GParamSpec *param, gpointer data) {
    GtkWidget *window = data;
    g_object_set_data(G_OBJECT(window), "float-warming", NULL);
    if (g_str_equal(gtk_label_get_text(GTK_LABEL(metadata)), "true")) {
        resident_surface_show(window);
        gtk_widget_set_opacity(window, 1);
    } else {
        resident_surface_park(window);
    }
    resident_ready(TRUE);
}

static gboolean resident_warm_frame(GtkWidget *window, GdkFrameClock *clock, gpointer data) {
    if (!g_object_get_data(G_OBJECT(window), "float-warming")) return G_SOURCE_REMOVE;
    guint frames = GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window), "float-frames")) + 1;
    g_object_set_data(G_OBJECT(window), "float-frames", GUINT_TO_POINTER(frames));
    if (frames < 3) return G_SOURCE_CONTINUE;
    g_object_set_data(G_OBJECT(window), "float-warming", NULL);
    resident_surface_park(window);
    resident_ready(TRUE);
    return G_SOURCE_REMOVE;
}

static gboolean resident_bind(GtkWidget *window) {
    GtkWidget *metadata = nav_find(window, "resident-visible");
    if (!GTK_IS_LABEL(metadata) || g_object_get_data(G_OBJECT(window), "resident-bound")) return FALSE;
    g_object_set_data(G_OBJECT(window), "resident-bound", GINT_TO_POINTER(1));
    g_signal_connect_object(metadata, "notify::label", G_CALLBACK(resident_changed), G_OBJECT(window), 0);
    if (g_str_equal(gtk_label_get_text(GTK_LABEL(metadata)), "true")) return FALSE;
    /* Render once without accepting input, then unmap the compositor surface. */
    gtk_widget_set_opacity(window, 0);
    resident_surface_input(window, FALSE);
    if (gtk_layer_set_keyboard_mode && gtk_layer_is_layer_window && gtk_layer_is_layer_window(GTK_WINDOW(window)))
        gtk_layer_set_keyboard_mode(GTK_WINDOW(window), 0);
    resident_ready(FALSE);
    g_object_set_data(G_OBJECT(window), "float-warming", GINT_TO_POINTER(1));
    gtk_widget_add_tick_callback(window, resident_warm_frame, NULL, NULL);
    return TRUE;
}
#endif
