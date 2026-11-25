#include <gtk/gtk.h>
#include <gmodule.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "navigation.h"
#include "thumbnail_playback.h"
#include "float_resident.h"
#include "soft_icons.h"
#include "popup_geometry.h"
extern void gtk_layer_set_keyboard_mode(GtkWindow *,gint) __attribute__((weak));
extern gboolean gtk_layer_is_layer_window(GtkWindow *) __attribute__((weak));
extern void gtk_layer_set_anchor(GtkWindow *,gint,gboolean) __attribute__((weak));
extern void gtk_layer_set_margin(GtkWindow *,gint,gint) __attribute__((weak));
static gboolean release_keyboard(gpointer data) {
    GtkWidget *window=data;
    if(gtk_layer_set_keyboard_mode&&gtk_layer_is_layer_window&&gtk_layer_is_layer_window(GTK_WINDOW(window)))
        gtk_layer_set_keyboard_mode(GTK_WINDOW(window),gtk_widget_get_mapped(window)&&!g_object_get_data(G_OBJECT(window),"float-warming")?2:0);
    return G_SOURCE_REMOVE;
}
static gboolean focus_acquired(GtkWidget *window,GdkEventFocus *event,gpointer unused) {
    release_keyboard(window);return FALSE;
}
static void action(const gchar *name) {
    const gchar *command=g_strcmp0(g_getenv("RACCON_KEYS_COMMAND"),"raccon-music")==0?"raccon-music":"raccon-float";
    gchar *exe=g_build_filename(g_get_home_dir(),".local","bin",command,NULL);
    gchar *argv[]={exe,(gchar*)name,NULL};
    g_spawn_async(NULL,argv,NULL,G_SPAWN_STDOUT_TO_DEV_NULL|G_SPAWN_STDERR_TO_DEV_NULL,NULL,NULL,NULL,NULL);g_free(exe);
}
static void tile_preview(GtkWidget *tile,gboolean stop) {
    GtkWidget *target=nav_find(tile,"preview-target");
    if(!GTK_IS_LABEL(target)||!*gtk_label_get_text(GTK_LABEL(target)))return;
    gchar **parts=g_strsplit(gtk_label_get_text(GTK_LABEL(target))," ",2);
    if(parts[0]&&parts[1]) {
        gchar *exe=g_build_filename(g_get_home_dir(),".local","bin","raccon-float",NULL);
        gchar *selection=g_strjoin(":",parts[0],parts[1],NULL);
        gchar *argv[]={exe,stop?"preview-stop":"preview-hover",stop?selection:parts[0],stop?NULL:parts[1],NULL};
        g_spawn_async(NULL,argv,NULL,G_SPAWN_STDOUT_TO_DEV_NULL|G_SPAWN_STDERR_TO_DEV_NULL,NULL,NULL,NULL,NULL);
        g_free(selection);g_free(exe);
    }
    g_strfreev(parts);
}
static GtkWidget *expanded_tile;
static gboolean keyboard_navigation;
static GtkWidget *tile_row(GtkWidget *tile) {
    for(GtkWidget *p=tile;p;p=gtk_widget_get_parent(p))if(nav_class(p,"wall-row"))return p;
    return NULL;
}
static void expand_tile(GtkWidget *tile) {
    if(expanded_tile==tile)return;
    if(expanded_tile) {
        GtkWidget *row=tile_row(expanded_tile);
        if(row)gtk_style_context_remove_class(gtk_widget_get_style_context(row),"expanded-row");
        gtk_style_context_remove_class(gtk_widget_get_style_context(expanded_tile),"expanded-tile");
        g_object_remove_weak_pointer(G_OBJECT(expanded_tile),(gpointer*)&expanded_tile);
    }
    expanded_tile=tile;
    if(tile) {
        g_object_add_weak_pointer(G_OBJECT(tile),(gpointer*)&expanded_tile);
        GtkWidget *row=tile_row(tile);
        if(row)gtk_style_context_add_class(gtk_widget_get_style_context(row),"expanded-row");
        gtk_style_context_add_class(gtk_widget_get_style_context(tile),"expanded-tile");
    }
}
static gboolean tile_enter(GtkWidget *w,GdkEventCrossing *event,gpointer unused) {
    if(!keyboard_navigation&&event->detail!=GDK_NOTIFY_INFERIOR)expand_tile(w);
    return FALSE;
}
static gboolean tile_leave(GtkWidget *w,GdkEventCrossing *event,gpointer unused) {
    if(!keyboard_navigation&&event->detail!=GDK_NOTIFY_INFERIOR&&expanded_tile==w) {
        GtkWidget *focus=gtk_window_get_focus(GTK_WINDOW(gtk_widget_get_toplevel(w)));
        expand_tile(focus&&nav_class(focus,"wall-tile")?focus:NULL);
    }
    return FALSE;
}
static gboolean tile_motion(GtkWidget *w,GdkEventMotion *event,gpointer unused) {
    keyboard_navigation=FALSE;expand_tile(w);return FALSE;
}
static void tile_focus(GObject *object,GParamSpec *param,gpointer unused) {
    GtkWidget *w=GTK_WIDGET(object);
    if(gtk_widget_has_focus(w))expand_tile(w);
    else if(expanded_tile==w)expand_tile(NULL);
    tile_preview(w,!gtk_widget_has_focus(w));
}
static gboolean keys(GtkWidget *w,GdkEventKey *e,gpointer unused) {
    guint key=gdk_keyval_to_lower(e->keyval);
    if(key==GDK_KEY_Left||key==GDK_KEY_Right||key==GDK_KEY_Up||key==GDK_KEY_Down||
       key==GDK_KEY_Tab||key==GDK_KEY_ISO_Left_Tab||key==GDK_KEY_Home||key==GDK_KEY_End||
       key==GDK_KEY_Page_Up||key==GDK_KEY_Page_Down)keyboard_navigation=TRUE;
    if((e->state&GDK_CONTROL_MASK)&&key==GDK_KEY_w){action("close");return TRUE;}
    if(key==GDK_KEY_Escape) {
        GtkWidget *preview=nav_find(w,"preview-active");
        if(GTK_IS_LABEL(preview)&&g_strcmp0(gtk_label_get_text(GTK_LABEL(preview)),"true")==0)action("preview-stop");
        else if(nav_find(w,"armed"))action("disarm");
        else action("close");
        return TRUE;
    }
    gboolean wallpaper=nav_find(w,"wallpaper-card")!=NULL;
    if(e->state&GDK_CONTROL_MASK && key>=GDK_KEY_1&&key<=GDK_KEY_5) {
        nav_nth(w,wallpaper?"nav-tab":"session-tile",key-GDK_KEY_1,wallpaper);return TRUE;
    }
    if(key==GDK_KEY_p && !(e->state&(GDK_CONTROL_MASK|GDK_MOD1_MASK|GDK_SUPER_MASK))) {
        GtkWidget *focus=gtk_window_get_focus(GTK_WINDOW(w));
        for(GtkWidget *p=focus;p&&p!=w;p=gtk_widget_get_parent(p)) {
            if(nav_class(p,"wall-cell")) {
                GtkWidget *tile=nav_find(p,"wall-tile");
                if(tile)tile_preview(tile,FALSE);
                return TRUE;
            }
        }
    }
    if(key==GDK_KEY_Home||key==GDK_KEY_End) {
        GPtrArray *items=g_ptr_array_new();nav_collect(w,items,wallpaper?"wall-tile":"session-tile");
        if(items->len)nav_focus(g_ptr_array_index(items,key==GDK_KEY_Home?0:items->len-1));
        g_ptr_array_unref(items);return TRUE;
    }
    return nav_key(w,e);
}
static gboolean released(GtkWidget *w,GdkEventKey *e,gpointer unused){return nav_release(w,e);}
static gboolean focus_reset(GtkWidget *w,GdkEventFocus *e,gpointer unused){g_object_set_data(G_OBJECT(w),"nav-held",NULL);return FALSE;}
static gboolean initial_focus(gpointer data) {
    GtkWidget *w=data;
    if(gtk_widget_get_mapped(w)&&!g_object_get_data(G_OBJECT(w),"float-warming")) {
        if(!nav_nth(w,"wall-tile",0,FALSE) && !nav_nth(w,"session-tile",0,FALSE))nav_nth(w,NULL,0,FALSE);
    }
    return G_SOURCE_REMOVE;
}
static const gchar *card_kind(GtkWidget *window) {
    if (!window) return NULL;
    if (nav_find(window, "music-card")) return "raccon-music";
    if (nav_find(window, "countdown-card")) return "raccon-countdown";
    return NULL;
}

