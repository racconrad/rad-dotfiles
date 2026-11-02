"""Duplicate wallpaper requests never repeat a backend or palette transaction."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SETTER=ROOT/'modules/wallpaper/files/.local/bin/wallpaper-set'


class WallpaperGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home'
        self.bin=self.root/'bin';self.bin.mkdir()
        self.cache=self.root/'cache';self.cache.mkdir()
        self.runtime=self.root/'run';self.runtime.mkdir()
        self.log=self.root/'calls'
        (self.home/'.local/bin').mkdir(parents=True)
        self.env={**os.environ,'HOME':str(self.home),'XDG_CACHE_HOME':str(self.cache),
                  'XDG_RUNTIME_DIR':str(self.runtime),'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],
                  'GUARD_LOG':str(self.log),'GUARD_FAIL':str(self.root/'fail')}
        fake='''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
name=Path(sys.argv[0]).name
try:os.fstat(9);inherited=True
except OSError:inherited=False
with open(os.environ['GUARD_LOG'],'a') as out:
 out.write(json.dumps(dict(command=name,args=sys.argv[1:],inherited=inherited))+'\\n')
if name=='awww':
 time.sleep(.08)
 if Path(os.environ['GUARD_FAIL']).exists():raise SystemExit(1)
if name=='waypaper' and '--no-post-command' not in sys.argv:raise SystemExit(97)
if name=='wallpaper-theme':
 path=sys.argv[1]
 cache=Path(os.environ['XDG_CACHE_HOME'])/'current-wallpaper'
 temp=cache.with_suffix('.tmp');temp.write_text(path+'\\n');temp.replace(cache)
'''
        for name in ('awww','waypaper'):
            p=self.bin/name;p.write_text(fake);p.chmod(0o755)
        p=self.home/'.local/bin/wallpaper-theme';p.write_text(fake);p.chmod(0o755)
        for name in ('pkill','pgrep'):
            p=self.bin/name;p.write_text('#!/bin/sh\nexit 0\n');p.chmod(0o755)
        self.image=self.root/'image with spaces.png';self.image.touch()
        self.video=self.root/'clip.mp4';self.video.touch()

    def run_setter(self,path):
        return subprocess.run(['bash',str(SETTER),str(path)],env=self.env,capture_output=True,text=True,timeout=5)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_current_image_and_symlink_do_not_touch_backend_or_theme(self):
        (self.cache/'current-wallpaper').write_text(str(self.image)+'\n')
        alias=self.root/'alias.png';alias.symlink_to(self.image)
        for path in (self.image,alias):self.assertEqual(self.run_setter(path).returncode,0)
        self.assertEqual(self.calls(),[])

    def test_concurrent_clicks_apply_image_once_and_do_not_pass_lock_to_children(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(self.run_setter,[self.image]*20))
        self.assertTrue(all(result.returncode==0 for result in results))
        self.assertEqual([call['command'] for call in self.calls()],['awww','wallpaper-theme'])
        self.assertFalse(any(call['inherited'] for call in self.calls()))

    def test_duplicate_video_is_not_restarted_and_lock_is_not_inherited(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(self.run_setter,[self.video]*10))
        self.assertTrue(all(result.returncode==0 for result in results))
        self.assertEqual([call['command'] for call in self.calls()],['waypaper','wallpaper-theme'])
        self.assertFalse(any(call['inherited'] for call in self.calls()))
        self.assertEqual(self.run_setter(self.image).returncode,0)
        self.assertEqual([call['command'] for call in self.calls()],['waypaper','wallpaper-theme','awww','wallpaper-theme'])

    def test_failed_backend_preserves_previous_wallpaper_and_can_retry(self):
        previous=self.root/'old.png';previous.touch()
        cache=self.cache/'current-wallpaper';cache.write_text(str(previous)+'\n')
        (self.root/'fail').touch()
        self.assertNotEqual(self.run_setter(self.image).returncode,0)
        self.assertEqual(cache.read_text().strip(),str(previous))
        self.assertEqual([call['command'] for call in self.calls()],['awww'])
        (self.root/'fail').unlink()
        self.assertEqual(self.run_setter(self.image).returncode,0)
        self.assertEqual(cache.read_text().strip(),str(self.image))
