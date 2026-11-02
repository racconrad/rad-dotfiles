#!/usr/bin/env python3
"""Wallpaper catalogue for the floating picker: `walls.py` prints JSON, `walls.py set KIND N` applies one.

Tiles reference wallpapers by index, so odd filenames (quotes, spaces) never reach Eww's shell strings.
"""
import hashlib
import time
import uuid
import tempfile
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOME = Path.home()
DIR = Path(os.environ.get('WALLPAPER_DIR', '@RDOT_HOME@/Pictures/Wallpapers'))
CACHE = Path(os.environ.get('XDG_CACHE_HOME', HOME / '.cache'))
THUMBS = CACHE / 'raccon-float/thumbs'
IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VIDEOS = {'.mp4', '.webm', '.mkv', '.mov'}
COLUMNS = 4
PAGE_SIZE = 12


def kind_of(path):
    ext = path.suffix.lower().rstrip("'")
    return 'images' if ext in IMAGES else 'videos' if ext in VIDEOS else None


def catalogue():
    files = sorted(p for p in DIR.iterdir() if p.is_file() and kind_of(p)) if DIR.is_dir() else []
    return {k: [p for p in files if kind_of(p) == k] for k in ('images', 'videos')}


def thumb(src):
    out = THUMBS / (hashlib.sha1(str(src).encode()).hexdigest() + '.png')
    if out.exists() and out.stat().st_size and src.stat().st_mtime <= out.stat().st_mtime:
        return str(out)
    # Two workers, one decoder thread each; never decode the whole library at open.
    vf = 'scale=480:300:force_original_aspect_ratio=increase,crop=480:300'
    fd, temporary = tempfile.mkstemp(suffix='.png', dir=THUMBS)
    os.close(fd)
    temp = Path(temporary)
    try:
        seeks = (['-ss', '1'], []) if kind_of(src) == 'videos' else ([],)
        for seek in seeks:
            try:
                result = subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y',
                    '-threads', '1', *seek, '-i', str(src), '-filter_threads', '1',
                    '-frames:v', '1', '-vf', vf, '-threads', '1', str(temp)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=8)
            except (subprocess.TimeoutExpired, OSError):
                continue
            if result.returncode == 0 and temp.stat().st_size:
                temp.replace(out)
                return str(out)
        return ''
    finally:
        temp.unlink(missing_ok=True)


def cached_thumb(src):
    out = THUMBS / (hashlib.sha1(str(src).encode()).hexdigest() + '.png')
    try:
        return str(out) if out.stat().st_size and src.stat().st_mtime <= out.stat().st_mtime else ''
    except OSError:return ''


REQUEST = Path(os.environ.get('XDG_RUNTIME_DIR', CACHE)) / 'raccon-float-gallery.json'

def request_gallery(section='all', page=None):
    if section not in ('all','images','videos'):raise ValueError('Unknown wallpaper section')
    REQUEST.parent.mkdir(parents=True,exist_ok=True)
    data=dict(section=section,page=page,token=uuid.uuid4().hex)
    fd,name=tempfile.mkstemp(dir=REQUEST.parent,prefix='.gallery-')
    try:
        with os.fdopen(fd,'w') as stream:json.dump(data,stream)
        os.replace(name,REQUEST)
    finally:
        if os.path.exists(name):os.unlink(name)


def gallery_request():
    try:
        value=json.loads(REQUEST.read_text())
        if isinstance(value,dict) and value.get('section') in ('all','images','videos'):return value
    except (OSError,ValueError):pass
    return dict(section='all',page=None,token='initial')


def current_wallpaper():
    try:
        value=(CACHE/'current-wallpaper').read_text().strip()
        return str(Path(value).resolve()) if value else ''
    except OSError:return ''