static gchar *card_pos_path(const gchar *kind) {
    return g_build_filename(g_get_user_state_dir(), kind, "pos.ini", NULL);
}

static void card_default_pos(GtkWidget *window, const gchar *kind, gint w, gint h, const GdkRectangle *bounds, gint *ox, gint *oy) {
    gchar *cfg_path = g_build_filename(g_get_home_dir(), ".config", "waybar", "config.jsonc", NULL);
    gchar *text = NULL;
    gchar *edge = NULL;
    if (g_file_get_contents(cfg_path, &text, NULL, NULL)) {
        GRegex *regex = g_regex_new("\"position\"[[:space:]]*:[[:space:]]*\"(top|bottom|left|right)\"", 0, 0, NULL);
        GMatchInfo *match = NULL;
        if (g_regex_match(regex, text, 0, &match)) edge = g_match_info_fetch(match, 1);
        g_match_info_free(match); g_regex_unref(regex); g_free(text);
    }
    g_free(cfg_path);
    if (g_strcmp0(kind, "raccon-countdown") == 0) {
        *ox = MAX(4, (bounds->width - w) / 2);
        *oy = g_strcmp0(edge, "top") == 0 ? 68 : 18;
    } else if (g_strcmp0(edge, "bottom") == 0) {
        *ox = MAX(4, bounds->width - w - 8);
        *oy = MAX(4, bounds->height - h - 4);
    } else if (g_strcmp0(edge, "left") == 0) {
        *ox = 64; *oy = 8;
    } else if (g_strcmp0(edge, "right") == 0) {
        *ox = MAX(4, bounds->width - w - 64); *oy = 8;
    } else {
        *ox = MAX(4, bounds->width - w - 8); *oy = 78;
    }
    g_free(edge);
}

