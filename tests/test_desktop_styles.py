"""Portable global styles, exercised in disposable homes without desktop services."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'modules/desktop-styles/files/.local/lib'))
spec=importlib.util.spec_from_file_location('styles_installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class DesktopStylesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='desktop styles ')
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)/'home with spaces'
        self.choices={key:value['default'] for key,value in installer.CATALOG['choices'].items()}

    def plan(self,requested):
        modules=installer.resolve_modules(requested,self.choices)
        return modules,installer.file_plan(self.home,modules,self.choices)

    def install_fixture(self):
        modules,plan=self.plan(['desktop-styles','power','desktop'])
        for relative,(data,mode) in plan.items():
            path=self.home/relative;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data);path.chmod(mode)
        return modules,plan

    def load_engine(self):
        spec=importlib.util.spec_from_file_location('installed_style_engine',self.home/'.local/lib/desktop_style/main.py')
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        return engine

    def test_module_resolves_without_widgets_and_preserves_asset_license(self):
        modules,plan=self.plan(['desktop-styles'])
        self.assertNotIn('widgets',modules)
        self.assertNotIn('tinywidgets',modules)
        self.assertIn('librsvg',installer.packages_for(modules))
        self.assertIn('adwaita-fonts',installer.packages_for(modules))
        self.assertEqual(plan['.local/share/fonts/Silkscreen/Silkscreen-Regular.ttf'][0][:4],b'\x00\x01\x00\x00')
        self.assertIn(b'SIL OPEN FONT LICENSE',plan['.local/share/fonts/Silkscreen/OFL.txt'][0])

    def test_exports_contain_no_runtime_state_or_machine_paths(self):
        _,plan=self.plan(['desktop-styles'])
        for relative,(data,_) in plan.items():
            self.assertFalse(relative.startswith('.local/state/desktop-style/'),relative)
            if relative.endswith(('.ttf','.png')):continue
            text=data.decode()
            self.assertNotIn(str(Path.home()),text,relative)
            self.assertNotIn('@RDOT_',text,relative)
        for name in ('rofi.rasi',):
            self.assertNotIn(b'background:',plan['.config/desktop-style/current/'+name][0])

    def test_imports_are_installed_only_with_styles(self):
        for requested,enabled in ((['desktop-styles'],True),(['hyprland','wallpaper'],False)):
            with self.subTest(enabled=enabled):
                _,plan=self.plan(requested)
                for relative in ('.config/rofi/clipboard.rasi','.config/rofi/wallpaper.rasi'):
                    self.assertEqual('desktop-style/current/' in plan[relative][0].decode(),enabled)
                hook=plan['.local/bin/wallpaper-theme'][0].decode()
                self.assertEqual('desktop-style" wallpaper' in hook,enabled)
                if enabled:
                    self.assertNotIn('desktop-style" wallpaper &',hook)

    def test_desktop_entry_supports_target_home_with_spaces(self):
        _,plan=self.plan(['desktop-styles'])
        text=plan['.local/share/applications/desktop-style.desktop'][0].decode()
        self.assertIn('Exec="'+str(self.home/'.local/bin/desktop-style')+'" apply',text)

    def test_fresh_install_applies_all_profiles_and_restores_without_widgetctl(self):
        _,plan=self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine()
            before=engine.managed_settings()
            self.assertFalse(engine.widgets_available())
            with patch.object(engine,'update'),patch.object(engine,'refresh_clients',return_value=[]):
                for name in engine.PROFILES:
                    engine.apply(name)
                    self.assertEqual(engine.read(engine.STATE/'selection.json')['style'],name)
                    self.assertEqual(engine.read(engine.CURRENT/'tokens.json')['style'],name)
                engine.reset()
                self.assertEqual(engine.managed_settings(),before)
                self.assertEqual(engine.read(engine.STATE/'selection.json')['style'],'original')
            self.assertFalse((self.home/'.config/eww/style.json').exists())

    def test_installed_cli_and_working_idle_guard(self):
        self.install_fixture()
        env={**os.environ,'HOME':str(self.home),'XDG_STATE_HOME':str(self.home/'.local/state')}
        result=subprocess.run([str(self.home/'.local/bin/desktop-style'),'list'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)),1)
        folder=self.home/'.local/state/desktop-power';folder.mkdir(parents=True)
        for mode,locks in (('working',False),('balanced',True)):
            (folder/'preference.json').write_text(json.dumps({'mode':mode}))
            result=subprocess.run([str(self.home/'.local/bin/idle-lock'),'--check'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['lock_on_idle'],locks)

    def test_exporter_drops_active_selection_backups_and_overrides(self):
        self.install_fixture()
        spec=importlib.util.spec_from_file_location('styles_capture',ROOT/'scripts/capture.py')
        capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
        private=self.home/'.local/state/desktop-style/original.json';private.parent.mkdir(parents=True)
        private.write_text('{"private":"rollback data"}')
        (self.home/'.config/desktop-style/backup.json').write_text('private backup')
        (self.home/'.config/desktop-style/current/rofi.rasi').write_text('background: red;')
        exported=Path(self.temp.name)/'export'
        with patch.object(capture,'ROOT',exported):capture.capture_styles(self.home)
        base=exported/'modules/desktop-styles/files'
        self.assertFalse((base/'.local/state').exists())
        self.assertFalse((base/'.config/desktop-style/backup.json').exists())
        self.assertNotIn('background:',(base/'.config/desktop-style/current/rofi.rasi').read_text())

    def test_wallpaper_change_invalidates_original_palette_cache(self):
        self.install_fixture()
        image=self.home/'wallpaper.png';image.write_bytes(b'first image')
        cache=self.home/'.cache';cache.mkdir()
        (cache/'current-wallpaper').write_text(str(image))
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine()
            colors={'primary':'#aaddff','surface':'#111111','on_surface':'#eeeeee'}
            def native():return subprocess.CompletedProcess([],0,json.dumps({'colors':{k:{'dark':{'color':v}} for k,v in colors.items()}}),'')
            with patch.object(engine,'run',side_effect=lambda *a,**k:native()) as invoke:
                self.assertEqual(engine.source_palette()['primary'],'#aaddff')
                image.write_bytes(b'different wallpaper')
                colors['primary']='#ffccaa'
                self.assertEqual(engine.source_palette()['primary'],'#ffccaa')
                self.assertEqual(invoke.call_count,2)
                self.assertIn('--dry-run',invoke.call_args.args[0])

    def test_actual_gtk_panel_cascade_uses_profile_font_border_and_contrast(self):
        import gi
        gi.require_version('Gtk','3.0')
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:self.skipTest('GTK display required for computed style probe')
        self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine()
            from desktop_style.appearance import build
            source=engine.source_palette()
            baseline=(self.home/'.config/desktop-menu/style.css').read_text()
            for name,profile in engine.PROFILES.items():
                with self.subTest(style=name),warnings.catch_warnings():
                    warnings.simplefilter('ignore',DeprecationWarning)
                    colors,_=engine.palette(name,source)
                    css=baseline
                    for key,value in colors.items():css=css.replace('@'+key+';',value+';')
                    css+='\n'+build(name,profile,colors)['panels']
                    window=Gtk.Window();window.set_name('desktop-menu')
                    panel=Gtk.Box();panel.get_style_context().add_class('panel');window.add(panel)
                    button=Gtk.Button(label='Aplicar');panel.add(button)
                    provider=Gtk.CssProvider();provider.load_from_data(css.encode())
                    Gtk.StyleContext.add_provider_for_screen(window.get_screen(),provider,600)
                    try:
                        context=panel.get_style_context()
                        self.assertEqual(context.get_border(0).left,profile['border'])
                        self.assertTrue(context.get_font(0).get_family().startswith(profile['font']))
                        self.assertEqual(button.get_style_context().get_property('border-radius',0),min(profile['radius'],10))
                        fg=context.get_color(0);bg=context.get_background_color(0)
                        fghex=engine.hexcolor((fg.red,fg.green,fg.blue));bghex=engine.hexcolor((bg.red,bg.green,bg.blue))
                        lo,hi=sorted([engine.luminance(fghex),engine.luminance(bghex)])
                        self.assertGreaterEqual((hi+.05)/(lo+.05),4.5)
                        # Hovering must use the paired foreground of the filled accent.
                        button.set_state_flags(Gtk.StateFlags.PRELIGHT,False)
                        context=button.get_style_context()
                        fg=context.get_color(Gtk.StateFlags.PRELIGHT);bg=context.get_background_color(Gtk.StateFlags.PRELIGHT)
                        lo,hi=sorted([engine.luminance(engine.hexcolor((v.red,v.green,v.blue))) for v in (fg,bg)])
                        self.assertGreaterEqual((hi+.05)/(lo+.05),4.5)
                    finally:
                        Gtk.StyleContext.remove_provider_for_screen(window.get_screen(),provider)
                        window.destroy()

        with patch.dict(os.environ, {'HOME': str(self.home), 'DESKTOP_STYLE_NO_TRANSITION': '1'}):
            engine = self.load_engine()
            bin_dir = self.home / '.local/bin'
            bin_dir.mkdir(parents=True, exist_ok=True)
            raccon_mode = bin_dir / 'raccon-canvas-mode'
            saved_raccon_mode = raccon_mode.read_bytes() if raccon_mode.exists() else None
            raccon_mode.unlink(missing_ok=True)
            wf_mode = bin_dir / 'wf-canvas-mode'
            wf_mode.write_text('#!/bin/sh\necho canvas\n')
            wf_mode.chmod(0o755)
            with patch.object(engine, 'BIN', bin_dir), patch.object(engine, 'run') as invoke:
                invoke.return_value = subprocess.CompletedProcess([], 0, '', '')
                engine.refresh_clients()
                self.assertEqual(invoke.call_args_list[-1].args[0], [bin_dir / 'wf-canvas-mode', 'refresh'])

            raccon_mode.write_bytes(saved_raccon_mode) if saved_raccon_mode else raccon_mode.write_text('#!/bin/sh\necho canvas\n')
            raccon_mode.chmod(0o755)
            with patch.object(engine, 'BIN', bin_dir), patch.object(engine, 'run') as invoke:
                invoke.return_value = subprocess.CompletedProcess([], 0, '', '')
                engine.refresh_clients()
                self.assertEqual(invoke.call_args_list[-1].args[0], [bin_dir / 'raccon-canvas-mode', 'refresh'])


if __name__=='__main__':unittest.main()
