"""A floating Kitty sidebar; Wayfire moves it without layer-shell size arithmetic."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

HOME=Path.home()
CONFIG=HOME/'.config/raccon-term/config.json'
KITTY_CONFIG=HOME/'.config/kitty/raccon-panel.conf'
RUNTIME=Path(os.environ.get('XDG_RUNTIME_DIR',HOME/'.cache'))/'raccon-term'
LOG=HOME/'.local/state/raccon-term/panel.log'
APP_ID='raccon-quick-terminal'
PREFIX=b'\x1bP@kitty-cmd'
SUFFIX=b'\x1b\\'
DEFAULTS=dict(width=640,gap=14,duration_in=240,duration_out=170,fps=60)


def read(path,default=None):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {} if default is None else default


def store(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def settings():
    data=read(CONFIG);out={}
    for key,lo,hi in (('width',280,1600),('gap',0,80),('duration_in',0,800),('duration_out',0,800),('fps',12,60)):
        try:out[key]=max(lo,min(hi,int(data.get(key,DEFAULTS[key]))))
        except (ValueError,TypeError):out[key]=DEFAULTS[key]
    try:
        # Respect an explicit system preference, independently of power profiles.
        import gi
        gi.require_version('Gtk','3.0')
        from gi.repository import Gtk
        pref=Gtk.Settings.get_default()
        if pref and not pref.get_property('gtk-enable-animations'):out.update(duration_in=0,duration_out=0)
    except (ImportError,ValueError):pass
    return out


def wayfire(method,data=None):
    path=os.environ.get('WAYFIRE_SOCKET') or next(iter(Path(os.environ.get('XDG_RUNTIME_DIR',RUNTIME.parent)).glob('wayfire-*.socket')),None)
    if not path:raise OSError('Wayfire IPC is unavailable')
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(.3);sock.connect(str(path))
        body=json.dumps(dict(method=method,data=data or {})).encode()
        sock.sendall(struct.pack('<I',len(body))+body)
        def exact(n):
            data=b''
            while len(data)<n:
                chunk=sock.recv(n-len(data))
                if not chunk:raise OSError('Wayfire IPC closed')
                data+=chunk
            return data
        length=struct.unpack('<I',exact(4))[0]
        if length>4*1024*1024:raise OSError('Invalid Wayfire response')
        result=json.loads(exact(length))
        if isinstance(result,dict) and result.get('error'):raise RuntimeError(result['error'])
        return result


def geometry(options,output=None,views=()):
    """Output-local fixed size: slide x only, with room for Waybar."""
    if output is None:
        output=wayfire('window-rules/get-focused-output').get('info',{})
        try:views=wayfire('window-rules/list-views')
        except (OSError,ValueError):views=[]
    size=output.get('geometry',{})
    ow,oh=int(size.get('width',0)),int(size.get('height',0))
    if ow<200 or oh<200:raise RuntimeError('Could not determine the active monitor size')
    gap=options['gap'];left=top=gap;right=ow-gap;bottom=oh-gap
    for view in views if isinstance(views,list) else ():
        if not view.get('mapped') or view.get('app-id')!='waybar' or view.get('output-name')!=output.get('name'):continue
        g=view.get('geometry',{});x,y,w,h=[int(g.get(k,0)) for k in ('x','y','width','height')]
        if w>=h:
            if y+h/2<oh/2:top=max(top,y+h+gap)
            else:bottom=min(bottom,y-gap)
        elif x+w/2<ow/2:left=max(left,x+w+gap)
        else:right=min(right,x-gap)
    width=min(options['width'],max(160,right-left))
    return dict(width=width,height=max(160,bottom-top),top=top,shown_x=max(left,right-width),hidden_x=ow+gap,
                output=output.get('name',''),output_id=output.get('id'),wset=output.get('wset-index'))


class Remote:
    """Documented Kitty protocol over this panel's private local socket."""
    def __init__(self,path):self.path=path
    def __call__(self,cmd,payload=None):
        info=self.path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():raise OSError('Invalid panel socket')
        message=dict(cmd=cmd,version=[0,42,0],no_response=False)
        if payload is not None:message['payload']=payload
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(.7);sock.connect(str(self.path))
            sock.sendall(PREFIX+json.dumps(message,separators=(',',':')).encode()+SUFFIX)
            data=b''
            while SUFFIX not in data:
                part=sock.recv(65536)
                if not part:raise OSError('Kitty closed the control socket')
                data+=part
                if len(data)>8*1024*1024:raise OSError('Kitty response too large')
        start=data.find(PREFIX)
        if start<0:raise OSError('Invalid Kitty response')
        response=json.loads(data[start+len(PREFIX):].split(SUFFIX,1)[0])
        if not response.get('ok'):raise RuntimeError(response.get('error','Kitty rejected the action'))
        return response.get('data')