static void card_apply_pos(GtkWidget *window, gint x, gint y) {
    if (!window || !gtk_layer_set_anchor || !gtk_layer_set_margin || !gtk_layer_is_layer_window ||
        !gtk_layer_is_layer_window(GTK_WINDOW(window))) return;
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkWindow *surface = gtk_widget_get_window(window);
    GdkMonitor *monitor = surface ? gdk_display_get_monitor_at_window(display, surface) : gdk_display_get_primary_monitor(display);
    if (!monitor && display && gdk_display_get_n_monitors(display)) monitor = gdk_display_get_monitor(display, 0);
    gint w = gtk_widget_get_allocated_width(window);
    gint h = gtk_widget_get_allocated_height(window);
    if (w < 10) w = g_strcmp0(card_kind(window), "raccon-countdown") == 0 ? 176 : 344;
    if (h < 10) h = g_strcmp0(card_kind(window), "raccon-countdown") == 0 ? 52 : 178;
    if (monitor) {
        GdkRectangle bounds;
        gdk_monitor_get_workarea(monitor, &bounds);
        x = CLAMP(x, 4, MAX(4, bounds.width - w - 4));
        y = CLAMP(y, 4, MAX(4, bounds.height - h - 4));
    } else {
        x = MAX(4, x);
        y = MAX(4, y);
    }
    gtk_layer_set_anchor(GTK_WINDOW(window), 0, TRUE);
    gtk_layer_set_anchor(GTK_WINDOW(window), 2, TRUE);
    gtk_layer_set_anchor(GTK_WINDOW(window), 1, FALSE);
    gtk_layer_set_anchor(GTK_WINDOW(window), 3, FALSE);
    gtk_layer_set_margin(GTK_WINDOW(window), 0, x);
    gtk_layer_set_margin(GTK_WINDOW(window), 2, y);
    g_object_set_data(G_OBJECT(window), "card-pos-set", GINT_TO_POINTER(1));
    g_object_set_data(G_OBJECT(window), "card-pos-x", GINT_TO_POINTER(x));
    g_object_set_data(G_OBJECT(window), "card-pos-y", GINT_TO_POINTER(y));
}

static void card_load_pos(GtkWidget *window, const gchar *kind) {
    gchar *path = card_pos_path(kind);
    GKeyFile *kf = g_key_file_new();
    if (g_key_file_load_from_file(kf, path, G_KEY_FILE_NONE, NULL) &&
        g_key_file_has_key(kf, "pos", "x", NULL) &&
        g_key_file_has_key(kf, "pos", "y", NULL)) {
        gint x = g_key_file_get_integer(kf, "pos", "x", NULL);
        gint y = g_key_file_get_integer(kf, "pos", "y", NULL);
        card_apply_pos(window, x, y);
    } else {
        g_object_set_data(G_OBJECT(window), "card-pos-set", NULL);
    }
    g_key_file_unref(kf);
    g_free(path);
}