def progressive_gallery(request):
    cat=catalogue();cat['all']=sorted(cat['images']+cat['videos'])
    section=request['section'];files=cat[section]
    pages=max(1,(len(files)+PAGE_SIZE-1)//PAGE_SIZE)
    page=max(0,min(int(request.get('page') or 0),pages-1))
    offset=page*PAGE_SIZE if request.get('page') is not None else 0
    if request.get('page') is not None:files=files[offset:offset+PAGE_SIZE]
    current=current_wallpaper()
    tiles=[];missing=[]
    for i,p in enumerate(files):
        cached=cached_thumb(p)
        source=str(p.resolve())
        tiles.append(dict(index=offset+i,name=p.stem,source=source,video=kind_of(p)=='videos',thumb=css_url(cached),has_thumb=bool(cached),current=source==current))
        if not cached:missing.append((p,tiles[-1]))
    data=dict(rows=[dict(i=r,count=len(tiles[i:i+COLUMNS]),tiles=tiles[i:i+COLUMNS]) for r,i in enumerate(range(0,len(tiles),COLUMNS))],
              section=section,page=page,pages=pages,counts={k:len(v) for k,v in cat.items()},loading=bool(missing),error='')
    return data,missing


def watch_gallery():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from raccon_events import FileEvents
    # One resident listener, two decoders maximum, and no queued stale work.
    # Emit cached images/placeholders BEFORE submitting any decoder work.
    THUMBS.mkdir(parents=True,exist_ok=True)
    active=None;pending={};missing=[];data=None;last=0;dirty=False
    with FileEvents([REQUEST,CACHE/'current-wallpaper']) as changes, ThreadPoolExecutor(max_workers=2) as pool:
        while True:
            request=gallery_request();token=request['token']
            if token!=active:
                active=token
                try:data,missing=progressive_gallery(request)
                except OSError:
                    data=dict(rows=[],section=request['section'],page=0,pages=1,counts=dict(all=0,images=0,videos=0),loading=False,error='Wallpaper folder is unavailable.')
                    missing=[]
                print(json.dumps(data),flush=True);last=time.monotonic();dirty=False
            current=current_wallpaper()
            for row in data.get('rows',[]):
                for tile in row['tiles']:
                    selected=bool(current) and tile.get('source')==current
                    if tile.get('current',False)!=selected:
                        tile['current']=selected;dirty=True
            for future,(generation,tile) in list(pending.items()):
                if not future.done():continue
                del pending[future]
                try:path=future.result()
                except (OSError,ValueError):path=''
                if generation==active:
                    tile.update(thumb=css_url(path),has_thumb=bool(path));dirty=True
            while missing and len(pending)<2:
                path,tile=missing.pop(0)
                future=pool.submit(thumb,path)
                pending[future]=(active,tile)
                future.add_done_callback(changes.wake)
            loading=bool(missing or any(g==active for g,t in pending.values()))
            if data['loading']!=loading:data['loading']=loading;dirty=True
            if dirty and (not loading or time.monotonic()-last>=.15):
                # A filter changed during decode: never flash the previous view.
                if gallery_request()['token']==active:print(json.dumps(data),flush=True)
                dirty=False;last=time.monotonic()
            # Only a pending publish batch has a deadline; an idle gallery sleeps
            # until a request or decoder completion, without repeatedly reading JSON.
            changes.wait(max(0,.15-(time.monotonic()-last)) if dirty else None)


def css_url(path):
    return path.replace('\\', '\\\\').replace('"', '\\"')


def rows(files, current, offset=0):
    with ThreadPoolExecutor(max_workers=2) as pool:
        thumbs = list(pool.map(thumb, files))
    tiles = [dict(index=offset+i, name=p.stem, video=kind_of(p) == 'videos', thumb=css_url(t), has_thumb=bool(t), current=str(p) == current)
             for i, (p, t) in enumerate(zip(files, thumbs))]
    return [dict(i=r, count=len(tiles[i:i + COLUMNS]), tiles=tiles[i:i + COLUMNS]) for r, i in enumerate(range(0, len(tiles), COLUMNS))]


def main(args):
    if args[:1]==['watch']:
        watch_gallery();return
    if args[:1]==['request']:
        request_gallery(args[1] if len(args)>1 else 'all',int(args[2]) if len(args)>2 else None);return
    if args[:1] == ['preview-stop']:
        from wall_preview import preview
        preview(selection=args[1] if len(args)>1 else '')
        return
    THUMBS.mkdir(parents=True, exist_ok=True)
    cat = catalogue()
    cat['all'] = sorted(cat['images'] + cat['videos'])
    if args[:1] in (['preview'], ['preview-hover']):
        path = cat[args[1]][int(args[2])]
        if kind_of(path) != 'videos':
            raise ValueError('Preview requires a video')
        from wall_preview import preview
        preview(path, selection=f"{args[1]}:{int(args[2])}", hover=args[0] == "preview-hover")
        return
    if args[:1] == ['set']:
        path = cat[args[1]][int(args[2])]
        if str(path.resolve())==current_wallpaper():return
        os.execv(str(HOME / '.local/bin/wallpaper-set'), ['wallpaper-set', str(path)])
    try:
        current = (CACHE / 'current-wallpaper').read_text().strip()
    except OSError:
        current = ''
    section = args[1] if len(args) > 1 and args[0] in ('page', 'list') else 'all'
    if section not in cat:
        raise ValueError('Unknown wallpaper section')
    requested = int(args[2]) if len(args) > 2 else 0
    pages = max(1, (len(cat[section]) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(requested, pages - 1))
    offset = page * PAGE_SIZE
    visible = cat[section][offset:offset + PAGE_SIZE]
    if not args or args[0] == 'list':
        offset = 0
        visible = cat[section]
    print(json.dumps(dict(rows=rows(visible, current, offset),
        section=section, page=page, pages=pages,
        counts={k: len(v) for k, v in cat.items()})))



if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        assert kind_of(Path("a.JPEG'")) == 'images' and kind_of(Path('b.mp4')) == 'videos'
        assert kind_of(Path('c.txt')) is None
        assert css_url('it"s\\') == 'it\\"s\\\\'
        print('ok')
    else:
        main(sys.argv[1:])
