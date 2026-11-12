/* Raccon selector: shared spatial keyboard navigation and bounded entrances. */
#include <gtk/gtk.h>
#include <gmodule.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "navigation.h"
#include "resident_surface.h"
#include "soft_icons.h"
#include "popup_geometry.h"

static const gchar *sections[]={"header","style-list","preview-column","footer",NULL};
static GtkWidget *resident;
static gchar *runtime_dir;
static gboolean visible, warming, seen_window;
static guint fade_tick;
static gint64 fade_started;
static gdouble fade_from, fade_target;

static void state(const gchar *name,const gchar *value) {
    gchar *path=g_build_filename(runtime_dir,name,NULL);
    g_file_set_contents(path,value,-1,NULL);g_free(path);
}
static void cancel_entrance(GtkWidget *window);
static gboolean initial_focus(gpointer window);
static gboolean motion(GtkWidget *window);
static void show_selector(void);
static void hide_selector(void);
static void configure_extras(GtkWidget *window);
static gboolean dismiss_extras(gboolean restore_focus);

static void pose(GtkWidget *window,const gchar *klass,gboolean enabled) {
    for(guint i=0;sections[i];i++) {
        GtkWidget *w=nav_find(window,sections[i]);
        if(!w)continue;
        GtkStyleContext *ctx=gtk_widget_get_style_context(w);
        if(enabled)gtk_style_context_add_class(ctx,klass);
        else gtk_style_context_remove_class(ctx,klass);
    }
}
static gboolean motion(GtkWidget *window) {
    gboolean enabled=TRUE;
    g_object_get(gtk_widget_get_settings(window),"gtk-enable-animations",&enabled,NULL);
    GtkWidget *root=nav_find(window,"style-selector");
    if(root) {
        GtkStyleContext *ctx=gtk_widget_get_style_context(root);
        if(enabled)gtk_style_context_remove_class(ctx,"reduce-motion");
        else gtk_style_context_add_class(ctx,"reduce-motion");
    }
    return enabled&&root&&nav_class(root,"motion");
}
static gboolean fade_frame(GtkWidget *window,GdkFrameClock *clock,gpointer unused) {
    gint64 now=gdk_frame_clock_get_frame_time(clock);
    if(!fade_started)fade_started=now;
    gdouble t=MIN(1.,(now-fade_started)/(fade_target?240000.:160000.));
    gdouble eased=1.-(1.-t)*(1.-t)*(1.-t);
    gtk_widget_set_opacity(window,fade_from+(fade_target-fade_from)*eased);
    if(t<1.)return G_SOURCE_CONTINUE;
    fade_tick=0;
    if(!visible)resident_surface_park(window);
    return G_SOURCE_REMOVE;
}
static void stop_fade(void) {
    if(fade_tick&&resident)gtk_widget_remove_tick_callback(resident,fade_tick);
    fade_tick=0;
}
static void destroyed(GtkWidget *window,gpointer unused) {
    if(resident!=window)return;
    stop_fade();
    g_object_remove_weak_pointer(G_OBJECT(window),(gpointer *)&resident);resident=NULL;
    state("ready","0");
    gchar *path=g_build_filename(runtime_dir,"mapped",NULL);unlink(path);g_free(path);
}
static void fade(gdouble target) {
    stop_fade();fade_started=0;fade_from=gtk_widget_get_opacity(resident);fade_target=target;
    if(!motion(resident)) {
        gtk_widget_set_opacity(resident,target);
        if(!visible)resident_surface_park(resident);
    } else fade_tick=gtk_widget_add_tick_callback(resident,fade_frame,NULL,NULL);
}
static void show_selector(void) {
    if(!resident)return;
    configure_extras(resident);
    gboolean opening=!visible;
    visible=TRUE;warming=FALSE;state("visible","1");
    if(opening) {
        stop_fade();gtk_widget_set_opacity(resident,0);
        resident_surface_show(resident);fade(1.);
    }
    gtk_window_present(GTK_WINDOW(resident));
    g_idle_add_full(G_PRIORITY_DEFAULT_IDLE,initial_focus,g_object_ref(resident),g_object_unref);
}
static void hide_selector(void) {
    if(!resident)return;
    dismiss_extras(FALSE);
    visible=FALSE;warming=FALSE;state("visible","0");
    resident_surface_input(resident,FALSE);
    cancel_entrance(resident);fade(0.);
}
static gboolean warm_frame(GtkWidget *window,GdkFrameClock *clock,gpointer data) {
    if(resident!=window||!warming||visible)return G_SOURCE_REMOVE;
    guint frames=GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window),"warm-frames"))+1;
    g_object_set_data(G_OBJECT(window),"warm-frames",GUINT_TO_POINTER(frames));
    if(frames%3)return G_SOURCE_CONTINUE;
    resident_surface_park(window);
    warming=FALSE;state("ready","1");
    return G_SOURCE_REMOVE;
}
static gboolean control(GIOChannel *channel,GIOCondition condition,gpointer unused) {
    gchar *line=NULL;
    while(g_io_channel_read_line(channel,&line,NULL,NULL,NULL)==G_IO_STATUS_NORMAL) {
        g_strstrip(line);
        if(g_str_equal(line,"show"))show_selector();
        else if(g_str_equal(line,"hide"))hide_selector();
        else if(g_str_equal(line,"toggle")) {if(visible)hide_selector();else show_selector();}
        g_free(line);line=NULL;
    }
    g_free(line);return G_SOURCE_CONTINUE;
}
static void cancel_entrance(GtkWidget *window) {
    guint tick=GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window),"style-tick"));
    guint timer=GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window),"style-timeout"));
    if(tick)gtk_widget_remove_tick_callback(window,tick);
    if(timer)g_source_remove(timer);
    g_object_set_data(G_OBJECT(window),"style-tick",NULL);
    g_object_set_data(G_OBJECT(window),"style-timeout",NULL);
    pose(window,"enter",FALSE);pose(window,"entering",FALSE);
}
static void unmapped(GtkWidget *window,gpointer unused) {cancel_entrance(window);}
static gboolean initial_focus(gpointer window) {
    if(!gtk_widget_get_mapped(window))return G_SOURCE_REMOVE;
    GPtrArray *items=g_ptr_array_new();nav_collect(window,items,"theme-choice");
    for(guint i=0;i<items->len;i++) {
        GtkWidget *w=g_ptr_array_index(items,i);
        if(nav_class(w,"selected")){nav_focus(w);break;}
    }
    g_ptr_array_unref(items);return G_SOURCE_REMOVE;
}
static void close_selector(void) {
    hide_selector();
}
static void configure_extras(GtkWidget *window) {
    GtkWidget *shell=nav_find(window,"style-shell"), *reveal=nav_find(window,"extra-revealer");
    gboolean enabled=TRUE,below=FALSE;
    gint screen_height=1080;
    g_object_get(gtk_widget_get_settings(window),"gtk-enable-animations",&enabled,NULL);
    GdkWindow *surface=gtk_widget_get_window(window);
    GdkMonitor *monitor=surface?gdk_display_get_monitor_at_window(gtk_widget_get_display(window),surface):NULL;
    if(monitor) { GdkRectangle bounds;gdk_monitor_get_geometry(monitor,&bounds);below=bounds.width<1080;screen_height=bounds.height; }
    GtkStyleContext *context=gtk_widget_get_style_context(shell?shell:window);
    if(below)gtk_style_context_add_class(context,"extras-below");
    else gtk_style_context_remove_class(context,"extras-below");
    if(GTK_IS_BOX(shell))gtk_orientable_set_orientation(GTK_ORIENTABLE(shell),below?GTK_ORIENTATION_VERTICAL:GTK_ORIENTATION_HORIZONTAL);
    guint ms=enabled?(shell&&nav_class(shell,"compact-motion")?140:240):0;
    if(GTK_IS_REVEALER(reveal)) {
        gtk_revealer_set_transition_type(GTK_REVEALER(reveal),enabled?(below?GTK_REVEALER_TRANSITION_TYPE_SLIDE_DOWN:GTK_REVEALER_TRANSITION_TYPE_SLIDE_RIGHT):GTK_REVEALER_TRANSITION_TYPE_NONE);
        gtk_revealer_set_transition_duration(GTK_REVEALER(reveal),ms);
        gtk_widget_set_valign(reveal,below?GTK_ALIGN_START:GTK_ALIGN_END);
        gtk_widget_set_halign(reveal,below?GTK_ALIGN_END:GTK_ALIGN_FILL);
    }
    GtkWidget *pages=nav_find(window,"extra-pages");
    if(GTK_IS_STACK(pages)) {
        gtk_stack_set_transition_type(GTK_STACK(pages),enabled?GTK_STACK_TRANSITION_TYPE_SLIDE_UP_DOWN:GTK_STACK_TRANSITION_TYPE_NONE);
        gtk_stack_set_transition_duration(GTK_STACK(pages),ms);
    }
    GtkWidget *scroll=nav_find(window,"extra-scroll"), *main=nav_find(window,"selector-main");
    if(GTK_IS_SCROLLED_WINDOW(scroll)) {
        gint main_height=0;
        if(below&&main)gtk_widget_get_preferred_height(main,NULL,&main_height);
        gtk_scrolled_window_set_propagate_natural_height(GTK_SCROLLED_WINDOW(scroll),TRUE);
        gtk_scrolled_window_set_propagate_natural_width(GTK_SCROLLED_WINDOW(scroll),TRUE);
        gtk_scrolled_window_set_max_content_height(GTK_SCROLLED_WINDOW(scroll),MAX(80,screen_height-main_height-24));
    }
}
static gboolean dismiss_extras(gboolean restore_focus) {
    if(!resident)return FALSE;
    GtkWidget *reveal=nav_find(resident,"extra-revealer");
    if(!GTK_IS_REVEALER(reveal)||!gtk_revealer_get_reveal_child(GTK_REVEALER(reveal)))return FALSE;
    gtk_revealer_set_reveal_child(GTK_REVEALER(reveal),FALSE);
    if(restore_focus) {
        GtkWidget *pages=nav_find(resident,"extra-pages");
        const gchar *page=GTK_IS_STACK(pages)?gtk_stack_get_visible_child_name(GTK_STACK(pages)):NULL;
        nav_nth(resident,g_strcmp0(page,"1")==0?"frames-toggle":"bar-toggle",0,FALSE);
    }
    /* Persist through the same FileEvents stream, without blocking GTK on IPC. */
    gchar *helper=g_build_filename(g_get_home_dir(),".local","bin","desktop-style",NULL);
    gchar *argv[]={helper,"extra","close",NULL};
    g_spawn_async(NULL,argv,NULL,0,NULL,NULL,NULL,NULL);g_free(helper);
    return TRUE;
}
static gboolean keys(GtkWidget *window,GdkEventKey *event,gpointer unused) {
    guint key=gdk_keyval_to_lower(event->keyval);
    if(key==GDK_KEY_Escape||((event->state&GDK_CONTROL_MASK)&&key==GDK_KEY_w)) {
        if(!g_object_get_data(G_OBJECT(window),"nav-held")) {
            g_object_set_data(G_OBJECT(window),"nav-held",GUINT_TO_POINTER(event->keyval));
            if(key!=GDK_KEY_Escape||!dismiss_extras(TRUE))close_selector();
        }
        return TRUE;
    }
    if(event->state&GDK_CONTROL_MASK) {
        if(key>=GDK_KEY_1&&key<=GDK_KEY_9) {
            if(!g_object_get_data(G_OBJECT(window),"nav-held")) {
                g_object_set_data(G_OBJECT(window),"nav-held",GUINT_TO_POINTER(event->keyval));
                nav_nth(window,"theme-choice",key-GDK_KEY_1,TRUE);
            }
            return TRUE;
        }
        if(key==GDK_KEY_Return||key==GDK_KEY_KP_Enter) {
            if(!g_object_get_data(G_OBJECT(window),"nav-held")) {
                g_object_set_data(G_OBJECT(window),"nav-held",GUINT_TO_POINTER(event->keyval));
                nav_nth(window,"apply",0,TRUE);
            }
            return TRUE;
        }
    }
    if(key==GDK_KEY_Home||key==GDK_KEY_End) {
        GPtrArray *items=g_ptr_array_new();nav_collect(window,items,"theme-choice");
        guint index=key==GDK_KEY_Home||!items->len?0:items->len-1;
        g_ptr_array_unref(items);
        nav_nth(window,"theme-choice",index,FALSE);return TRUE;
    }
    return nav_key(window,event);
}
static gboolean release(GtkWidget *window,GdkEventKey *event,gpointer unused){return nav_release(window,event);}
static gboolean focus_out(GtkWidget *window,GdkEventFocus *event,gpointer unused) {
    g_object_set_data(G_OBJECT(window),"nav-held",NULL);return FALSE;
}
static gboolean release_keyboard(gpointer data) {
    GtkWidget *window=data;
    if(gtk_layer_set_keyboard_mode&&gtk_layer_is_layer_window&&gtk_layer_is_layer_window(GTK_WINDOW(window)))
        gtk_layer_set_keyboard_mode(GTK_WINDOW(window),visible&&!warming&&gtk_widget_get_mapped(window)?2:0);
    return G_SOURCE_REMOVE;
}
static gboolean focus_in(GtkWidget *window,GdkEventFocus *event,gpointer unused) {
    release_keyboard(window);return FALSE;
}
static gboolean mapped(GSignalInvocationHint *hint,guint count,const GValue *values,gpointer unused) {
    GtkWidget *window=g_value_get_object(&values[0]);
    soft_icons_apply(window);
    if(!GTK_IS_WINDOW(window)||!nav_find(window,"style-selector"))return TRUE;
    popup_geometry_bind(window,1040,740);
    gboolean first=!g_object_get_data(G_OBJECT(window),"style-bound");
    if(resident!=window) {
        stop_fade();
        if(resident)g_object_remove_weak_pointer(G_OBJECT(resident),(gpointer *)&resident);
        resident=window;g_object_add_weak_pointer(G_OBJECT(window),(gpointer *)&resident);
    }
    if(first) {
        g_signal_connect(window,"key-press-event",G_CALLBACK(keys),NULL);
        g_signal_connect(window,"key-release-event",G_CALLBACK(release),NULL);
        g_signal_connect(window,"focus-out-event",G_CALLBACK(focus_out),NULL);
        g_signal_connect(window,"focus-in-event",G_CALLBACK(focus_in),NULL);
        g_signal_connect(window,"unmap",G_CALLBACK(unmapped),NULL);
        g_signal_connect(window,"destroy",G_CALLBACK(destroyed),NULL);
        g_object_set_data(G_OBJECT(window),"style-bound",GINT_TO_POINTER(1));
    }
    cancel_entrance(window);
    GtkWidget *hidden=nav_find(window,"initial-hidden");
    if(first&&!visible&&(seen_window||(GTK_IS_LABEL(hidden)&&g_str_equal(gtk_label_get_text(GTK_LABEL(hidden)),"true")))) {
        visible=FALSE;warming=TRUE;state("visible","0");
        gtk_widget_set_opacity(window,0);
        resident_surface_input(window,FALSE);state("ready","0");
        gtk_widget_add_tick_callback(window,warm_frame,NULL,NULL);
    } else if(!warming) {
        visible=TRUE;state("visible","1");
    }
    seen_window=TRUE;
    state("mapped","1");
    configure_extras(window);
    /* Exclusive focus is an opening request, never a persistent grab. */
    g_timeout_add_full(G_PRIORITY_DEFAULT,120,release_keyboard,g_object_ref(window),g_object_unref);
    GtkWidget *preview=nav_find(window,"preview-stack");
    if(GTK_IS_STACK(preview))gtk_stack_set_transition_duration(GTK_STACK(preview),nav_find(window,"compact-motion")?140:240);
    if(!warming)g_idle_add_full(G_PRIORITY_DEFAULT_IDLE,initial_focus,g_object_ref(window),g_object_unref);
    return TRUE;
}
G_MODULE_EXPORT void gtk_module_init(gint *argc,gchar ***argv) {
    if(!g_getenv("RACCON_STYLE_KEYS"))return;
    gchar *exe=g_file_read_link("/proc/self/exe",NULL);
    gboolean owner=exe&&g_str_has_suffix(exe,"/eww");g_free(exe);
    if(!owner)return;
    const gchar *base=g_getenv("XDG_RUNTIME_DIR");
    gchar *fallback=g_build_filename(g_get_home_dir(),".cache",NULL);
    runtime_dir=g_build_filename(base?base:fallback,"desktop-style",NULL);g_free(fallback);
    g_mkdir_with_parents(runtime_dir,0700);
    gchar *path=g_build_filename(runtime_dir,"control",NULL);
    struct stat info;
    if(lstat(path,&info)<0)mkfifo(path,0600);
    if(lstat(path,&info)==0&&S_ISFIFO(info.st_mode)&&info.st_uid==getuid()) {
        int fd=open(path,O_RDWR|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC);
        if(fd>=0) {
            GIOChannel *channel=g_io_channel_unix_new(fd);
            g_io_channel_set_encoding(channel,NULL,NULL);g_io_channel_set_close_on_unref(channel,TRUE);
            g_io_add_watch(channel,G_IO_IN,control,NULL);g_io_channel_unref(channel);
        }
    }
    g_free(path);
    state("revision",g_getenv("RACCON_STYLE_REVISION")?g_getenv("RACCON_STYLE_REVISION"):"");
    path=g_build_filename(runtime_dir,"mapped",NULL);unlink(path);g_free(path);
    g_type_class_ref(GTK_TYPE_WIDGET);
    g_signal_add_emission_hook(g_signal_lookup("map",GTK_TYPE_WIDGET),0,mapped,NULL,NULL);
}
