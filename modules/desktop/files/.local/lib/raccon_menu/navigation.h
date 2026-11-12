/* Shared GTK keyboard navigation; no subprocess per arrow key. */
#include <gtk/gtk.h>
static gboolean nav_class(GtkWidget *w, const gchar *name) {
    return gtk_style_context_has_class(gtk_widget_get_style_context(w), name);
}
static GtkWidget *nav_find(GtkWidget *w, const gchar *name) {
    if (nav_class(w,name)) return w;
    if (!GTK_IS_CONTAINER(w)) return NULL;
    GList *children=gtk_container_get_children(GTK_CONTAINER(w)); GtkWidget *found=NULL;
    for (GList *it=children;it&&!found;it=it->next) found=nav_find(it->data,name);
    g_list_free(children);return found;
}
static void nav_collect(GtkWidget *w,GPtrArray *out,const gchar *klass) {
    if (!gtk_widget_get_mapped(w)||!gtk_widget_is_sensitive(w)) return;
    if (gtk_widget_get_can_focus(w) && (!klass || nav_class(w,klass)) &&
        (GTK_IS_BUTTON(w)||GTK_IS_ENTRY(w)||GTK_IS_RANGE(w)||GTK_IS_SWITCH(w)||GTK_IS_CALENDAR(w))) g_ptr_array_add(out,w);
    if (!GTK_IS_CONTAINER(w)) return;
    GList *children=gtk_container_get_children(GTK_CONTAINER(w));
    for(GList *it=children;it;it=it->next) nav_collect(it->data,out,klass);
    g_list_free(children);
}
static void nav_focus(GtkWidget *w) {
    gtk_widget_grab_focus(w);
    for(GtkWidget *p=gtk_widget_get_parent(w);p;p=gtk_widget_get_parent(p)) {
        if(!GTK_IS_SCROLLED_WINDOW(p)) continue;
        GtkWidget *content=gtk_bin_get_child(GTK_BIN(p));
        if(GTK_IS_VIEWPORT(content)) content=gtk_bin_get_child(GTK_BIN(content));
        gint x,y;
        if(content && gtk_widget_translate_coordinates(w,content,0,0,&x,&y)) {
            GtkAdjustment *a=gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(p));
            gdouble top=gtk_adjustment_get_value(a),size=gtk_adjustment_get_page_size(a);
            if(y<top) gtk_adjustment_set_value(a,y);
            else if(y+gtk_widget_get_allocated_height(w)>top+size)
                gtk_adjustment_set_value(a,y+gtk_widget_get_allocated_height(w)-size);
        }
    }
}
static gboolean nav_nth(GtkWidget *root,const gchar *klass,guint index,gboolean activate) {
    GPtrArray *items=g_ptr_array_new(); nav_collect(root,items,klass);
    gboolean found=index<items->len;
    if(found) {GtkWidget *w=g_ptr_array_index(items,index);nav_focus(w);if(activate&&GTK_IS_BUTTON(w))gtk_button_clicked(GTK_BUTTON(w));}
    g_ptr_array_unref(items);return found;
}
static gdouble nav_score(gdouble dx,gdouble dy,guint key) {
    gdouble along=0,cross=0;
    switch(key) {
        case GDK_KEY_Left:along=-dx;cross=ABS(dy);break;
        case GDK_KEY_Right:along=dx;cross=ABS(dy);break;
        case GDK_KEY_Up:along=-dy;cross=ABS(dx);break;
        case GDK_KEY_Down:along=dy;cross=ABS(dx);break;
        default:return G_MAXDOUBLE;
    }
    return along>1 ? along+cross*4 : G_MAXDOUBLE;
}
static gboolean nav_key(GtkWidget *window,GdkEventKey *event) {
    guint key=event->keyval; GtkWidget *focus=gtk_window_get_focus(GTK_WINDOW(window));
    if(event->state&(GDK_CONTROL_MASK|GDK_MOD1_MASK|GDK_SUPER_MASK)) return FALSE;
    if(GTK_IS_CALENDAR(focus))return FALSE;
    if(key==GDK_KEY_Return||key==GDK_KEY_KP_Enter||key==GDK_KEY_space) {
        if(!focus||(!GTK_IS_BUTTON(focus)&&!GTK_IS_SWITCH(focus)))return FALSE;
        if(!g_object_get_data(G_OBJECT(window),"nav-held")) {
            g_object_set_data(G_OBJECT(window),"nav-held",GUINT_TO_POINTER(key));
            if(GTK_IS_BUTTON(focus))gtk_button_clicked(GTK_BUTTON(focus));
            else gtk_switch_set_active(GTK_SWITCH(focus),!gtk_switch_get_active(GTK_SWITCH(focus)));
        }
        return TRUE;
    }
    if((key==GDK_KEY_Page_Down||key==GDK_KEY_Page_Up)&&!GTK_IS_EDITABLE(focus)&&!GTK_IS_RANGE(focus)) {
        GdkEventKey step=*event;step.keyval=key==GDK_KEY_Page_Down?GDK_KEY_Down:GDK_KEY_Up;
        for(guint i=0;i<3;i++)nav_key(window,&step);
        return TRUE;
    }
    if(key!=GDK_KEY_Left&&key!=GDK_KEY_Right&&key!=GDK_KEY_Up&&key!=GDK_KEY_Down)return FALSE;
    /* Keep editing and slider-axis steps; perpendicular arrows leave the control. */
    gboolean horizontal=key==GDK_KEY_Left||key==GDK_KEY_Right;
    if(GTK_IS_EDITABLE(focus)&&horizontal)return FALSE;
    if(GTK_IS_RANGE(focus)&&horizontal==
       (gtk_orientable_get_orientation(GTK_ORIENTABLE(focus))==GTK_ORIENTATION_HORIZONTAL))return FALSE;
    GPtrArray *items=g_ptr_array_new();nav_collect(window,items,NULL);
    gint fx=0,fy=0;
    if(focus) {gtk_widget_translate_coordinates(focus,window,0,0,&fx,&fy);fx+=gtk_widget_get_allocated_width(focus)/2;fy+=gtk_widget_get_allocated_height(focus)/2;}
    GtkWidget *best=NULL;gdouble score=G_MAXDOUBLE;
    for(guint i=0;i<items->len;i++) {
        GtkWidget *w=g_ptr_array_index(items,i);if(w==focus||nav_class(w,"video-preview"))continue;
        gint x,y;if(!gtk_widget_translate_coordinates(w,window,0,0,&x,&y))continue;
        gdouble candidate=nav_score(x+gtk_widget_get_allocated_width(w)/2-fx,y+gtk_widget_get_allocated_height(w)/2-fy,key);
        if(!focus||candidate<score){best=w;score=candidate;if(!focus)break;}
    }
    if(best)nav_focus(best);
    g_ptr_array_unref(items);return TRUE;
}
static gboolean nav_release(GtkWidget *window,GdkEventKey *event) {
    if(GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(window),"nav-held"))==event->keyval) {
        g_object_set_data(G_OBJECT(window),"nav-held",NULL);return TRUE;
    }
    return FALSE;
}
