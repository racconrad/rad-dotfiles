"""Deliver resident visibility commands before importing the style renderer."""
import json
import os
from pathlib import Path
import stat
import sys


def send(args):
    commands={'toggle':'toggle','open':'show','close':'hide','prewarm':'ping'}
    if len(args)>1 or (args and args[0] not in commands):return False
    home=Path.home();here=Path(__file__).resolve().parent
    root=Path(os.environ.get('XDG_RUNTIME_DIR',home/'.cache'))/'desktop-style'
    try:
        try:
            if json.loads((home/'.config/desktop-style/selector.json').read_text()).get('backend')=='rofi':return False
        except (OSError,ValueError):pass
        sources=[here/'selector_input.c',here.parent/'raccon_menu/navigation.h']
        sources.extend(p for p in (here.parent/'raccon_menu/resident_surface.h',) if p.is_file())
        revision=str(max(p.stat().st_mtime_ns for p in sources))
        if (root/'revision').read_text().strip()!=revision or not (root/'mapped').exists():return False
        fd=os.open(root/'control',os.O_WRONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
        try:
            info=os.fstat(fd)
            if not stat.S_ISFIFO(info.st_mode) or info.st_uid!=os.getuid():return False
            os.write(fd,(commands[args[0] if args else 'toggle']+'\n').encode())
            return True
        finally:os.close(fd)
    except OSError:return False


if __name__=='__main__':
    if not send(sys.argv[1:]):
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from desktop_style.main import main
        main()