static void card_save_pos(const gchar *kind, gint x, gint y) {
    if (!kind) return;
    gchar *path = card_pos_path(kind);
    gchar *dir = g_path_get_dirname(path);
    g_mkdir_with_parents(dir, 0700);
    g_free(dir);
    GKeyFile *kf = g_key_file_new();
    g_key_file_set_integer(kf, "pos", "x", x);
    g_key_file_set_integer(kf, "pos", "y", y);
    gchar *data = g_key_file_to_data(kf, NULL, NULL);
    if (data) { g_file_set_contents(path, data, -1, NULL); g_free(data); }
    g_key_file_unref(kf);
    g_free(path);
}

typedef struct {
    gboolean moved;
    GdkDevice *device;
    gint press_x, press_y;   /* pointer offset inside the surface at press */
    gint start_x, start_y;
    gint cur_x, cur_y;       /* last margin requested */
    gint prev_x, prev_y;     /* margin the compositor may still be using */
    gint last_gx, last_gy;   /* last pointer position in workarea space */
    gint want_x, want_y;
    guint tick;
} CardDrag;

static CardDrag *card_drag(GtkWidget *win) {
    return g_object_get_data(G_OBJECT(win), "card-drag");
}

static void card_drag_flush(GtkWidget *win, CardDrag *d) {
    if (!d->moved || (d->want_x == d->cur_x && d->want_y == d->cur_y)) return;
    card_apply_pos(win, d->want_x, d->want_y);
    d->prev_x = d->cur_x; d->prev_y = d->cur_y;
    d->cur_x = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(win), "card-pos-x"));
    d->cur_y = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(win), "card-pos-y"));
}

/* One margin update per compositor frame keeps the move in step with the display. */
static gboolean card_drag_frame(GtkWidget *win, GdkFrameClock *clock, gpointer unused) {
    CardDrag *d = card_drag(win);
    if (!d) return G_SOURCE_REMOVE;
    card_drag_flush(win, d);
    d->tick = 0;
    return G_SOURCE_REMOVE;
}

static gboolean card_drag_press(GtkWidget *w, GdkEventButton *e, gpointer unused) {
    if (e->button != 1 || e->type != GDK_BUTTON_PRESS) return FALSE;
    GtkWidget *win = gtk_widget_get_toplevel(w);
    const gchar *kind = card_kind(win);
    if (!GTK_IS_WINDOW(win) || !kind || card_drag(win)) return FALSE;
    gint base_x = 0, base_y = 0;
    if (g_object_get_data(G_OBJECT(win), "card-pos-set")) {
        base_x = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(win), "card-pos-x"));
        base_y = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(win), "card-pos-y"));
    } else {
        GdkDisplay *display = gtk_widget_get_display(win);
        GdkWindow *surface = gtk_widget_get_window(win);
        GdkMonitor *monitor = surface ? gdk_display_get_monitor_at_window(display, surface) : gdk_display_get_primary_monitor(display);
        if (!monitor && display && gdk_display_get_n_monitors(display)) monitor = gdk_display_get_monitor(display, 0);
        GdkRectangle bounds = {0, 0, 1920, 1080};
        if (monitor) gdk_monitor_get_workarea(monitor, &bounds);
        gint ww = gtk_widget_get_allocated_width(win), wh = gtk_widget_get_allocated_height(win);
        card_default_pos(win, kind, ww > 10 ? ww : 324, wh > 10 ? wh : 168, &bounds, &base_x, &base_y);
    }
    CardDrag *d = g_new0(CardDrag, 1);
    d->device = e->device;
    d->press_x = (gint)e->x; d->press_y = (gint)e->y;
    if (gtk_widget_get_window(win) && e->device)
        gdk_window_get_device_position(gtk_widget_get_window(win), e->device, &d->press_x, &d->press_y, NULL);
    d->start_x = d->cur_x = d->prev_x = d->want_x = base_x;
    d->start_y = d->cur_y = d->prev_y = d->want_y = base_y;
    d->last_gx = base_x + d->press_x;
    d->last_gy = base_y + d->press_y;
    g_object_set_data_full(G_OBJECT(win), "card-drag", d, g_free);
    gtk_style_context_add_class(gtk_widget_get_style_context(win), "card-dragging");
    if (e->device && gtk_widget_get_window(w))
        gdk_seat_grab(gdk_device_get_seat(e->device), gtk_widget_get_window(w),
                      GDK_SEAT_CAPABILITY_POINTER, TRUE, NULL, (GdkEvent *)e, NULL, NULL);
    gtk_grab_add(w);
    return TRUE;
}

