"""Small inline Eww preview: one cached 4-second clip, 12 fps, no player window."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache')) / 'raccon-float/preview'
STATE = ROOT / 'state.json'


def read_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def write_state(data):
    ROOT.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=ROOT, suffix='.json')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
        os.replace(name, STATE)
    finally:
        Path(name).unlink(missing_ok=True)


def preview(path=None, selection="", hover=False):
    previous = read_state()
    if path is None and selection and previous.get('selection') != selection:
        return
    if path is not None and previous.get('active') and previous.get('selection') == selection and selection:
        return
    token = uuid.uuid4().hex
    if path is None:
        write_state({'token': token, 'active': False})
        return
    write_state({'token': token, 'selection': selection, 'active': True, 'message': 'Loading preview…'})
    if hover:
        time.sleep(.18)
        if read_state().get('token') != token:
            return
    try:
        key = hashlib.sha256(f'tile-v2:{path}:{path.stat().st_mtime_ns}'.encode()).hexdigest()[:24]
        target = ROOT / key
        with (ROOT/'decode.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if read_state().get('token') != token:
                return
            if not list(target.glob('*.jpg')):
                temporary = Path(tempfile.mkdtemp(dir=ROOT))
                try:
                    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y',
                        '-threads', '1', '-i', str(path), '-t', '4', '-an',
                        '-filter_threads', '1', '-vf',
                        'fps=12,scale=340:214:force_original_aspect_ratio=increase,crop=340:214',
                        '-frames:v', '48', '-q:v', '5', '-threads', '1', str(temporary/'%03d.jpg')],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE, timeout=15, check=True)
                    if not list(temporary.glob('*.jpg')):
                        raise ValueError('No video frames')
                    if target.exists():
                        shutil.rmtree(target)
                    temporary.rename(target)
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary)
            frames = [str(p) for p in sorted(target.glob('*.jpg'))]
        if read_state().get('token') == token:
            write_state({'token': token, 'selection': selection, 'active': True, 'frames': frames,
                         'message': 'Preview · muted'})
    except (OSError, ValueError, subprocess.SubprocessError):
        if read_state().get('token') == token:
            write_state({'token': token, 'selection': selection, 'active': True, 'message': 'Could not preview this video.'})


def presentation(state):
    frames = state.get('frames', []) if state.get('active') else []
    clip = str(Path(frames[0]).parent) if frames else ''
    selection = state.get('selection', '')
    return dict(active=bool(state.get('active')), selection=selection, clip=clip,
                playback=selection+'\n'+clip, message=state.get('message', ''))


def watch():
    last = None
    while True:
        # Eww receives only state changes. Native GTK advances the active image.
        line = json.dumps(presentation(read_state()))
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(.1)


if __name__ == '__main__':
    if sys.argv[1:] == ['watch']:
        watch()