def windows(remote):
    value=remote('ls')
    return json.loads(value) if isinstance(value,str) else value


def launch_args(geo,socket_path):
    # Offscreen layer-shell margins made Kitty request -1x-1, wrapping to
    # UINT32_MAX and disconnecting Wayland. A normal xdg window always keeps
    # positive fixed dimensions; only its compositor position is animated.
    return ['kitty','--config',str(KITTY_CONFIG),'--class='+APP_ID,'--title=Quick terminal',
            '--listen-on=unix:'+str(socket_path),'-o','remember_window_size=no',
            '-o',f'initial_window_width={geo["width"]}',
            '-o',f'initial_window_height={geo["height"]}']


class Panel:
    def __init__(self,root=RUNTIME,request=None,clock=time.monotonic,sleep=time.sleep,compositor=None):
        self.root=Path(root);self.socket=self.root/'kitty.sock'
        self.remote=request or Remote(self.socket);self.clock=clock;self.sleep=sleep
        self.wf=compositor or wayfire;self.view_id=None
        self.intent=self.root/'intent.json';self.state=self.root/'state.json'
    def alive(self):
        try:return bool(windows(self.remote))
        except (OSError,ValueError,RuntimeError):return False
    def bind_view(self):
        views=self.wf('window-rules/list-views')
        matches=[v for v in views if v.get('mapped') and v.get('app-id')==APP_ID and v.get('role')=='toplevel']
        if not matches:raise RuntimeError('Kitty window is not mapped in Wayfire')
        view=max(matches,key=lambda v:v['id']);self.view_id=view['id'];return view
    def prepare(self,geo):
        view=self.bind_view()
        values=dict(id=self.view_id,**{'tiled-edges':0},sticky=True)
        if geo.get('output_id') is not None:values['output_id']=geo['output_id']
        self.wf('window-rules/configure-view',values)
        if geo.get('wset') is not None and view.get('wset-index')!=geo['wset']:
            self.wf('wsets/send-view-to-wset',{'view-id':self.view_id,'wset-index':geo['wset']})
    def move(self,geo,x):
        self.wf('window-rules/configure-view',dict(id=self.view_id,geometry=dict(
            x=int(x),y=geo['top'],width=geo['width'],height=geo['height']),**{'tiled-edges':0}))
    def alpha(self,value):
        self.wf('wf/alpha/set-view-alpha',{'view-id':self.view_id,'alpha':float(value)})
    def visibility(self,visible):
        self.wf('wm-actions/set-minimized',{'view_id':self.view_id,'state':not visible})
        if visible:self.wf('wm-actions/set-always-on-top',{'view_id':self.view_id,'state':True})
    def start(self,geo):
        if not shutil.which('kitty'):raise RuntimeError('Kitty is required')
        # A stale socket belongs only to this panel. Never kill other Kitty windows.
        self.socket.unlink(missing_ok=True)
        LOG.parent.mkdir(parents=True,exist_ok=True)
        with LOG.open('ab') as log:
            log.write((time.strftime('[%Y-%m-%d %H:%M:%S] ')+f'starting xdg Kitty sidebar {geo["width"]}x{geo["height"]}\n').encode())
            log.flush()
            child=subprocess.Popen(launch_args(geo,self.socket),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        deadline=self.clock()+5
        while self.clock()<deadline:
            if self.alive():
                try:self.bind_view();return
                except RuntimeError:pass
            if child.poll() not in (None,0):break
            self.sleep(.025)
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=.3)
            except subprocess.TimeoutExpired:child.kill()
        raise RuntimeError('Kitty panel could not start. See '+str(LOG))
    def animate(self,options):
        state=read(self.state);geo=state.get('geometry');ready=self.alive()
        if ready:self.bind_view()
        progress=float(state.get('progress',0)) if ready else 0
        mapped=bool(state.get('visible')) and ready;segment=None
        try:
            while True:
                intent=read(self.intent);target=intent.get('target','hidden')
                if target=='visible' and not ready:
                    geo=geometry(options);self.start(geo);progress=0;mapped=False;ready=True
                elif target=='visible' and not geo:
                    geo=geometry(options)
                destination=1. if target=='visible' else 0.
                if destination and not mapped:
                    self.prepare(geo);self.alpha(0);self.move(geo,geo['hidden_x'])
                    self.visibility(True);mapped=True
                now=self.clock()
                if segment is None or segment[0]!=target:
                    ms=options['duration_in' if destination else 'duration_out']
                    if abs(destination-progress)<.001:ms=0
                    segment=(target,now,progress,ms/1000)
                _,began,initial,duration=segment
                fraction=min(1.,(now-began)/duration) if duration else 1.
                eased=1-(1-fraction)**3
                progress=initial+(destination-initial)*eased
                if mapped:
                    x=round(geo['hidden_x']+(geo['shown_x']-geo['hidden_x'])*progress)
                    self.move(geo,x);self.alpha(progress)
                state=dict(visible=mapped,progress=progress,target=target,geometry=geo,error='',backend='xdg-wayfire',view_id=self.view_id)
                store(self.state,state)
                if fraction>=1:
                    # Release worker ownership while the intent lock is held so
                    # a request arriving at this boundary can take over reliably.
                    with (self.root/'intent.lock').open('w') as guard:
                        fcntl.flock(guard,fcntl.LOCK_EX)
                        if read(self.intent).get('seq')!=intent.get('seq'):
                            segment=None;continue
                        if destination==0 and mapped:
                            self.visibility(False);mapped=False;self.move(geo,geo['shown_x']);self.alpha(1)
                        elif destination==1:
                            self.wf('window-rules/focus-view',{'id':self.view_id})
                        if target=='closed' and ready:
                            self.remote('close-window',dict(match='all',ignore_no_match=True))
                        store(self.state,dict(state,visible=mapped,progress=destination))
                        fcntl.flock(self.worker,fcntl.LOCK_UN)
                        return
                self.sleep(1/options['fps'])
        except Exception as exc:
            # Leave a failed slide usable rather than stranded outside the screen.
            try:
                if mapped and geo:
                    self.move(geo,geo['shown_x']);self.alpha(1);self.visibility(True)
            except (OSError,ValueError,RuntimeError):pass
            store(self.state,dict(state,error=str(exc)))
            raise
    def command(self,action,options=None):
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.root.is_symlink() or self.root.stat().st_uid!=os.getuid():raise RuntimeError('Invalid runtime directory')
        os.chmod(self.root,0o700)
        with (self.root/'worker.lock').open('w') as worker:
            self.worker=worker
            try:fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB);owner=True
            except BlockingIOError:owner=False
            with (self.root/'intent.lock').open('w') as guard:
                fcntl.flock(guard,fcntl.LOCK_EX)
                intent=read(self.intent)
                current=intent.get('target','hidden')
                if owner and not self.alive():current='closed'
                target=('hidden' if current=='visible' else 'visible') if action=='toggle' else {'show':'visible','hide':'hidden','close':'closed'}[action]
                store(self.intent,dict(target=target,seq=int(intent.get('seq',0))+1))
            if not owner:
                try:fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB);owner=True
                except BlockingIOError:return
            self.animate(settings() if options is None else options)


def main(args=None):
    args=sys.argv[1:] if args is None else args
    action=args[0] if args else 'toggle'
    if action in ('-h','--help'):
        print('raccon-term [toggle|show|hide|close|status]\nSuper+F12: show/hide · Super+Shift+F12: close\nCtrl+Esc: hide · Ctrl+Shift+Q: close the panel session')
        return 0
    if len(args)>1 or action not in ('toggle','show','hide','close','status'):
        print('Usage: raccon-term [toggle|show|hide|close|status]',file=sys.stderr);return 2
    if action=='status':print(json.dumps(read(RUNTIME/'state.json')));return 0
    try:Panel().command(action);return 0
    except Exception as exc:
        print('raccon-term: '+str(exc),file=sys.stderr)
        if shutil.which('notify-send'):
            subprocess.run(['notify-send','-a','Raccon','Quick terminal',str(exc)[:240]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
        return 1