static gboolean card_drag_motion(GtkWidget *w, GdkEventMotion *e, gpointer unused) {
    GtkWidget *win = gtk_widget_get_toplevel(w);
    CardDrag *d = GTK_IS_WINDOW(win) ? card_drag(win) : NULL;
    if (!d) return FALSE;
    gint lx = (gint)e->x, ly = (gint)e->y;
    if (gtk_widget_get_window(win) && d->device)
        gdk_window_get_device_position(gtk_widget_get_window(win), d->device, &lx, &ly, NULL);
    /* Surface-local coordinates may predate the last margin commit; pointer motion is
       continuous, so the interpretation closest to the previous position is the real one. */
    gint ngx = lx + d->cur_x, ngy = ly + d->cur_y;
    gint ogx = lx + d->prev_x, ogy = ly + d->prev_y;
    if (ABS(ngx - d->last_gx) + ABS(ngy - d->last_gy) <= ABS(ogx - d->last_gx) + ABS(ogy - d->last_gy)) {
        d->prev_x = d->cur_x; d->prev_y = d->cur_y;
        d->last_gx = ngx; d->last_gy = ngy;
    } else {
        d->last_gx = ogx; d->last_gy = ogy;
    }
    d->want_x = d->last_gx - d->press_x;
    d->want_y = d->last_gy - d->press_y;
    if (!d->moved && (ABS(d->want_x - d->start_x) > 3 || ABS(d->want_y - d->start_y) > 3)) d->moved = TRUE;
    if (d->moved && !d->tick) d->tick = gtk_widget_add_tick_callback(win, card_drag_frame, NULL, NULL);
    return TRUE;
}

static gboolean card_drag_release(GtkWidget *w, GdkEventButton *e, gpointer unused) {
    GtkWidget *win = gtk_widget_get_toplevel(w);
    CardDrag *d = GTK_IS_WINDOW(win) ? card_drag(win) : NULL;
    if (!d) return FALSE;
    if (d->tick) gtk_widget_remove_tick_callback(win, d->tick);
    card_drag_flush(win, d);
    gboolean moved = d->moved;
    gint x = d->cur_x, y = d->cur_y;
    gtk_grab_remove(w);
    if (e->device) gdk_seat_ungrab(gdk_device_get_seat(e->device));
    g_object_set_data(G_OBJECT(win), "card-drag", NULL);
    gtk_style_context_remove_class(gtk_widget_get_style_context(win), "card-dragging");
    if (moved) {
        card_save_pos(card_kind(win), x, y);
        return TRUE;
    }
    if (g_strcmp0(card_kind(win), "raccon-countdown") == 0) {
        GtkWidget *card = nav_find(win, "countdown-card");
        gboolean exp = card && nav_class(card, "expanded");
        gchar *cfg = g_build_filename(g_get_home_dir(), ".config", "raccon-countdown", NULL);
        gchar *arg = g_strdup_printf("expanded=%s", exp ? "false" : "true");
        gchar *argv[] = {"eww", "-c", cfg, "update", arg, NULL};
        g_spawn_async(NULL, argv, NULL, G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL,
                      NULL, NULL, NULL, NULL);
        g_free(cfg); g_free(arg);
        return TRUE;
    }
    return FALSE;
}

static GtkWidget *countdown_window;
static guint countdown_tick, countdown_ms;
static gint64 countdown_started;
static gdouble countdown_from, countdown_target, countdown_progress = 1.0;

