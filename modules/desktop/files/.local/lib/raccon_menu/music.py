#!/usr/bin/env python3
"""Stream the active MPRIS player as JSON lines for the menu music card."""
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CACHE = Path.home() / '.cache/raccon-menu/art'
FIELDS = ('player', 'status', 'title', 'artist', 'art', 'position', 'length')
FORMAT = '\x1f'.join('{{%s}}' % key for key in
                     ('playerName', 'status', 'title', 'artist', 'mpris:artUrl', 'position', 'mpris:length'))
EMPTY = {'visible': False, 'playing': False, 'title': '', 'artist': '', 'art': '', 'has_art': False,
         'time': '', 'percent': 0}
MAX_ART = 8 << 20


def clock(micro):
    seconds = max(0, int(micro or 0) // 1_000_000)
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


def artwork(url):
    if url.startswith('file://'):
        path = urllib.request.url2pathname(url[7:])
        # The path lands in a CSS url('...'); quotes would break the card style.
        return path if Path(path).is_file() and not set('\'\\') & set(path) else ''
    if not url.startswith(('http://', 'https://')):
        return ''
    target = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if target.is_file():
        return str(target)
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = response.read(MAX_ART + 1)
        if len(data) > MAX_ART:
            return ''
        CACHE.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix('.part')
        part.write_bytes(data)
        part.replace(target)
        return str(target)
    except (OSError, ValueError):
        return ''


def state(line, art_cache):
    values = dict(zip(FIELDS, line.rstrip('\n').split('\x1f')))
    if len(values) < len(FIELDS) or not values['title']:
        return EMPTY
    url = values['art']
    if url not in art_cache:
        art_cache.clear()
        art_cache[url] = artwork(url) if url else ''
    art = art_cache[url]
    position, length = (int(values[k]) if values[k].isdigit() else 0 for k in ('position', 'length'))
    return {'visible': True, 'playing': values['status'] == 'Playing', 'title': values['title'],
            'artist': values['artist'] or values['player'].split('.')[0].capitalize(),
            'art': art, 'has_art': bool(art),
            'time': f'{clock(position)} / {clock(length)}' if length else clock(position),
            'percent': round(min(100, position * 100 / length), 1) if length else 0}


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from raccon_events import FileEvents
    flag = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'raccon-music.open'
    def stop(_signal, _frame):
        raise SystemExit()
    signal.signal(signal.SIGTERM, stop)
    art_cache = {}
    follow = None
    with FileEvents([flag]) as changes:
        emit(EMPTY)
        try:
            while True:
                if not flag.exists():
                    if follow is not None:
                        follow.terminate()
                        try:
                            follow.wait(timeout=.5)
                        except subprocess.TimeoutExpired:
                            follow.kill()
                            follow.wait()
                        follow.stdout.close()
                        follow = None
                    changes.wait()
                    continue
                if follow is None:
                    try:
                        follow = subprocess.Popen(['playerctl', '--follow', 'metadata', '--format', FORMAT],
                                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        changes.wait(3600)
                        continue
                    buffered, last = b'', None
                ready, _, _ = select.select([changes, follow.stdout], [], [])
                if changes in ready:
                    changes.drain()
                    if not flag.exists():
                        continue
                if follow.stdout in ready:
                    chunk = os.read(follow.stdout.fileno(), 65536)
                    if not chunk:
                        follow.wait()
                        follow.stdout.close()
                        follow = None
                        emit(EMPTY)
                        changes.wait(2)
                        continue
                    buffered += chunk
                    while b'\n' in buffered:
                        line, buffered = buffered.split(b'\n', 1)
                        value = state(line.decode(errors='replace'), art_cache)
                        if value != last:
                            emit(value)
                            last = value
        finally:
            if follow is not None:
                follow.terminate()
                try:
                    follow.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    follow.kill()
                    follow.wait()
                follow.stdout.close()


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        line = '\x1f'.join(['spotify', 'Playing', 'Song', '', '', '61000000', '183000000'])
        out = state(line, {})
        assert out['time'] == '1:01 / 3:03' and out['artist'] == 'Spotify' and out['playing'], out
        assert state('\x1f' * 6, {}) == EMPTY
        assert clock(3_723_000_000) == '1:02:03'
        print('ok')
    else:
        main()
