"""Eww menu contracts without a graphical session or real power/session actions."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import signal
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'modules/desktop/files/.local/lib/raccon_menu/backend.py'
spec = importlib.util.spec_from_file_location('raccon_menu_backend', SOURCE)
menu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(menu)


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for name in ('STATE', 'POWER', 'RUNTIME'):
            path = self.base / name.lower()
            path.mkdir()
            p = patch.object(menu, name, path)
            p.start()
            self.addCleanup(p.stop)

    def test_selection_is_a_preview_and_does_not_write_power_preference(self):
        with patch.object(menu, 'update') as update, patch.object(menu, 'run') as run:
            menu.main(['select', 'working'])
            update.assert_called_once_with(selected='working', error='')
            run.assert_not_called()
        self.assertFalse((menu.POWER / 'preference.json').exists())

    def test_search_is_literal_accent_insensitive_and_never_a_shell_command(self):
        apps = [dict(name='Configuración de audio', search='configuracion de audio', token='a'*64),
                dict(name="L'éditeur", search="l'editeur", token='b'*64)]
        (menu.STATE / 'apps.json').write_text(json.dumps(apps))
        self.assertEqual(menu.filter_apps('AÚDIO configuración'), [apps[0]])
        self.assertEqual(menu.filter_apps("L'éditeur"), [apps[1]])
        with patch.object(menu, 'update') as update, patch.object(menu, 'run') as run:
            menu.main(['query', "'; $(touch should-not-exist) #"])
            update.assert_called_once_with(apps=[], query_empty=True)
            run.assert_not_called()
        self.assertFalse((self.base / 'should-not-exist').exists())

    def test_enter_uses_current_query_before_debounce_completes(self):
        apps = [dict(search='alpha', token='a'*64), dict(search='beta', token='b'*64)]
        (menu.STATE / 'apps.json').write_text(json.dumps(apps))
        with patch.object(menu, 'launch_app') as launch:
            menu.main(['launch-first', 'beta'])
            launch.assert_called_once_with('b'*64)

    def test_apply_uses_power_controller_and_reports_partial_failure(self):
        (menu.POWER / 'status.json').write_text(json.dumps(
            dict(source='working', transition=False, errors={'cpu': 'unavailable'})))
        with patch.object(menu, 'eww', return_value='working'), \
             patch.object(menu, 'update') as update, patch.object(menu, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'pending settings'):
                menu.apply_mode()
            self.assertEqual(run.call_args.args[0], [menu.BIN / 'desktop-power', 'set', 'working'])
            self.assertEqual(update.call_args.kwargs, dict(busy=False))

    def test_critical_actions_require_matching_confirmation(self):
        with patch.object(menu, 'eww', return_value=''), patch.object(menu, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Select the action'):
                menu.session_action('poweroff')
            run.assert_not_called()
        with patch.object(menu, 'eww', return_value='suspend'), \
             patch.object(menu, 'run') as run, patch.object(menu, 'close'):
            menu.session_action('suspend')
            run.assert_called_once_with(['systemctl', 'suspend'], timeout=15)

    def test_logout_is_limited_to_an_identified_session(self):
        with patch.object(menu, 'eww', return_value='logout'), patch.object(menu, 'run') as run, \
             patch.dict(os.environ, {'XDG_SESSION_ID': 'bad; value'}):
            with self.assertRaisesRegex(ValueError, 'identify'):
                menu.session_action('logout')
            run.assert_not_called()

    def test_modes_and_session_values_are_allowlisted(self):
        with patch.object(menu, 'update') as update, patch.object(menu, 'run') as run:
            for args in (['select', 'unknown'], ['confirm', 'invalid'], ['tab', 'nope'], ['media', '; reboot']):
                with self.assertRaises(ValueError): menu.main(args)
            update.assert_not_called()
            run.assert_not_called()

    def test_palette_prefers_waybar_and_handles_atomic_replacement(self):
        config = self.base / '.config'
        (config / 'eww').mkdir(parents=True)
        (config / 'waybar').mkdir()
        (config / 'eww/_colors.scss').write_text('$primary: #112233;')
        bar = config / 'waybar/colors.css'
        bar.write_text('@define-color primary #abcdef;')
        with patch.object(menu, 'HOME', self.base), patch.object(menu, 'CONFIG', config / 'raccon-menu'):
            menu.palette()
            output = config / 'raccon-menu/_palette.scss'
            self.assertIn('$primary: #abcdef;', output.read_text())
            replacement = bar.with_suffix('.next')
            replacement.write_text('@define-color primary #445566;')
            replacement.replace(bar)
            menu.palette()
            self.assertIn('$primary: #445566;', output.read_text())

    def test_short_menu_motion_survives_saving_but_respects_gtk(self):
        self.assertEqual(menu.motion({'policy': {'animation_factor': 0}}), .6)
        self.assertEqual(menu.motion({'policy': {'animation_factor': .45}}), .6)
        from gi.repository import Gtk
        class Settings:
            def get_property(self, name): return False
        with patch.object(Gtk.Settings, 'get_default', return_value=Settings()):
            self.assertEqual(menu.motion({'policy': {'animation_factor': 1}}), 0)

    def test_waybar_outline_tracks_battery_role_and_configuration(self):
        config = self.base / '.config'
        (config / 'desktop-power').mkdir(parents=True)
        (config / 'desktop-power/config.toml').write_text('[appearance]\nwarning="error"\n')
        with patch.object(menu, 'HOME', self.base), patch.object(menu, 'CONFIG', config / 'raccon-menu'):
            (menu.POWER / 'status.json').write_text('{"level":"warning"}')
            menu.palette()
            generated = (config / 'raccon-menu/_palette.scss').read_text()
            self.assertIn('$island_outline: rgba($error, .6);', generated)
            (menu.POWER / 'status.json').write_text('{"level":"normal"}')
            menu.palette()
            self.assertIn('$island_outline: rgba($outline_variant, .45);',
                          (config / 'raccon-menu/_palette.scss').read_text())

    def test_daily_apps_use_local_favorites_without_removed_editor_tile(self):
        catalog = [dict(id='com.valvesoftware.Steam.desktop', token='a'*64, name='Steam', icon='steam'),
                   dict(id='com.microsoft.VSCode.desktop', token='b'*64, name='Code', icon='code')]
        with tempfile.TemporaryDirectory() as tmp, patch.object(menu, 'STATE', Path(tmp)):
            self.assertEqual([app['name'] for row in menu.daily_apps(catalog) for app in row],
                             ['Browser', 'Files', 'Terminal'])  # no personal apps built in
            (Path(tmp) / 'favorites.json').write_text('["com.valvesoftware.Steam.desktop", "missing.desktop"]')
            rows = menu.daily_apps(catalog)
            (Path(tmp) / 'favorites.json').write_text('{"not": "a list"}')
            self.assertEqual(len(menu.daily_apps(catalog)[0]), 3)
        self.assertEqual([app['name'] for row in rows for app in row],
                         ['Browser', 'Files', 'Terminal', 'Steam'])
        self.assertEqual(rows[1][0]['value'], 'a'*64)

    def test_transient_ipc_retry_does_not_retry_real_errors(self):
        import subprocess
        unavailable = subprocess.CompletedProcess([], 1, '', 'Resource temporarily unavailable')
        ready = subprocess.CompletedProcess([], 0, 'pong', '')
        with patch.object(menu.subprocess, 'run', side_effect=[unavailable, ready]) as run, \
             patch.object(menu.time, 'sleep'):
            self.assertEqual(menu.eww('ping'), 'pong')
            self.assertEqual(run.call_count, 2)
        with patch.object(menu.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'bad config')) as run:
            with self.assertRaisesRegex(RuntimeError, 'bad config'): menu.eww('get', 'page')
            self.assertEqual(run.call_count, 1)

    def test_concurrent_prewarm_builds_one_complete_native_module(self):
        from concurrent.futures import ThreadPoolExecutor
        source = self.base / 'source'
        source.mkdir()
        (source / 'input.c').write_text('test source')
        builds = []
        def command(argv, **kwargs):
            if argv[0] == 'pkg-config': return ''
            builds.append(argv)
            time.sleep(.03)
            Path(argv[argv.index('-o') + 1]).write_bytes(b'complete-module')
            return ''
        with patch.object(menu, 'HOME', self.base), patch.object(menu, 'HERE', source), \
             patch.object(menu, 'run', side_effect=command), ThreadPoolExecutor(max_workers=2) as pool:
            paths = list(pool.map(lambda _: menu.build_input_module(), range(2)))
        self.assertEqual(len(builds), 1)
        self.assertEqual(paths[0], paths[1])
        self.assertEqual(paths[0].read_bytes(), b'complete-module')

    def test_successful_empty_ping_reuses_daemon(self):
        with patch.object(menu, 'eww', return_value=''), patch.object(menu.subprocess, 'Popen') as spawn:
            menu.ensure_daemon({})
            spawn.assert_not_called()

    def test_startup_does_not_wait_for_long_lived_daemon_output(self):
        fake_bin = self.base / 'bin'
        fake_bin.mkdir()
        fake = fake_bin / 'eww'
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
config = Path(args[args.index('-c') + 1])
if '--no-daemonize' not in args: raise SystemExit(98)
pidfile = config / 'pid'
command = args[args.index('--no-daemonize') + 1]
if command == 'daemon':
    pidfile.write_text(str(os.getpid()))
    print('daemon ready', flush=True)
    while True: time.sleep(.05)
elif command == 'ping':
    try: os.kill(int(pidfile.read_text()), 0)
    except (OSError, ValueError): raise SystemExit(1)
    print('pong')
else: raise SystemExit(97)
''')
        fake.chmod(0o755)
        config = self.base / 'config'
        config.mkdir()
        env = {**os.environ, 'PATH': str(fake_bin) + os.pathsep + os.environ['PATH']}
        def cleanup():
            child = menu._daemon_process
            if child is not None:
                child.terminate()
                child.wait(timeout=2)
                menu._daemon_process = None
                return
            if (config / 'pid').exists():
                pid = int((config / 'pid').read_text())
                try:
                    os.kill(pid, signal.SIGTERM)
                    os.waitpid(pid, 0)
                except (ProcessLookupError, ChildProcessError):
                    pass
        self.addCleanup(cleanup)
        with patch.object(menu, 'CONFIG', config), patch.dict(os.environ, env):
            started = time.monotonic()
            menu.ensure_daemon(env)
            self.assertLess(time.monotonic() - started, 3)
            first_pid = (config / 'pid').read_text()
            menu.ensure_daemon(env)
            self.assertEqual((config / 'pid').read_text(), first_pid)
            self.assertIn('daemon ready', (menu.STATE / 'daemon.log').read_text())

    def test_toggle_recovers_a_hidden_existing_surface(self):
        def response(*args, **kwargs):
            return 'raccon-menu: raccon-menu' if args == ('active-windows',) else 'false'
        with patch.object(menu, 'build_input_module', return_value=Path('/tmp/input.so')), \
             patch.object(menu, 'palette'), patch.object(menu, 'ensure_daemon'), \
             patch.object(menu, 'eww', side_effect=response), patch.object(menu, 'update') as update, \
             patch.object(menu, 'close') as close:
            menu.show()
            update.assert_called_once_with(revealed=True)
            close.assert_not_called()

    def test_open_confirms_visibility_after_an_empty_ipc_response(self):
        active = iter(('', '', 'raccon-menu: raccon-menu', 'raccon-menu: raccon-menu'))
        visible = iter(('false', 'true'))
        def response(*args, **kwargs):
            if args == ('active-windows',): return next(active)
            if args == ('get', 'revealed'): return next(visible)
            return ''
        with patch.object(menu, 'build_input_module', return_value=Path('/tmp/input.so')), \
             patch.object(menu, 'palette'), patch.object(menu, 'ensure_daemon'), \
             patch.object(menu, 'eww', side_effect=response), patch.object(menu, 'update') as update, \
             patch.object(menu, 'cached_applications', return_value=[]), \
             patch.object(menu, 'snapshot', return_value={}), patch.object(menu, 'mode_rows', return_value=[]), \
             patch.object(menu, 'geometry', return_value=(0, 660, 400)), patch.object(menu.time, 'sleep'):
            menu.show('home')
            self.assertTrue(update.call_args_list[0].kwargs['revealed'])
            self.assertEqual(update.call_args.kwargs, {'revealed': True})


if __name__ == '__main__':
    unittest.main()
