#include <gtk/gtk.h>
#include <gmodule.h>
#include "navigation.h"
#include "thumbnail_playback.h"
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
    if(gtk_widget_get_mapped(w)) {
        if(!nav_nth(w,"wall-tile",0,FALSE) && !nav_nth(w,"session-tile",0,FALSE))nav_nth(w,NULL,0,FALSE);
    }
    return G_SOURCE_REMOVE;
}
static gboolean mapped(GSignalInvocationHint *hint,guint count,const GValue *values,gpointer unused) {
    GtkWidget *w=g_value_get_object(&values[0]);
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
    /* Hidden metadata labels do not map: bind them when their toplevel maps. */
    if(GTK_IS_WINDOW(w)&&gtk_window_get_window_type(GTK_WINDOW(w))==GTK_WINDOW_TOPLEVEL) {
        if(!g_object_get_data(G_OBJECT(w),"float-keys")) {
            g_signal_connect(w,"key-press-event",G_CALLBACK(keys),NULL);
            g_signal_connect(w,"key-release-event",G_CALLBACK(released),NULL);
            g_signal_connect(w,"focus-out-event",G_CALLBACK(focus_reset),NULL);
            g_object_set_data(G_OBJECT(w),"float-keys",GINT_TO_POINTER(1));
        }
        GtkWidget *metadata=nav_find(w,"preview-playback");
        if(metadata&&!g_object_get_data(G_OBJECT(metadata),"native-playback")) {
            g_signal_connect(metadata,"notify::label",G_CALLBACK(play_update),NULL);
            g_object_set_data(G_OBJECT(metadata),"native-playback",GINT_TO_POINTER(1));
            play_update(G_OBJECT(metadata),NULL,NULL);
        }
        g_timeout_add_full(G_PRIORITY_DEFAULT,260,initial_focus,g_object_ref(w),g_object_unref);
    }
    return TRUE;
}
G_MODULE_EXPORT void gtk_module_init(gint *argc,gchar ***argv) {
    if(!g_getenv("RACCON_FLOAT_KEYS"))return;
    gchar *exe=g_file_read_link("/proc/self/exe",NULL);
    gboolean owner=exe&&g_str_has_suffix(exe,"/eww");g_free(exe);if(!owner)return;
    g_type_class_ref(GTK_TYPE_WIDGET);
    g_signal_add_emission_hook(g_signal_lookup("map",GTK_TYPE_WIDGET),0,mapped,NULL,NULL);
}
