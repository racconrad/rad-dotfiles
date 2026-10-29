/* Raccon selector: shared spatial keyboard navigation and bounded entrances. */
#include <gtk/gtk.h>
#include <gmodule.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../raccon_menu/navigation.h"

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
    gdouble t=MIN(1.,(now-fade_started)/(fade_target?180000.:120000.));
    gdouble eased=1.-(1.-t)*(1.-t)*(1.-t);
    gtk_widget_set_opacity(window,fade_from+(fade_target-fade_from)*eased);
    if(t<1.)return G_SOURCE_CONTINUE;
    fade_tick=0;
    if(!visible)gtk_widget_hide(window);
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
    gchar *path=g_build_filename(runtime_dir,"mapped",NULL);unlink(path);g_free(path);
}
static void fade(gdouble target) {
    stop_fade();fade_started=0;fade_from=gtk_widget_get_opacity(resident);fade_target=target;
    if(!motion(resident)) {
        gtk_widget_set_opacity(resident,target);
        if(!visible)gtk_widget_hide(resident);
    } else fade_tick=gtk_widget_add_tick_callback(resident,fade_frame,NULL,NULL);
}
static void show_selector(void) {
    if(!resident)return;
    gboolean opening=!visible;
    visible=TRUE;warming=FALSE;state("visible","1");
    if(opening) {
        stop_fade();gtk_widget_set_opacity(resident,0);
        gtk_widget_show(resident);fade(1.);
    }
    gtk_window_present(GTK_WINDOW(resident));
    g_idle_add_full(G_PRIORITY_DEFAULT_IDLE,initial_focus,g_object_ref(resident),g_object_unref);
}
static void hide_selector(void) {
    if(!resident)return;
    visible=FALSE;warming=FALSE;state("visible","0");
    cancel_entrance(resident);fade(0.);
}
static gboolean warm_frame(GtkWidget *window,GdkFrameClock *clock,gpointer data);
static gboolean warm_again(gpointer window) {
    if(resident==window&&warming&&!visible) {
        gtk_widget_set_opacity(window,0);gtk_widget_show(window);
        gtk_widget_add_tick_callback(window,warm_frame,GINT_TO_POINTER(1),NULL);
    }
    return G_SOURCE_REMOVE;
}
static gboolean warm_frame(GtkWidget *window,GdkFrameClock *clock,gpointer data) {
    if(resident!=window||!warming||visible)return G_SOURCE_REMOVE;
    guint frames=GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window),"warm-frames"))+1;
    g_object_set_data(G_OBJECT(window),"warm-frames",GUINT_TO_POINTER(frames));
    if(frames%3)return G_SOURCE_CONTINUE;
    gtk_widget_hide(window);
    if(!data)g_timeout_add_full(G_PRIORITY_DEFAULT,60,warm_again,g_object_ref(window),g_object_unref);
    else warming=FALSE;
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
static gboolean enter_frame(GtkWidget *window,GdkFrameClock *clock,gpointer unused) {
    guint frames=GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window),"style-frames"))+1;
    g_object_set_data(G_OBJECT(window),"style-frames",GUINT_TO_POINTER(frames));
    if(frames<2)return G_SOURCE_CONTINUE;
    pose(window,"enter",FALSE);
    g_object_set_data(G_OBJECT(window),"style-tick",NULL);
    return G_SOURCE_REMOVE;
}
static gboolean entrance_done(gpointer window) {
    pose(window,"entering",FALSE);
    g_object_set_data(G_OBJECT(window),"style-timeout",NULL);
    return G_SOURCE_REMOVE;
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
static gboolean keys(GtkWidget *window,GdkEventKey *event,gpointer unused) {
    guint key=gdk_keyval_to_lower(event->keyval);
    if(key==GDK_KEY_Escape||((event->state&GDK_CONTROL_MASK)&&key==GDK_KEY_w)) {
        if(!g_object_get_data(G_OBJECT(window),"nav-held")) {
            g_object_set_data(G_OBJECT(window),"nav-held",GUINT_TO_POINTER(event->keyval));
            close_selector();
        }
        return TRUE;
    }
    if(event->state&GDK_CONTROL_MASK) {
        if(key>=GDK_KEY_1&&key<=GDK_KEY_7) {
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
        nav_nth(window,"theme-choice",key==GDK_KEY_Home?0:6,FALSE);return TRUE;
    }
    return nav_key(window,event);
}
static gboolean release(GtkWidget *window,GdkEventKey *event,gpointer unused){return nav_release(window,event);}
static gboolean focus_out(GtkWidget *window,GdkEventFocus *event,gpointer unused) {
    g_object_set_data(G_OBJECT(window),"nav-held",NULL);return FALSE;
}
static gboolean mapped(GSignalInvocationHint *hint,guint count,const GValue *values,gpointer unused) {
    GtkWidget *window=g_value_get_object(&values[0]);
    if(!GTK_IS_WINDOW(window)||!nav_find(window,"style-selector"))return TRUE;
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
        g_signal_connect(window,"unmap",G_CALLBACK(unmapped),NULL);
        g_signal_connect(window,"destroy",G_CALLBACK(destroyed),NULL);
        g_object_set_data(G_OBJECT(window),"style-bound",GINT_TO_POINTER(1));
    }
    cancel_entrance(window);
    GtkWidget *hidden=nav_find(window,"initial-hidden");
    if(first&&!visible&&(seen_window||(GTK_IS_LABEL(hidden)&&g_str_equal(gtk_label_get_text(GTK_LABEL(hidden)),"true")))) {
        visible=FALSE;warming=TRUE;state("visible","0");
        gtk_widget_set_opacity(window,0);
        gtk_widget_add_tick_callback(window,warm_frame,NULL,NULL);
    } else if(!warming) {
        visible=TRUE;state("visible","1");
    }
    seen_window=TRUE;
    state("mapped","1");
    GtkWidget *preview=nav_find(window,"preview-stack");
    if(GTK_IS_STACK(preview))gtk_stack_set_transition_duration(GTK_STACK(preview),nav_find(window,"compact-motion")?140:220);
    if(!warming&&motion(window)) {
        pose(window,"enter",TRUE);pose(window,"entering",TRUE);
        g_object_set_data(G_OBJECT(window),"style-frames",NULL);
        guint tick=gtk_widget_add_tick_callback(window,enter_frame,NULL,NULL);
        g_object_set_data(G_OBJECT(window),"style-tick",GUINT_TO_POINTER(tick));
        guint timer=g_timeout_add_full(G_PRIORITY_DEFAULT,420,entrance_done,g_object_ref(window),g_object_unref);
        g_object_set_data(G_OBJECT(window),"style-timeout",GUINT_TO_POINTER(timer));
    }
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
