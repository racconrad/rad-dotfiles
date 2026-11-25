"""One MPRIS + Cava status follower shared by all Waybar music widgets."""
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import uuid

import raccon_cava
from raccon_events import FileEvents

RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', Path.home() / '.cache'))
ROOT = RUNTIME / 'raccon-waybar-music'
# Match the music card's existing flag, including its /tmp fallback.
FLAG = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'raccon-music.open'
META_FORMAT = '\x1f'.join('{{%s}}' % k for k in ('status', 'title', 'artist', 'album', 'playerName'))
IDLE_BARS = '▁▁▁▁▁▁▁▁'
TRACK_WIDTH = 22
TIPS = dict(
    open='Show music player',
    viz='Live audio visualizer · click for player · scroll for volume',
    track='Now playing · click for player · middle: play/pause · right: raise app',
    prev='Previous',
    play='Play / Pause',
    next='Next',
)


def marquee(text, step, width=TRACK_WIDTH):
    """Return a fixed-width scrolling slice when text exceeds width."""
    if not text or len(text) <= width:
        return text
    if step <= 3:
        return text[:width]
    loop = text + '   ·   '
    idx = (step - 3) % len(loop)
    doubled = loop + loop
    return doubled[idx:idx + width]


def format_track(title, artist):
    title = (title or '').strip()
    artist = (artist or '').strip()
    if title and artist:
        return f'{title} · {artist}'
    return title or artist


def format_tooltip(status, title, artist, album, player):
    lines = []
    if title:
        lines.append(title)
    meta = ' · '.join(part for part in (artist, album) if part)
    if meta:
        lines.append(meta)
    state_label = f'{status} · {player}' if player else status
    if state_label:
        lines.append(state_label)
    lines.append('Click: player · Middle: play/pause · Right: raise app')
    return '\n'.join(lines)


def snapshot(status, card_open, track='', bars='', level=0, tooltip=''):
    icons = dict(open='\ueb3b', prev='\ueba4', play='\ueb4b' if status == 'Playing' else '\ueb68', next='\ueba6')
    active = status in ('Playing', 'Paused') and not card_open
    if not active:
        out = {mode: dict(text='') for mode in icons}
        out['viz'] = dict(text='')
        out['track'] = dict(text='')
        return out
    base = status.lower()
    lvl = max(0, min(3, int(level)))
    reactive = [base, f'level-{lvl}'] if status == 'Playing' else [base]
    out = {}
    for mode, icon in icons.items():
        out[mode] = dict(text=icon, tooltip=TIPS[mode], **{'class': base})
    out['viz'] = dict(
        text=bars if (status == 'Playing' and bars) else IDLE_BARS,
        tooltip=tooltip or TIPS['viz'],
        **{'class': reactive},
    )
    out['track'] = (
        dict(text=track, tooltip=tooltip or TIPS['track'], **{'class': reactive})
        if track else dict(text='')
    )
    return out


def directory():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if ROOT.is_symlink() or ROOT.stat().st_uid != os.getuid():
        raise OSError('Invalid music runtime directory')
    ROOT.chmod(0o700)


