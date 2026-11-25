"""Compile the floating cards' GTK keyboard adapter and confetti binary, only when sources change."""
import fcntl
import os
from pathlib import Path
import shlex
import subprocess
HERE=Path(__file__).resolve().parent
CACHE=Path.home()/'.cache/raccon-float'
OUT=CACHE/'keyboard.so'
CONFETTI=CACHE/'raccon-confetti'
OUT.parent.mkdir(parents=True,exist_ok=True)
with (OUT.parent/'keyboard.lock').open('w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    if not OUT.exists() or OUT.stat().st_mtime_ns < max((HERE/n).stat().st_mtime_ns for n in ('float_input.c','navigation.h','thumbnail_playback.h','float_resident.h','resident_surface.h','soft_icons.h', 'popup_geometry.h')):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0','libjpeg'],text=True))
        temp=OUT.with_name(f'keyboard-{os.getpid()}.so')
        try:
            subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-Wno-unused-parameter',str(HERE/'float_input.c'),'-o',str(temp),*flags],check=True)
            temp.replace(OUT)
        finally:temp.unlink(missing_ok=True)
    confetti_src=HERE/'confetti.c'
    if confetti_src.exists() and (not CONFETTI.exists() or CONFETTI.stat().st_mtime_ns < confetti_src.stat().st_mtime_ns):
        try:
            cflags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0','gtk-layer-shell-0'],text=True))
            temp_c=CONFETTI.with_name(f'confetti-{os.getpid()}')
            try:
                subprocess.run(['cc','-O2','-Wall','-Wextra','-Wno-unused-parameter',str(confetti_src),'-o',str(temp_c),*cflags,'-lm'],check=True)
                temp_c.replace(CONFETTI)
            finally:temp_c.unlink(missing_ok=True)
        except (OSError, subprocess.CalledProcessError):
            pass
print(OUT)
