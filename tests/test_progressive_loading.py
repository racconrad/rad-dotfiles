"""First paint must not wait for image decoding or application discovery."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import Future
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'modules/desktop-styles/files/.local/lib'))
sys.path.insert(0,str(ROOT/'modules/base/files/.local/lib'))
spec=importlib.util.spec_from_file_location('progressive_walls',ROOT/'modules/desktop/files/.local/lib/raccon_menu/walls.py')
walls=importlib.util.module_from_spec(spec);spec.loader.exec_module(walls)

class GalleryTests(unittest.TestCase):
    def test_initial_gallery_uses_cache_without_decoding(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);image=root/'image.png';image.touch()
            with patch.object(walls,'THUMBS',root),patch.object(walls,'catalogue',return_value={'images':[image],'videos':[]}),patch.object(walls,'thumb',side_effect=AssertionError('decoded on first paint')):
                data,missing=walls.progressive_gallery(dict(section='all',page=None))
                self.assertTrue(data['loading']);self.assertEqual(len(missing),1)
                self.assertEqual(data['rows'][0]['tiles'][0]['index'],0)
                self.assertFalse(data['rows'][0]['tiles'][0]['has_thumb'])
    def test_request_is_atomic_and_does_not_decode(self):
        with tempfile.TemporaryDirectory() as root,patch.object(walls,'REQUEST',Path(root)/'request.json'),patch.object(walls,'thumb',side_effect=AssertionError):
            walls.request_gallery('videos');first=walls.gallery_request()
            walls.request_gallery('images',2);second=walls.gallery_request()
            self.assertNotEqual(first['token'],second['token']);self.assertEqual(second['page'],2)
            self.assertEqual(list(Path(root).iterdir()),[walls.REQUEST])
    def test_first_state_is_emitted_before_any_decoder_submission(self):
        with tempfile.TemporaryDirectory() as root,patch.object(walls,'REQUEST',Path(root)/'request.json'),patch.object(walls,'THUMBS',Path(root)),patch.object(walls,'progressive_gallery',return_value=({'loading':True},[(Path('video.mp4'),{})])),patch.object(walls,'ThreadPoolExecutor') as pool,patch('builtins.print',side_effect=RuntimeError('first state delivered')):
            with self.assertRaisesRegex(RuntimeError,'first state'):walls.watch_gallery()
            pool.return_value.__enter__.return_value.submit.assert_not_called()
    def test_old_filter_results_never_publish_over_new_filter(self):
        request={'section':'all','token':'A','page':None};output=[]
        def gallery(req):
            tile={'thumb':'','has_thumb':False}
            return {'section':req['section'],'loading':True,'rows':[{'tiles':[tile]}]},[(Path(req['token']),tile)]
        class Pool:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def submit(self,fn,path):
                future=Future();future.set_result('/thumb/'+str(path));return future
        def emit(value,**kwargs):
            data=json.loads(value);output.append(data)
            if not data['loading']:raise RuntimeError('finished')
        class Events:
            def __init__(self,paths):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def wake(self,future=None):pass
            def wait(self,timeout=None):request.update(section='videos',token='B')
        with tempfile.TemporaryDirectory() as root,patch.object(walls,'THUMBS',Path(root)),patch.object(walls,'gallery_request',side_effect=lambda:dict(request)),patch.object(walls,'progressive_gallery',side_effect=gallery),patch.object(walls,'ThreadPoolExecutor',Pool),patch('raccon_events.FileEvents',Events),patch('builtins.print',side_effect=emit):
            with self.assertRaisesRegex(RuntimeError,'finished'):walls.watch_gallery()
        self.assertEqual([x['section'] for x in output],['all','videos','videos'])
        self.assertEqual(output[-1]['rows'][0]['tiles'][0]['thumb'],'/thumb/B')
        self.assertFalse(any('/thumb/A' in json.dumps(x) for x in output))

class StyleTests(unittest.TestCase):
    def test_initial_previews_never_render_or_extract_colors(self):
        from desktop_style import main as s
        with tempfile.TemporaryDirectory() as root,patch.object(s,'STATE',Path(root)/'state'),patch.object(s,'CONFIG',Path(root)/'config'),patch.object(s,'preview',side_effect=AssertionError('rendered')),patch.object(s,'source_palette',side_effect=AssertionError('extracted')):
            catalog=s.initial_catalog()
            self.assertEqual(set(catalog),set(s.PROFILES))
            self.assertTrue(all(Path(row['preview']).is_file() for row in catalog.values()))
    def test_background_previews_preserve_new_selection(self):
        from desktop_style import main as s
        with tempfile.TemporaryDirectory() as root,patch.object(s,'STATE',Path(root)),patch.object(s,'CONFIG',Path(root)/'config'),patch.object(s,'source_palette',return_value={'surface':'#111111'}):
            s.save(s.STATE/'ui.json',dict(selected='modern',current='original',busy=False))
            calls=[]
            def render(key,source):
                calls.append(key)
                if len(calls)==1:s.update(_publish=False,selected='retro')
                return dict(id=key,preview='preview',swatches='swatches')
            with patch.object(s,'preview',side_effect=render):s.refresh_previews()
            self.assertEqual(calls[0],'modern')
            self.assertEqual(s.read(s.STATE/'ui.json')['selected'],'retro')
            self.assertEqual(len(calls),len(s.PROFILES))

class MenuProgressiveTests(unittest.TestCase):
    def test_initial_state_never_enumerates_apps_or_queries_live_desktop(self):
        from test_raccon_menu import menu
        with tempfile.TemporaryDirectory() as root,patch.object(menu,'STATE',Path(root)),patch.object(menu,'cached_applications',side_effect=AssertionError('enumerated before show')),patch.object(menu,'snapshot',side_effect=AssertionError('live state before show')):
            values=menu.initial_values('home',False)
            self.assertEqual(values['catalogue']['apps'],[])
            self.assertTrue(values['catalogue']['favorites'])

class StyleFastPathTests(unittest.TestCase):
    def test_resident_command_is_delivered_without_renderer(self):
        import os
        path=ROOT/'modules/desktop-styles/files/.local/lib/desktop_style/cli.py'
        spec=importlib.util.spec_from_file_location('style_fast',path)
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as root,patch.object(cli.Path,'home',return_value=Path(root)),patch.dict(os.environ,{'XDG_RUNTIME_DIR':root}):
            runtime=Path(root)/'desktop-style';runtime.mkdir()
            sources=(path.parent/'selector_input.c',path.parent.parent/'raccon_menu/navigation.h')
            # Portable modules are split; use a fixture matching their installed layout.
            fixture=Path(root)/'lib/desktop_style';fixture.mkdir(parents=True)
            (fixture/'selector_input.c').touch()
            (fixture.parent/'raccon_menu').mkdir();(fixture.parent/'raccon_menu/navigation.h').touch()
            cli.__file__=str(fixture/'cli.py')
            revision=max((fixture/'selector_input.c').stat().st_mtime_ns,(fixture.parent/'raccon_menu/navigation.h').stat().st_mtime_ns)
            (runtime/'revision').write_text(str(revision));(runtime/'mapped').touch()
            os.mkfifo(runtime/'control');fd=os.open(runtime/'control',os.O_RDWR|os.O_NONBLOCK)
            try:
                self.assertTrue(cli.send(['open']))
                self.assertEqual(os.read(fd,1024),b'show\n')
                self.assertFalse(cli.send(['apply','retro']))
                (runtime/'revision').write_text('stale')
                self.assertFalse(cli.send(['toggle']))
            finally:os.close(fd)
