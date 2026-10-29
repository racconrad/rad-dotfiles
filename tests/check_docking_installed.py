#!/usr/bin/env python3
"""Opt-in installed-shell integration check using a private Wayfire and real Waybar.

Run from any directory after installing the desktop module. No user bar or
connectivity settings are changed; temporary shells are shut down afterwards.
"""
import os,sys,subprocess,time,json,socket,struct,tempfile
from pathlib import Path
from unittest.mock import patch
HOME=Path.home()
sys.path.insert(0,str(HOME/'.local/lib/raccon_menu'))
import positioning
from transport import send
base=Path(tempfile.mkdtemp(prefix='waybar-docking-',dir='/tmp'))
(base/'wayfire.ini').write_text('[core]\nplugins = ipc ipc-rules\nxwayland = false\nbackground_color = 0.08 0.08 0.1 1\n')
env=dict(os.environ,WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='gles2',XDG_RUNTIME_DIR=str(base),WAYLAND_DISPLAY='',WAYFIRE_SOCKET='')
log=(base/'wayfire.log').open('w');compositor=subprocess.Popen(['wayfire','-c',str(base/'wayfire.ini')],env=env,stdout=log,stderr=log)
bar=None
try:
 for _ in range(200):
  if list(base.glob('wayfire-*.socket')):break
  if compositor.poll() is not None:raise RuntimeError('Compositor failed')
  time.sleep(.02)
 env['WAYFIRE_SOCKET']=str(next(base.glob('wayfire-*.socket')))
 env['WAYLAND_DISPLAY']=next(x.name for x in base.glob('wayland-*') if not x.name.endswith('.lock'))
 (base/'bar.css').write_text('* {font-family:sans-serif;font-size:12px;} window#waybar{background:#223344;color:white;}')
 for cfg in ('raccon-menu',):
  subprocess.run([str(HOME/'.local/bin')+'/'+('desktop-menu' if cfg=='raccon-menu' else cfg),'prepare'],env=env,check=True,capture_output=True,timeout=15)
 for edge in ('bottom','top','left','right'):
  data={'position':edge,'layer':'top','exclusive':True,'margin-top':6,'margin-bottom':6,'margin-left':6,'margin-right':6,'modules-left':['clock']}
  data['height' if edge in ('top','bottom') else 'width']=38 if edge in ('top','bottom') else 42
  (base/'bar.json').write_text(json.dumps(data))
  barlog=(base/('bar-'+edge+'.log')).open('w')
  bar=subprocess.Popen(['waybar','-c',str(base/'bar.json'),'-s',str(base/'bar.css')],env=env,stdout=barlog,stderr=barlog)
  time.sleep(.5)
  with patch.dict(os.environ,env):
   root='raccon-menu'
   positioning.refresh(base/root,force=True)
   for section,page in (('home',0),('audio',4),('connections',5),('bluetooth',6)):
    if section=='home':assert send('show 0',str(base/root))
    else:subprocess.run([str(HOME/'.local/bin/desktop-panel'),section],env=env,check=True,capture_output=True)
    time.sleep(.4)
    views=positioning.ipc('window-rules/list-views')
    b=next(x['geometry'] for x in views if x.get('app-id')=='waybar' and x.get('mapped'))
    w=next(x['geometry'] for x in views if x.get('app-id')==root and x.get('mapped'))
    gap={'bottom':b['y']-(w['y']+w['height']), 'top':w['y']-(b['y']+b['height']),
         'left':w['x']-(b['x']+b['width']), 'right':b['x']-(w['x']+w['width'])}[edge]
    print(edge,section,'gap',gap,'window',w,flush=True)
    assert abs(gap-4)<=1,(edge,root,gap,b,w)
    assert w['x']>=0 and w['y']>=0,w
    assert not any(v.get('app-id')=='desktop-panel' and v.get('mapped') for v in views),views
    if section!='home':assert 650<=w['width']<=800,w
    if section in ('connections','bluetooth'):
     # Freeze providers in this private runtime; exercise dense lists and forms with fixtures.
     (base/root/'page').write_text('0');time.sleep(.3)
     def update(**values):
      subprocess.run(['eww','-c',str(HOME/'.config/raccon-menu'),'--no-daemonize','update',
       *[key+'='+json.dumps(value,ensure_ascii=False) for key,value in values.items()]],env=env,check=True,capture_output=True)
     if section=='connections':
      rows=[dict(token=f'{i:024x}',title='Una red Wi-Fi con un nombre bastante largo '+str(i),active=i==0,signal=100-i*10,secured=True) for i in range(4)]
      frame=dict(available=True,ready=True,error='',enabled=True,rows=rows,list_page=1,page_count=4,total=15,empty=False)
      cases=[dict(wifi=frame),dict(wifi_selected=dict(token=rows[1]['token'],title=rows[1]['title'],active=False,secured=True,signal=90,security='WPA2 WPA3')),
       dict(wifi_selected=dict(token=rows[2]['token'],title=rows[2]['title'],active=False,secured=False,signal=80,security='Abierta')),
       dict(wifi_selected=dict(token=rows[0]['token'],title=rows[0]['title'],active=True,secured=True,signal=100,security='WPA2'))]
     else:
      rows=[dict(token=f'{i:024x}',title='Auriculares con un nombre bastante largo '+str(i),connected=i==0,paired=True,battery='100%',icon='audio-headset-symbolic',kind='Auriculares',address='00:11:22:33:44:55',signal='-50 dBm') for i in range(4)]
      frame=dict(available=True,ready=True,error='',enabled=True,scanning=False,rows=rows,list_page=0,page_count=3,total=11,empty=False,detail=dict(token='',connected=False,paired=False))
      cases=[dict(bluetooth=frame),dict(bluetooth=dict(frame,detail=rows[0]))]
     for index,values in enumerate(cases):
      update(**values);time.sleep(.35)
      send('inspect',str(base/root));time.sleep(.06)
      info=dict(line.split('=',1) for line in (base/root/'inspect').read_text().splitlines() if '=' in line)
      print(edge,section,'view',index,'fit', {k:v for k,v in info.items() if k.startswith('service_')},flush=True)
      assert int(info['service_height']) >= w['height']-50, info
      assert info['service_overflow']=='0' and info['service_scrolls']=='0',info
      if section=='connections': assert info['password_mapped']==('1' if index==1 else '0'),info
      if edge=='bottom' and os.environ.get('RACCON_MENU_SNAPSHOTS')=='1':
       subprocess.run(['grim',str(base/(section+'-'+str(index)+'.png'))],env=env,check=True,capture_output=True)
    send('hide',str(base/root));time.sleep(.15)
  bar.terminate();bar.wait(timeout=3);bar=None;barlog.close();time.sleep(.1)
 print('All four edges: 4px adjacency and integrated main-menu dropdowns OK',flush=True)
finally:
 if bar is not None:
  bar.terminate();bar.wait(timeout=3)
 for cfg in ('raccon-menu',):
  try:subprocess.run(['eww','-c',str(HOME/'.config')+'/'+cfg,'--no-daemonize','kill'],env=env,capture_output=True,timeout=3)
  except Exception:pass
 compositor.terminate()
 try:compositor.wait(timeout=3)
 except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
 log.close()
 print('Artifacts',base)
