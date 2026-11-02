"""Calendar/agenda for the resident Raccon window; preserves legacy event storage."""
import calendar
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
    try:return dt.date.fromisoformat(load(ROOT/'calendar-date.json',dt.date.today().isoformat()))
    except (OSError,ValueError,TypeError):return dt.date.today()


def events():
    rows=load(EVENTS,[])
    if not isinstance(rows,list) or any(not isinstance(r,dict) or not all(isinstance(r.get(k),str) for k in ('id','date','title')) for r in rows):
        raise ValueError('Could not read the agenda. Your events file was preserved.')
    for row in rows:
        try:dt.date.fromisoformat(row['date'])
        except ValueError:raise ValueError('An event has an invalid date. Your events file was preserved.')
    return rows


def tasks():
    if not PLANNER.exists():return []
    result=subprocess.run([str(PLANNER),'--once','tasks'],capture_output=True,text=True,timeout=5,check=True)
    return [dict(token=token(item['id']),title=item['text'],done=bool(item['done']),id=item['id'])
            for group in json.loads(result.stdout).get('groups',[]) for item in group.get('items',[])]


MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')


def calendar_grid(date, rows):
    first=date.replace(day=1);occupied={r['date'] for r in rows};today=dt.date.today()
    cells=[]
    for offset in range(42):
        try:day=first+dt.timedelta(days=offset-first.weekday())
        except OverflowError:
            cells.append(dict(day='',iso='',selected=False,today=False,other=True,event=False));continue
        cells.append(dict(day=str(day.day),iso=day.isoformat(),selected=day==date,today=day==today,
                          other=day.month!=date.month,event=day.isoformat() in occupied))
    return [cells[i:i+7] for i in range(0,42,7)]


def snapshot(task_rows=(), rows=None, error=''):
    date=selected();rows=events() if rows is None else rows
    present=[dict(token=token(r['id']),title=r['title']) for r in rows if r['date']==date.isoformat()]
    upcoming=[dict(title=r['title'],date=r['date']) for r in sorted(rows,key=lambda r:r['date']) if r['date']>date.isoformat()][:3]
    return dict(day=date.day,month=date.month,year=date.year,date=date.strftime('%d/%m/%Y'),iso=date.isoformat(),
                month_title=f'{MONTHS[date.month-1]} {date.year}',weekdays=['M','T','W','T','F','S','S'],
                weeks=calendar_grid(date,rows),events=present,upcoming=upcoming,
                tasks=list(task_rows) if date==dt.date.today() else [],error=error)


def watch():
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from raccon_events import FileEvents
    previous=None;task_rows=[];refresh=0;task_error=''
    with FileEvents([ROOT/'calendar-date.json',ROOT/'calendar-tasks.json',EVENTS,ROOT/'page',ROOT/'visible']) as changes:
        while True:
            try:active=(ROOT/'page').read_text().strip()=='7' and (ROOT/'visible').read_text().strip()=='1'
            except OSError:active=False
            if active or previous is None:
                if active and time.monotonic()>=refresh:
                    try:task_rows=tasks();task_error=''
                    except Exception:task_rows=[];task_error='Could not load tasks. Reopen the calendar to retry.'
                    refresh=time.monotonic()+15
                try:frame=snapshot(task_rows,error=task_error)
                except Exception as exc:frame=snapshot(rows=[],error=str(exc))
                if frame!=previous:
                    print(json.dumps(frame,ensure_ascii=False),flush=True);previous=frame
            changed=changes.wait(max(0,refresh-time.monotonic()) if active else None)
            if ROOT/'calendar-tasks.json' in changed or ROOT/'page' in changed or ROOT/'visible' in changed:refresh=0


def action(args):
    ROOT.mkdir(parents=True,exist_ok=True)
    if args[0]=='select':
        if len(args)==2:date=dt.date.fromisoformat(args[1])
        else:
            day,month,year=map(int,args[1:4]);date=dt.date(year,month,day)
        store(ROOT/'calendar-date.json',date.isoformat());return
    if args[0]=='move':
        offset=int(args[1])
        if offset not in (-1,1):raise ValueError('Invalid month change.')
        date=selected();index=date.year*12+date.month-1+offset;year,month=divmod(index,12);month+=1
        date=dt.date(year,month,min(date.day,calendar.monthrange(year,month)[1]))
        store(ROOT/'calendar-date.json',date.isoformat());return
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
            date=dt.date.fromisoformat(args[1]) if len(args)>1 else selected()
            rows.append(dict(id=uuid.uuid4().hex,date=date.isoformat(),title=title))
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
