"""Popup trees stay resident while hidden surfaces release compositor input."""
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from test_desktop_events import Lines
from test_raccon_menu import menu

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT/'modules/desktop/files/.local/lib/raccon_menu'
BASE = ROOT/'modules/base/files/.local/lib'
sys.path.insert(0, str(BASE))


class SurfaceTests(unittest.TestCase):
    def test_popup_keyboard_handoff_never_keeps_an_exclusive_grab(self):
        files=[ROOT/'modules/desktop-styles/files/.local/lib/desktop_style/selector_input.c',LIB/'float_input.c']
        for i,path in enumerate(files):
            source=path.read_text()
            release=source.split('static gboolean release_keyboard(gpointer data) {',1)[1].split('\n}',1)[0]
            fixture='''
#include <assert.h>
typedef int gboolean;
typedef void *gpointer;
typedef struct {int mapped, mode;} GtkWidget;
#define GTK_WINDOW(w) (w)
#define G_OBJECT(w) (w)
static void *g_object_get_data(GtkWidget *w,const char *key) {return 0;}
#define G_SOURCE_REMOVE 0
static int visible=1,warming=0;
static int gtk_layer_is_layer_window(GtkWidget *w) {return 1;}
static int gtk_widget_get_mapped(GtkWidget *w) {return w->mapped;}
static void gtk_layer_set_keyboard_mode(GtkWidget *w,int m) {w->mode=m;}
static gboolean release_keyboard(gpointer data) {BODY
}
int main(void) {
 GtkWidget w={.mapped=1,.mode=1}; release_keyboard(&w); assert(w.mode==2);
 w.mapped=0; w.mode=1; release_keyboard(&w); assert(w.mode==0);
 EXTRA
}
'''.replace('BODY',release).replace('EXTRA','w.mapped=1; visible=0; release_keyboard(&w); assert(w.mode==0); visible=1; warming=1; release_keyboard(&w); assert(w.mode==0);' if i==0 else '')
            with tempfile.TemporaryDirectory() as temp:
                temp=Path(temp);(temp/'test.c').write_text(fixture)
                subprocess.run(['cc',str(temp/'test.c'),'-o',str(temp/'test')],check=True,capture_output=True)
                subprocess.run([str(temp/'test')],check=True)

    def test_hidden_surface_unmaps_and_releases_input_then_reacquires_on_open(self):
        # Exercise the production helper with a GDK boundary fixture: no display
        # or compositor is required to verify input/focus/mapping invariants.
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef int gboolean;
typedef int gint;
#define TRUE 1
#define FALSE 0
#define GTK_WINDOW(x) (x)
#define G_OBJECT(x) (x)
#define GINT_TO_POINTER(x) ((void *)(intptr_t)(x))
typedef struct { int mapped, input, focus, keyboard, parked; double opacity; } GtkWidget;
typedef GtkWidget GtkWindow;
typedef GtkWidget GdkWindow;
typedef void GdkDisplay;
typedef struct { int empty; } cairo_region_t;
static int shapes = 1, hides, shows;
static cairo_region_t empty_region;
static void gtk_window_set_accept_focus(GtkWindow *w,int value) { w->focus=value; }
static GdkWindow *gtk_widget_get_window(GtkWidget *w) { return w; }
static GdkDisplay *gdk_window_get_display(GdkWindow *w) { return w; }
static int gdk_display_supports_input_shapes(GdkDisplay *d) { return shapes; }
static cairo_region_t *cairo_region_create(void) { return &empty_region; }
static void cairo_region_destroy(cairo_region_t *r) { }
static void gtk_widget_input_shape_combine_region(GtkWidget *w,cairo_region_t *r) { w->input=r?0:1; }
static void gtk_widget_set_opacity(GtkWidget *w,double opacity) { w->opacity=opacity; }
static void g_object_set_data(GtkWidget *w,const char *key,void *value) { w->parked=(intptr_t)value; }
static void gtk_widget_hide(GtkWidget *w) { hides++;w->mapped=0; }
static void gtk_widget_show(GtkWidget *w) { shows++;w->mapped=1; }
static int gtk_widget_get_mapped(GtkWidget *w) { return w->mapped; }
void gtk_layer_set_keyboard_mode(GtkWindow *w,int mode) { w->keyboard=mode; }
int gtk_layer_is_layer_window(GtkWindow *w) { return 1; }
#include "resident_surface.h"
int main(void) {
 GtkWidget w={.mapped=1,.input=1,.focus=1,.keyboard=2,.opacity=1};
 for(int i=0;i<1000;i++) {
  resident_surface_park(&w);
  assert(!w.mapped && !w.input && !w.focus && !w.keyboard && w.parked && w.opacity==0);
  resident_surface_show(&w);
  assert(w.mapped && w.input && w.focus && w.keyboard==1 && !w.parked);
 }
 assert(hides==1000 && shows==1000);
 shapes=0;
 GtkWidget fallback={.mapped=1,.input=1,.focus=1,.keyboard=2};
 resident_surface_park(&fallback);
 assert(!fallback.mapped && !fallback.focus && !fallback.keyboard);
 resident_surface_show(&fallback);
 assert(fallback.mapped && fallback.focus && hides==1001 && shows==1001);
}
'''
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'test.c';path.write_text(source)
            subprocess.run(['cc','-std=c11','-I',str(LIB),str(path),'-o',str(root/'test')],check=True,capture_output=True)
            subprocess.run([str(root/'test')],check=True)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        p=patch.object(menu,'RUNTIME',self.root);p.start();self.addCleanup(p.stop)

    def test_prepare_does_no_work_for_a_ready_resident(self):
        (self.root/'ready').write_text('1')
        with patch.object(menu,'native_send',return_value=True),patch.object(menu,'show') as show:
            menu.prepare_resident()
            show.assert_not_called()

    def test_prepare_waits_for_readiness_and_not_just_a_mapped_window(self):
        (self.root/'ready').write_text('0')
        def warmed():
            time.sleep(.08);temp=self.root/'.ready';temp.write_text('1');temp.replace(self.root/'ready')
        worker=threading.Thread(target=warmed);worker.start()
        with patch.object(menu,'show') as show:
            started=time.monotonic();menu.prepare_resident()
            self.assertGreaterEqual(time.monotonic()-started,.06)
            show.assert_called_once_with('home',prewarm=True)
        worker.join()

    def test_login_race_retries_then_prepares(self):
        calls=[]
        def show(*args,**kwargs):
            calls.append(args)
            if len(calls)==1:raise RuntimeError('Eww is still starting')
            (self.root/'ready').write_text('1')
        with patch.object(menu,'show',side_effect=show),patch.object(menu.time,'sleep') as delay:
            menu.prepare_resident()
            self.assertEqual(len(calls),2)
            delay.assert_called_once_with(.2)



class CatalogueTests(unittest.TestCase):
    def test_installs_refresh_apps_and_identical_metadata_is_not_republished(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);data=root/'data';(data/'applications').mkdir(parents=True)
            env={**os.environ,'HOME':str(root),'XDG_STATE_HOME':str(root/'state'),
                 'XDG_DATA_HOME':str(data),'XDG_DATA_DIRS':str(root/'system'),
                 'PYTHONPATH':str(LIB)}
            child=subprocess.Popen([sys.executable,'-u',str(LIB/'backend.py'),'watch-catalogue'],
                                   env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                output=Lines(child)
                self.assertEqual(output.get()['apps'],[])
                desktop=data/'applications/raccon-fixture.desktop'
                text='[Desktop Entry]\nType=Application\nName=Raccon Fixture\nExec=/bin/true\nIcon=application-default-icon\n'
                # Wait until GIO has enumerated/armed its app-directory monitors.
                deadline=time.monotonic()+2
                while not (root/'state/raccon-menu/apps.json').exists() and time.monotonic()<deadline:time.sleep(.01)
                desktop.write_text(text)
                value=output.until(lambda value:bool(value['apps']))
                self.assertEqual(value['apps'][0]['id'],'raccon-fixture.desktop')
                desktop.write_text(text)
                self.assertFalse(select.select([child.stdout],[],[],.4)[0])
                desktop.unlink()
                self.assertEqual(output.get()['apps'],[])
            finally:
                child.terminate();child.communicate(timeout=3)
