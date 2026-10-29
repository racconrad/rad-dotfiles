"""Small, themed layer surfaces. No fullscreen surface or pointer interception."""
import json
import math
import os
from pathlib import Path
import socket
import sys

DEFAULT = {'radius': 8, 'font': 'Inter', 'colors': {'surface_container': '#1c2024',
           'on_surface': '#e0e2e8', 'on_surface_variant': '#c2c7cf', 'primary': '#9ccbfb'}}


def theme():
    path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))/'desktop-style/current/tokens.json'
    try:
        tokens = json.loads(path.read_text())
        return {**DEFAULT, **tokens, 'colors': {**DEFAULT['colors'], **tokens.get('colors', {})}}
    except (OSError, ValueError, TypeError):
        return DEFAULT


def color(cr, value, alpha=1):
    rgb = value.lstrip('#')[:6]
    try: channels = [int(rgb[i:i+2], 16)/255 for i in (0,2,4)]
    except ValueError: channels = [.6,.8,1]
    cr.set_source_rgba(*channels, alpha)


def rounded(cr, x, y, width, height, radius):
    radius = max(0, min(radius, width/2, height/2))
    if not radius:
        cr.rectangle(x,y,width,height); return
    for cx,cy,start in ((x+width-radius,y+radius,-math.pi/2), (x+width-radius,y+height-radius,0),
                        (x+radius,y+height-radius,math.pi/2), (x+radius,y+radius,math.pi)):
        cr.arc(cx,cy,radius,start,start+math.pi/2)
    cr.close_path()


def label(cr, text, x, y, width, font, size, bold=False):
    import gi
    gi.require_version('Pango', '1.0'); gi.require_version('PangoCairo', '1.0')
    from gi.repository import Pango, PangoCairo
    layout = PangoCairo.create_layout(cr)
    desc = Pango.FontDescription(); desc.set_family(font); desc.set_size(size*Pango.SCALE)
    if bold: desc.set_weight(Pango.Weight.SEMIBOLD)
    layout.set_font_description(desc); layout.set_width(int(width*Pango.SCALE))
    layout.set_ellipsize(Pango.EllipsizeMode.END); layout.set_single_paragraph_mode(True)
    layout.set_text(text,-1); cr.move_to(x,y); PangoCairo.show_layout(cr,layout)


def arrow(cr, x, y, direction, size=6):
    vectors = {'left':(-1,0), 'right':(1,0), 'up':(0,-1), 'down':(0,1)}
    dx,dy = vectors[direction]
    cr.move_to(x-dx*size,y-dy*size); cr.line_to(x+dx*size,y+dy*size)
    cr.move_to(x+dx*size-dy*size*.65-dx*size*.65, y+dy*size+dx*size*.65-dy*size*.65)
    cr.line_to(x+dx*size,y+dy*size)
    cr.line_to(x+dx*size+dy*size*.65-dx*size*.65, y+dy*size-dx*size*.65-dy*size*.65)
    cr.stroke()


def paint_hud(cr, width, height, state, tokens):
    colors = tokens['colors']; radius = tokens.get('radius',8)
    color(cr, colors['surface_container']); rounded(cr,0,0,width,height,radius); cr.fill()
    mode = state.get('mode'); preview = state.get('preview')
    if mode:
        title = {'resize':'Resize', 'move':'Move into split', 'preselect':'Next window'}[mode]
        subtitle = 'Choose a direction · Esc' if mode=='preselect' else 'Arrows · Enter / Esc'
    elif preview:
        title = 'Next window · '+preview['direction'].capitalize()
        subtitle = 'Super+Esc to cancel'
    else:
        title = state.get('hint') or ''
        subtitle = None
    color(cr, colors['on_surface'])
    label(cr,title,16,8 if subtitle else 17,width-140 if (mode or preview) else width-32,tokens['font'],11,True)
    if subtitle:
        color(cr,colors['on_surface_variant']); label(cr,subtitle,16,29,width-135,tokens['font'],9)
    if mode or preview:
        color(cr,colors['primary']); cr.set_line_width(1.7); cr.set_line_cap(1)
        if preview:
            arrow(cr,width-38,height/2,preview['direction'],9)
        else:
            for direction,x,y in (('left',width-100,32),('up',width-76,18),('down',width-76,39),('right',width-52,32)):
                arrow(cr,x,y,direction,5)


def paint_preview(cr, width, height, tokens):
    color(cr,tokens['colors']['primary'],.13)
    rounded(cr,1,1,width-2,height-2,tokens.get('radius',8)); cr.fill_preserve()
    color(cr,tokens['colors']['primary'],.85); cr.set_line_width(2); cr.stroke()


