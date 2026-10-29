"""Catalogue paging and bounded, atomic thumbnail generation (no desktop needed)."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'modules/desktop/files/.local/lib/raccon_menu'
spec = importlib.util.spec_from_file_location('walls', LIB/'walls.py')
walls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(walls)

class GalleryTests(unittest.TestCase):
    def test_only_visible_page_is_decoded_with_absolute_selection_indices(self):
        files = [Path(f'/wall/{i:03}.png') for i in range(29)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls, 'THUMBS', Path(tmp)), patch.object(walls, 'catalogue', return_value={'images':files,'videos':[]}), patch.object(walls, 'thumb', side_effect=lambda p: str(p)) as thumb:
            out = io.StringIO()
            with contextlib.redirect_stdout(out): walls.main(['page', 'images', '1'])
            page = json.loads(out.getvalue())
            self.assertEqual(thumb.call_count, 12)
            self.assertEqual([t['index'] for r in page['rows'] for t in r['tiles']], list(range(12,24)))
            self.assertEqual(page['pages'],3)

    def test_mixed_gallery_default_and_video_filter_select_same_file(self):
        image=Path('/wall/a.png');video=Path('/wall/b.mp4')
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls,'THUMBS',Path(tmp)), patch.object(walls,'catalogue',side_effect=lambda: {'images':[image],'videos':[video]}), patch.object(walls,'thumb',side_effect=str):
            out=io.StringIO()
            with contextlib.redirect_stdout(out):walls.main([])
            data=json.loads(out.getvalue())
            self.assertEqual(data['section'],'all')
            self.assertEqual(data['counts'],{'images':1,'videos':1,'all':2})
            self.assertEqual([t['name'] for r in data['rows'] for t in r['tiles']],['a','b'])
            for section,index in (('all','1'),('videos','0')):
                with patch.object(walls.os,'execv',side_effect=RuntimeError('exec intercepted')) as execute:
                    with self.assertRaisesRegex(RuntimeError,'exec intercepted'):
                        walls.main(['set',section,index])
                    self.assertEqual(execute.call_args.args[1][-1],str(video))

    def test_close_unmaps_before_resetting_gallery_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);log=root/'calls';fake=root/'eww'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$EWW_TEST_LOG"\ncase "$*" in *active-windows) echo "wallpaper: wallpaper";; esac\n')
            fake.chmod(0o755)
            helper=root/'python3';helper.write_text('#!/bin/sh\nexit 0\n');helper.chmod(0o755)
            subprocess.run(['bash',str(ROOT/'modules/desktop/files/.local/bin/raccon-float'),'close'],
                env={**os.environ,'PATH':str(root)+':'+os.environ['PATH'],'EWW_TEST_LOG':str(log),'XDG_RUNTIME_DIR':str(root),'XDG_CACHE_HOME':str(root)},check=True)
            calls=log.read_text().splitlines()
            fade=next(i for i,c in enumerate(calls) if 'update shown=false' in c)
            close=next(i for i,c in enumerate(calls) if 'close wallpaper' in c)
            reset=next(i for i,c in enumerate(calls) if 'update body=false' in c)
            self.assertLess(fade,close)
            self.assertLess(close,reset)

    def test_scroll_contains_all_items_and_video_markers(self):
        images=[Path(f'/wall/{i:03}.png') for i in range(25)]
        video=Path('/wall/026.mp4')
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls,'THUMBS',Path(tmp)), patch.object(walls,'catalogue',return_value={'images':images,'videos':[video]}), patch.object(walls,'thumb',side_effect=str):
            out=io.StringIO()
            with contextlib.redirect_stdout(out):walls.main(['list','all'])
            tiles=[t for row in json.loads(out.getvalue())['rows'] for t in row['tiles']]
            self.assertEqual(len(tiles),26)
            self.assertEqual([t['index'] for t in tiles],list(range(26)))
            self.assertFalse(tiles[0]['video'])
            self.assertTrue(tiles[-1]['video'])

    def test_preview_never_applies_wallpaper(self):
        import types
        from unittest.mock import Mock
        preview=Mock()
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls,'THUMBS',Path(tmp)), patch.object(walls,'catalogue',return_value={'images':[],'videos':[Path('/wall/clip.mp4')]}), patch.dict('sys.modules',{'wall_preview':types.SimpleNamespace(preview=preview)}), patch.object(walls.os,'execv') as apply:
            walls.main(['preview','all','0'])
            preview.assert_called_once_with(Path('/wall/clip.mp4'), selection='all:0', hover=False)
            apply.assert_not_called()

    def test_empty_and_out_of_range_page(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls,'THUMBS',Path(tmp)), patch.object(walls,'catalogue',return_value={'images':[],'videos':[]}):
            out=io.StringIO()
            with contextlib.redirect_stdout(out):walls.main(['page','videos','99'])
            page=json.loads(out.getvalue())
            self.assertEqual((page['page'],page['pages'],page['rows']),(0,1,[]))

    def test_thumbnail_published_atomically_then_reused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls,'THUMBS',Path(tmp)):
            src=Path(tmp)/'source.png';src.write_bytes(b'source')
            def decode(argv, **kwargs):
                self.assertEqual(kwargs['timeout'],8)
                self.assertEqual(argv[argv.index('-threads')+1],'1')
                Path(argv[-1]).write_bytes(b'complete thumbnail')
                return type('Result',(),{'returncode':0})()
            with patch.object(walls.subprocess,'run',side_effect=decode) as run:
                first=walls.thumb(src);self.assertTrue(Path(first).exists())
                self.assertEqual(walls.thumb(src),first)
                self.assertEqual(run.call_count,1)

    def test_failed_decoder_does_not_publish_partial_thumbnail(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(walls,'THUMBS',Path(tmp)):
            src=Path(tmp)/'broken.mp4';src.touch()
            with patch.object(walls.subprocess,'run',side_effect=walls.subprocess.TimeoutExpired('ffmpeg',8)) as run:
                self.assertEqual(walls.thumb(src),'')
                self.assertEqual(run.call_count,2)
            self.assertEqual(list(Path(tmp).glob('*.png')),[])

class InlinePreviewTests(unittest.TestCase):
    def test_decode_cache_and_stop(self):
        module_spec=importlib.util.spec_from_file_location('inline_preview',LIB/'wall_preview.py')
        preview=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(preview)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'clip.mp4';source.touch()
            preview.ROOT=root/'cache';preview.STATE=preview.ROOT/'state.json'
            def decode(argv,**kwargs):
                Path(argv[-1].replace('%03d','001')).write_bytes(b'frame')
            with patch.object(preview.subprocess,'run',side_effect=decode) as run:
                preview.preview(source)
                self.assertTrue(preview.read_state()['frames'])
                preview.preview(source)
                self.assertEqual(run.call_count,1)
            preview.preview()
            self.assertFalse(preview.read_state()['active'])
            self.assertNotIn('frames',preview.read_state())

    def test_leaving_old_tile_does_not_stop_new_tile(self):
        module_spec=importlib.util.spec_from_file_location('inline_preview',LIB/'wall_preview.py')
        preview=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(preview)
        with tempfile.TemporaryDirectory() as tmp:
            preview.ROOT=Path(tmp);preview.STATE=preview.ROOT/'state.json'
            preview.write_state({'active':True,'selection':'all:2','frames':['frame.jpg']})
            preview.preview(selection='all:1')
            self.assertTrue(preview.read_state()['active'])
            preview.preview(selection='all:2')
            self.assertFalse(preview.read_state()['active'])

    def test_eww_presentation_is_constant_across_frames(self):
        module_spec=importlib.util.spec_from_file_location('inline_preview',LIB/'wall_preview.py')
        preview=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(preview)
        state={'active':True,'selection':'all:2','frames':['/cache/clip/001.jpg','/cache/clip/002.jpg']}
        data=preview.presentation(state)
        self.assertEqual(data['playback'],'all:2\n/cache/clip')
        self.assertNotIn('frame',data)
        self.assertEqual(data,preview.presentation(state))
        self.assertEqual(preview.presentation({'active':False})['clip'],'')

    def test_decode_failure_visible_inside_card(self):
        module_spec=importlib.util.spec_from_file_location('inline_preview',LIB/'wall_preview.py')
        preview=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(preview)
        with tempfile.TemporaryDirectory() as tmp:
            preview.ROOT=Path(tmp);preview.STATE=preview.ROOT/'state.json'
            preview.preview(Path(tmp)/'missing.mp4')
            state=preview.read_state()
            self.assertTrue(state['active'])
            self.assertIn('Could not',state['message'])
            self.assertNotIn('frames',state)

if __name__=='__main__':unittest.main()
