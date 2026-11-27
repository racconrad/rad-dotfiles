from pathlib import Path
import sys
import importlib

ROOT = Path(__file__).resolve().parents[1]


class Context:
    """Provides access to installer globals, mocks, and helpers."""

    def __init__(self, g=None):
        if isinstance(g, Context):
            self._g = g._g
        elif isinstance(g, dict):
            self._g = g
        elif g is not None and hasattr(g, '__dict__'):
            self._g = g.__dict__
        else:
            self._g = {}

    def __getattr__(self, name):
        if name in self._g:
            return self._g[name]
        for mod_name in ('install', 'scripts.install', 'rdot_install', 'rdot_install_zsh', 'bundle_installer', 'styles_installer'):
            mod = sys.modules.get(mod_name)
            if mod is not None and hasattr(mod, name):
                return getattr(mod, name)
        for sub in ('install_selection', 'install_widgets', 'install_plan', 'install_setup', 'install_wizard', 'install_screens', 'install_render'):
            sub_mod = sys.modules.get(sub) or sys.modules.get(f'scripts.{sub}')
            if sub_mod is None:
                try:
                    sub_mod = importlib.import_module(sub)
                except ImportError:
                    try:
                        sub_mod = importlib.import_module(f'scripts.{sub}')
                    except ImportError:
                        sub_mod = None
            if sub_mod is not None and hasattr(sub_mod, name):
                return getattr(sub_mod, name)
        import subprocess
        import shutil
        if name == 'subprocess':
            return subprocess
        if name == 'shutil':
            return shutil
        if name == 'ROOT':
            return ROOT
        raise AttributeError(f"Context has no attribute '{name}'")
