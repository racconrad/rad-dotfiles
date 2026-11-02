"""Power mode startup regression: never unload animate while it inhibits output."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'modules/power/files'
sys.dont_write_bytecode = True
sys.path.insert(0, str(PAYLOAD / '.local/lib'))
from desktop_power import effects, storage


class StartupTests(unittest.TestCase):
    def setUp(self):
        with patch.object(storage, 'CONFIG', PAYLOAD / '.config/desktop-power'):
            self.config = storage.load_config()

    def test_widget_policy_is_sent_through_the_public_profile_api(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);ctl=home/'.local/bin/widgetctl';ctl.parent.mkdir(parents=True);ctl.touch()
            state=home/'state';state.mkdir();status=state/'status.json';status.write_text('{"policy":{"widgets":false}}')
            with patch.object(effects,'HOME',home),patch.object(effects,'STATE',state),patch.object(effects,'run',side_effect=[json.dumps({'frame':'none'}),'']) as run:
                effects.widget_policy()
            self.assertEqual(run.call_args.args[0],[str(ctl),'--config',str(home/'.config/eww'),'policy',str(status)])

    def test_saving_preserves_animate_and_restores_window_matchers(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            ini = home / '.config/wayfire.ini'
            ini.parent.mkdir()
            original = ('[core]\nplugins = animate autostart ipc ipc-rules blur\n'
                        '[animate]\nenabled_for = app_id is "kitty"\n'
                        'fade_enabled_for = type is "panel"\n'
                        'duration = 240ms circle\n')
            ini.write_text(original)
            batches = []

            def ipc(method, data=None):
                if method == 'wayfire/get-config-option':
                    return {'result': 'ok', 'value': 'different'}
                if method == 'wayfire/set-config-options':
                    batches.append(data)
                if method == 'window-rules/list-views':
                    return []
                return {'result': 'ok'}

            for mode in ('performance', 'working'):
                profile = copy.deepcopy(self.config['profiles'][mode])
                profile['disable_plugins'].append('animate')  # Older user configs.
                with patch.object(effects, 'HOME', home), patch.object(effects, 'ipc', ipc):
                    effects.wayfire(profile)
                    saving = batches[-1]
                    self.assertIn('animate', saving['core/plugins'].split())
                    self.assertEqual(saving['animate/enabled_for'], 'none')
                    self.assertEqual(saving['animate/fade_enabled_for'], 'none')
                    self.assertEqual(saving['animate/duration'], '0ms circle')
                    effects.wayfire(self.config['profiles']['complete'])
                    self.assertEqual(batches[-1]['animate/enabled_for'], 'app_id is "kitty"')
                    self.assertEqual(batches[-1]['animate/fade_enabled_for'], 'type is "panel"')
                    self.assertEqual(batches[-1]['animate/duration'], '240ms circle')
            self.assertEqual(ini.read_text(), original)

    @unittest.skipUnless(os.environ.get('RUN_WAYFIRE_INTEGRATION') == '1',
                         'Set RUN_WAYFIRE_INTEGRATION=1 for isolated compositor test')
    def test_early_saving_renders_instead_of_leaving_black_output(self):
        from PIL import Image

        for mode in ('performance', 'working'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                ini = home / '.config/wayfire.ini'
                ini.parent.mkdir()
                ini.write_text('[core]\nplugins = animate autostart ipc ipc-rules\n'
                               'xwayland = false\nbackground_color = 1.0 0.0 0.0 1.0\n'
                               '[animate]\nstartup_duration = 400ms linear\n'
                               '[autostart]\nautostart_wf_shell = false\n')
                env = dict(os.environ, WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1',
                           WLR_RENDERER='gles2', XDG_RUNTIME_DIR=temp,
                           WAYLAND_DISPLAY='', WAYFIRE_SOCKET='')
                with (home / 'wayfire.log').open('w') as log:
                    process = subprocess.Popen(['wayfire', '-c', str(ini)], env=env,
                                               stdout=log, stderr=log)
                    try:
                        deadline = time.monotonic() + 5
                        while not list(home.glob('wayfire-*.socket')):
                            self.assertIsNone(process.poll(), (home / 'wayfire.log').read_text())
                            self.assertLess(time.monotonic(), deadline)
                            time.sleep(.002)
                        ready = time.monotonic()
                        env['WAYFIRE_SOCKET'] = str(next(home.glob('wayfire-*.socket')))
                        env['WAYLAND_DISPLAY'] = next(p.name for p in home.glob('wayland-*')
                                                      if not p.name.endswith('.lock'))
                        profile = copy.deepcopy(self.config['profiles'][mode])
                        profile['disable_plugins'].append('animate')
                        with patch.dict(os.environ, env), patch.object(effects, 'HOME', home):
                            effects.wayfire(profile)
                            self.assertLess(time.monotonic() - ready, .35,
                                            'Must apply during the startup inhibit window')
                            self.assertIn('animate', effects.ipc('wayfire/get-config-option',
                                          {'option': 'core/plugins'})['value'].split())
                        time.sleep(.8)
                        subprocess.run(['grim', str(home / 'screen.png')], env=env,
                                       check=True, capture_output=True, timeout=3)
                        with Image.open(home / 'screen.png') as screenshot:
                            self.assertEqual(screenshot.getpixel((50, 50))[:3], (255, 0, 0))
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


if __name__ == '__main__':
    unittest.main()
