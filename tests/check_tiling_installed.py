#!/usr/bin/env python3
"""Real Wayfire test of the staged tiler with private animated GTK clients.

No user workspace, focus, window geometry or floating-mode state is modified.
"""
import importlib.machinery,importlib.util,json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'modules/wayfire/files/.local/bin/wf-tile'
with tempfile.TemporaryDirectory(prefix='dwindle-preflight-') as temporary:
 with socket.socket(socket.AF_UNIX) as probe:
  try:probe.bind(str(Path(temporary)/'probe.sock'))
  except PermissionError:
   raise SystemExit('El entorno bloquea sockets. Ejecutá esta prueba desde una terminal normal.')
base=Path(tempfile.mkdtemp(prefix='dwindle-check-'))
config=base/'wayfire.ini';config.write_text('''[core]
plugins = ipc ipc-rules simple-tile move resize wsets wm-actions vswitch
xwayland = false
vwidth = 3
vheight = 3
[simple-tile]
tile_by_default = !(app_id is "pavucontrol")
animation_duration = 0
inner_gap_size = 8
outer_horiz_gap_size = 12
outer_vert_gap_size = 12
''')
(base/'client.py').write_text('''import gi,json,sys,time
from pathlib import Path
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
label,path=sys.argv[1:];GLib.set_prgname(label)
w=Gtk.Window(title=label);w.set_default_size(400,300);w.set_decorated(False)
a=Gtk.DrawingArea();w.add(a);counter=0
last_geometry=None
def draw(widget,cr):
 global last_geometry
 phase=int(time.monotonic()*5)%2
 cr.set_source_rgb(.2+.25*phase,.25,.4);cr.paint()
 cr.set_source_rgb(1,1,1);cr.set_font_size(18);cr.move_to(18,32);cr.show_text(label+' '+str(counter))
 last_geometry=dict(width=a.get_allocated_width(),height=a.get_allocated_height(),counter=counter)
 Path(path).write_text(json.dumps(last_geometry))
def tick():
 global counter
 counter+=1;a.queue_draw();return True
a.connect('draw',draw);w.connect('destroy',Gtk.main_quit);w.show_all();GLib.timeout_add(70,tick);Gtk.main()
''')
env=dict(os.environ,WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='gles2',XDG_RUNTIME_DIR=str(base),WAYLAND_DISPLAY='',WAYFIRE_SOCKET='',WAYFIRE_CONFIG_FILE=str(config),WF_TILE_FLOAT_STATE=str(base/'float.json'),WF_TILE_NO_NOTIFY='1')
env.pop('GTK_MODULES',None);env.pop('RACCON_MENU_CONFIG',None)
env.pop('DISPLAY',None);env.pop('WAYLAND_SOCKET',None)
env['LIBGL_ALWAYS_SOFTWARE']='1'
env['WF_TILE_STATE_DIR']=str(base/'state')
env['XDG_CACHE_HOME']=str(base/'cache')
log=(base/'wayfire.log').open('w');compositor=subprocess.Popen(['wayfire','-c',str(config)],env=env,stdout=log,stderr=log)
clients=[];watcher=None
try:
 for _ in range(200):
  sockets=list(base.glob('wayfire-*.socket'))
  if sockets:break
  if compositor.poll() is not None:raise RuntimeError('Private Wayfire failed')
  time.sleep(.02)
 env['WAYFIRE_SOCKET']=str(sockets[0]);env['WAYLAND_DISPLAY']=next(x.name for x in base.glob('wayland-*') if not x.name.endswith('.lock'))
 os.environ.update({k:env[k] for k in ('WAYFIRE_SOCKET','WAYFIRE_CONFIG_FILE','XDG_RUNTIME_DIR','WF_TILE_FLOAT_STATE','WF_TILE_NO_NOTIFY','WF_TILE_STATE_DIR','XDG_CACHE_HOME')})
 loader=importlib.machinery.SourceFileLoader('tiler',str(SOURCE));spec=importlib.util.spec_from_loader(loader.name,loader);tile=importlib.util.module_from_spec(spec);loader.exec_module(tile)
 ipc=tile.IPC()
 watchlog=(base/'watch.log').open('w');watcher=subprocess.Popen([str(SOURCE),'watch'],env=env,stdout=watchlog,stderr=watchlog)
 time.sleep(.15)
 def views():return ipc.call('window-rules/list-views')
 def get(vid):return next(v for v in views() if v['id']==vid)
 def wait_until(check):
  for _ in range(100):
   result=check()
   if result:return result
   time.sleep(.025)
  raise AssertionError('Condition timed out: '+str(views()))
 def add(label):
  clientlog=(base/(label+'.log')).open('w')
  clients.append(subprocess.Popen([sys.executable,str(base/'client.py'),label,str(base/(label+'.json'))],env=env,stdout=clientlog,stderr=clientlog))
  view=wait_until(lambda:next((v for v in views() if v.get('app-id')==label),None))
  time.sleep(.18);return view['id']
 def focus(vid):ipc.call('window-rules/focus-view',{'id':vid});time.sleep(.04)
 def layout():
  out=ipc.call('window-rules/get-focused-output')['info'];return tile.get_layout(ipc,out)[1]
 def action(*args):subprocess.run([str(SOURCE),*args],env=env,check=True,capture_output=True,text=True,timeout=5);time.sleep(.15)
 def status():return json.loads(subprocess.check_output([str(SOURCE),'status'],env=env,text=True,timeout=5))
 def frame_updates(vid,label):
  view=get(vid);g=view['geometry'];x=int(g['x']+g['width']/2);y=int(g['y']+g['height']/2)
  observed=set()
  for _ in range(5):
   subprocess.run(['grim',str(base/'frame.png')],env=env,check=True,capture_output=True)
   observed.add(Image.open(base/'frame.png').getpixel((x,y)));time.sleep(.09)
  assert len(observed)>1,('Frozen content',label,observed,g)
  data=json.loads((base/(label+'.json')).read_text());assert abs(data['width']-g['width'])<=1 and abs(data['height']-g['height'])<=1,(data,g)
  print('Live content and actual client dimensions',label,'OK',flush=True)
 a=add('tile-a')
 assert int(ipc.call('wayfire/get-config-option',{'option':'simple-tile/inner_gap_size'})['value'])==0
 b=add('tile-b');focus(b)
 assert int(ipc.call('wayfire/get-config-option',{'option':'simple-tile/inner_gap_size'})['value'])==8
 # Regression: a bare single-view IPC root loses its native parent in 0.11.
 # The next repair/retile or unmap used to dereference that null parent.
 action('toggle');assert list(dict(tile.leaves(layout())))==[a]
 action('repair');action('arrange');action('repair')
 for _ in range(3):action('retile')
 assert compositor.poll() is None
 assert list(dict(tile.leaves(layout())))==[a]
 focus(b);action('toggle')
 print('Single remaining tile survives repair, arrange and repeated retile',flush=True)
 focus(b);c=add('tile-c');focus(c);d=add('tile-d')
 tree=layout();print('Four-window tree',tree,flush=True)
 assert [vid for vid,_ in tile.leaves(tree)]==[a,b,c,d]
 root=tree['vertical-split'];assert root[0]['view-id']==a
 assert root[1]['horizontal-split'][0]['view-id']==b
 assert [x['view-id'] for x in root[1]['horizontal-split'][1]['vertical-split']]==[c,d]
 focus(a);e=add('tile-e');tree=layout();assert [x['view-id'] for x in tree['vertical-split'][0]['horizontal-split']]==[a,e]
 # Directional preselection is consumed only by the next tiled window.
 focus(a);action('preselect','left');h=add('tile-h')
 assert status()['preselection'] is None
 assert get(h)['geometry']['x'] < get(a)['geometry']['x']
 assert set(dict(tile.leaves(layout())))=={a,b,c,d,e,h}
 # Move actually inserts a split; undo/redo keep the same living windows.
 focus(h);before=tile.strip_geometry(layout());action('move','right')
 moved=tile.strip_geometry(layout());assert moved!=before
 action('undo');assert set(dict(tile.leaves(layout())))=={a,b,c,d,e,h}
 action('redo');assert set(dict(tile.leaves(layout())))=={a,b,c,d,e,h}
 focus(a);action('favorite','save');action('ratio');action('favorite','load')
 assert set(dict(tile.leaves(layout())))=={a,b,c,d,e,h}
 # The resident UI owns keyboard focus during resize; the saved target survives.
 focus(a);action('resize-mode');assert status()['mode']=='resize'
 action('key','right');action('key','escape');assert status()['mode'] is None
 # Native hotkey sender reuses the resident service without another interpreter.
 native=base/'cache/wf-tile/client';assert native.is_file()
 resident=status()['pid']
 for _ in range(10):
  subprocess.run([str(native),'focus','right'],env=env,check=True,capture_output=True,timeout=5)
 assert status()['pid']==resident
 # Scratchpad keeps the application alive and releases it back into tiling.
 focus(h);action('scratch','assign','1');assert get(h)['minimized'];assert h not in dict(tile.leaves(layout()))
 action('scratch','toggle','1');assert not get(h)['minimized'];assert get(h)['tiled-edges']==0
 action('scratch','toggle','1');assert get(h)['minimized']
 action('scratch','release','1');assert h in dict(tile.leaves(layout()));assert not get(h)['minimized']
 print('Preselection, move, undo/redo, favorite, modal resize, native sender and scratchpads: OK',flush=True)
 focus(e)
 action('toggle');assert e not in dict(tile.leaves(layout()));assert get(e)['tiled-edges']==0
 floating=dict(x=220,y=170,width=480,height=300)
 ipc.call('window-rules/configure-view',{'id':e,'geometry':floating});time.sleep(.15)
 action('toggle');assert e in dict(tile.leaves(layout()))
 action('toggle');assert get(e)['geometry']==floating,(get(e),floating)
 print('Float/tile restores custom geometry',flush=True)
 focus(a)
 for _ in range(4):action('resize','down');action('resize','up')
 action('togglesplit');action('togglesplit');action('repair');frame_updates(a,'tile-a')
 tool=add('pavucontrol');assert tool not in dict(tile.leaves(layout())),layout()
 focus(a);action('mode','float');assert not dict(tile.leaves(layout()))
 f=add('tile-f');assert f not in dict(tile.leaves(layout()));assert get(f)['tiled-edges']==0
 action('mode','tile');assert f in dict(tile.leaves(layout()));assert tool not in dict(tile.leaves(layout()))
 frame_updates(f,'tile-f')
 subprocess.run(['grim',str(base/'dwindle.png')],env=env,check=True,capture_output=True)
 assert ipc.call('wsets/set-output-wset',{'output-id':get(f)['output-id'],'wset-index':2})['result']=='ok'
 g=add('tile-g');assert g not in dict(tile.leaves(layout()));assert get(g)['tiled-edges']==0
 print('Floating workspace, exclusions, Dwindle, toggles and frame updates: OK',flush=True)
 print('Artifacts',base,flush=True)
finally:
 for process in [*clients,watcher,compositor]:
  if process is None:continue
  process.terminate()
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 log.close()
 print('Private test files',base,flush=True)
