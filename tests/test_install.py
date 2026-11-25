"""Installer contracts, exercised against disposable homes without packages or GUI."""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import itertools
import json
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rdot_install', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='raccon-test-')
        self.home = Path(self.temp.name) / 'home with spaces'
        self.choices = {key: info['default'] for key, info in installer.CATALOG['choices'].items()}
        self.output = io.StringIO()

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, requested=None, choices=None):
        choices = choices or self.choices
        modules = installer.resolve_modules(requested or installer.CATALOG['defaults'], choices)
        return modules, installer.file_plan(self.home, modules, choices)

    def install(self, requested=None, choices=None):
        choices = choices or self.choices
        modules, plan = self.plan(requested, choices)
        with redirect_stdout(self.output):
            backup = installer.apply_plan(self.home, plan, modules, choices)
        return backup

    def test_dry_run_creates_nothing_even_with_packages_flag(self):
        result = subprocess.run([str(ROOT / 'install.sh'), '--target', str(self.home),
                                 '--dry-run', '--packages'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Preview only', result.stdout)
        self.assertFalse(self.home.exists())

    def test_generated_python_bytecode_is_never_installed(self):
        source = Path(self.temp.name) / 'source'
        base = source / 'modules/base/files/.local/lib/example'
        cache = base / '__pycache__'
        cache.mkdir(parents=True)
        (base / 'module.py').write_text('value = 1\n')
        (cache / 'module.pyc').write_bytes(b'\xff\x00bytecode')
        with patch.object(installer, 'ROOT', source):
            plan = installer.file_plan(self.home, ['base'], self.choices)
        self.assertEqual(set(plan), {'.local/lib/example/module.py'})

    def test_every_alternative_renders_valid_configs_without_orbit_or_machine_paths(self):
        keys = list(self.choices)
        values = [installer.CATALOG['choices'][key]['options'] for key in keys]
        for options in itertools.product(*values):
            choices = dict(zip(keys, options))
            with self.subTest(choices=choices):
                modules, plan = self.plan(choices=choices)
                for relative, (data, _) in plan.items():
                    if relative.endswith(('.png', '.ttf')):
                        continue
                    text = data.decode()
                    self.assertNotIn('@RDOT_', text, relative)
                    self.assertNotIn(str(Path.home()), text, relative)
                    self.assertIsNone(re.search(r'/mnt/(?:me|code)(?:/|[\s\"\'])', text), relative)
                    self.assertNotIn('orbit', text.lower(), relative)
                    if relative.endswith('.toml'):
                        tomllib.loads(text)
                    elif relative.endswith('.json') or relative.endswith('.jsonc'):
                        json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
                    elif relative.endswith('.py') or data.startswith(b'#!/usr/bin/env python3'):
                        ast.parse(text, filename=relative)
                wf = plan['.config/wayfire.ini'][0].decode()
                self.assertIn('command_terminal = ' + choices['terminal'], wf)
                self.assertIn('notifications = ' + choices['notifications'], wf)
                self.assertFalse('[output:' in wf, 'Se filtraron monitores de la máquina original')
                self.assertNotIn('command_widgets', wf)
                bar = json.loads(plan['.config/waybar/config.jsonc'][0])
                self.assertNotIn('custom/notification', bar['modules-right'])
                self.assertNotIn('custom/notification', bar)
                locker = plan['.local/bin/lock'][0].decode()
                self.assertIn('exec ' + choices['lock'], locker)

    def test_backup_restore_and_no_op_preserve_original_files(self):
        config = self.home / '.config/kitty/kitty.conf'
        config.parent.mkdir(parents=True)
        config.write_text('personal terminal\n')
        config.chmod(0o600)
        backup = self.install()
        self.assertEqual((backup / 'files/.config/kitty/kitty.conf').read_text(), 'personal terminal\n')
        marker = json.loads((self.home / '.rdot').read_text())
        self.assertEqual(marker['version'], installer.RELEASE['version'])
        self.assertEqual(marker['choices']['terminal'], 'kitty')
        inode, mtime = config.stat().st_ino, config.stat().st_mtime_ns
        self.assertIsNone(self.install())
        self.assertEqual((config.stat().st_ino, config.stat().st_mtime_ns), (inode, mtime))
        with redirect_stdout(self.output):
            installer.restore(backup, self.home)
        self.assertEqual(config.read_text(), 'personal terminal\n')
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.home / '.rdot').exists())
        self.assertFalse((self.home / '.config/wayfire.ini').exists())

    def test_existing_file_symlink_is_backed_up_without_writing_through(self):
        outside = Path(self.temp.name) / 'outside'
        outside.write_text('unchanged target')
        config = self.home / '.config/kitty/kitty.conf'
        config.parent.mkdir(parents=True)
        config.symlink_to(outside)
        backup = self.install(['terminal'])
        self.assertFalse(config.is_symlink())
        self.assertEqual(outside.read_text(), 'unchanged target')
        with redirect_stdout(self.output):
            installer.restore(backup, self.home)
        self.assertTrue(config.is_symlink())
        self.assertEqual(config.readlink(), outside)

    def test_parent_symlinks_are_rejected_before_writes(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        self.home.mkdir()
        (self.home / '.config').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'manual review'):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.home / '.local').exists())

    def test_write_failure_rolls_back_all_files_including_marker(self):
        config = self.home / '.config/kitty/kitty.conf'
        config.parent.mkdir(parents=True)
        config.write_text('before')
        original = installer.atomic_write
        failed = False

        def fail_once(path, data, mode):
            nonlocal failed
            if str(path).endswith('.local/bin/wf-ws') and not failed:
                failed = True
                raise OSError('simulated full disk')
            original(path, data, mode)

        with patch.object(installer, 'atomic_write', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'full disk'):
                self.install()
        self.assertTrue(failed)
        self.assertEqual(config.read_text(), 'before')
        self.assertFalse((self.home / '.config/wayfire.ini').exists())
        self.assertFalse((self.home / '.rdot').exists())

    def test_restore_does_not_destroy_later_user_edits(self):
        backup = self.install(['terminal'])
        config = self.home / '.config/kitty/kitty.conf'
        config.write_text('user edit')
        with self.assertRaisesRegex(ValueError, 'File changed'):
            installer.restore(backup, self.home)
        self.assertEqual(config.read_text(), 'user edit')
        self.assertTrue((self.home / '.rdot').exists())

    def test_minimal_modules_do_not_enable_other_matugen_outputs(self):
        modules, plan = self.plan(['themes', 'terminal'])
        config = tomllib.loads(plan['.config/matugen/config.toml'][0].decode())
        self.assertEqual(set(config['templates']), {'gtk3', 'gtk4', 'qt5ct', 'qt6ct', 'kitty'})
        self.assertNotIn('.config/wayfire.ini', plan)
        self.assertNotIn('.config/eww/style.json', plan)

    def test_new_alternative_updates_previously_installed_dependents(self):
        self.install()
        choices = {**self.choices, 'terminal': 'alacritty', 'notifications': 'mako'}
        requested = installer.with_previous(self.home, ['terminal', 'notifications'], choices)
        modules, plan = self.plan(requested, choices)
        self.assertNotIn('kitty', modules)
        self.assertNotIn('swaync', modules)
        self.assertIn('command_terminal = alacritty', plan['.config/wayfire.ini'][0].decode())
        with redirect_stdout(self.output):
            installer.apply_plan(self.home, plan, modules, choices)
        receipt = installer.read_receipt(self.home)
        self.assertIn('wayfire', receipt['modules'])
        self.assertNotIn('kitty', receipt['modules'])
        self.assertEqual(receipt['choices']['terminal'], 'alacritty')

    def test_widget_preferences_are_optional_and_keep_private_instances_out(self):
        modules, plan = self.plan(['wayfire', 'widgets'])
        self.assertIn('.config/eww/style.json', plan)
        self.assertIn('.local/state/randly-widgets/palette.scss', plan)
        self.assertNotIn('.config/eww/instances.json', plan)
        self.assertIn('command_widgets', plan['.config/wayfire.ini'][0].decode())

    def test_unknown_or_conflicting_modules_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown module'):
            self.plan(['orbit'])
        with self.assertRaisesRegex(ValueError, 'alternative'):
            self.plan(['kitty', 'alacritty'])

    def test_backup_parent_symlink_is_rejected(self):
        state = self.home / '.local/state/raccon-dots'
        state.mkdir(parents=True)
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (state / 'backups').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'manual review'):
            self.install(['terminal'])
        self.assertEqual(list(outside.iterdir()), [])

    def test_each_standalone_module_has_resolvable_files_and_syntax(self):
        for name in installer.CATALOG['modules']:
            choices = self.choices.copy()
            for group, info in installer.CATALOG['choices'].items():
                if name in info['options']:
                    choices[group] = name
            with self.subTest(module=name):
                modules, plan = self.plan([name], choices)
                self.assertGreater(len(plan), 0)
                for relative, (data, _) in plan.items():
                    if relative.endswith('.toml'):
                        tomllib.loads(data.decode())
                    if relative.endswith('.json'):
                        json.loads(data)
                    if data.startswith(b'#!/usr/bin/env bash'):
                        result = subprocess.run(['bash', '-n'], input=data, capture_output=True)
                        self.assertEqual(result.returncode, 0, (relative, result.stderr.decode()))
                if name == 'vscode':
                    settings = json.loads(plan['.config/Code/User/settings.json'][0])
                    self.assertNotIn('geminicodeassist.project', settings)
                    self.assertNotIn('dart.flutterSdkPath', settings)

    def test_shell_choice_configures_both_terminals_and_vscode(self):
        choices = {**self.choices, 'shell': 'fish'}
        for terminal in ('kitty', 'alacritty'):
            choices['terminal'] = terminal
            modules, plan = self.plan(['terminal', 'shell', 'vscode'], choices)
            settings = json.loads(plan['.config/Code/User/settings.json'][0])
            self.assertEqual(settings['terminal.integrated.defaultProfile.linux'], 'fish')
            if terminal == 'kitty':
                self.assertIn('shell fish', plan['.config/kitty/kitty.conf'][0].decode())
            else:
                config = tomllib.loads(plan['.config/alacritty/alacritty.toml'][0].decode())
                self.assertEqual(config['terminal']['shell']['program'], 'fish')

    def wizard_args(self, selection=None):
        selection = installer.validate_selection(selection or {})
        return SimpleNamespace(target=self.home, selection=selection, profile=None,
                               save_profile=None, packages=selection['packages'],
                               extra_packages=list(selection['extra_packages']),
                               setup=list(selection['setup']),
                               tinywidgets_source=selection['tinywidgets_source'],
                               **{key: None for key in self.choices})

    def test_interactive_menu_cycles_choices_and_previews_without_installing(self):
        args = self.wizard_args()
        with patch('builtins.input', side_effect=['', 'l', '1', '5', 'p', 'd', '', '0', 'v', '', 'q']), redirect_stdout(self.output):
            self.assertIsNone(installer.interactive(args))
        self.assertEqual(args.terminal, 'alacritty')
        self.assertEqual(args.shell, 'fish')
        self.assertTrue(args.packages)
        self.assertIn('terminal=alacritty', self.output.getvalue())
        self.assertIn('BEFORE YOU START', self.output.getvalue())
        self.assertIn('DESKTOP FEATURES', self.output.getvalue())
        self.assertFalse(self.home.exists())

    def test_exact_raccoon_art_is_used(self):
        self.assertEqual(installer.MASCOT, (ROOT / 'assets/raccoon.txt').read_text())
        self.assertEqual(len(installer.MASCOT.splitlines()), 12)
        self.assertTrue(installer.MASCOT.startswith('⠀⠀⠀⠀⢀⣠⠤⠒⠒⠒⠒⠒⠒⠤⠤'))

    def test_setup_profile_roundtrip_and_reinstall_are_idempotent(self):
        args = self.wizard_args({'requested': ['terminal', 'shell', 'nvim'],
                                 'choices': {**self.choices, 'shell': 'fish'},
                                 'packages': True, 'extra_packages': ['jq'],
                                 'setup': ['nvim-plugins']})
        selection = installer.selection_for(args, args.selection['requested'])
        modules = installer.resolve_modules(selection['requested'], selection['choices'])
        plan = installer.file_plan(self.home, modules, selection['choices'])
        with redirect_stdout(self.output):
            backup = installer.apply_plan(self.home, plan, modules, selection['choices'], selection)
            second = installer.apply_plan(self.home, plan, modules, selection['choices'], selection)
        self.assertIsNone(second)
        receipt = installer.read_receipt(self.home)
        self.assertEqual(receipt['selection'], selection)
        self.assertEqual(installer.load_selection(self.home), selection)
        copied = json.loads((self.home / '.config/raccon-dots/profile.json').read_text())
        self.assertEqual(copied, selection)
        self.assertEqual(receipt['files']['.config/kitty/kitty.conf']['sha256'],
                         installer.hashlib.sha256(plan['.config/kitty/kitty.conf'][0]).hexdigest())
        exported = Path(self.temp.name) / 'profiles/personal.json'
        with redirect_stdout(self.output):
            installer.save_profile(exported, selection)
        self.assertEqual(installer.load_selection(self.home, exported), selection)
        self.assertEqual(exported.stat().st_mode & 0o777, 0o600)
        with redirect_stdout(self.output):
            installer.restore(backup, self.home)
        self.assertFalse((self.home / '.config/raccon-dots/profile.json').exists())

    def test_cli_loads_and_exports_profile_without_enabling_unselected_apps(self):
        profile = Path(self.temp.name) / 'input.json'
        profile.write_bytes(installer.json_bytes(installer.validate_selection({
            'requested': ['terminal', 'shell'], 'choices': {**self.choices, 'shell': 'fish'}})))
        exported = Path(self.temp.name) / 'export.json'
        result = subprocess.run([str(ROOT / 'install.sh'), '--target', str(self.home), '--profile', str(profile),
                                 '--save-profile', str(exported), '--yes'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = installer.load_selection(self.home)
        self.assertEqual(saved['requested'], ['terminal', 'shell'])
        self.assertEqual(saved['choices']['shell'], 'fish')
        self.assertTrue(exported.is_file())
        self.assertFalse((self.home / '.config/wayfire.ini').exists())

    def test_dry_run_with_profile_setup_and_export_has_no_side_effects(self):
        profile = Path(self.temp.name) / 'input.json'
        profile.write_bytes(installer.json_bytes(installer.validate_selection({
            'requested': ['vscode'], 'packages': True, 'setup': ['vscode-extensions'], 'extra_packages': ['jq']})))
        exported = Path(self.temp.name) / 'export.json'
        result = subprocess.run([str(ROOT / 'install.sh'), '--target', str(self.home), '--profile', str(profile),
                                 '--save-profile', str(exported), '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('vscode-extensions', result.stdout)
        self.assertFalse(self.home.exists())
        self.assertFalse(exported.exists())

    def test_invalid_profiles_and_option_injection_are_rejected(self):
        invalid = [[], {'requested': ['orbit']}, {'packages': 'yes'}, {'choices': {'terminal': 'arbitrary'}},
                   {'setup': ['shell-command']}, {'extra_packages': ['--noconfirm']},
                   {'extra_packages': ['a; echo bad']}, {'requested': ['terminal'], 'setup': ['nvim-plugins']},
                   {'tinywidgets_source': 'bad\npath'}, {'schema': 42}]
        for profile in invalid:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                installer.validate_selection(profile)
        self.assertFalse(self.home.exists())

    def test_wizard_can_save_setup_packages_apps_and_alternatives(self):
        args = self.wizard_args({'requested': ['terminal', 'shell']})
        args.save_profile = Path(self.temp.name) / 'personal.json'
        inputs = ['', 'l', '1', 'p', '1', 's', '1', 'w', 'q']
        with patch('builtins.input', side_effect=inputs), redirect_stdout(self.output):
            self.assertIsNone(installer.interactive(args))
        profile = installer.load_selection(self.home, args.save_profile)
        self.assertEqual(profile['choices']['terminal'], 'alacritty')
        self.assertEqual(profile['extra_packages'], ['jq'])
        self.assertTrue(profile['packages'])
        self.assertIn('vscode', profile['requested'])
        self.assertEqual(profile['setup'], ['vscode-extensions'])
        self.assertFalse(self.home.exists())

    def test_wizard_can_uncheck_a_previously_selected_feature(self):
        args = self.wizard_args({'requested': ['terminal', 'wallpaper']})
        inputs = ['', '6', 'i', 'y']
        with patch('builtins.input', side_effect=inputs), redirect_stdout(self.output):
            requested = installer.interactive(args)
        self.assertEqual(requested, ['terminal'])
        self.assertNotIn('wallpaper', installer.resolve_modules(requested, installer.choices_for(args)))

    def test_minimal_wayfire_does_not_start_unselected_features_or_apps(self):
        choices = {**self.choices, 'launcher': 'fuzzel'}
        modules, plan = self.plan(['wayfire'], choices)
        wf = plan['.config/wayfire.ini'][0].decode()
        for key in ['bar =', 'desktop_power =', 'wallpaper_daemon =', 'command_wallpaper =',
                    'command_shot_area =', 'osd =', 'command_browser =', 'command_files =', 'command_editor =']:
            self.assertIsNone(re.search('^' + re.escape(key), wf, re.M), key)
        self.assertIn('background_mode = simple', wf)
        self.assertNotIn('firefox', installer.packages_for(modules))
        self.assertNotIn('dolphin', installer.packages_for(modules))

    def test_browser_and_filemanager_alternatives_update_menu_and_shortcuts(self):
        choices = {**self.choices, 'browser': 'chromium', 'filemanager': 'thunar'}
        modules, plan = self.plan(choices=choices)
        wf = plan['.config/wayfire.ini'][0].decode()
        menu = plan['.local/lib/raccon_menu/backend.py'][0].decode()
        self.assertIn('command_browser = chromium', wf)
        self.assertIn('command_files = thunar', wf)
        self.assertIn("['chromium']", menu)
        self.assertIn("['thunar']", menu)
        self.assertNotIn('firefox', installer.packages_for(modules))
        self.assertNotIn('dolphin', installer.packages_for(modules))

    def test_external_setup_runs_requested_actions_and_records_success(self):
        selection = installer.validate_selection({'requested': ['vscode', 'nvim'],
                                                   'setup': ['vscode-extensions', 'nvim-plugins']})
        with patch.object(installer.subprocess, 'run') as run, redirect_stdout(self.output):
            installer.run_setup(selection, self.home)
        self.assertEqual(run.call_count, 2)
        self.assertIn('install-vscode-extensions.sh', run.call_args_list[0].args[0][1])
        self.assertEqual(run.call_args_list[1].args[0], ['nvim', '--headless', '+Lazy! sync', '+qa'])
        status = json.loads((self.home / '.local/state/raccon-dots/setup.json').read_text())
        self.assertTrue(all(v['status'] == 'complete' for v in status['actions'].values()))

    def test_plymouth_setup_runs_in_the_foreground_for_sudo(self):
        selection = installer.validate_selection({'requested': ['themes'], 'setup': ['plymouth']})
        with patch.object(installer.subprocess, 'run') as run, redirect_stdout(self.output):
            installer.run_setup(selection, self.home)
        command = run.call_args.args[0]
        self.assertTrue(command[1].endswith('extras/install-plymouth.sh'))
        self.assertNotIn('start_new_session', run.call_args.kwargs)
        theme = installer.ROOT / 'extras/plymouth/raccon-code'
        self.assertTrue(all((theme / f).is_file() for f in
                            ('raccon-code.plymouth', 'raccon-code.script', 'raccoon.png', 'bar.png', 'track.png')))

    def test_failed_app_setup_preserves_preferences_and_records_a_retryable_failure(self):
        selection = installer.validate_selection({'requested': ['vscode'], 'setup': ['vscode-extensions']})
        modules = installer.resolve_modules(selection['requested'], selection['choices'])
        plan = installer.file_plan(self.home, modules, selection['choices'])
        with redirect_stdout(self.output):
            backup = installer.apply_plan(self.home, plan, modules, selection['choices'], selection)
        with patch.object(installer.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['code'])), redirect_stdout(self.output):
            with self.assertRaisesRegex(ValueError, 'preferences are saved'):
                installer.run_setup(selection, self.home)
        self.assertEqual(installer.load_selection(self.home), selection)
        state = json.loads((self.home / '.local/state/raccon-dots/setup.json').read_text())
        self.assertEqual(state['actions']['vscode-extensions']['status'], 'failed')
        # Setup status does not change the receipt behind the backup journal's back.
        with redirect_stdout(self.output):
            installer.restore(backup, self.home)

    def test_installed_aur_packages_are_not_sent_back_to_pacman_sync(self):
        def pacman(command, **kwargs):
            if command[:2] == ['pacman', '-Q']:
                return SimpleNamespace(returncode=0 if command[-1] == 'eww' else 1)
            return SimpleNamespace(returncode=0)
        with patch.object(installer.shutil, 'which', return_value='/usr/bin/pacman'), \
                patch.object(installer.subprocess, 'run', side_effect=pacman) as run:
            installer.install_packages(['eww', 'jq'])
        calls = [c.args[0] for c in run.call_args_list]
        self.assertIn(['sudo', 'pacman', '-S', '--needed', '--', 'jq'], calls)
        self.assertNotIn(['pacman', '-Si', 'eww'], calls)

    def test_changed_profile_keeps_loadable_history_and_no_op_does_not_duplicate_it(self):
        profile = Path(self.temp.name) / 'profiles/personal.json'
        first = installer.validate_selection({'requested': ['terminal']})
        second = installer.validate_selection({'requested': ['terminal', 'shell']})
        with redirect_stdout(self.output):
            installer.save_profile(profile, first)
            installer.save_profile(profile, second)
            installer.save_profile(profile, second)
        history = list((profile.parent / '.history/personal').glob('*.json'))
        self.assertEqual(len(history), 1)
        self.assertEqual(installer.load_selection(self.home, history[0]), first)
        self.assertEqual(installer.load_selection(self.home, profile), second)

    def test_legacy_receipt_migrates_physical_alternatives_to_selectable_roles(self):
        selection = installer.validate_selection({'name': 'raccon-dots', 'version': '0.1.0',
            'modules': ['base', 'kitty', 'fuzzel', 'desktop', 'desktop-menu', 'wayfire'],
            'choices': self.choices})
        self.assertIn('terminal', selection['requested'])
        self.assertIn('launcher', selection['requested'])
        self.assertNotIn('base', selection['requested'])
        self.assertNotIn('kitty', selection['requested'])
        self.assertNotIn('fuzzel', selection['requested'])

    def test_wizard_restore_recovers_previous_files_and_preferences(self):
        def apply(selection):
            modules = installer.resolve_modules(selection['requested'], selection['choices'])
            plan = installer.file_plan(self.home, modules, selection['choices'])
            return installer.apply_plan(self.home, plan, modules, selection['choices'], selection)
        first = installer.validate_selection({'requested': ['terminal', 'shell'],
                                               'choices': {**self.choices, 'shell': 'fish'}})
        second = installer.validate_selection({'requested': ['terminal', 'shell']})
        with redirect_stdout(self.output):
            apply(first)
            apply(second)
            with patch('builtins.input', side_effect=['1', 'y', '']):
                self.assertTrue(installer.recovery_screen(self.wizard_args(second)))
        self.assertEqual(installer.load_selection(self.home), first)
        self.assertIn('shell fish', (self.home / '.config/kitty/kitty.conf').read_text())

    def test_external_setup_with_temporary_target_is_rejected_before_file_installation(self):
        with redirect_stdout(self.output), patch('sys.stderr', self.output):
            with self.assertRaises(SystemExit):
                installer.main(['--target', str(self.home), '--modules', 'vscode',
                                '--setup', 'vscode-extensions', '--yes'])
        self.assertFalse(self.home.exists())
        self.assertIn('require your real HOME', self.output.getvalue())

    def test_tinywidgets_setup_preflight_requires_source_before_build_or_downloads(self):
        selection = installer.validate_selection({'requested': ['widgets'], 'packages': True,
                    'setup': ['tinywidgets'], 'tinywidgets_source': str(Path(self.temp.name) / 'missing')})
        with patch.object(installer.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'valid tinyWidgets source'):
                installer.setup_preflight(selection, self.home)
        run.assert_not_called()
        self.assertFalse(self.home.exists())


if __name__ == '__main__':
    unittest.main()