static void countdown_pose(GtkWidget *win, gdouble progress) {
    countdown_progress = progress;
    if (!win) return;
    gtk_widget_set_opacity(win, CLAMP(progress, 0.0, 1.0));
    GtkWidget *stage = nav_find(win, "motion-stage");
    if (stage && g_object_class_find_property(G_OBJECT_GET_CLASS(stage), "translate-y")) {
        gdouble offset = -(1.0 - progress) * 85.0;
        gchar y[G_ASCII_DTOSTR_BUF_SIZE + 2];
        g_ascii_dtostr(y, sizeof(y) - 1, offset);
        g_strlcat(y, "%", sizeof(y));
        g_object_set(stage, "translate-y", y, NULL);
    }
}

static gboolean countdown_anim_frame(GtkWidget *win, GdkFrameClock *clock, gpointer unused) {
    if (win != countdown_window) { countdown_tick = 0; return G_SOURCE_REMOVE; }
    gint64 now = g_get_monotonic_time();
    if (!countdown_started) countdown_started = now;
    gdouble t = countdown_ms ? MIN(1.0, (now - countdown_started) / (countdown_ms * 1000.0)) : 1.0;
    gdouble rem = 1.0 - t;
    gdouble eased = countdown_target > countdown_from ? 1.0 - rem * rem * rem : t * t;
    countdown_pose(win, countdown_from + (countdown_target - countdown_from) * eased);
    if (t < 1.0) return G_SOURCE_CONTINUE;
    countdown_tick = 0;
    return G_SOURCE_REMOVE;
}

static void countdown_animate(GtkWidget *win, gdouble target, guint ms) {
    if (!win) return;
    if (countdown_tick) { gtk_widget_remove_tick_callback(win, countdown_tick); countdown_tick = 0; }
    if (target > 0.5 && countdown_progress >= 0.99) countdown_progress = 0.0;
    countdown_from = countdown_progress;
    countdown_target = target;
    countdown_ms = ms;
    countdown_started = 0;
    if (!ms) { countdown_pose(win, target); return; }
    countdown_pose(win, countdown_from);
    countdown_tick = gtk_widget_add_tick_callback(win, countdown_anim_frame, NULL, NULL);
}

static gboolean countdown_ctl_read(GIOChannel *ch, GIOCondition cond, gpointer unused) {
    gchar *line = NULL;
    while (g_io_channel_read_line(ch, &line, NULL, NULL, NULL) == G_IO_STATUS_NORMAL) {
        g_strstrip(line);
        if (g_strcmp0(line, "hide") == 0) countdown_animate(countdown_window, 0.0, 165);
        else if (g_strcmp0(line, "show") == 0) countdown_animate(countdown_window, 1.0, 200);
        g_free(line); line = NULL;
    }
    g_free(line);
    return TRUE;
}

