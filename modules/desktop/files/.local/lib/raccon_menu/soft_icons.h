#ifndef RACCON_SOFT_ICONS_H
#define RACCON_SOFT_ICONS_H
#include <gtk/gtk.h>

static const gchar *soft_icon_name(const gchar *name) {
    static const struct { const gchar *source, *glyph; } icons[] = {
        {"window-close-symbolic", "raccon-close-symbolic"}, {"system-search-symbolic", "raccon-search-symbolic"},
        {"network-wireless-symbolic", "raccon-wifi-symbolic"}, {"network-wireless-offline-symbolic", "raccon-wifi-off-symbolic"},
        {"network-disconnect-symbolic", "raccon-wifi-off-symbolic"}, {"bluetooth-symbolic", "raccon-bluetooth-symbolic"},
        {"audio-volume-high-symbolic", "raccon-volume-symbolic"}, {"audio-volume-medium-symbolic", "raccon-volume-symbolic"},
        {"audio-volume-low-symbolic", "raccon-volume-symbolic"}, {"audio-volume-muted-symbolic", "raccon-volume-off-symbolic"},
        {"x-office-calendar-symbolic", "raccon-calendar-symbolic"}, {"system-shutdown-symbolic", "raccon-power-symbolic"},
        {"preferences-system-power-symbolic", "raccon-power-symbolic"}, {"system-lock-screen-symbolic", "raccon-lock-symbolic"},
        {"system-log-out-symbolic", "raccon-logout-symbolic"}, {"system-reboot-symbolic", "raccon-restart-symbolic"},
        {"system-suspend-symbolic", "raccon-sleep-symbolic"}, {"weather-clear-night-symbolic", "raccon-sleep-symbolic"},
        {"view-app-grid-symbolic", "raccon-grid-symbolic"}, {"view-grid-symbolic", "raccon-grid-symbolic"},
        {"preferences-system-notifications-symbolic", "raccon-bell-symbolic"},
        {"preferences-desktop-keyboard-shortcuts-symbolic", "raccon-keyboard-symbolic"},
        {"emblem-ok-symbolic", "raccon-check-symbolic"}, {"object-select-symbolic", "raccon-check-symbolic"},
        {"list-add-symbolic", "raccon-plus-symbolic"}, {"list-remove-symbolic", "raccon-minus-symbolic"},
        {"go-previous-symbolic", "raccon-left-symbolic"}, {"go-next-symbolic", "raccon-right-symbolic"},
        {"go-up-symbolic", "raccon-up-symbolic"}, {"go-down-symbolic", "raccon-down-symbolic"}, {"pan-down-symbolic", "raccon-down-symbolic"},
        {"media-playback-start-symbolic", "raccon-play-symbolic"}, {"media-playback-pause-symbolic", "raccon-pause-symbolic"},
        {"media-skip-backward-symbolic", "raccon-previous-symbolic"}, {"media-skip-forward-symbolic", "raccon-next-symbolic"},
        {"audio-x-generic-symbolic", "raccon-music-symbolic"}, {"image-x-generic-symbolic", "raccon-image-symbolic"},
        {"image-missing-symbolic", "raccon-image-symbolic"}, {"preferences-desktop-wallpaper-symbolic", "raccon-image-symbolic"},
        {"video-x-generic-symbolic", "raccon-video-symbolic"}, {"avatar-default-symbolic", "raccon-user-symbolic"},
        {"go-home-symbolic", "raccon-home-symbolic"}, {"web-browser", "raccon-browser-symbolic"},
        {"system-file-manager", "raccon-folder-symbolic"}, {"utilities-terminal", "raccon-prompt-symbolic"},
        {"computer-symbolic", "raccon-monitor-symbolic"}, {"computer", "raccon-monitor-symbolic"},
        {"preferences-desktop-display-symbolic", "raccon-monitor-symbolic"},
        {"battery-low-symbolic", "raccon-battery-symbolic"}, {"battery-low", "raccon-battery-symbolic"},
        {"power-profile-balanced-symbolic", "raccon-balanced-symbolic"}, {"power-profile-balanced", "raccon-balanced-symbolic"},
        {"preferences-system-symbolic", "raccon-balanced-symbolic"}, {"preferences-system", "raccon-balanced-symbolic"},
        {"weather-clear-symbolic", "raccon-sun-symbolic"}, {"weather-clear", "raccon-sun-symbolic"},
        {"preferences-system-windows-symbolic", "raccon-windows-symbolic"},
        {"preferences-desktop-theme-symbolic", "raccon-palette-symbolic"},
        {"process-working-symbolic", "raccon-loader-symbolic"}, {"view-refresh-symbolic", "raccon-restart-symbolic"},
        {"document-edit-symbolic", "raccon-edit-symbolic"}, {"edit-undo-symbolic", "raccon-undo-symbolic"}, {"audio-headphones-symbolic", "raccon-headphones-symbolic"},
        {"view-reveal-symbolic", "raccon-eye-symbolic"}, {"utilities-terminal-symbolic", "raccon-prompt-symbolic"},
        {"format-text-code-symbolic", "raccon-code-symbolic"}, {"applications-games-symbolic", "raccon-gamepad-symbolic"},
        {"insert-link-symbolic", "raccon-link-symbolic"}, {"window-minimize-symbolic", "raccon-minus-symbolic"},
        {"applications-engineering-symbolic", "raccon-sparkle-symbolic"}, {"preferences-desktop-symbolic", "raccon-monitor-symbolic"}
    };
    if (!name) return NULL;
    for (guint i = 0; i < G_N_ELEMENTS(icons); i++)
        if (g_str_equal(name, icons[i].source)) return icons[i].glyph;
    return NULL;
}
static gboolean soft_icon_class(GtkWidget *widget, const gchar *name) {
    for (; widget; widget = gtk_widget_get_parent(widget))
        if (gtk_style_context_has_class(gtk_widget_get_style_context(widget), name)) return TRUE;
    return FALSE;
}
static void soft_icons_apply(GtkWidget *widget);
static void soft_icon_changed(GObject *image, GParamSpec *param, gpointer unused) {
    soft_icons_apply(GTK_WIDGET(image));
}
static void soft_icons_apply(GtkWidget *widget) {
    if (!GTK_IS_IMAGE(widget) || g_object_get_data(G_OBJECT(widget), "soft-icon-changing")) return;
    static gboolean theme_ready;
    if (!theme_ready) {
        gchar *path = g_build_filename(g_get_home_dir(), ".config", "raccon-menu", "assets", "icons", NULL);
        gtk_icon_theme_prepend_search_path(gtk_icon_theme_get_default(), path);
        g_free(path); theme_ready = TRUE;
    }
    if (!g_object_get_data(G_OBJECT(widget), "soft-icon-bound")) {
        g_object_set_data(G_OBJECT(widget), "soft-icon-bound", GINT_TO_POINTER(1));
        g_signal_connect(widget, "notify::icon-name", G_CALLBACK(soft_icon_changed), NULL);
        g_signal_connect(widget, "notify::gicon", G_CALLBACK(soft_icon_changed), NULL);
    }
    const gchar *name = NULL;
    GtkIconSize size = GTK_ICON_SIZE_BUTTON;
    GtkImageType storage = gtk_image_get_storage_type(GTK_IMAGE(widget));
    if (storage == GTK_IMAGE_ICON_NAME) gtk_image_get_icon_name(GTK_IMAGE(widget), &name, &size);
    else if (storage == GTK_IMAGE_GICON) {
        GIcon *icon = NULL;
        gtk_image_get_gicon(GTK_IMAGE(widget), &icon, &size);
        if (G_IS_THEMED_ICON(icon)) name = g_themed_icon_get_names(G_THEMED_ICON(icon))[0];
    }
    const gchar *replacement = soft_icon_name(name);
    gboolean app = soft_icon_class(widget, "app-icon");
    gboolean daily = soft_icon_class(widget, "daily-app");
    gboolean control = replacement || (name && g_str_has_prefix(name, "raccon-") && g_str_has_suffix(name, "-symbolic"));
    if (!app && !daily && !control) return;
    g_object_set_data(G_OBJECT(widget), "soft-icon-changing", GINT_TO_POINTER(1));
    if (replacement && !app) gtk_image_set_from_icon_name(GTK_IMAGE(widget), replacement, size);
    gint pixels = app ? 24 : daily ? 32 : size == GTK_ICON_SIZE_DIALOG ? 48 : size == GTK_ICON_SIZE_DND ? 32 : size == GTK_ICON_SIZE_LARGE_TOOLBAR ? 24 : 20;
    gtk_image_set_pixel_size(GTK_IMAGE(widget), pixels);
    gtk_widget_set_size_request(widget, pixels, pixels);
    gtk_widget_set_halign(widget, GTK_ALIGN_CENTER);
    gtk_widget_set_valign(widget, GTK_ALIGN_CENTER);
    g_object_set_data(G_OBJECT(widget), "soft-icon-changing", NULL);
}
#endif
