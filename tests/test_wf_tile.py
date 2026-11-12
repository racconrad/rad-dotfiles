"""Dwindle tree edits, floating restoration and native IPC failure contracts."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'modules/wayfire/files/.local/bin/wf-tile'
loader=importlib.machinery.SourceFileLoader('wf_tile_under_test',str(SOURCE))
spec=importlib.util.spec_from_loader(loader.name,loader);tile=importlib.util.module_from_spec(spec);loader.exec_module(tile)


class FakeIPC:
    def __init__(self,layout,views,focus=1):
        self.layout=copy.deepcopy(layout);self.views=views;self.focus=focus;self.calls=[]
        self.out=dict(id=1,geometry=dict(x=0,y=0,width=1200,height=800),workarea=dict(x=0,y=0,width=1200,height=760),
                      **{'wset-index':1},workspace=dict(x=0,y=0,grid_width=3,grid_height=3))
    def call(self,method,data=None):
        self.calls.append((method,data))
        if method=='window-rules/get-focused-output':return dict(info=self.out)
        if method=='window-rules/get-focused-view':return dict(info=next(v for v in self.views if v['id']==self.focus))
        if method=='window-rules/list-views':return self.views
        if method=='window-rules/view-info':return dict(info=next((v for v in self.views if v['id']==data['id']),None))
        if method=='window-rules/output-info':return self.out
        if method=='simple-tile/get-layout':return dict(layout=copy.deepcopy(self.layout))
        if method=='simple-tile/set-layout':self.layout=data['layout'];return dict(result='ok')
        return dict(result='ok')


def view(vid=1,**extras):
    return dict(dict(id=vid,role='toplevel',mapped=True,minimized=False,fullscreen=False,
                     geometry=dict(x=10,y=20,width=500,height=400),**{'output-id':1,'wset-index':1,'tiled-edges':15}),**extras)


class DwindleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        config=self.base/'wayfire.ini'
        config.write_text('[simple-tile]\ntile_by_default = true\n')
        p=patch.object(tile,'INI',str(config));p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'XDG_RUNTIME_DIR':self.temp.name});p.start();self.addCleanup(p.stop)
        p=patch.object(tile,'FLOAT_STATE',str(self.base/'floating.json'));p.start();self.addCleanup(p.stop)

    def test_first_four_windows_alternate_columns_rows_columns(self):
        tree=tile.dwindle_layout([1,2,3,4])
        self.assertEqual([v for v,p in tile.leaves(tree)],[1,2,3,4])
        self.assertEqual(tree['vertical-split'][0]['view-id'],1)
        second=tree['vertical-split'][1]['horizontal-split']
        self.assertEqual(second[0]['view-id'],2)
        self.assertEqual([x['view-id'] for x in second[1]['vertical-split']],[3,4])

    def test_new_window_splits_focused_leaf_and_preserves_other_ratios(self):
        tree={'vertical-split':[{'view-id':1,'percent':.65},{'view-id':2,'percent':.35}]}
        original=copy.deepcopy(tree)
        result=tile.strip_geometry(tile.insert_dwindle(tree,3,1))
        self.assertEqual(tree,original)
        self.assertEqual(result['vertical-split'][0]['weight'],.65)
        self.assertEqual(result['vertical-split'][1],{'view-id':2,'weight':.35})
        self.assertEqual([x['view-id'] for x in result['vertical-split'][0]['horizontal-split']],[1,3])

    def test_pruning_collapses_empty_nodes_and_keeps_parent_share(self):
        tree={'vertical-split':[{'horizontal-split':[{'view-id':1,'percent':.5},{'view-id':2,'percent':.5}], 'percent':.7},
                                {'view-id':3,'percent':.3}]}
        result=tile.prune_tree(tree,{1})
        self.assertEqual(result['vertical-split'][0],{'view-id':2,'percent':.7})
        self.assertEqual(dict(tile.leaves(result)).keys(),{2,3})
        self.assertIsNone(tile.prune_tree(tree,{1,2,3}))

    def test_auto_adoption_targets_previous_focus_but_never_floating_exceptions(self):
        ipc=FakeIPC({'vertical-split':[{'view-id':i,'percent':1/3} for i in (1,2,3)]},[view(i) for i in (1,2,3)],3)
        tile.cmd_adopt(ipc,3,[1,2])
        self.assertEqual([x['view-id'] for x in ipc.layout['vertical-split'][0]['horizontal-split']],[1,3])
        ipc=FakeIPC({'view-id':1,'weight':1.0},[view(1),view(3,**{'tiled-edges':0})],3)
        tile.cmd_adopt(ipc,3,[1])
        self.assertFalse(any(method=='simple-tile/set-layout' for method,_ in ipc.calls))

    def test_new_window_on_floating_workspace_is_untiled(self):
        tile.save_floating({'1:0:0'})
        ipc=FakeIPC(tile.dwindle_layout([1,2]),[view(1),view(2)],2)
        tile.cmd_adopt(ipc,2,[1])
        self.assertEqual(list(dict(tile.leaves(ipc.layout))),[1])
        args=next(args for method,args in ipc.calls if method=='window-rules/configure-view')
        self.assertEqual(args['tiled-edges'],0)
        self.assertEqual(args['geometry']['width'],720)

    def test_toggle_restores_previously_resized_floating_geometry(self):
        floating=view(1,**{'tiled-edges':0});original=copy.deepcopy(floating['geometry'])
        ipc=FakeIPC({'view-id':2,'weight':1.0},[floating,view(2)])
        tile.cmd_toggle(ipc)
        self.assertEqual(set(dict(tile.leaves(ipc.layout))),{1,2})
        floating['tiled-edges']=15;floating['geometry']=dict(x=0,y=0,width=600,height=760)
        tile.cmd_toggle(ipc)
        args=next(args for method,args in reversed(ipc.calls) if method=='window-rules/configure-view')
        self.assertEqual(args['geometry'],original)
        self.assertEqual(args['tiled-edges'],0)

    def test_comfortable_float_is_centered_and_does_not_move_other_tiles(self):
        ipc=FakeIPC(tile.dwindle_layout([1,2,3]),[view(i) for i in (1,2,3)])
        tile.cmd_toggle(ipc)
        self.assertEqual(set(dict(tile.leaves(ipc.layout))),{2,3})
        args=next(args for method,args in ipc.calls if method=='window-rules/configure-view')
        self.assertEqual(args['geometry'],dict(x=240,y=133,width=720,height=494))

    def test_failed_native_layout_is_reported_instead_of_silent_success(self):
        ipc=FakeIPC({},[view()])
        ipc.call=lambda *args,**kwargs:dict(error='Geometry becomes too small')
        with self.assertRaisesRegex(RuntimeError,'too small'):
            tile.set_layout(ipc,{'wset-index':1}, {},{})

    def test_single_window_ipc_always_has_an_explicit_parent_container(self):
        # Wayfire's bare-root special case omits parent; later repair/detach
        # dereferences it. The recursive split case establishes that parent.
        ipc=FakeIPC({},[view()])
        original={'view-id':1,'weight':.4}
        tile.set_layout(ipc,ipc.out,{'x':0,'y':0},original)
        payload=next(data['layout'] for method,data in ipc.calls if method=='simple-tile/set-layout')
        self.assertNotIn('view-id',payload)
        self.assertEqual(payload,{'vertical-split':[{'view-id':1,'weight':1.0}]})
        self.assertEqual(original,{'view-id':1,'weight':.4})

    def test_toggle_to_one_remaining_tile_and_repair_keep_parent_container(self):
        ipc=FakeIPC(tile.dwindle_layout([1,2]),[view(1),view(2)])
        tile.cmd_toggle(ipc)
        tile.cmd_repair(ipc)
        writes=[data['layout'] for method,data in ipc.calls if method=='simple-tile/set-layout']
        self.assertEqual(len(writes),2)
        for payload in writes:
            self.assertNotIn('view-id',payload)
            self.assertEqual(list(dict(tile.leaves(payload))),[2])

    def test_retile_with_no_orphans_does_not_rebuild_or_refocus(self):
        ipc=FakeIPC(tile.dwindle_layout([1,2]),[view(1),view(2)])
        tile.cmd_retile(ipc)
        self.assertFalse(any(method in ('simple-tile/set-layout','window-rules/focus-view') for method,_ in ipc.calls))

    def test_retile_orphan_writes_only_recovered_workspace_once(self):
        ipc=FakeIPC({},[view(1)])
        tile.cmd_retile(ipc)
        writes=[data for method,data in ipc.calls if method=='simple-tile/set-layout']
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0]['workspace'],{'x':0,'y':0})
        self.assertEqual(writes[0]['layout'],{'vertical-split':[{'view-id':1,'weight':1.0}]})

    def test_retile_ignores_floating_windows_and_widget_surfaces(self):
        ipc=FakeIPC({},[view(1,**{'tiled-edges':0}),view(2,role='desktop-environment')])
        tile.cmd_retile(ipc)
        self.assertFalse(any(method=='simple-tile/set-layout' for method,_ in ipc.calls))

    def test_rapid_insertions_never_duplicate_or_lose_ids(self):
        tree=None
        for vid in range(1,26):
            tree=tile.insert_dwindle(tree,vid,(vid%5)+1)
            self.assertEqual(sorted(dict(tile.leaves(tree))),list(range(1,vid+1)))
        for vid in range(1,26,2):tree=tile.prune_tree(tree,{vid})
        self.assertEqual(sorted(dict(tile.leaves(tree))),list(range(2,26,2)))


if __name__=='__main__':unittest.main()
