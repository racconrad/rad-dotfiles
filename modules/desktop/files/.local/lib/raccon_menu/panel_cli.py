"""Only visibility/navigation imports on the panel's warm path."""
import os
import sys
from transport import send

pages = {'audio':'4','connections':'5','bluetooth':'6','calendar':'7'}
args = sys.argv[1:]
command = None
if not args: command = 'service 4'
elif len(args) == 1 and args[0] in pages: command = 'service '+pages[args[0]]
elif args == ['close']: command = 'hide'
elif len(args) == 2 and args[0] == 'tab' and args[1] in pages: command = 'service '+pages[args[1]]
runtime = os.path.join(os.environ.get('XDG_RUNTIME_DIR',os.path.expanduser('~/.cache')),'raccon-menu')
if command and send(command,runtime): raise SystemExit(0)
os.execv(sys.executable,[sys.executable,os.path.join(os.path.dirname(__file__),'panels.py'),*args])
