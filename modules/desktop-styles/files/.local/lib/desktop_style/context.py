from pathlib import Path
import sys


class Context:
    """Provides access to module attributes with fallback to desktop_style.main or defaults."""

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
        main_mod = sys.modules.get('desktop_style.main')
        if main_mod is not None and hasattr(main_mod, name):
            return getattr(main_mod, name)
        if name == 'HOME':
            return Path.home()
        if name == 'CONFIG':
            return self.HOME / '.config/desktop-style'
        if name == 'STATE':
            return self.HOME / '.local/state/desktop-style'
        if name == 'CURRENT':
            return self.CONFIG / 'current'
        if name == 'BIN':
            return self.HOME / '.local/bin'
        from desktop_style import helpers
        if hasattr(helpers, name):
            return getattr(helpers, name)
        from desktop_style import colors
        if hasattr(colors, name):
            return getattr(colors, name)
        from desktop_style import launchers
        if hasattr(launchers, name):
            return getattr(launchers, name)
        from desktop_style import pipeline
        if hasattr(pipeline, name):
            return getattr(pipeline, name)
        from desktop_style import frames
        if hasattr(frames, name):
            return getattr(frames, name)
        from desktop_style import apply
        if hasattr(apply, name):
            return getattr(apply, name)
        from desktop_style import sddm
        if hasattr(sddm, name):
            return getattr(sddm, name)
        raise AttributeError(f"Context has no attribute '{name}'")
