"""A fixed Kitty sidebar with serialized, interruptible opacity transitions."""
import fcntl
import json
import math
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
DEFAULTS=dict(width=520,height=520,gap=14,duration_in=170,duration_out=113,fps=60)
TOGGLE_INTERVAL=.28


def read(path,default=None):
    try:
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) else ({} if default is None else default)
    except (OSError,ValueError):return {} if default is None else default


def number(value,default=0):
    try:
        result=float(value)
        return result if math.isfinite(result) else default
    except (ValueError,TypeError,OverflowError):return default


def store(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def event(message):
    # Lifecycle only: never log the shell, commands, environment or RC ls data.
    try:
        LOG.parent.mkdir(parents=True,exist_ok=True)
        with LOG.open('a') as stream:stream.write(time.strftime('[%Y-%m-%d %H:%M:%S] ')+message+'\n')
    except OSError:pass


def notify_waybar():
    """Refresh only the quick-terminal modules, after a lifecycle change."""
    try:
        subprocess.run(['pkill','-RTMIN+9','-u',str(os.getuid()),'-x','waybar'],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1)
    except (OSError,subprocess.TimeoutExpired):pass


def settings():
    data=read(CONFIG);out={}
    for key,lo,hi in (('width',280,1600),('height',240,1200),('gap',0,80),('duration_in',0,800),('duration_out',0,800),('fps',12,60)):
        try:out[key]=max(lo,min(hi,int(data.get(key,DEFAULTS[key]))))
        except (ValueError,TypeError,OverflowError):out[key]=DEFAULTS[key]
    try:
        # Respect an explicit system preference, independently of power profiles.
        import gi
        gi.require_version('Gtk','3.0')
        from gi.repository import Gtk
        pref=Gtk.Settings.get_default()
        if pref and not pref.get_property('gtk-enable-animations'):out.update(duration_in=0,duration_out=0)
    except (ImportError,ValueError):pass
    return out


class Wayfire:
    """Reuse one connection per worker instead of opening two per animation frame."""
    def __init__(self):self.sock=None
    def close(self):
        if self.sock:self.sock.close();self.sock=None
    def __call__(self,method,data=None):
        try:return self.request(method,data)
        except (OSError,ValueError,RuntimeError):
            # A timed-out stream may still contain the previous reply. Never
            # reuse it or replay a mutation whose outcome is unknown.
            self.close()
            raise
    def request(self,method,data=None):
        if self.sock is None:
            path=os.environ.get('WAYFIRE_SOCKET') or next(iter(Path(os.environ.get('XDG_RUNTIME_DIR',RUNTIME.parent)).glob('wayfire-*.socket')),None)
            if not path:raise OSError('Wayfire IPC is unavailable')
            self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(.7)
            try:self.sock.connect(str(path))
            except OSError:self.close();raise
        sock=self.sock
        body=json.dumps(dict(method=method,data=data or {})).encode()
        sock.sendall(struct.pack('<I',len(body))+body)
        return self.receive()
    def receive(self):
        sock=self.sock
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


def wayfire(method,data=None):
    client=Wayfire()
    try:return client(method,data)
    finally:client.close()


def geometry(options,output=None,views=(),request=wayfire):
    """Output-local fixed size, always inside the work area, with room for Waybar."""
    if output is None:
        output=request('window-rules/get-focused-output').get('info') or {}
        try:views=request('window-rules/list-views')
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
    height=min(options.get('height',520),max(160,bottom-top))
    top+=max(0,(bottom-top-height)//2)
    return dict(width=width,height=height,top=top,shown_x=max(left,right-width),
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
    # positive fixed dimensions; only compositor opacity is animated.
    return ['kitty','--config',str(KITTY_CONFIG),'--class='+APP_ID,'--title=Quick terminal',
            '--listen-on=unix:'+str(socket_path),'-o','remember_window_size=no',
            '-o',f'initial_window_width={geo["width"]}',
            '-o',f'initial_window_height={geo["height"]}']


class Panel:
    def __init__(self,root=RUNTIME,request=None,clock=time.monotonic,sleep=time.sleep,compositor=None):
        self.root=Path(root);self.socket=self.root/'kitty.sock'
        self.remote=request or Remote(self.socket);self.clock=clock;self.sleep=sleep
        self.wf=compositor or Wayfire();self.view_id=None
        self.intent=self.root/'intent.json';self.state=self.root/'state.json'
    def alive(self):
        try:
            if windows(self.remote):return True
        except (OSError,ValueError,RuntimeError):pass
        # A busy or closing RC endpoint is not proof the view has disappeared.
        views=self.wf('window-rules/list-views')
        if any(v.get('mapped') and v.get('app-id')==APP_ID for v in views):
            raise RuntimeError('Quick terminal is still running but not responding; retry shortly')
        return False
    def bind_view(self):
        views=self.wf('window-rules/list-views')
        matches=[v for v in views if v.get('mapped') and v.get('app-id')==APP_ID and v.get('role')=='toplevel']
        if not matches:raise RuntimeError('Kitty window is not mapped in Wayfire')
        view=max(matches,key=lambda v:v['id']);self.view_id=view['id'];return view
    def prepare(self,geo):
        view=self.bind_view()
        # One in-bounds transaction per reveal. Never move a minimized window,
        # animate geometry, or move it to its current output again.
        values=dict(id=self.view_id,**{'tiled-edges':0},sticky=False,geometry=dict(
            x=geo['shown_x'],y=geo['top'],width=geo['width'],height=geo['height']))
        if geo.get('output_id') is not None and view.get('output-id')!=geo['output_id']:
            values['output_id']=geo['output_id']
        event(f'place view={self.view_id} geometry={values["geometry"]}')
        self.wf('window-rules/configure-view',values)
        if geo.get('wset') is not None and view.get('wset-index')!=geo['wset']:
            self.wf('wsets/send-view-to-wset',{'view-id':self.view_id,'wset-index':geo['wset']})
    def alpha(self,value):
        self.wf('wf/alpha/set-view-alpha',{'view-id':self.view_id,'alpha':float(value)})
    def visibility(self,visible):
        event(f'visibility view={self.view_id} visible={visible}')
        self.wf('wm-actions/set-minimized',{'view_id':self.view_id,'state':not visible})
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
            # This process owns the newly spawned child: a mapped view with an
            # unready RC socket is normal during startup, not a duplicate.
            try:
                if windows(self.remote):
                    self.bind_view();return
            except (OSError,ValueError,RuntimeError):pass
            if child.poll() is not None:break
            self.sleep(.025)
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=.3)
            except subprocess.TimeoutExpired:child.kill()
        raise RuntimeError('Kitty panel could not start. See '+str(LOG))
    def animate(self,options):
        state=read(self.state);geo=state.get('geometry');ready=self.alive()
        view=self.bind_view() if ready else {}
        progress=max(0.,min(1.,number(state.get('progress')))) if ready else 0
        mapped=ready and not view.get('minimized',not state.get('visible'))
        if not mapped:progress=0
        segment=None
        try:
            while True:
                intent=read(self.intent);target=intent.get('target','hidden')
                if target=='visible' and not ready:
                    geo=geometry(options,request=self.wf);self.start(geo);self.bind_view();progress=0;mapped=False;ready=True
                elif target=='visible' and not geo:
                    geo=geometry(options,request=self.wf)
                destination=1. if target=='visible' else 0.
                if destination and not mapped:
                    geo=geometry(options,request=self.wf)
                    self.alpha(0);self.visibility(True);mapped=True
                    entrance=geo
                    self.prepare(entrance)
                    # Read committed bounds, not pending geometry reported by IPC.
                    deadline=self.clock()+1.5;settled=0
                    while self.clock()<deadline:
                        if read(self.intent).get('seq')!=intent.get('seq'):break
                        view=self.bind_view();placed=view.get('bbox') or view.get('base-geometry') or view.get('geometry',{})
                        correct=abs(placed.get('x',-10000)-entrance['shown_x'])<=4 and abs(placed.get('y',-10000)-geo['top'])<=4
                        settled=settled+1 if correct else 0
                        if settled>=3:break
                        self.sleep(.03)
                    if read(self.intent).get('seq')!=intent.get('seq'):continue
                    if settled<3:raise RuntimeError('Terminal placement did not settle; retry opening')
                now=self.clock()
                if segment is None or segment[0]!=target:
                    ms=options['duration_in' if destination else 'duration_out']
                    if target=='closed' or abs(destination-progress)<.001:ms=0
                    segment=(target,now,progress,ms/1000)
                _,began,initial,duration=segment
                fraction=min(1.,(now-began)/duration) if duration else 1.
                eased=1-(1-fraction)**3
                progress=initial+(destination-initial)*eased

                if mapped and target!='closed':self.alpha(progress)
                state=dict(visible=mapped,progress=progress,target=target,geometry=geo,error='',backend='xdg-wayfire',view_id=self.view_id,animation='fade')
                store(self.state,state)
                if fraction>=1:
                    # Release worker ownership while the intent lock is held so
                    # a request arriving at this boundary can take over reliably.
                    with (self.root/'intent.lock').open('w') as guard:
                        fcntl.flock(guard,fcntl.LOCK_EX)
                        if read(self.intent).get('seq')!=intent.get('seq'):
                            segment=None;continue
                        if destination==0 and mapped and target!='closed':
                            self.visibility(False);mapped=False
                        elif destination==1:
                            self.wf('window-rules/focus-view',{'id':self.view_id})
                        if target=='closed' and ready:
                            self.remote('close-window',dict(match='all',ignore_no_match=True));mapped=False
                        store(self.state,dict(state,visible=mapped,progress=destination))
                        if self.root==RUNTIME:notify_waybar()
                        event(f'settled seq={intent.get("seq")} target={target} view={self.view_id}')
                        fcntl.flock(self.worker,fcntl.LOCK_UN)
                        return
                self.sleep(1/options['fps'])
        except Exception as exc:
            # Restore only a still-live view; don't send more mutations to a
            # disappeared client or leave an invisible terminal over the desktop.
            try:
                if mapped and self.alive():
                    self.bind_view();self.visibility(False)
            except (OSError,ValueError,RuntimeError):pass
            store(self.state,dict(state,error=str(exc),visible=False,progress=0))
            if self.root==RUNTIME:notify_waybar()
            event(f'controller error: {str(exc)[:240]}')
            raise
    def command(self,action,options=None,expected_seq=None):
        try:return self._command(action,options,expected_seq)
        except (OSError,ValueError,RuntimeError) as exc:
            event(f'command {action} failed: {str(exc)[:240]}')
            raise
        finally:
            if isinstance(self.wf,Wayfire):self.wf.close()
    def _command(self,action,options=None,expected_seq=None):
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.root.is_symlink() or self.root.stat().st_uid!=os.getuid():raise RuntimeError('Invalid runtime directory')
        os.chmod(self.root,0o700)
        with (self.root/'worker.lock').open('w') as worker:
            self.worker=worker
            with (self.root/'intent.lock').open('w') as guard:
                fcntl.flock(guard,fcntl.LOCK_EX)
                try:fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB);owner=True
                except BlockingIOError:owner=False
                intent=read(self.intent)
                # Focus loss belongs to the reveal that observed it. Discard
                # stale watcher requests atomically with the newest intent.
                if expected_seq is not None and intent.get('seq')!=expected_seq:return
                now=self.clock()
                # Repeated key presses must not reverse native minimize/map
                # transactions mid-flight. Explicit hide/close can interrupt.
                elapsed=now-number(intent.get('last_toggle'),-TOGGLE_INTERVAL)
                if action=='toggle' and (not owner or 0<=elapsed<TOGGLE_INTERVAL):return
                current=intent.get('target','hidden')
                if owner:
                    if not self.alive():current='closed'
                    else:
                        view=self.bind_view()
                        hidden=view.get('minimized',not read(self.state).get('visible'))
                        current='hidden' if hidden else 'visible'
                target=('hidden' if current=='visible' else 'visible') if action=='toggle' else {'show':'visible','hide':'hidden','close':'closed'}[action]
                store(self.intent,dict(target=target,seq=int(number(intent.get('seq')))+1,
                                       last_toggle=now if action=='toggle' else intent.get('last_toggle',-TOGGLE_INTERVAL)))
                event(f'accepted action={action} target={target} seq={int(number(intent.get("seq")))+1}')
            if not owner:return
            try:self.animate(settings() if options is None else options)
            finally:
                if isinstance(self.wf,Wayfire):self.wf.close()


def watch_focus():
    """Follow native focus/minimize/close events; no repeated Kitty/Wayfire queries."""
    RUNTIME.mkdir(parents=True,exist_ok=True)
    with (RUNTIME/'focus.lock').open('w') as guard:
        try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        panel=Panel();events=Wayfire();armed=False;armed_seq=None
        try:
            events('window-rules/events/watch',dict(events=['view-focused','view-minimized','view-unmapped']))
            events.sock.settimeout(None)
            # Subscribe before checking: exit may race with watcher startup.
            try:
                if not panel.alive():
                    notify_waybar();return
            except RuntimeError:pass  # An unready RC endpoint can still own a view.
            focus=panel.wf('window-rules/get-focused-view').get('info') or {}
            message=dict(event='view-focused',view=focus)
            while True:
                state=read(panel.state);intent=read(panel.intent)
                if intent.get('seq')!=armed_seq:armed=False
                armed_seq=intent.get('seq')
                view=message.get('view') or {};kind=message.get('event')
                same=view.get('id') is not None and view.get('id')==state.get('view_id')
                own=same or (view.get('parent') is not None and view.get('parent')==state.get('view_id'))
                if kind in ('view-minimized','view-unmapped') and same:
                    notify_waybar()
                    if kind=='view-unmapped':return
                if not state.get('visible') or intent.get('target')!='visible':
                    armed=False
                elif kind=='view-focused':
                    if own:armed=True
                    elif armed:
                        try:panel.command('hide',expected_seq=armed_seq)
                        except (OSError,ValueError,RuntimeError):pass
                        armed=False
                message=events.receive()
        except (OSError,ValueError,RuntimeError):
            notify_waybar()
        finally:
            events.close()
            if isinstance(panel.wf,Wayfire):panel.wf.close()


def indicator(part='toggle'):
    """Read actual liveness on startup and lifecycle signals, including native close."""
    panel=Panel();state=read(panel.state)
    try:live=panel.alive()
    except RuntimeError:live=True
    except OSError:live=False
    status='closed'
    if live:
        status='visible' if state.get('visible') else 'hidden'
        try:status='hidden' if panel.bind_view().get('minimized') else 'visible'
        except RuntimeError:status='closed';live=False
        except (OSError,ValueError):pass
    if isinstance(panel.wf,Wayfire):panel.wf.close()
    icons={'toggle':'󰆍','hide':'󰅒','close':'󰅖'}
    hint={'toggle':f'Quick terminal · {status}\nClick: show / hide · Middle: hide · Right: close session\nSuper+Space: show / hide',
          'hide':'Hide terminal · keep the session running\nCtrl+Esc',
          'close':'Close terminal session\nSuper+Shift+F12 · Ctrl+Shift+Q'}
    return dict(text=icons[part] if live or part=='toggle' else '',
                **{'class':status},tooltip=hint[part])


def main(args=None):
    args=sys.argv[1:] if args is None else args
    action=args[0] if args else 'toggle'
    if action=='watch-focus':watch_focus();return 0
    if action=='indicator' and len(args)<=2 and (len(args)==1 or args[1] in ('toggle','hide','close')):
        print(json.dumps(indicator(args[1] if len(args)==2 else 'toggle')));return 0
    if action in ('-h','--help'):
        print('raccon-term [toggle|show|hide|close|status]\nSuper+Space: show/hide · Super+Shift+Space: close\nCtrl+Esc: hide · Ctrl+Shift+Q: close the panel session')
        return 0
    if len(args)>1 or action not in ('toggle','show','hide','close','status'):
        print('Usage: raccon-term [toggle|show|hide|close|status]',file=sys.stderr);return 2
    if action=='status':print(json.dumps(read(RUNTIME/'state.json')));return 0
    try:
        Panel().command(action)
        if action in ('show','toggle') and read(RUNTIME/'state.json').get('visible'):
            subprocess.Popen([str(HOME/'.local/bin/raccon-term'),'watch-focus'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        return 0
    except Exception as exc:
        print('raccon-term: '+str(exc),file=sys.stderr)
        if shutil.which('notify-send'):
            try:subprocess.run(['notify-send','-a','Raccon','Quick terminal',str(exc)[:240]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
            except (OSError,subprocess.TimeoutExpired):pass
        return 1
