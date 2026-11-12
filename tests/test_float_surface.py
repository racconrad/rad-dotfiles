"""Verify native floating-card residency without a compositor."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeResidencyTests(unittest.TestCase):
    def test_hidden_warmup_parks_then_reuses_the_surface(self):
        library = ROOT / 'modules/desktop/files/.local/lib/raccon_menu'
        self.assertTrue((library / 'float_resident.h').is_file())
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef int gboolean;
typedef int gint;
typedef unsigned guint;
typedef char gchar;
typedef void *gpointer;
typedef struct { int mapped,input,focus,keyboard,parked,warming,frames,bound; double opacity; char *text; } GtkWidget;
typedef GtkWidget GtkWindow;
typedef GtkWidget GObject;
typedef GtkWidget GdkWindow;
typedef void GdkDisplay;
typedef void GdkFrameClock;
typedef void GParamSpec;
typedef struct { int empty; } cairo_region_t;
#define TRUE 1
#define FALSE 0
#define G_SOURCE_REMOVE 0
#define G_SOURCE_CONTINUE 1
#define GTK_WINDOW(x) (x)
#define GTK_WIDGET(x) (x)
#define GTK_LABEL(x) (x)
#define GTK_IS_LABEL(x) ((x)!=NULL)
#define G_OBJECT(x) (x)
#define GINT_TO_POINTER(x) ((void *)(intptr_t)(x))
#define GPOINTER_TO_UINT(x) ((guint)(intptr_t)(x))
#define GUINT_TO_POINTER(x) ((void *)(intptr_t)(x))
#define G_CALLBACK(x) (x)
static GtkWidget metadata;
static cairo_region_t region;
static void gtk_window_set_accept_focus(GtkWindow *w,int x){w->focus=x;}
static GdkWindow *gtk_widget_get_window(GtkWidget *w){return w;}
static GdkDisplay *gdk_window_get_display(GdkWindow *w){return w;}
static int gdk_display_supports_input_shapes(GdkDisplay *d){return 1;}
static cairo_region_t *cairo_region_create(void){return &region;}
static void cairo_region_destroy(cairo_region_t *r){}
static void gtk_widget_input_shape_combine_region(GtkWidget *w,cairo_region_t *r){w->input=!r;}
static void gtk_widget_set_opacity(GtkWidget *w,double x){w->opacity=x;}
static void g_object_set_data(GtkWidget *w,const char *key,void *v){
 int n=(intptr_t)v;
 if(!strcmp(key,"raccon-parked"))w->parked=n;
 if(!strcmp(key,"float-warming"))w->warming=n;
 if(!strcmp(key,"float-frames"))w->frames=n;
 if(!strcmp(key,"resident-bound"))w->bound=n;
}
static void *g_object_get_data(GtkWidget *w,const char *key){
 return (void *)(intptr_t)(!strcmp(key,"float-warming")?w->warming:!strcmp(key,"float-frames")?w->frames:w->bound);
}
static void gtk_widget_hide(GtkWidget *w){w->mapped=0;}
static void gtk_widget_show(GtkWidget *w){w->mapped=1;}
static int gtk_widget_get_mapped(GtkWidget *w){return w->mapped;}
void gtk_layer_set_keyboard_mode(GtkWindow *w,int m){w->keyboard=m;}
int gtk_layer_is_layer_window(GtkWindow *w){return 1;}
static GtkWidget *nav_find(GtkWidget *w,const char *key){return &metadata;}
static const char *gtk_label_get_text(GtkWidget *w){return w->text;}
static int g_str_equal(const char *a,const char *b){return !strcmp(a,b);}
#define g_signal_connect_object(...) ((void)0)
#define gtk_widget_add_tick_callback(...) ((void)0)
static int ready_state;
static const char *g_getenv(const char *s){return NULL;}
static const char *g_get_user_runtime_dir(void){return "/tmp";}
static int g_strcmp0(const char *a,const char *b){return a?strcmp(a,b):-1;}
static char *g_build_filename(const char *a,const char *b,void *unused){return (char *)b;}
static void g_free(void *p){}
static void g_file_set_contents(const char *p,const char *s,int len,void *error){ready_state=!strcmp(s,"1");}
#include "float_resident.h"
int main(void){
 GtkWidget w={.mapped=1,.input=1,.focus=1,.keyboard=1,.opacity=1}; metadata.text="false";
 assert(resident_bind(&w)); assert(!ready_state); assert(!w.input&&!w.focus&&w.opacity==0&&!w.keyboard);
 assert(resident_warm_frame(&w,NULL,NULL)==G_SOURCE_CONTINUE);
 assert(resident_warm_frame(&w,NULL,NULL)==G_SOURCE_CONTINUE);
 assert(resident_warm_frame(&w,NULL,NULL)==G_SOURCE_REMOVE);
 assert(!w.mapped&&w.parked&&!w.keyboard&&ready_state);
 metadata.text="true"; resident_changed(&metadata,NULL,&w);
 assert(w.mapped&&w.input&&w.focus&&w.opacity==1&&!w.parked);
 metadata.text="false"; resident_changed(&metadata,NULL,&w);
 assert(!w.mapped&&!w.input&&!w.focus&&!w.keyboard);
 metadata.text="true"; resident_changed(&metadata,NULL,&w);
 assert(w.mapped&&w.input&&w.focus&&w.opacity==1);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'test.c').write_text(source)
            result = subprocess.run(['cc', '-I', str(library), str(path / 'test.c'), '-o', str(path / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(path / 'test')], check=True)
