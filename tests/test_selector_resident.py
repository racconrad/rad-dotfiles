"""Resident selector transport and first-start ordering without desktop mutations."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'modules/desktop-styles/files/.local/lib/desktop_style'
spec=importlib.util.spec_from_file_location('resident_styles',LIB/'main.py')
styles=importlib.util.module_from_spec(spec);spec.loader.exec_module(styles)


class ResidentSelectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.runtime=self.home/'runtime';self.runtime.mkdir()
        self.control=self.runtime/'desktop-style';self.control.mkdir()
        self.state=self.home/'state';self.state.mkdir()
        self.config=self.home/'config';self.config.mkdir()
        here=self.home/'lib/desktop_style';here.mkdir(parents=True)
        (here/'selector_input.c').write_bytes((LIB/'selector_input.c').read_bytes())
        navigation=here.parent/'raccon_menu/navigation.h';navigation.parent.mkdir()
        navigation.write_bytes((ROOT/'modules/desktop/files/.local/lib/raccon_menu/navigation.h').read_bytes())
        p=patch.object(styles,'__file__',str(here/'main.py'));p.start();self.addCleanup(p.stop)
        for name,value in (('HOME',self.home),('STATE',self.state),('CONFIG',self.config)):
            p=patch.object(styles,name,value);p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'XDG_RUNTIME_DIR':str(self.runtime)});p.start();self.addCleanup(p.stop)
        self.config.joinpath('eww.yuck').write_text('(deflisten ui :initial "{}" "watch")\n')
        self.control.joinpath('revision').write_text(styles.selector_revision())
        self.control.joinpath('mapped').touch()

    def fifo(self):
        os.mkfifo(self.control/'control',0o600)
        fd=os.open(self.control/'control',os.O_RDWR|os.O_NONBLOCK)
        self.addCleanup(os.close,fd)
        return fd

    def test_warm_visibility_never_starts_an_eww_client_or_rebuilds_assets(self):
        fd=self.fifo()
        with patch.object(styles.subprocess,'run',side_effect=AssertionError('IPC on warm path')), \
             patch.object(styles,'source_palette',side_effect=AssertionError('Assets on warm path')):
            styles.open_selector();styles.toggle_selector();styles.close_selector();styles.open_selector(prewarm=True)
        self.assertEqual(os.read(fd,4096),b'show\ntoggle\nhide\nping\n')

    def test_stale_module_missing_reader_and_regular_file_use_recovery_path(self):
        fd=self.fifo()
        self.control.joinpath('revision').write_text('old')
        self.assertFalse(styles.selector_send('show'))
        self.control.joinpath('revision').write_text(styles.selector_revision())
        self.assertTrue(styles.selector_send('hide'))
        self.assertEqual(os.read(fd,4096),b'hide\n')
        self.control.joinpath('control').unlink()
        os.mkfifo(self.control/'control',0o600)
        self.assertFalse(styles.selector_send('show'))
        self.control.joinpath('control').unlink()
        self.control.joinpath('control').write_text('keep')
        self.assertFalse(styles.selector_send('show'))
        self.assertEqual(self.control.joinpath('control').read_text(),'keep')

    def test_offline_updates_are_persisted_without_dead_ipc(self):
        with patch.object(styles,'eww',side_effect=AssertionError('IPC without daemon')):
            styles.update(selected='glass')
        self.assertEqual(styles.read(self.state/'ui.json')['selected'],'glass')

    def test_renderer_edits_do_not_invalidate_the_native_resident(self):
        fd=self.fifo()
        Path(styles.__file__).write_text('# Updated theme names and rendering\n')
        self.assertTrue(styles.selector_send('show'))
        self.assertEqual(os.read(fd,4096),b'show\n')

    def test_cold_open_publishes_state_only_after_daemon_is_ready(self):
        module=self.home/'selector.so';module.touch()
        source=ROOT/'modules/desktop-styles/files/.config/desktop-style/source-colors.json'
        colors=json.loads(source.read_text())
        catalogue={k:dict(id=k,**v,preview='',swatches='',count=2) for k,v in styles.PROFILES.items()}
        started=[];commands=[]
        def eww(*args,**kwargs):
            self.assertTrue(started,'Eww was contacted before launch')
            commands.append(args)
            return subprocess.CompletedProcess([],0,'','')
        def spawn(*args,**kwargs):started.append(kwargs)
        with patch.object(styles,'selector_send',return_value=False), \
             patch.object(styles,'selector_module',return_value=module), \
             patch.object(styles,'source_palette',return_value=colors), \
             patch.object(styles,'preview_catalog',return_value=catalogue), \
             patch.object(styles,'selector_daemon_running',side_effect=lambda:bool(started)), \
             patch.object(styles.subprocess,'Popen',side_effect=spawn),patch.object(styles,'eww',side_effect=eww):
            styles.open_selector(prewarm=True)
        self.assertEqual(len(started),1)
        self.assertEqual([args[0] for args in commands],['update','open'])
        self.assertIn('selector_prewarm=true',commands[0])
        self.assertEqual(started[0]['env']['LANGUAGE'],'en_US:en')
        self.assertFalse(styles.read(self.state/'ui.json')['busy'])
        self.assertEqual(styles.read(self.state/'ui.json')['extra'],'')
        self.assertFalse(styles.read(self.state/'ui.json')['frames_loaded'])


if __name__=='__main__':unittest.main()
