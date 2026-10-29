"""Personal preset portability, dependency planning and terminal interaction contracts."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_install import installer
from terminal_ui import frame

ROOT = installer.ROOT


class WidgetBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rdot-widgets-')
        self.home = Path(self.temp.name) / 'home'
        self.output = io.StringIO()

    def tearDown(self):
        self.temp.cleanup()

    def selection(self, **options):
        return installer.validate_selection({'requested': ['tinywidgets'],
                                             'widgets': {'install': 'configure', **options}})

    def plan(self, selection):
        modules = installer.selected_modules(selection, self.home)
        return modules, installer.file_plan(self.home, modules, selection['choices'], selection)

    def args(self, selection):
        return SimpleNamespace(target=self.home, selection=selection, profile=None, save_profile=None,
            packages=selection['packages'], extra_packages=list(selection['extra_packages']),
            setup=list(selection['setup']), tinywidgets_source=selection['tinywidgets_source'],
            widget_options=dict(selection['widgets']), plain=True,
            **{k: None for k in selection['choices']})

    def test_first_class_feature_resolves_personal_subfeatures(self):
        selection = self.selection()
        modules, plan = self.plan(selection)
        for name in ['widgets', 'widgets-profiles', 'widgets-themes', 'widgets-motion', 'widgets-palette']:
            self.assertIn(name, modules)
        self.assertTrue(any('/profiles/Personal.json' in p for p in plan))
        self.assertEqual(json.loads(plan['.config/eww/animation.json'][0])['fps'], 60)
        self.assertEqual(json.loads(plan['.config/eww/style.json'][0]),
                         {'skin': 'bento', 'fx': 'focus', 'background': 'surface'})

    def test_all_personal_layouts_follow_the_tinywidgets_instance_contract(self):
        profiles = ROOT / 'modules/widgets-profiles/files/.config/eww/profiles'
        self.assertEqual({p.stem for p in profiles.glob('*.json')},
                         {'Personal', 'Trabajo', 'Gaming', 'Dashboard', 'Cyberpunk', 'silly'})
        for path in profiles.glob('*.json'):
            document = json.loads(path.read_text())
            ids = set()
            for widget in document['widgets']:
                self.assertRegex(widget['id'], r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
                self.assertNotIn(widget['id'], ids)
                ids.add(widget['id'])
                self.assertIsInstance(widget['show'], bool)
                self.assertIn(widget['anchor'], ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'])
                self.assertIsInstance(widget['x'], int)
                self.assertIsInstance(widget['y'], int)
                if widget['window'] in ('command', 'api', 'photo', 'image', 'note', 'obsidian'):
                    self.assertFalse(widget['show'])
                self.assertFalse({'command', 'cmd', 'token', 'headers', 'url', 'path'} & widget['opts'].keys())
            self.assertNotIn(str(Path.home()), path.read_text())
            self.assertNotIn('/mnt/me', path.read_text())

    def test_personal_layout_enables_minecraft_dependency_without_owner_apps(self):
        selection = self.selection(profile='Personal')
        modules, plan = self.plan(selection)
        self.assertIn('widgets-minecraft', modules)
        self.assertIn('python-pillow', installer.packages_for(modules))
        widgets = json.loads(plan['.config/eww/instances.json'][0])['widgets']
        self.assertEqual(len(widgets), 15)
        chest = next(w for w in widgets if w['window'] == 'chest')
        # The owner's installed apps are never shipped; each user fills the chest.
        self.assertEqual(json.loads(chest['opts']['launchers']), [])

    def test_layout_dependencies_follow_the_active_profile(self):
        for profile, module, package in [('Gaming', 'widgets-music', 'playerctl'),
                                         ('Cyberpunk', 'widgets-github', 'github-cli')]:
            with self.subTest(profile=profile):
                modules, _ = self.plan(self.selection(profile=profile))
                self.assertIn(module, modules)
                self.assertIn(package, installer.packages_for(modules))

    def test_keep_layout_preserves_existing_instances(self):
        instances = self.home / '.config/eww/instances.json'
        instances.parent.mkdir(parents=True)
        instances.write_text('private existing layout')
        modules, plan = self.plan(self.selection(profile='keep'))
        self.assertNotIn('.config/eww/instances.json', plan)
        self.assertEqual(instances.read_text(), 'private existing layout')

    def test_fresh_keep_seeds_selected_layout_with_correct_dependencies(self):
        selection = self.selection(profile='keep', profiles=['Gaming'])
        modules, plan = self.plan(selection)
        self.assertIn('widgets-music', modules)
        self.assertEqual(len(json.loads(plan['.config/eww/instances.json'][0])['widgets']), 3)
        self.assertIn('.config/eww/profiles/Gaming.json', plan)
        self.assertNotIn('.config/eww/profiles/Personal.json', plan)

    def test_selected_theme_and_motion_replace_only_global_preset_contents(self):
        selection = self.selection(theme='quiet', motion='balanced')
        modules, plan = self.plan(selection)
        self.assertEqual(json.loads(plan['.config/eww/style.json'][0])['fx'], 'none')
        self.assertEqual(json.loads(plan['.config/eww/animation.json'][0])['fps'], 24)
        self.assertIn('.config/eww/presets/themes/personal.json', plan)
        self.assertIn('.config/eww/presets/motion/personal.json', plan)

    def test_auto_builds_only_when_runtime_or_requested_collection_is_missing(self):
        selection = self.selection(install='auto')
        self.assertIn('tinywidgets', installer.effective_setup(selection, self.home))
        for path in ['.local/bin/widgetctl', '.local/lib/randly-widgets/randly-widget-manager']:
            target = self.home / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('installed')
        self.assertNotIn('tinywidgets', installer.effective_setup(selection, self.home))
        minecraft = self.selection(install='auto', profile='Personal')
        self.assertIn('tinywidgets', installer.effective_setup(minecraft, self.home))
        collection = self.home / '.config/eww/widgets/minecraft/collection.json'
        collection.parent.mkdir(parents=True)
        collection.write_text('{}')
        self.assertNotIn('tinywidgets', installer.effective_setup(minecraft, self.home))

    def test_missing_source_and_foreign_eww_are_explained_before_any_write(self):
        selection = self.selection(install='build')
        selection['tinywidgets_source'] = '~/missing-source'
        report = installer.readiness(selection, self.home)
        self.assertTrue(any('valid tinyWidgets source' in s for s in report['blockers']))
        self.assertFalse(self.home.exists())
        foreign = self.home / '.config/eww/eww.yuck'
        foreign.parent.mkdir(parents=True)
        foreign.write_text('another application')
        report = installer.readiness(self.selection(), self.home)
        self.assertTrue(any('another configuration' in s for s in report['blockers']))
        self.assertEqual(foreign.read_text(), 'another application')

    def test_invalid_widget_options_are_rejected(self):
        invalid = [{'profile': 'missing'}, {'theme': {}}, {'motion': 'bogus'}, {'install': 'shell-command'},
                   {'profiles': ['bogus']}, {'components': ['orbit']},
                   {'profile': 'Personal', 'profiles': ['Trabajo']}, {'profiles': []}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.selection(**value)

    def test_cli_installs_and_restores_the_selected_personal_profile_in_a_temporary_home(self):
        source = self.home / '.config/eww/instances.json'
        source.parent.mkdir(parents=True)
        source.write_text('original private layout')
        command = [str(ROOT / 'install.sh'), '--target', str(self.home), '--modules', 'tinywidgets',
                   '--widget-install', 'configure', '--widget-profile', 'Personal',
                   '--widget-theme', 'quiet', '--widget-motion', 'balanced', '--yes']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = installer.load_selection(self.home)
        self.assertEqual(saved['widgets']['profile'], 'Personal')
        self.assertEqual(saved['widgets']['theme'], 'quiet')
        self.assertEqual(len(json.loads(source.read_text())['widgets']), 15)
        backup = next((self.home / '.local/state/raccon-dots/backups').iterdir())
        with redirect_stdout(self.output):
            installer.restore(backup, self.home)
        self.assertEqual(source.read_text(), 'original private layout')

    def test_check_mode_reports_build_blockers_without_side_effects(self):
        result = subprocess.run([str(ROOT / 'install.sh'), '--target', str(self.home),
            '--modules', 'tinywidgets', '--tinywidgets-source', '~/missing-source', '--check'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('NEEDS ATTENTION', result.stdout)
        self.assertFalse(self.home.exists())

    def test_dependency_details_distinguish_installed_missing_and_manual_packages(self):
        selection = self.selection(profile='Personal')
        modules, _ = self.plan(selection)
        inventory = {'known': True, 'installed': {'eww'}, 'available': {'python-pillow'}}
        lines = installer.component_details('widgets-minecraft', selection['requested'], selection['choices'], modules, inventory)
        self.assertTrue(any('python-pillow [needs install]' in line for line in lines))
        self.assertTrue(any('eww [installed]' in line for line in lines))
        self.assertTrue(any('[manual package source]' in line for line in lines))

    def test_widget_page_saves_choices_and_subfeatures_without_installing(self):
        args = self.args(self.selection())
        args.save_profile = Path(self.temp.name) / 'personal.json'
        inputs = ['', 't', '2', '3', '4', '13', 'w', 'q']
        with patch('builtins.input', side_effect=inputs), redirect_stdout(self.output):
            self.assertIsNone(installer.interactive(args))
        saved = installer.load_selection(self.home, args.save_profile)
        self.assertEqual(saved['widgets']['profile'], 'Personal')
        self.assertEqual(saved['widgets']['theme'], 'quiet')
        self.assertEqual(saved['widgets']['motion'], 'balanced')
        self.assertFalse(self.home.exists())

    def test_starting_profile_loads_a_complete_selection_for_review(self):
        args = self.args(installer.validate_selection({}))
        selection = installer.selection_for(args, args.selection['requested'])
        modules = installer.selected_modules(selection, self.home)
        rows = installer.rows_for('r', args, args.selection['requested'], selection, modules, {'known': False})
        index = next(i + 1 for i, row in enumerate(rows) if row['id'] == 'raccoon-desktop')
        with patch('builtins.input', side_effect=['', 'r', str(index), 'q']), redirect_stdout(self.output):
            self.assertIsNone(installer.interactive(args))
        self.assertEqual(args.widget_options['profile'], 'Personal')
        self.assertTrue(args.packages)
        self.assertFalse(self.home.exists())

    def test_terminal_layout_stays_in_bounds_and_always_exposes_dependencies(self):
        args = self.args(self.selection(profile='Personal'))
        selection = installer.selection_for(args, args.selection['requested'])
        modules = installer.selected_modules(selection, self.home)
        rows = installer.rows_for('t', args, args.selection['requested'], selection, modules, {'known': False})
        details = installer.component_details('widgets-minecraft', selection['requested'], selection['choices'], modules, {'known': False})
        for width, height in [(80, 24), (120, 32), (60, 18), (40, 12)]:
            with self.subTest(width=width):
                lines = frame('0.3.0', 'TINYWIDGETS / YOUR DEN', [('t', 'Widgets')], rows, 12,
                              details, 'Ready to review', width=width, height=height)
                self.assertLessEqual(len(lines), height)
                self.assertTrue(all(len(line) < width for line, _ in lines))
                if width >= 54:
                    text = '\n'.join(line for line, _ in lines)
                    self.assertIn('Needs:', text)
                    self.assertIn('Packages:', text)
                    self.assertTrue(any(style == 'focus' for _, style in lines))

    def test_capture_drops_private_sources_and_custom_commands_but_keeps_safe_appearance(self):
        spec = importlib.util.spec_from_file_location('widget_capture', ROOT / 'scripts/capture_widget_presets.py')
        capture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(capture)
        source = {'widgets': [{'id': 'my-api', 'window': 'api', 'show': True, 'anchor': 'top-left', 'x': 10, 'y': 20,
            'opts': {'token': 'sensitive', 'url': 'private-endpoint', 'command': 'do something', 'width': '300', 'skin': 'clean'}},
            {'id':'notes','window':'obsidian','show':True,'opts':{'vault':'private-vault','folder':'private-folder','window_frame':'Glass','frame_controls':'yes'}}]}
        exported = capture.portable_layout(source)
        self.assertFalse(exported['widgets'][0]['show'])
        self.assertEqual(exported['widgets'][0]['opts'], {'width': '300', 'skin': 'clean'})
        self.assertNotIn('sensitive', json.dumps(exported))
        self.assertFalse(exported['widgets'][1]['show'])
        self.assertEqual(exported['widgets'][1]['opts'],{'window_frame':'Glass','frame_controls':'yes'})
        self.assertNotIn('private-vault',json.dumps(exported))

    def test_incomplete_app_setup_remains_retryable_even_if_partial_binaries_exist(self):
        selection = self.selection(install='auto')
        for path in ['.local/bin/widgetctl', '.local/lib/randly-widgets/randly-widget-manager']:
            file = self.home / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('partially installed')
        state = self.home / '.local/state/raccon-dots/setup.json'
        state.parent.mkdir(parents=True)
        for status in ('failed', 'running', 'cancelled'):
            with self.subTest(status=status):
                state.write_text(json.dumps({'actions': {'tinywidgets': {'status': status}}}))
                self.assertIn('tinywidgets', installer.effective_setup(selection, self.home))
        state.write_text(json.dumps({'actions': {'tinywidgets': {'status': 'complete'}}}))
        self.assertNotIn('tinywidgets', installer.effective_setup(selection, self.home))

    def test_live_setup_progress_records_real_output_without_downloads(self):
        output = Path(self.temp.name) / 'setup.log'
        class TtyOutput(io.StringIO):
            def isatty(self):
                return True
        progress = TtyOutput()
        with output.open('w') as log, patch.object(installer.sys, 'stdout', progress):
            installer.run_logged_command([installer.sys.executable, '-c', 'print("setup complete")'],
                                         dict(installer.os.environ), log, 'local check')
        self.assertEqual(output.read_text().strip(), 'setup complete')
        self.assertIn('elapsed', progress.getvalue())

    def test_configure_mode_never_runs_a_stale_rebuild_action(self):
        selection = installer.validate_selection({'requested': ['tinywidgets'],
            'setup': ['tinywidgets'], 'widgets': {'install': 'configure'}})
        self.assertNotIn('tinywidgets', installer.effective_setup(selection, self.home))

    def test_unrelated_setup_does_not_erase_previous_tinywidgets_failure(self):
        state = self.home / '.local/state/raccon-dots/setup.json'
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({'actions': {'tinywidgets': {'status': 'failed'}}}))
        selection = installer.validate_selection({'requested': ['vscode'], 'setup': ['vscode-extensions']})
        with patch.object(installer.subprocess, 'run'), redirect_stdout(self.output):
            installer.run_setup(selection, self.home)
        saved = json.loads(state.read_text())
        self.assertEqual(saved['actions']['tinywidgets']['status'], 'failed')
        self.assertEqual(saved['actions']['vscode-extensions']['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
