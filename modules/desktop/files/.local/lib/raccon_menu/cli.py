"""Tiny warm path. Import the controller only for work requiring it."""
import os
import sys
from transport import request, send

command = request(sys.argv[1:])
if command is not None and send(command):
    raise SystemExit(0)
os.execv(sys.executable, [sys.executable, os.path.join(os.path.dirname(__file__), 'backend.py'), *sys.argv[1:]])