static void countdown_init_ctl(void) {
    static gboolean bound;
    if (bound || g_strcmp0(g_getenv("RACCON_KEYS_COMMAND"), "raccon-countdown") != 0) return;
    bound = TRUE;
    const gchar *base = g_get_user_runtime_dir();
    gchar *pipe = g_build_filename(base, "raccon-countdown-ctl", NULL);
    struct stat st;
    if (lstat(pipe, &st) < 0) mkfifo(pipe, 0600);
    if (lstat(pipe, &st) == 0 && S_ISFIFO(st.st_mode) && st.st_uid == getuid()) {
        int fd = open(pipe, O_RDWR | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
        if (fd >= 0) {
            GIOChannel *ch = g_io_channel_unix_new(fd);
            g_io_channel_set_encoding(ch, NULL, NULL);
            g_io_channel_set_close_on_unref(ch, TRUE);
            g_io_add_watch(ch, G_IO_IN, countdown_ctl_read, NULL);
            g_io_channel_unref(ch);
        }
    }
    g_free(pipe);
}

static gboolean mapped(GSignalInvocationHint *hint,guint count,const GValue *values,gpointer unused) {
    GtkWidget *w=g_value_get_object(&values[0]);
    soft_icons_apply(w);
    /* Eww overlays default to pass-through; Play must receive clicks itself. */
    GtkWidget *parent=gtk_widget_get_parent(w);
    if(parent && GTK_IS_OVERLAY(parent) && gtk_bin_get_child(GTK_BIN(parent))!=w)
        gtk_overlay_set_overlay_pass_through(GTK_OVERLAY(parent),w,!GTK_IS_BUTTON(w));
    if(GTK_IS_BUTTON(w)&&nav_class(w,"wall-tile")&&!g_object_get_data(G_OBJECT(w),"preview-focus")) {
        g_signal_connect(w,"notify::has-focus",G_CALLBACK(tile_focus),NULL);
        gtk_widget_add_events(w,GDK_POINTER_MOTION_MASK);
        g_signal_connect(w,"motion-notify-event",G_CALLBACK(tile_motion),NULL);
        g_signal_connect(w,"enter-notify-event",G_CALLBACK(tile_enter),NULL);
        g_signal_connect(w,"leave-notify-event",G_CALLBACK(tile_leave),NULL);
        g_object_set_data(G_OBJECT(w),"preview-focus",GINT_TO_POINTER(1));
    }
    if(nav_class(w,"wall-thumb")&&!g_object_get_data(G_OBJECT(w),"native-draw")) {
        g_signal_connect_after(w,"draw",G_CALLBACK(play_draw),NULL);
        g_object_set_data(G_OBJECT(w),"native-draw",GINT_TO_POINTER(1));
    }
    if((nav_class(w,"music-drag-surface")||nav_class(w,"card-drag-surface"))&&!g_object_get_data(G_OBJECT(w),"card-drag-bound")) {
        gtk_widget_add_events(w,GDK_BUTTON_PRESS_MASK|GDK_BUTTON_RELEASE_MASK|GDK_POINTER_MOTION_MASK);
        g_signal_connect(w,"button-press-event",G_CALLBACK(card_drag_press),NULL);
        g_signal_connect(w,"motion-notify-event",G_CALLBACK(card_drag_motion),NULL);
        g_signal_connect(w,"button-release-event",G_CALLBACK(card_drag_release),NULL);
        g_object_set_data(G_OBJECT(w),"card-drag-bound",GINT_TO_POINTER(1));
    }
    /* Hidden metadata labels do not map: bind them when their toplevel maps. */
    if(GTK_IS_WINDOW(w)&&gtk_window_get_window_type(GTK_WINDOW(w))==GTK_WINDOW_TOPLEVEL) {
        if(nav_find(w,"music-card")) {
            popup_geometry_bind(w,344,178);
            card_load_pos(w,"raccon-music");
        }
        else if(nav_find(w,"countdown-card")) {
            countdown_window = w;
            gtk_window_set_resizable(GTK_WINDOW(w), FALSE);
            card_load_pos(w,"raccon-countdown");
            countdown_animate(w, 1.0, 200);
        }
        else if(nav_find(w,"wallpaper-card")) popup_geometry_bind(w,756,470);
        else if(nav_find(w,"session-row")) popup_geometry_bind(w,720,232);
        if(!g_object_get_data(G_OBJECT(w),"float-keys")) {
            g_signal_connect(w,"key-press-event",G_CALLBACK(keys),NULL);
            g_signal_connect(w,"key-release-event",G_CALLBACK(released),NULL);
            g_signal_connect(w,"focus-out-event",G_CALLBACK(focus_reset),NULL);
            g_signal_connect(w,"focus-in-event",G_CALLBACK(focus_acquired),NULL);
            g_object_set_data(G_OBJECT(w),"float-keys",GINT_TO_POINTER(1));
        }
        GtkWidget *metadata=nav_find(w,"preview-playback");
        if(metadata&&!g_object_get_data(G_OBJECT(metadata),"native-playback")) {
            g_signal_connect(metadata,"notify::label",G_CALLBACK(play_update),NULL);
            g_object_set_data(G_OBJECT(metadata),"native-playback",GINT_TO_POINTER(1));
            play_update(G_OBJECT(metadata),NULL,NULL);
        }
        if(resident_bind(w))return TRUE;
        g_timeout_add_full(G_PRIORITY_DEFAULT,260,initial_focus,g_object_ref(w),g_object_unref);
        g_timeout_add_full(G_PRIORITY_DEFAULT,120,release_keyboard,g_object_ref(w),g_object_unref);
    }
    return TRUE;
}
G_MODULE_EXPORT void gtk_module_init(gint *argc,gchar ***argv) {
    if(!g_getenv("RACCON_FLOAT_KEYS"))return;
    gchar *exe=g_file_read_link("/proc/self/exe",NULL);
    gboolean owner=exe&&g_str_has_suffix(exe,"/eww");g_free(exe);if(!owner)return;
    g_type_class_ref(GTK_TYPE_WIDGET);
    countdown_init_ctl();
    g_signal_add_emission_hook(g_signal_lookup("map",GTK_TYPE_WIDGET),0,mapped,NULL,NULL);
}
