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
        modules,plan=self.plan(['desktop-styles'])
        for relative,(data,mode) in plan.items():
            path=self.home/relative;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data);path.chmod(mode)
        return modules,plan

    def load_engine(self):
        spec=importlib.util.spec_from_file_location('installed_style_engine',self.home/'.local/lib/desktop_style/main.py')
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        return engine

    def test_shell_fade_preserves_apps_and_restores_replacement_surfaces(self):
        from desktop_style.transition import Fade
        views=[{'id':1,'app-id':'waybar','mapped':True},
               {'id':2,'app-id':'kitty','mapped':True},
               {'id':3,'app-id':'awww-daemon','mapped':True},
               {'id':4,'app-id':'rw-test-clock','mapped':False}]
        alpha={1:.8,2:.7,3:1,4:1}
        def request(method,data=None):
            if method=='window-rules/list-views':return views
            key=data['view-id']
            if method.endswith('get-view-alpha'):return {'alpha':alpha[key]}
            alpha[key]=data['alpha'];return {'result':'ok'}
        fade=Fade(request)
        fade.frame(0)
        self.assertEqual(alpha,{1:0,2:.7,3:1,4:1})
        views.append({'id':5,'app-id':'desktop-style','mapped':True});alpha[5]=.9
        fade.frame(0)
        self.assertEqual(alpha[5],0)
        fade.restore()
        self.assertEqual(alpha,{1:.8,2:.7,3:1,4:1,5:.9})

    def test_shell_fade_worker_restores_on_error_and_parent_eof(self):
        from desktop_style import transition
        for failure in (False,True):
            with self.subTest(failure=failure),patch.object(transition,'Fade') as factory,patch.object(transition.select,'select',return_value=([object()],[],[])),patch('builtins.print'):
                fade=factory.return_value
                if failure:fade.animate.side_effect=OSError('IPC lost')
                transition.worker()
                fade.restore.assert_called_once()
                if not failure:self.assertEqual(fade.animate.call_args_list[-1].args,(True,))

    def test_module_resolves_without_widgets_and_preserves_asset_license(self):
        modules,plan=self.plan(['desktop-styles'])
        self.assertNotIn('widgets',modules)
        self.assertNotIn('tinywidgets',modules)
        self.assertIn('librsvg',installer.packages_for(modules))
        self.assertIn('adwaita-fonts',installer.packages_for(modules))
        self.assertEqual(plan['.local/share/fonts/Silkscreen/Silkscreen-Regular.ttf'][0][:4],b'\x00\x01\x00\x00')
        self.assertIn(b'SIL OPEN FONT LICENSE',plan['.local/share/fonts/Silkscreen/OFL.txt'][0])
        self.assertIn('idle-lock',plan['.config/wayfire.ini'][0].decode())

    def test_exports_contain_no_runtime_state_or_machine_paths(self):
        _,plan=self.plan(['desktop-styles'])
        for relative,(data,_) in plan.items():
            self.assertFalse(relative.startswith('.local/state/desktop-style/'),relative)
            if relative.endswith(('.ttf','.png')):continue
            text=data.decode()
            self.assertNotIn(str(Path.home()),text,relative)
            self.assertNotIn('@RDOT_',text,relative)
        source=plan['.config/desktop-style/eww.yuck'][0].decode()
        match=re.search(r'\(deflisten ui :initial ("(?:[^"\\]|\\.)*")',source)
        initial=json.loads(json.loads(match[1]))
        self.assertEqual(initial['current'],'original')
        self.assertEqual(initial['selected'],'modern')
        self.assertFalse(initial['busy'])
        self.assertEqual(len(initial['choices']),7)
        self.assertEqual([row['name'] for row in initial['choices']],
                         ['Default','Transparent','Classic','Mono','Retro','Night','Raccon Retrofuture'])
        self.assertEqual(source.count(':image-height 280'),1)
        for name in ('waybar.css','raccon.scss','rofi.rasi'):
            self.assertNotIn(b'background:',plan['.config/desktop-style/current/'+name][0])

    def test_imports_are_installed_only_with_styles(self):
        for requested,enabled in ((['desktop-styles'],True),(['wayfire','waybar','wallpaper'],False)):
            with self.subTest(enabled=enabled):
                _,plan=self.plan(requested)
                for relative in ('.config/waybar/style.css','.config/rofi/clipboard.rasi','.config/rofi/wallpaper.rasi'):
                    self.assertEqual('desktop-style/current/' in plan[relative][0].decode(),enabled)
                menu=plan['.config/raccon-menu/eww.scss'][0].decode()
                self.assertEqual('@import "desktop-style";' in menu,enabled)
                shortcut=plan['.config/wayfire.ini'][0].decode()
                self.assertEqual('binding_desktop_style = <super> <alt> KEY_T' in shortcut,enabled)
                self.assertNotIn('desktop-style prewarm',shortcut)
                hook=plan['.local/bin/wallpaper-theme'][0].decode()
                self.assertEqual('desktop-style" wallpaper' in hook,enabled)

    def test_desktop_entry_supports_target_home_with_spaces(self):
        _,plan=self.plan(['desktop-styles'])
        text=plan['.local/share/applications/desktop-style.desktop'][0].decode()
        self.assertIn('Exec="'+str(self.home/'.local/bin/desktop-style')+'" open',text)

    def test_selector_adapter_builds_in_fresh_install_with_spaces(self):
        self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home)}):
            engine=self.load_engine()
            module=engine.selector_module()
            self.assertTrue(module.is_file())
            before=module.stat().st_mtime_ns
            self.assertEqual(engine.selector_module().stat().st_mtime_ns,before)

    def test_fresh_install_applies_all_profiles_and_restores_without_widgetctl(self):
        _,plan=self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine()
            before=engine.managed_settings()
            self.assertFalse(engine.widgets_available())
            with patch.object(engine,'update'),patch.object(engine,'refresh_clients',return_value=[]),patch.object(engine,'preview',return_value={}),patch.object(engine,'run') as external:
                adopted=[]
                def popup_palette(argv, *args, **kwargs):
                    adopted.append(engine.read(engine.CURRENT/'tokens.json').get('style'))
                    return subprocess.CompletedProcess(argv,0,'','')
                external.side_effect=popup_palette
                for name in engine.PROFILES:
                    engine.apply(name)
                    self.assertEqual(engine.read(engine.STATE/'selection.json')['style'],name)
                    # Eww renders :initial before the deflisten stream arrives.
                    # A CSS reload must never briefly restore shipped Moderno.
                    yuck=(engine.CONFIG/'eww.yuck').read_text()
                    initial=json.loads(json.loads(re.search(r'\(deflisten ui :initial ("(?:[^"\\]|\\.)*")',yuck)[1]))
                    self.assertEqual(initial['current'],name)
                    self.assertEqual(initial['selected'],name)
                # Simulate an original-appearance backup from an older release.
                # Reset may restore colors, but must retain today's selector UI.
                original=engine.read(engine.STATE/'original.json')
                self.assertNotIn(str(engine.CONFIG/'eww.yuck'),original)
                original[str(engine.CONFIG/'eww.yuck')]='(defwidget obsolete-selector [] (box))\n'
                engine.save(engine.STATE/'original.json',original)
                engine.reset()
                self.assertEqual((engine.CONFIG/'eww.yuck').read_text(),yuck)
                self.assertEqual(adopted,list(engine.PROFILES)+[None])
                self.assertEqual(len(external.call_args_list),len(engine.PROFILES)+1)
                for invocation in external.call_args_list:
                    self.assertEqual(invocation.args[0], [sys.executable,self.home/'.local/lib/raccon_menu/backend.py','palette'])
                self.assertEqual(engine.managed_settings(),before)
                self.assertEqual(engine.read(engine.STATE/'selection.json')['style'],'original')
            self.assertFalse((self.home/'.config/eww/style.json').exists())
            self.assertEqual((self.home/'.config/waybar/colors.css').read_bytes(),plan['.config/waybar/colors.css'][0])

    def test_installed_cli_and_working_idle_guard(self):
        self.install_fixture()
        env={**os.environ,'HOME':str(self.home),'XDG_STATE_HOME':str(self.home/'.local/state')}
        result=subprocess.run([str(self.home/'.local/bin/desktop-style'),'list'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)),7)
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
        yuck=self.home/'.config/desktop-style/eww.yuck'
        text=yuck.read_text()
        match=re.search(r'\(deflisten ui :initial ("(?:[^"\\]|\\.)*")',text)
        initial=json.loads(json.loads(match[1]))
        initial.update(current='glass',selected='windows',busy=True,notice='Private runtime trace')
        yuck.write_text(text[:match.start(1)]+json.dumps(json.dumps(initial))+text[match.end(1):])
        private=self.home/'.local/state/desktop-style/original.json';private.parent.mkdir(parents=True)
        private.write_text('{"private":"rollback data"}')
        (self.home/'.config/desktop-style/backup.json').write_text('private backup')
        (self.home/'.config/desktop-style/current/waybar.css').write_text('background: red;')
        exported=Path(self.temp.name)/'export'
        with patch.object(capture,'ROOT',exported):capture.capture_styles(self.home)
        base=exported/'modules/desktop-styles/files'
        self.assertFalse((base/'.local/state').exists())
        self.assertFalse((base/'.config/desktop-style/backup.json').exists())
        text=(base/'.config/desktop-style/eww.yuck').read_text()
        self.assertNotIn('Private runtime trace',text)
        match=re.search(r'\(deflisten ui :initial ("(?:[^"\\]|\\.)*")',text)
        initial=json.loads(json.loads(match[1]))
        self.assertEqual(initial['current'],'original')
        self.assertEqual(initial['selected'],'modern')
        self.assertNotIn('background:',(base/'.config/desktop-style/current/waybar.css').read_text())

    def test_original_palette_is_not_recovered_from_themed_waybar(self):
        self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine()
            original=engine.source_palette()
            raw=self.home/'.config/matugen/out/desktop-style-source.json'
            raw.parent.mkdir(parents=True,exist_ok=True)
            raw.write_text(json.dumps(original))
            engine.save(engine.STATE/'selection.json',{'style':'monochrome'})
            (self.home/'.config/waybar/colors.css').write_text('@define-color primary #ffffff;\n@define-color surface #000000;\n@define-color on_surface #ffffff;')
            self.assertEqual(engine.source_palette(refresh=True),original)
            self.assertEqual(json.loads(raw.read_text()),original)

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

    def test_monochrome_background_is_actual_dominant_image_color(self):
        from PIL import Image
        self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine();original=engine.source_palette()
            image=self.home/'wallpaper.png'
            photo=Image.new('RGB',(32,32),'#d08030')
            photo.paste('#080808',(0,0,8,8));photo.save(image)
            folder=self.home/'.cache';folder.mkdir()
            (folder/'current-wallpaper').write_text(str(image))
            raw=self.home/'.config/matugen/out/desktop-style-source.json';raw.parent.mkdir(parents=True,exist_ok=True)
            raw.write_text(json.dumps(original))
            colors,pair=engine.palette('monochrome',engine.source_palette())
            self.assertEqual(colors['surface'],'#d08030')
            self.assertEqual(colors['on_surface'],'#080808')
            self.assertEqual(set(colors.values()),set(pair))
            self.assertGreaterEqual(engine.contrast_ratio(*pair),4.5)

    def test_monochrome_gray_wallpaper_does_not_inherit_matugen_blue_seed(self):
        from PIL import Image
        self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine();original=engine.source_palette()
            image=self.home/'gray.png';Image.new('RGB',(16,16),'#303030').save(image)
            folder=self.home/'.cache';folder.mkdir();(folder/'current-wallpaper').write_text(str(image))
            raw=self.home/'.config/matugen/out/desktop-style-source.json';raw.parent.mkdir(parents=True,exist_ok=True);raw.write_text(json.dumps(original))
            colors,pair=engine.palette('monochrome',engine.source_palette())
            self.assertEqual(colors['surface'],'#303030')
            self.assertNotEqual(colors['on_surface'],'#ffffff')
            self.assertGreaterEqual(engine.contrast_ratio(*pair),4.5)

    def test_repeated_waybar_reload_emits_close_write_without_replacing_monitor_inode(self):
        import time
        from gi.repository import Gio,GLib
        self.install_fixture()
        with patch.dict(os.environ,{'HOME':str(self.home),'DESKTOP_STYLE_NO_TRANSITION':'1'}):
            engine=self.load_engine();path=self.home/'.config/waybar/style.css'
            before=path.read_bytes();inode=path.stat().st_ino;events=[]
            monitor=Gio.File.new_for_path(str(path)).monitor_file(Gio.FileMonitorFlags.NONE,None)
            monitor.connect('changed',lambda _m,_f,_o,event:events.append(event))
            try:
                for _ in range(2):
                    events.clear();engine.reload_bar_style();deadline=time.monotonic()+2
                    while Gio.FileMonitorEvent.CHANGES_DONE_HINT not in events and time.monotonic()<deadline:
                        GLib.MainContext.default().iteration(False);time.sleep(.005)
                    self.assertIn(Gio.FileMonitorEvent.CHANGES_DONE_HINT,events)
                    self.assertEqual(path.stat().st_ino,inode)
                    self.assertEqual(path.read_bytes(),before)
            finally:monitor.cancel()

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


if __name__=='__main__':unittest.main()
