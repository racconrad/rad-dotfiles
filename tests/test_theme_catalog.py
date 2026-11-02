"""Merged selections and preview caching survive real state transitions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'modules/desktop-styles/files/.local/lib/desktop_style/main.py'
spec=importlib.util.spec_from_file_location('catalog_styles',SOURCE)
styles=importlib.util.module_from_spec(spec);spec.loader.exec_module(styles)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)
        for key,value in [('HOME',self.home),('STATE',self.home/'state'),('CONFIG',self.home/'config')]:
            p=patch.object(styles,key,value);p.start();self.addCleanup(p.stop)

    def test_merge_migrates_selection_and_keeps_custom_frame_choices(self):
        styles.save(styles.STATE/'selection.json',dict(style='windows',name='Windows',warnings=['Keep']))
        styles.save(styles.STATE/'widget-frame.json',dict(version=2,styles=dict(windows='retro',gnome='glass',ascii='none')))
        styles.migrate_theme_state()
        self.assertEqual(styles.read(styles.STATE/'selection.json'),dict(style='modern',name='Default',warnings=['Keep']))
        choices=styles.read(styles.STATE/'widget-frame.json')['styles']
        self.assertEqual(choices['modern'],'retro');self.assertEqual(choices['ascii'],'none')
        self.assertEqual(choices['gnome'],'glass')
        styles.migrate_theme_state()
        self.assertEqual(styles.read(styles.STATE/'widget-frame.json')['styles'],choices)

    def test_explicit_default_frame_wins_over_an_older_merged_theme(self):
        styles.save(styles.STATE/'selection.json',dict(style='gnome'))
        styles.save(styles.STATE/'widget-frame.json',dict(version=2,styles=dict(modern='ascii',gnome='retro')))
        styles.migrate_theme_state()
        self.assertEqual(styles.widget_frame('windows'),'ascii')

    def test_apply_and_background_preview_producers_share_one_cache(self):
        def render(key,source):
            image=styles.CONFIG/(key+'.png');swatches=styles.CONFIG/(key+'.svg')
            styles.write(image,'cached raster');styles.write(swatches,'cached swatches')
            return dict(id=key,**styles.PROFILES[key],preview=str(image),swatches=str(swatches))
        styles.save(styles.STATE/'ui.json',dict(selected='modern',current='original',busy=False))
        source={'primary':'#123456'}
        with patch.object(styles,'preview',side_effect=render) as rendered,patch.object(styles,'source_palette',return_value=source),\
             patch.object(styles,'update') as published:
            first=styles.preview_catalog(source)
            styles.refresh_previews()
            self.assertEqual(styles.preview_catalog(source),first)
            self.assertEqual(rendered.call_count,len(styles.PROFILES));published.assert_not_called()
            # A changed layout really does invalidate the same cache.
            styles.save(styles.CONFIG/'waybar.json',dict(position='top',layout='continuous'))
            styles.refresh_previews()
            self.assertEqual(rendered.call_count,2*len(styles.PROFILES))
            self.assertEqual(published.call_count,2)

    def test_small_raster_is_prepared_once_and_reused_on_next_open(self):
        colors,_=styles.palette('ascii',{})
        def convert(argv):styles.write(Path(argv[-1]),'cached PNG')
        with patch.object(styles,'run',side_effect=convert) as run:
            first=styles.preview('ascii',colors)
            self.assertEqual(styles.preview('ascii',colors),first)
            self.assertEqual(run.call_count,1)
        self.assertTrue(first['preview'].endswith('.png'))
        self.assertEqual(styles.initial_catalog()['ascii']['preview'],first['preview'])

    def test_state_updates_use_listener_without_starting_eww_clients(self):
        with patch.object(styles,'selector_send',side_effect=AssertionError('redundant resident IPC')),\
             patch.object(styles.subprocess,'run',side_effect=AssertionError('redundant Eww process')):
            styles.update(selected='night')
        self.assertEqual(styles.read(styles.STATE/'ui.json')['selected'],'ascii')

    def test_extra_panels_toggle_exclusively_and_keep_exit_content(self):
        styles.extra_action('bar')
        state=styles.read(styles.STATE/'ui.json')
        self.assertEqual(state['extra'],'bar');self.assertFalse(state.get('frames_loaded',False))
        styles.extra_action('frames')
        state=styles.read(styles.STATE/'ui.json')
        self.assertEqual(state['extra'],'frames');self.assertTrue(state['frames_loaded'])
        styles.extra_action('close')
        state=styles.read(styles.STATE/'ui.json')
        self.assertEqual(state['extra'],'');self.assertEqual(state['extra_page'],'frames')
        self.assertTrue(state['frames_loaded']) # Retain widgets through the closing slide.
        styles.extra_action('bar');styles.extra_action('bar')
        self.assertEqual(styles.read(styles.STATE/'ui.json')['extra'],'')

    def test_unknown_extra_panel_does_not_change_state(self):
        styles.extra_action('bar');before=(styles.STATE/'ui.json').read_bytes()
        with self.assertRaises(ValueError):styles.extra_action('invalid')
        self.assertEqual((styles.STATE/'ui.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
