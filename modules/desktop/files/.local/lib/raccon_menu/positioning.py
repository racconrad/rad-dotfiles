"""Place resident shells against the actual Waybar, with configuration fallback."""
import configparser
import glob
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time

HOME = Path.home()
CONFIG = HOME / '.config/waybar/config.jsonc'
GAP = 4
_last = {}


def jsonc(text):
    # Strip comments only outside JSON strings, preserving URLs and escaped quotes.
    out, index, quoted = [], 0, False
    while index < len(text):
        char = text[index]
        if quoted:
            out.append(char)
            if char == '\\' and index + 1 < len(text):
                index += 1; out.append(text[index])
            elif char == '"': quoted = False
        elif char == '"': quoted = True; out.append(char)
        elif text[index:index+2] == '//':
            end = text.find('\n', index); index = len(text) if end < 0 else end; continue
        elif text[index:index+2] == '/*':
            end = text.find('*/', index+2); index = len(text) if end < 0 else end+2; continue
        else: out.append(char)
        index += 1
    return json.loads(''.join(out))


def config(output=''):
    try:
        value = jsonc(CONFIG.read_text())
        bars = value if isinstance(value,list) else [value]
        return next((bar for bar in bars if isinstance(bar,dict) and
                     (not bar.get('output') or output in ([bar['output']] if isinstance(bar['output'],str) else bar['output']))), {})
    except (OSError,ValueError,TypeError): return {}


def ipc(method):
    root = os.environ.get('XDG_RUNTIME_DIR', '/run/user/'+str(os.getuid()))
    paths = [os.environ['WAYFIRE_SOCKET']] if os.environ.get('WAYFIRE_SOCKET') else glob.glob(root+'/wayfire*.socket')
    if not paths: raise OSError('No Wayfire socket')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(.12);connection.connect(paths[0])
        message=json.dumps(dict(method=method,data={})).encode()
        connection.sendall(struct.pack('=I',len(message))+message)
        def read(length):
            result=b''
            while len(result)<length:
                part=connection.recv(length-len(result))
                if not part: raise OSError('Wayfire closed the socket')
                result+=part
            return result
        length=struct.unpack('=I',read(4))[0]
        if length>4*1024*1024:raise OSError('Unexpected Wayfire response size')
        return json.loads(read(length))


def number(value, default=0):
    try: return max(0,int(value))
    except (ValueError,TypeError): return default


def layout(bar, geometry=None, output=None):
    """Return native layer-shell insets in output-local coordinates."""
    output = output or dict(x=0,y=0,width=1920,height=1080)
    width, height = number(output.get('width'),1920), number(output.get('height'),1080)
    edge = bar.get('position','bottom')
    if edge not in ('top','bottom','left','right'):edge='bottom'
    if geometry:
        x,y,w,h=[number(geometry.get(key)) for key in ('x','y','width','height')]
        # Wayfire layer geometry is local to its output.
        edge = ('top' if y+h/2<height/2 else 'bottom') if w>=h else ('left' if x+w/2<width/2 else 'right')
        if edge in ('top','bottom'):
            start,end=x,max(0,width-x-w)
            inset=y+h+GAP if edge=='top' else height-y+GAP
        else:
            start,end=y,max(0,height-y-h)
            inset=x+w+GAP if edge=='left' else width-x+GAP
    else:
        inset=number(bar.get('height'),32) if edge in ('top','bottom') else number(bar.get('width'),48)
        inset+=number(bar.get('margin-'+edge))+GAP
        start=number(bar.get('margin-left' if edge in ('top','bottom') else 'margin-top'),8)
        end=number(bar.get('margin-right' if edge in ('top','bottom') else 'margin-bottom'),8)
    return dict(edge=edge,inset=max(GAP,inset),start=max(4,start),end=max(4,end),
                ox=int(output.get('x',0)),oy=int(output.get('y',0)),ow=width,oh=height)


def current():
    try:
        response=ipc('window-rules/get-focused-output')
        if not isinstance(response,dict):raise ValueError('Invalid focused output')
        focus=response.get('info') or {}
        if not focus:
            outputs=ipc('window-rules/list-outputs')
            if not isinstance(outputs,list):raise ValueError('Invalid output list')
            focus=next((item for item in outputs if isinstance(item,dict)),{})
        if not isinstance(focus,dict) or not focus:raise OSError('No output')
        views=ipc('window-rules/list-views')
        if not isinstance(views,list):raise ValueError('Invalid view list')
        bars=[v for v in views if isinstance(v,dict) and v.get('mapped') and v.get('app-id')=='waybar' and v.get('output-name')==focus.get('name')]
        chosen=max(bars,key=lambda v:v['geometry']['width']*v['geometry']['height']) if bars else None
        result=layout(config(focus.get('name','')),chosen['geometry'] if chosen else None,focus.get('geometry'))
        result['source']='wayfire' if chosen else 'config'
        return result
    except (OSError,ValueError,TypeError,KeyError):
        return dict(layout(config()),source='config')


def refresh(runtime, force=False):
    runtime=Path(runtime)
    now=time.monotonic()
    if not force and now-_last.get(str(runtime),0)<.5:return
    _last[str(runtime)]=now
    data=current()
    try:data['config_mtime']=CONFIG.stat().st_mtime_ns
    except OSError:data['config_mtime']=0
    parser=configparser.ConfigParser();parser['dock']={key:str(value) for key,value in data.items()}
    import io
    stream=io.StringIO();parser.write(stream);text=stream.getvalue()
    target=runtime/'dock.ini'
    try:
        if data['source']=='config' and target.exists():
            previous=configparser.ConfigParser();previous.read(target)
            if previous.get('dock','source',fallback='')=='wayfire' and previous.getint('dock','config_mtime',fallback=-1)==data['config_mtime']:
                return
        if target.exists() and target.read_text()==text:return
        runtime.mkdir(parents=True,exist_ok=True)
        temp=runtime/('.dock-'+str(os.getpid())+'.tmp');temp.write_text(text);temp.replace(target)
        from transport import send
        send('dock',str(runtime))
    except OSError:pass


def watch(runtime):
    def run():
        while True:
            refresh(runtime)
            time.sleep(.5)
    threading.Thread(target=run,daemon=True).start()
