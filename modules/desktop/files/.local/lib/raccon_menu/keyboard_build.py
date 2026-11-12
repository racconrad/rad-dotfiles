"""Compile the floating cards' GTK keyboard adapter, only when its sources change."""
import fcntl
import os
from pathlib import Path
import shlex
import subprocess
HERE=Path(__file__).resolve().parent
OUT=Path.home()/'.cache/raccon-float/keyboard.so'
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
print(OUT)
