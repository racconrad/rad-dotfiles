#!/usr/bin/env python3
"""CLI compatibility entry point for the packaged Raccon SDDM theme."""
from pathlib import Path
import runpy

module = runpy.run_path(str(Path(__file__).resolve().parents[2] /
    'modules/desktop-styles/files/.local/share/raccon/sddm/prepare.py'))
prepare = module['prepare']

if __name__ == '__main__':
    module['main']()
