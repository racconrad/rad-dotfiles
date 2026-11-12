"""Run native key handlers against a headless widget boundary, without a display."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / 'modules/desktop/files/.local/lib/raccon_menu'
HARNESS = r'''
#include <gtk/gtk.h>
typedef struct Fake Fake;
struct Fake { int kind, x, y, clicks; gboolean mapped, sensitive; const char *klass; char *text; Fake *focus; Fake *children[8]; guint count, held; };
static Fake *active_window;
static gboolean kind(gpointer w, int value) { return w && ((Fake *)w)->kind == value; }
static gboolean classified(gpointer w, const char *name) { return w && !g_strcmp0(((Fake *)w)->klass, name); }
static GList *fake_children(gpointer w) { GList *list=NULL; for(guint i=0;i<((Fake *)w)->count;i++)list=g_list_append(list,((Fake *)w)->children[i]); return list; }
static gboolean coordinates(gpointer w,gpointer root,int x,int y,int *out_x,int *out_y) { *out_x=((Fake *)w)->x;*out_y=((Fake *)w)->y;return TRUE; }
static void focus(gpointer w) {active_window->focus=w;}
static void clicked(gpointer w) {((Fake *)w)->clicks++;}
static void text(gpointer w,const char *value) {g_free(((Fake *)w)->text);((Fake *)w)->text=g_strdup(value);}
#undef GTK_IS_WIDGET
#undef GTK_IS_CONTAINER
#undef GTK_IS_BUTTON
#undef GTK_IS_ENTRY
#undef GTK_IS_EDITABLE
#undef GTK_IS_RANGE
#undef GTK_IS_SWITCH
#undef GTK_IS_CALENDAR
#undef GTK_WINDOW
#undef GTK_CONTAINER
#undef GTK_BUTTON
#undef GTK_ENTRY
#undef GTK_SWITCH
#undef G_OBJECT
#define GTK_IS_WIDGET(w) ((w)!=NULL)
#define GTK_IS_CONTAINER(w) ((w)&&((Fake *)(w))->count)
#define GTK_IS_BUTTON(w) kind(w,1)
#define GTK_IS_ENTRY(w) kind(w,2)
#define GTK_IS_EDITABLE(w) kind(w,2)
#define GTK_IS_RANGE(w) kind(w,3)
#define GTK_IS_SWITCH(w) kind(w,4)
#define GTK_IS_CALENDAR(w) kind(w,5)
#define GTK_WINDOW(w) ((GtkWindow *)(w))
#define GTK_CONTAINER(w) ((GtkContainer *)(w))
#define GTK_BUTTON(w) ((GtkButton *)(w))
#define GTK_ENTRY(w) ((GtkEntry *)(w))
#define GTK_SWITCH(w) ((GtkSwitch *)(w))
#define G_OBJECT(w) ((GObject *)(w))
#define gtk_widget_get_style_context(w) ((GtkStyleContext *)(w))
#define gtk_style_context_has_class(w,n) classified(w,n)
#define gtk_widget_get_mapped(w) (((Fake *)(w))->mapped)
#define gtk_widget_is_sensitive(w) (((Fake *)(w))->sensitive)
#define gtk_widget_get_can_focus(w) (((Fake *)(w))->kind>0)
#define gtk_container_get_children(w) fake_children(w)
#define gtk_widget_grab_focus(w) focus(w)
#define gtk_widget_get_parent(w) NULL
#define gtk_orientable_get_orientation(w) GTK_ORIENTATION_HORIZONTAL
#define gtk_widget_translate_coordinates(w,r,x,y,a,b) coordinates(w,r,x,y,a,b)
#define gtk_widget_get_allocated_width(w) 20
#define gtk_widget_get_allocated_height(w) 20
#define gtk_window_get_focus(w) ((GtkWidget *)((Fake *)(w))->focus)
#define gtk_button_clicked(w) clicked(w)
#define gtk_entry_get_text(w) (((Fake *)(w))->text)
#define gtk_entry_set_text(w,v) text(w,v)
#define g_object_get_data(w,n) GUINT_TO_POINTER(((Fake *)(w))->held)
#define g_object_set_data(w,n,v) (((Fake *)(w))->held=GPOINTER_TO_UINT(v))
#include "INPUT_SOURCE"
static Fake widget(int kind, const char *klass, int x,int y) { return (Fake){.kind=kind,.klass=klass,.mapped=TRUE,.sensitive=TRUE,.x=x,.y=y,.text=g_strdup("")}; }
int main(void) {
    Fake window=widget(0,"window",0,0), entry=widget(2,"app-search",0,0);
    Fake button=widget(1,"app-launch",0,100), slider=widget(3,"slider",0,200);
    window.children[0]=&entry;window.children[1]=&button;window.children[2]=&slider;window.count=3;
    active_window=&window;window.focus=&entry;
    GdkEventKey e={0};e.keyval=GDK_KEY_Down;
    g_assert(nav_key((GtkWidget *)&window,&e));g_assert(window.focus==&button);
    window.focus=&entry;e.keyval=GDK_KEY_Left;g_assert(!nav_key((GtkWidget *)&window,&e));
    window.focus=&slider;e.keyval=GDK_KEY_Up;
    g_assert(nav_key((GtkWidget *)&window,&e));g_assert(window.focus==&button);
    window.focus=&slider;e.keyval=GDK_KEY_Right;g_assert(!nav_key((GtkWidget *)&window,&e));
    window.focus=&button;e.keyval=GDK_KEY_Return;
    g_assert(nav_key((GtkWidget *)&window,&e));g_assert(nav_key((GtkWidget *)&window,&e));g_assert_cmpint(button.clicks,==,1);
    g_assert(nav_release((GtkWidget *)&window,&e));g_assert(nav_key((GtkWidget *)&window,&e));g_assert_cmpint(button.clicks,==,2);
    nav_release((GtkWidget *)&window,&e);
    Fake back=widget(1,"service-back",0,300);window.children[3]=&back;window.count=4;
    menu_window=(GtkWidget *)&window;current_page=6;
    text(&entry,"audio");e.keyval=GDK_KEY_Escape;
    g_assert(key_press(menu_window,&e,NULL));g_assert_cmpstr(entry.text,==,"");g_assert_cmpuint(current_page,==,6);g_assert_cmpint(back.clicks,==,0);
    g_assert(key_press(menu_window,&e,NULL));g_assert_cmpint(back.clicks,==,1);g_assert_cmpuint(current_page,==,6);
    back.sensitive=FALSE;g_assert(!nav_nth(menu_window,"service-back",0,TRUE));
    back.sensitive=TRUE;back.mapped=FALSE;g_assert(!nav_nth(menu_window,"service-back",0,TRUE));
    Fake keys=widget(2,"keys-search",0,0), keyrow=widget(1,"key-row",0,100);
    window.children[0]=&keys;window.children[1]=&keyrow;window.count=2;window.focus=&keys;current_page=8;
    e.keyval=GDK_KEY_Down;g_assert(key_press(menu_window,&e,NULL));g_assert(window.focus==&keyrow);
    return 0;
}
'''


class NavigationKeyTests(unittest.TestCase):
    def test_native_arrows_activation_and_nested_escape(self):
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True))
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory) / 'keys.c', Path(directory) / 'keys'
            source.write_text(HARNESS.replace('INPUT_SOURCE', str(LIB / 'input.c')))
            built = subprocess.run(['cc', str(source), '-o', str(binary), *flags], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