def main():
    import cairo
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import Gtk, Gdk, GLib, GtkLayerShell
    ui_path, control_path = map(Path,sys.argv[1:3])
    Gtk.init([])
    state = {}; tokens = theme(); last = None; theme_stamp = None
    windows = []
    for name in ('hud','preview'):
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_title('Raccon Tiling '+name); window.set_decorated(False); window.set_app_paintable(True)
        window.set_visual(window.get_screen().get_rgba_visual())
        GtkLayerShell.init_for_window(window); GtkLayerShell.set_namespace(window,'raccon-tiling-'+name)
        GtkLayerShell.set_layer(window,GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_exclusive_zone(window,-1)
        GtkLayerShell.set_keyboard_mode(window,GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_anchor(window,GtkLayerShell.Edge.TOP,True)
        if name=='preview': GtkLayerShell.set_anchor(window,GtkLayerShell.Edge.LEFT,True)
        area = Gtk.DrawingArea(); window.add(area)
        def draw(widget,cr,kind=name):
            cr.set_operator(cairo.OPERATOR_SOURCE); cr.set_source_rgba(0,0,0,0); cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            if kind=='hud': paint_hud(cr,widget.get_allocated_width(),widget.get_allocated_height(),state,tokens)
            else: paint_preview(cr,widget.get_allocated_width(),widget.get_allocated_height(),tokens)
            return False
        area.connect('draw',draw)
        window.connect('realize',lambda widget: widget.get_window().input_shape_combine_region(cairo.Region(),0,0))
        windows.append(window)
    hud, preview = windows
    def send(*args):
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(1); client.connect(str(control_path))
                client.sendall((' '.join(args)+'\n').encode()); client.recv(65536)
        except OSError:
            hud.hide(); preview.hide()
    def on_key(widget,event):
        name = Gdk.keyval_name(event.keyval)
        key = {'Left':'left','Right':'right','Up':'up','Down':'down','h':'left','l':'right','k':'up','j':'down',
               'Escape':'escape','Return':'enter','KP_Enter':'enter'}.get(name)
        if key: send('key',key)
        return True
    hud.connect('key-press-event',on_key)
    def poll():
        nonlocal state,last,tokens,theme_stamp
        try:
            stamp = ui_path.stat().st_mtime_ns
            token_path = Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'desktop-style/current/tokens.json'
            token_stamp = token_path.stat().st_mtime_ns if token_path.exists() else 0
            if stamp==last and token_stamp==theme_stamp: return True
            state = json.loads(ui_path.read_text()); last = stamp
            theme_stamp = token_stamp
        except (OSError,ValueError):
            return True
        tokens = theme()
        visible = bool(state.get('mode') or state.get('preview') or state.get('hint'))
        if not visible:
            GtkLayerShell.set_keyboard_mode(hud,GtkLayerShell.KeyboardMode.NONE)
            hud.hide(); preview.hide(); return True
        geometry = state.get('output_geometry') or {'x':0,'y':0,'width':1920,'height':1080}
        display = Gdk.Display.get_default()
        monitors = [display.get_monitor(i) for i in range(display.get_n_monitors())]
        monitor = min(monitors,key=lambda m:abs(m.get_geometry().x-geometry['x'])+abs(m.get_geometry().y-geometry['y']))
        for window in windows: GtkLayerShell.set_monitor(window,monitor)
        hud.set_size_request(min(440,geometry['width']-32),56)
        hud.resize(min(440,geometry['width']-32),56)
        GtkLayerShell.set_margin(hud,GtkLayerShell.Edge.TOP,28)
        GtkLayerShell.set_keyboard_mode(hud,GtkLayerShell.KeyboardMode.EXCLUSIVE if state.get('mode') else GtkLayerShell.KeyboardMode.NONE)
        hud.show_all(); hud.queue_draw()
        if state.get('preview'):
            g = state['preview']['geometry']
            width = max(2,min(g['width'],geometry['width'])); height = max(2,min(g['height'],geometry['height']))
            preview.set_size_request(width,height)
            preview.resize(width,height)
            GtkLayerShell.set_margin(preview,GtkLayerShell.Edge.LEFT,max(0,min(g['x'],geometry['width']-width)))
            GtkLayerShell.set_margin(preview,GtkLayerShell.Edge.TOP,max(0,min(g['y'],geometry['height']-height)))
            preview.show_all(); preview.queue_draw()
        else: preview.hide()
        return True
    GLib.timeout_add(60,poll)
    Gtk.main()


if __name__=='__main__':
    main()
