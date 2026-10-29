"""Calendar/agenda for the resident Raccon window; preserves legacy event storage."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

HOME=Path.home()
ROOT=Path(os.environ.get('XDG_RUNTIME_DIR',HOME/'.cache'))/'raccon-menu'
EVENTS=HOME/'.local/share/desktop-menu/events.json'
PLANNER=HOME/'.config/eww/scripts/planner'


def load(path,default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default


def store(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream,ensure_ascii=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def token(value):return hashlib.sha256(str(value).encode()).hexdigest()[:24]


def selected():
    return dt.date.fromisoformat(load(ROOT/'calendar-date.json',dt.date.today().isoformat()))


def events():
    rows=load(EVENTS,[])
    if not isinstance(rows,list) or any(not isinstance(r,dict) or not all(isinstance(r.get(k),str) for k in ('id','date','title')) for r in rows):
        raise ValueError('Could not read the agenda. Your events file was preserved.')
    return rows


def tasks():
    if not PLANNER.exists():return []
    result=subprocess.run([str(PLANNER),'--once','tasks'],capture_output=True,text=True,timeout=5,check=True)
    return [dict(token=token(item['id']),title=item['text'],done=bool(item['done']),id=item['id'])
            for group in json.loads(result.stdout).get('groups',[]) for item in group.get('items',[])]


def snapshot(task_rows=()):
    date=selected();rows=events()
    present=[dict(token=token(r['id']),title=r['title']) for r in rows if r['date']==date.isoformat()]
    upcoming=[dict(title=r['title'],date=r['date']) for r in sorted(rows,key=lambda r:r['date']) if r['date']>date.isoformat()][:3]
    return dict(day=date.day,month=date.month,year=date.year,date=date.strftime('%d/%m/%Y'),
                events=present,upcoming=upcoming,tasks=list(task_rows) if date==dt.date.today() else [],error='')


def watch():
    previous=None;task_rows=[];refresh=0;task_revision=None
    while True:
        try:
            active=(ROOT/'page').read_text().strip()=='7'
        except OSError:active=False
        if active or previous is None:
            try:
                error=''
                revision=load(ROOT/'calendar-tasks.json',0)
                if revision!=task_revision:refresh=0;task_revision=revision
                if active and time.monotonic()>=refresh:
                    try:task_rows=tasks()
                    except Exception:task_rows=[];error='Could not load tasks.'
                    refresh=time.monotonic()+15
                frame=snapshot(task_rows);frame['error']=error
            except Exception as exc:
                today=dt.date.today();frame=dict(day=today.day,month=today.month,year=today.year,date=today.strftime('%d/%m/%Y'),events=[],upcoming=[],tasks=[],error=str(exc))
            if frame!=previous:
                print(json.dumps(frame,ensure_ascii=False),flush=True);previous=frame
        time.sleep(.4 if active else 1)


def action(args):
    ROOT.mkdir(parents=True,exist_ok=True)
    if args[0]=='select':
        day,month,year=map(int,args[1:4]);store(ROOT/'calendar-date.json',dt.date(year,month,day).isoformat());return
    if args[0]=='today':store(ROOT/'calendar-date.json',dt.date.today().isoformat());return
    if args[0]=='task':
        row=next(r for r in tasks() if r['token']==args[1])
        subprocess.run([str(PLANNER),'task',str(row['id'])],check=True,capture_output=True,timeout=5)
        store(ROOT/'calendar-tasks.json',time.time_ns());return
    EVENTS.parent.mkdir(parents=True,exist_ok=True)
    with EVENTS.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=events()
        if args[0]=='add':
            title=sys.stdin.read(501).strip()
            if not title or len(title)>500:raise ValueError('Enter an event with up to 500 characters.')
            rows.append(dict(id=uuid.uuid4().hex,date=selected().isoformat(),title=title))
        elif args[0]=='remove':rows=[r for r in rows if token(r['id'])!=args[1]]
        else:raise ValueError('Unknown calendar action.')
        store(EVENTS,rows)


if __name__=='__main__':
    try:
        if sys.argv[1:]==['watch']:watch()
        else:action(sys.argv[1:])
    except (KeyboardInterrupt,BrokenPipeError):pass
    except Exception as exc:
        # Surface failures without resetting the entry or overwriting user data.
        message='Could not update the agenda: '+str(exc)
        subprocess.run(['eww','--no-daemonize','-c',str(HOME/'.config/raccon-menu'),'update','error='+json.dumps(message)],capture_output=True)
        raise SystemExit(1)
