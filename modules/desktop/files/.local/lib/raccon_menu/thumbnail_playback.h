/* Only the active thumbnail redraws; decoded frames never pass through Eww/CSS. */
#include <stdio.h>
#include <setjmp.h>
#include <jpeglib.h>
typedef struct {struct jpeg_error_mgr base;jmp_buf jump;} FrameError;
typedef struct {struct jpeg_decompress_struct jpeg;FrameError error;FILE *file;GdkPixbuf *pixbuf;gboolean created;} FrameDecode;
static void frame_error(j_common_ptr jpeg) {longjmp(((FrameError*)jpeg->err)->jump,1);}
/* Decode locally: the system GdkPixbuf loader delegates JPEG to a D-Bus service. */
static GdkPixbuf *frame_load(const gchar *path) {
    FrameDecode *ctx=g_new0(FrameDecode,1);GdkPixbuf *result=NULL;
    ctx->file=fopen(path,"rb");if(!ctx->file){g_free(ctx);return NULL;}
    ctx->jpeg.err=jpeg_std_error(&ctx->error.base);ctx->error.base.error_exit=frame_error;
    if(setjmp(ctx->error.jump))goto done;
    jpeg_create_decompress(&ctx->jpeg);ctx->created=TRUE;jpeg_stdio_src(&ctx->jpeg,ctx->file);
    if(jpeg_read_header(&ctx->jpeg,TRUE)!=JPEG_HEADER_OK)goto done;
    if(ctx->jpeg.image_width>512||ctx->jpeg.image_height>512)goto done;
    ctx->jpeg.out_color_space=JCS_RGB;jpeg_start_decompress(&ctx->jpeg);
    ctx->pixbuf=gdk_pixbuf_new(GDK_COLORSPACE_RGB,FALSE,8,ctx->jpeg.output_width,ctx->jpeg.output_height);
    if(!ctx->pixbuf)goto done;
    while(ctx->jpeg.output_scanline<ctx->jpeg.output_height) {
        JSAMPROW row=gdk_pixbuf_get_pixels(ctx->pixbuf)+ctx->jpeg.output_scanline*gdk_pixbuf_get_rowstride(ctx->pixbuf);
        jpeg_read_scanlines(&ctx->jpeg,&row,1);
    }
    jpeg_finish_decompress(&ctx->jpeg);result=ctx->pixbuf;ctx->pixbuf=NULL;
done:
    if(ctx->pixbuf)g_object_unref(ctx->pixbuf);
    if(ctx->created)jpeg_destroy_decompress(&ctx->jpeg);
    fclose(ctx->file);g_free(ctx);return result;
}
static GtkWidget *play_target;
static GPtrArray *play_frames;
static guint play_timer;
static gint64 play_started;
static void play_clear(void) {
    if(play_timer){g_source_remove(play_timer);play_timer=0;}
    if(play_target){gtk_widget_queue_draw(play_target);g_object_remove_weak_pointer(G_OBJECT(play_target),(gpointer*)&play_target);play_target=NULL;}
    if(play_frames){g_ptr_array_unref(play_frames);play_frames=NULL;}
}
static gboolean play_tick(gpointer data) {
    if(!play_target||!gtk_widget_get_mapped(play_target)){play_timer=0;play_clear();return G_SOURCE_REMOVE;}
    gtk_widget_queue_draw(play_target);return G_SOURCE_CONTINUE;
}
static gboolean play_draw(GtkWidget *w,cairo_t *cr,gpointer unused) {
    if(w!=play_target||!play_frames||!play_frames->len)return FALSE;
    guint index=((g_get_monotonic_time()-play_started)*12/1000000)%play_frames->len;
    GdkPixbuf *frame=g_ptr_array_index(play_frames,index);
    gint width=gtk_widget_get_allocated_width(w),height=gtk_widget_get_allocated_height(w),radius=0;
    gtk_style_context_get(gtk_widget_get_style_context(w),gtk_widget_get_state_flags(w),"border-radius",&radius,NULL);
    gdouble r=MIN(radius,MIN(width,height)/2);
    cairo_save(cr);cairo_new_sub_path(cr);
    cairo_arc(cr,width-r,r,r,-G_PI/2,0);cairo_arc(cr,width-r,height-r,r,0,G_PI/2);
    cairo_arc(cr,r,height-r,r,G_PI/2,G_PI);cairo_arc(cr,r,r,r,G_PI,3*G_PI/2);cairo_close_path(cr);cairo_clip(cr);
    gdk_cairo_set_source_pixbuf(cr,frame,(width-gdk_pixbuf_get_width(frame))/2.,(height-gdk_pixbuf_get_height(frame))/2.);
    cairo_paint(cr);
    GtkWidget *button=gtk_widget_get_parent(w);
    if(button&&gtk_widget_has_focus(button)) {
        GdkRGBA *color=NULL;
        gtk_style_context_get(gtk_widget_get_style_context(w),gtk_widget_get_state_flags(w),"outline-color",&color,NULL);
        if(color) {gdk_cairo_set_source_rgba(cr,color);cairo_set_line_width(cr,3);cairo_rectangle(cr,1.5,1.5,width-3,height-3);cairo_stroke(cr);gdk_rgba_free(color);}
    }
    cairo_restore(cr);return FALSE;
}
static GtkWidget *play_find(GtkWidget *w,const gchar *key) {
    if(GTK_IS_BUTTON(w)&&nav_class(w,"wall-tile")) {
        GtkWidget *label=nav_find(w,"preview-target");
        if(GTK_IS_LABEL(label)&&g_strcmp0(gtk_label_get_text(GTK_LABEL(label)),key)==0)return nav_find(w,"wall-thumb");
    }
    if(!GTK_IS_CONTAINER(w))return NULL;
    GList *children=gtk_container_get_children(GTK_CONTAINER(w));GtkWidget *found=NULL;
    for(GList *it=children;it&&!found;it=it->next)found=play_find(it->data,key);
    g_list_free(children);return found;
}
static void play_update(GObject *object,GParamSpec *param,gpointer unused) {
    play_clear();
    const gchar *text=gtk_label_get_text(GTK_LABEL(object));
    gchar **parts=g_strsplit(text,"\n",2);
    if(!parts[0]||!parts[1]||!*parts[1]){g_strfreev(parts);return;}
    gchar *key=g_strdup(parts[0]);for(gchar *p=key;*p;p++)if(*p==':')*p=' ';
    GtkWidget *target=play_find(gtk_widget_get_toplevel(GTK_WIDGET(object)),key);g_free(key);
    if(target) {
        GPtrArray *frames=g_ptr_array_new_with_free_func(g_object_unref);
        for(guint i=1;i<=48;i++) {
            gchar *name=g_strdup_printf("%03u.jpg",i),*path=g_build_filename(parts[1],name,NULL);g_free(name);
            GdkPixbuf *frame=frame_load(path);g_free(path);
            if(!frame)break;
            g_ptr_array_add(frames,frame);
        }
        if(frames->len) {
            play_frames=frames;play_target=target;
            g_object_add_weak_pointer(G_OBJECT(target),(gpointer*)&play_target);
            play_started=g_get_monotonic_time();play_timer=g_timeout_add(83,play_tick,NULL);gtk_widget_queue_draw(target);
        }else g_ptr_array_unref(frames);
    }
    g_strfreev(parts);
}
