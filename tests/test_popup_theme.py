"""Popup themes follow resolved tokens even without Waybar Matugen exports."""
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT/'modules/desktop/files/.local/lib/raccon_menu'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


menu = load('popup_theme_menu', LIB/'backend.py')
styles = load('popup_theme_styles', ROOT/'modules/desktop-styles/files/.local/lib/desktop_style/main.py')
appearance = load('popup_theme_adapter', ROOT/'modules/desktop-styles/files/.local/lib/desktop_style/appearance.py')


class PopupThemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        for key, value in dict(HOME=self.home, CONFIG=self.home/'.config/raccon-menu', POWER=self.home/'.local/state/desktop-power').items():
            p = patch.object(menu, key, value); p.start(); self.addCleanup(p.stop)
        for name in ('raccon-menu','raccon-float','raccon-music','desktop-style/current','eww','waybar'):
            (self.home/'.config'/name).mkdir(parents=True)
        self.tokens = self.home/'.config/desktop-style/current/tokens.json'
        (self.home/'.config/waybar/colors.css').write_text('@define-color primary #ee1133;')
        (self.home/'.config/eww/_colors.scss').write_text('$primary: #112233;')
        self.source = dict(re.findall(r'\$(\w+):\s*(#[\da-fA-F]{6});',
            (ROOT/'modules/desktop-styles/files/.config/desktop-style/_palette.scss').read_text()))

    def publish(self, name):
        colors, _ = styles.palette(name, self.source)
        output = appearance.build(name, styles.PROFILES[name], colors)
        new = self.tokens.with_suffix('.next'); new.write_text(output['tokens']); new.replace(self.tokens)
        (menu.CONFIG/'_desktop-style.scss').write_text(output['raccon'])
        return colors

    def test_all_profiles_override_stale_palettes_and_update_local_imports(self):
        for name in styles.PROFILES:
            with self.subTest(style=name):
                colors = self.publish(name); menu.palette()
                for popup in ('raccon-menu','raccon-float','raccon-music'):
                    folder = self.home/'.config'/popup
                    self.assertIn('$primary: '+colors['primary']+';', (folder/'_palette.scss').read_text())
                    self.assertEqual((folder/'_desktop-style.scss').read_text(), (menu.CONFIG/'_desktop-style.scss').read_text())
                shape = self.home/'.config/raccon-float/_tokens.scss'
                self.assertIn('$radius: '+str(styles.PROFILES[name]['radius'])+'px;', shape.read_text())
                self.assertIn(styles.PROFILES[name]['font'], shape.read_text())
                before = shape.stat().st_mtime_ns; menu.palette()
                self.assertEqual(shape.stat().st_mtime_ns, before)
                self.assertEqual(menu.appearance_state({})['motion'], menu.motion({}) > 0)
        self.assertIn('#ee1133', (self.home/'.config/waybar/colors.css').read_text())

    def test_restore_or_invalid_tokens_fall_back_without_retaining_old_style(self):
        self.publish('ascii'); menu.palette()
        self.tokens.unlink(); menu.palette()
        self.assertIn('$primary: #ee1133;', (menu.CONFIG/'_palette.scss').read_text())
        self.assertEqual(menu.appearance_state({})['style'], 'original')
        for value in ('[]','null','{broken','{"style":[],"colors":[]}'):
            self.tokens.write_text(value); menu.palette()
            self.assertEqual(menu.appearance_state({})['style'], 'original')

    def test_theme_listener_changes_while_main_menu_is_hidden(self):
        self.publish('modern')
        runtime = self.home/'runtime/raccon-menu'; runtime.mkdir(parents=True)
        (runtime/'visible').write_text('0')
        env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(runtime.parent),
                   XDG_STATE_HOME=str(self.home/'.local/state'),
                   PYTHONPATH=str(ROOT/'modules/base/files/.local/lib'))
        proc = subprocess.Popen([sys.executable, str(LIB/'backend.py'), 'listen-appearance'], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def receive():
            ready, _, _ = select.select([proc.stdout], [], [], 4)
            self.assertTrue(ready, 'appearance listener did not emit')
            return json.loads(proc.stdout.readline())
        try:
            self.assertEqual(receive()['style'], 'modern')
            self.publish('ascii')
            state = receive(); self.assertEqual(state['style'], 'ascii'); self.assertEqual(state['motion'], menu.motion({}) > 0)
            self.assertEqual((runtime/'visible').read_text(), '0')
        finally:
            proc.terminate(); proc.communicate(timeout=4)

    def test_music_refresh_never_toggles_or_closes_the_card(self):
        binary = self.home/'.local/bin'; binary.mkdir(parents=True)
        backend = self.home/'.local/lib/raccon_menu/backend.py'; backend.parent.mkdir(parents=True); backend.write_text('')
        eww = binary/'eww'; log = self.home/'calls'
        eww.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'); eww.chmod(0o755)
        env = dict(os.environ, HOME=str(self.home), PATH=str(binary)+':'+os.environ['PATH'], CALL_LOG=str(log))
        subprocess.run(['bash', str(ROOT/'modules/desktop/files/.local/bin/raccon-music'), 'refresh'], env=env, check=True)
        calls = log.read_text()
        self.assertIn('reload', calls)
        self.assertNotIn('active-windows', calls); self.assertNotIn(' close ', calls); self.assertNotIn(' open ', calls)