def serve():
    directory()
    with (ROOT / 'provider.lock').open('w') as lock:
        for attempt in range(20):
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if (ROOT / 'subscribe').exists() or attempt == 19:
                    return
                time.sleep(0.02)
        path = ROOT / 'subscribe'
        path.unlink(missing_ok=True)
        os.mkfifo(path, 0o600)
        inbox = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        (ROOT / 'provider.pid').write_text(str(os.getpid()))
        clients = {}
        child = None
        cava_proc = None
        status, title, artist, album, player = '', '', '', '', ''
        bars, level = IDLE_BARS, 0
        marquee_step, next_marquee = 0, 0.0
        buffered, cava_buf, requests, latest = b'', b'', b'', None
        retry, cava_retry, idle_until = 0.0, 0.0, time.monotonic() + 5
        poll = select.poll()
        poll.register(inbox, select.POLLIN)
        with FileEvents([FLAG]) as changes:
            poll.register(changes, select.POLLIN)

            def remove(fd):
                nonlocal idle_until
                poll.unregister(fd)
                name = clients.pop(fd)
                os.close(fd)
                (ROOT / name).unlink(missing_ok=True)
                if not clients:
                    idle_until = time.monotonic() + 3

            def send(fd):
                try:
                    # One small atomic pipe write; a slow/dead bar cannot block others.
                    os.write(fd, latest)
                except OSError:
                    remove(fd)

            def publish():
                nonlocal latest
                card_open = FLAG.exists()
                full = format_track(title, artist)
                visible_track = marquee(full, marquee_step) if status == 'Playing' else full[:TRACK_WIDTH]
                tip = format_tooltip(status, title, artist, album, player) if full else ''
                payload = snapshot(status, card_open, track=visible_track, bars=bars, level=level, tooltip=tip)
                value = json.dumps(payload, ensure_ascii=False).encode() + b'\n'
                if value == latest:
                    return
                latest = value
                for fd in tuple(clients):
                    send(fd)

            def stop_player():
                nonlocal child
                if child is None:
                    return
                if child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                child.stdout.close()
                child = None

            def stop_cava():
                nonlocal cava_proc, cava_buf, bars, level
                if cava_proc is not None:
                    try:
                        poll.unregister(cava_proc.stdout)
                    except (KeyError, ValueError):
                        pass
                    cava_proc = raccon_cava.stop(cava_proc)
                cava_buf = b''
                bars = IDLE_BARS
                level = 0

            def sync_cava(now):
                nonlocal cava_proc, cava_retry, cava_buf
                want = bool(clients) and status == 'Playing' and not FLAG.exists()
                if not want:
                    if cava_proc is not None:
                        stop_cava()
                    return
                if cava_proc is None and now >= cava_retry:
                    try:
                        cava_proc = raccon_cava.spawn(
                            ROOT / 'cava.conf', bars=8, framerate=22, max_range=7, nonblocking=True
                        )
                        poll.register(cava_proc.stdout, select.POLLIN | select.POLLHUP)
                        cava_buf = b''
                    except OSError:
                        stop_cava()
                        cava_retry = now + 3

            try:
                publish()
                while clients or time.monotonic() < idle_until:
                    now = time.monotonic()
                    if child is None and now >= retry:
                        try:
                            child = subprocess.Popen(
                                ['playerctl', '--follow', 'metadata', '--format', META_FORMAT],
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL,
                            )
                            os.set_blocking(child.stdout.fileno(), False)
                            poll.register(child.stdout, select.POLLIN | select.POLLHUP)
                            buffered = b''
                        except OSError:
                            stop_player()
                            retry = now + 2

                    sync_cava(now)

                    full_track = format_track(title, artist)
                    scrolling = bool(clients) and status == 'Playing' and not FLAG.exists() and len(full_track) > TRACK_WIDTH
                    if scrolling and now >= next_marquee:
                        if next_marquee > 0:
                            marquee_step += 1
                            publish()
                        next_marquee = now + 0.42
                    elif not scrolling:
                        next_marquee = 0.0

                    deadlines = []
                    if not clients:
                        deadlines.append(idle_until)
                    if child is None:
                        deadlines.append(retry)
                    if bool(clients) and status == 'Playing' and not FLAG.exists() and cava_proc is None:
                        deadlines.append(cava_retry)
                    if scrolling and next_marquee > 0:
                        deadlines.append(next_marquee)
                    timeout = max(0, (min(deadlines) - time.monotonic()) * 1000) if deadlines else None

                    for fd, _flags in poll.poll(timeout):
                        if fd == inbox:
                            requests += os.read(inbox, 65536)
                            while b'\n' in requests:
                                line, requests = requests.split(b'\n', 1)
                                name = os.fsdecode(line)
                                if not name.startswith('client-') or '/' in name or len(name) > 100:
                                    continue
                                client_path = ROOT / name
                                try:
                                    info = client_path.lstat()
                                    if not stat.S_ISFIFO(info.st_mode) or info.st_uid != os.getuid():
                                        continue
                                    writer = os.open(client_path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
                                except OSError:
                                    continue
                                clients[writer] = name
                                poll.register(writer, select.POLLERR | select.POLLHUP)
                                send(writer)
                            if len(requests) > 65536:
                                requests = b''
                        elif fd in clients:
                            # Closing a module's read end wakes POLLERR immediately.
                            remove(fd)
                        elif fd == changes.fileno():
                            if changes.drain():
                                sync_cava(time.monotonic())
                                publish()
                        elif child is not None and fd == child.stdout.fileno():
                            data = os.read(fd, 65536)
                            if not data:
                                poll.unregister(fd)
                                stop_player()
                                status, title, artist, album, player = '', '', '', '', ''
                                marquee_step = 0
                                stop_cava()
                                retry = time.monotonic() + 2
                                publish()
                            else:
                                buffered += data
                                while b'\n' in buffered:
                                    line, buffered = buffered.split(b'\n', 1)
                                    parts = line.decode(errors='replace').rstrip('\r\n').split('\x1f')
                                    if len(parts) >= 5:
                                        new_status, new_title, new_artist, new_album, new_player = parts[:5]
                                    else:
                                        new_status = parts[0].strip() if parts else ''
                                        new_title = new_artist = new_album = new_player = ''
                                    if (new_title, new_artist) != (title, artist):
                                        marquee_step = 0
                                        next_marquee = 0.0
                                    status = new_status.strip()
                                    title, artist, album, player = new_title, new_artist, new_album, new_player.strip()
                                    sync_cava(time.monotonic())
                                    publish()
                                if len(buffered) > 65536:
                                    buffered = b''
                        elif cava_proc is not None and fd == cava_proc.stdout.fileno():
                            data = os.read(fd, 65536)
                            if not data:
                                stop_cava()
                                cava_retry = time.monotonic() + 2
                                publish()
                            else:
                                cava_buf += data
                                if b'\n' in cava_buf:
                                    lines = cava_buf.split(b'\n')
                                    cava_buf = lines[-1]
                                    # Render only the freshest audio frame to keep zero lag.
                                    for raw in reversed(lines[:-1]):
                                        vals = raccon_cava.parse_line(raw.decode(errors='replace'), bars=8, max_range=7)
                                        if vals is not None:
                                            bars = raccon_cava.bars_text(vals)
                                            level = raccon_cava.energy_level(vals, max_range=7)
                                            publish()
                                            break
                                if len(cava_buf) > 65536:
                                    cava_buf = b''
            finally:
                path.unlink(missing_ok=True)
                (ROOT / 'provider.pid').unlink(missing_ok=True)
                if cava_proc is not None and cava_proc.poll() is None:
                    cava_proc.terminate()
                if child is not None and child.poll() is None:
                    child.terminate()
                stop_cava()
                stop_player()
                for fd in tuple(clients):
                    remove(fd)
                os.close(inbox)


def updates():
    directory()
    path = ROOT / ('client-' + str(os.getpid()) + '-' + uuid.uuid4().hex)
    os.mkfifo(path, 0o600)
    reader = keeper = -1
    try:
        reader = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        # Keep the pipe alive only until the provider's first snapshot arrives.
        keeper = os.open(path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        with (ROOT / 'start.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            launched = False
            for _ in range(60):
                try:
                    inbox = os.open(ROOT / 'subscribe', os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                    try:
                        os.write(inbox, os.fsencode(path.name) + b'\n')
                    finally:
                        os.close(inbox)
                    break
                except OSError:
                    if not launched:
                        subprocess.Popen(
                            [sys.executable, str(Path(__file__).resolve()), 'serve'],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True,
                        )
                        launched = True
                    time.sleep(0.025)  # Startup/reconnection only.
            else:
                raise OSError('Music status provider did not start')
        if not select.select([reader], [], [], 2)[0]:
            raise OSError('Music status subscription timed out')
        os.close(keeper)
        keeper = -1
        os.set_blocking(reader, True)
        with os.fdopen(reader) as stream:
            reader = -1
            yield from stream
    finally:
        for fd in (reader, keeper):
            if fd >= 0:
                os.close(fd)
        path.unlink(missing_ok=True)


def listen(mode):
    previous = None
    while True:
        try:
            for line in updates():
                value = json.loads(line)[mode]
                if value != previous:
                    print(json.dumps(value, ensure_ascii=False), flush=True)
                    previous = value
        except BrokenPipeError:
            return
        except (OSError, ValueError, KeyError):
            pass
        value = dict(text='')
        if value != previous:
            print(json.dumps(value), flush=True)
            previous = value
        time.sleep(1)  # Provider failure/restart only.


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    try:
        if mode == 'serve':
            def stop(*_args):
                raise SystemExit(0)
            signal.signal(signal.SIGTERM, stop)
            serve()
        elif mode in TIPS:
            listen(mode)
        else:
            raise SystemExit('Usage: waybar-music open|viz|track|prev|play|next')
    except (BrokenPipeError, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    main()
