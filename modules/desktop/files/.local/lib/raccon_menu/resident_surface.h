/* Keep the GTK tree resident, but release the compositor surface when idle. */
#ifndef RACCON_RESIDENT_SURFACE_H
#define RACCON_RESIDENT_SURFACE_H
extern void gtk_layer_set_keyboard_mode(GtkWindow *, gint) __attribute__((weak));
extern gboolean gtk_layer_is_layer_window(GtkWindow *) __attribute__((weak));

static gboolean resident_surface_input(GtkWidget *widget, gboolean enabled) {
    gtk_window_set_accept_focus(GTK_WINDOW(widget), enabled);
    GdkWindow *window = gtk_widget_get_window(widget);
    if (!window || !gdk_display_supports_input_shapes(gdk_window_get_display(window))) return FALSE;
    cairo_region_t *region = enabled ? NULL : cairo_region_create();
    /* Store the shape on the widget too, so GTK keeps it across allocations. */
    gtk_widget_input_shape_combine_region(widget, region);
    if (region) cairo_region_destroy(region);
    return TRUE;
}
static void resident_surface_park(GtkWidget *widget) {
    gtk_widget_set_opacity(widget, 0);
    if (gtk_layer_set_keyboard_mode && gtk_layer_is_layer_window &&
            gtk_layer_is_layer_window(GTK_WINDOW(widget)))
        gtk_layer_set_keyboard_mode(GTK_WINDOW(widget), 0);
    resident_surface_input(widget, FALSE);
    g_object_set_data(G_OBJECT(widget), "raccon-parked", GINT_TO_POINTER(TRUE));
    /* Opacity-zero layers can retain seat focus or have their input region
       replaced during an Eww allocation/reload. Unmap to release both. */
    gtk_widget_hide(widget);
}
static void resident_surface_show(GtkWidget *widget) {
    resident_surface_input(widget, TRUE);
    if (gtk_layer_set_keyboard_mode && gtk_layer_is_layer_window &&
            gtk_layer_is_layer_window(GTK_WINDOW(widget)))
        gtk_layer_set_keyboard_mode(GTK_WINDOW(widget), 1);
    g_object_set_data(G_OBJECT(widget), "raccon-parked", NULL);
    if (!gtk_widget_get_mapped(widget)) gtk_widget_show(widget);
}
#endif
