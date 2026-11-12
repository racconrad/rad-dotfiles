#ifndef RACCON_POPUP_GEOMETRY_H
#define RACCON_POPUP_GEOMETRY_H

#include <gtk/gtk.h>

static gboolean popup_geometry_size(GtkWidget *window, GdkEvent *event, gpointer unused) {
    GtkWidget *viewport = g_object_get_data(G_OBJECT(window), "popup-viewport");
    if (!viewport) return FALSE;
    gint width = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(window), "popup-width"));
    gint height = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(window), "popup-height"));
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkWindow *surface = gtk_widget_get_window(window);
    GdkMonitor *monitor = surface ? gdk_display_get_monitor_at_window(display, surface) : gdk_display_get_primary_monitor(display);
    if (!monitor && gdk_display_get_n_monitors(display)) monitor = gdk_display_get_monitor(display, 0);
    if (monitor) {
        GdkRectangle bounds;
        gdk_monitor_get_workarea(monitor, &bounds);
        width = MIN(width, MAX(1, bounds.width - 32));
        height = MIN(height, MAX(1, bounds.height - 112));
    }
    gint old_width, old_height;
    gtk_widget_get_size_request(viewport, &old_width, &old_height);
    if (old_width != width || old_height != height) {
        gtk_widget_set_size_request(viewport, width, height);
        GtkWidget *content = gtk_bin_get_child(GTK_BIN(viewport));
        if (GTK_IS_VIEWPORT(content)) content = gtk_bin_get_child(GTK_BIN(content));
        if (content) gtk_widget_set_size_request(content, width, height);
        gtk_window_resize(GTK_WINDOW(window), width, height);
    }
    return FALSE;
}

static void popup_geometry_bind(GtkWidget *window, gint width, gint height) {
    GtkWidget *existing = g_object_get_data(G_OBJECT(window), "popup-viewport");
    if (existing && gtk_bin_get_child(GTK_BIN(window)) != existing)
        g_object_set_data(G_OBJECT(window), "popup-viewport", NULL);
    if (!g_object_get_data(G_OBJECT(window), "popup-viewport")) {
        GtkWidget *content = gtk_bin_get_child(GTK_BIN(window));
        if (!content) return;
        GtkWidget *viewport = gtk_scrolled_window_new(NULL, NULL);
        gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(viewport), GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC);
        gtk_scrolled_window_set_propagate_natural_width(GTK_SCROLLED_WINDOW(viewport), FALSE);
        gtk_scrolled_window_set_propagate_natural_height(GTK_SCROLLED_WINDOW(viewport), FALSE);
        gtk_style_context_add_class(gtk_widget_get_style_context(viewport), "popup-viewport");
        g_object_set_data_full(G_OBJECT(window), "popup-viewport", g_object_ref(viewport), g_object_unref);
        g_object_ref(content);
        gtk_container_remove(GTK_CONTAINER(window), content);
        gtk_container_add(GTK_CONTAINER(viewport), content);
        gtk_container_add(GTK_CONTAINER(window), viewport);
        g_object_unref(content);
        gtk_widget_show(gtk_bin_get_child(GTK_BIN(viewport)));
        gtk_widget_show(viewport);
        gtk_window_set_resizable(GTK_WINDOW(window), FALSE);
        g_signal_connect(window, "configure-event", G_CALLBACK(popup_geometry_size), NULL);
    }
    g_object_set_data(G_OBJECT(window), "popup-width", GINT_TO_POINTER(width));
    g_object_set_data(G_OBJECT(window), "popup-height", GINT_TO_POINTER(height));
    popup_geometry_size(window, NULL, NULL);
}

#endif
