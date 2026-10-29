"""Stateful regressions for history, placement, scratchpads and modal focus."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_wf_tile import tile, view
sys.path.insert(0,str(Path(tile.__file__).resolve().parents[1]/'lib'))
from wf_tile.engine import Engine, FocusedIPC
from wf_tile import ui


class Desktop:
    def __init__(self):
        self.out = {'id':1,'name':'HEADLESS-1','geometry':dict(x=0,y=0,width=1200,height=800),
                    'workarea':dict(x=0,y=0,width=1200,height=760),'wset-index':1,
                    'workspace':dict(x=0,y=0,grid_width=3,grid_height=3)}
        self.outputs = [self.out]; self.focus=1; self.views={}; self.trees={}; self.calls=[]
        self.options={}; self.reject=False

    def add(self,vid,app=None):
        self.views[vid]=view(vid,**{'app-id':app or f'app-{vid}'})

    def key(self, data=None):
        data=data or {}; ws=data.get('workspace',self.out['workspace'])
        return data.get('wset-index',self.out['wset-index']),ws['x'],ws['y']

    def hydrate(self,tree,geometry=None,percent=1.):
        geometry=geometry or self.out['workarea']; node=copy.deepcopy(tree)
        node['geometry']=dict(geometry);node['percent']=percent;node.pop('weight',None)
        if 'view-id' in node:
            if node['view-id'] in self.views:
                self.views[node['view-id']]['geometry']=dict(geometry)
            return node
        key=next(k for k in ('vertical-split','horizontal-split') if k in node)
        kids=node[key]; total=sum(c.get('weight',c.get('percent',1)) for c in kids) or 1
        offset=0; axis,size=('x','width') if key=='vertical-split' else ('y','height')
        result=[]
        for i,child in enumerate(kids):
            share=child.get('weight',child.get('percent',1))/total
            length=geometry[size]-offset if i==len(kids)-1 else round(geometry[size]*share)
            g=dict(geometry);g[axis]+=offset;g[size]=length;offset+=length
            result.append(self.hydrate(child,g,share))
        node[key]=result;return node

    def call(self,method,data=None):
        self.calls.append((method,copy.deepcopy(data)));data=data or {}
        if method=='window-rules/get-focused-output':return {'info':copy.deepcopy(self.out)}
        if method=='window-rules/get-focused-view':return {'info':copy.deepcopy(self.views.get(self.focus))}
        if method=='window-rules/output-info':return copy.deepcopy(next(o for o in self.outputs if o['id']==data['id']))
        if method=='window-rules/list-outputs':return copy.deepcopy(self.outputs)
        if method=='window-rules/list-views':return copy.deepcopy(list(self.views.values()))
        if method=='window-rules/view-info':return {'info':copy.deepcopy(self.views.get(data['id']))}
        if method=='window-rules/focus-view':self.focus=data['id']
        if method=='simple-tile/get-layout':return {'layout':self.hydrate(self.trees.get(self.key(data),{'vertical-split':[]}))}
        if method=='simple-tile/set-layout':
            if self.reject:return {'error':'Geometry becomes too small'}
            ids=list(vid for vid,_ in tile.leaves(data['layout']))
            assert len(ids)==len(set(ids)),ids
            assert all(vid in self.views for vid in ids),ids
            self.trees[self.key(data)]=copy.deepcopy(data['layout'])
            all_ids={vid for tree in self.trees.values() for vid,_ in tile.leaves(tree)}
            for vid,v in self.views.items():v['tiled-edges']=15 if vid in all_ids else 0
            self.hydrate(data['layout'])
        if method=='window-rules/configure-view':
            target=self.views[data['id']]
            if 'geometry' in data:target['geometry']=copy.deepcopy(data['geometry'])
            if 'tiled-edges' in data:target['tiled-edges']=data['tiled-edges']
            if 'output_id' in data:target['output-id']=data['output_id']
        if method=='wm-actions/set-minimized':self.views[data['view_id']]['minimized']=data['state']
        if method=='wm-actions/set-always-on-top':self.views[data['view_id']]['always-on-top']=data['state']
        if method=='wsets/send-view-to-wset':self.views[data['view-id']]['wset-index']=data['wset-index']
        if method=='vswitch/send-view':
            g=self.views[data['view-id']]['geometry'];ws=self.out['workspace']
            g['x']+=(data['x']-ws['x'])*1200;g['y']+=(data['y']-ws['y'])*800
        if method=='wayfire/set-config-options':self.options.update(data)
        return {'result':'ok'}


class Features(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        env=patch.dict(os.environ,{'XDG_RUNTIME_DIR':str(self.base),'WF_TILE_STATE_DIR':str(self.base/'state'),
                                  'WF_TILE_NO_NOTIFY':'1'});env.start();self.addCleanup(env.stop)
        patcher=patch.object(tile,'FLOAT_STATE',str(self.base/'floating.json'));patcher.start();self.addCleanup(patcher.stop)
        config=self.base/'wayfire.ini';config.write_text('[simple-tile]\ninner_gap_size = 10\nouter_horiz_gap_size = 20\nouter_vert_gap_size = 20\n')
        patcher=patch.object(tile,'INI',str(config));patcher.start();self.addCleanup(patcher.stop)
        self.d=Desktop()
        for vid in (1,2,3):self.d.add(vid)
        self.d.call('simple-tile/set-layout',{'layout':tile.dwindle_layout([1,2,3])})
        self.e=Engine(tile,self.d)

    def tree(self):return tile.get_layout(self.d,self.d.out)[1]
    def ids(self):return set(dict(tile.leaves(self.tree())))

    def test_preselection_places_next_window_on_chosen_side_then_consumes_once(self):
        self.e.execute(['preselect','left'])
        preview=json.loads((self.base/'wf-tile/ui.json').read_text())['preview']
        self.assertEqual(preview['direction'],'left')
        self.d.add(4);self.d.call('simple-tile/set-layout',{'layout':tile.insert_dwindle(self.tree(),4,3)})
        self.e.adopt(4,[3,2,1])
        node=self.tree()['vertical-split'][0]['vertical-split']
        self.assertEqual([n['view-id'] for n in node],[4,1])
        self.assertIsNone(self.e.preselection);self.assertEqual(self.ids(),{1,2,3,4})

    def test_floating_utility_does_not_consume_preselection(self):
        self.e.preselect('down');self.d.add(4);self.d.views[4]['tiled-edges']=0
        self.e.adopt(4,[1]);self.assertIsNotNone(self.e.preselection)
        self.assertNotIn(4,self.ids())

    def test_preselection_cancels_when_workspace_changes(self):
        self.e.preselect('down');self.d.out['workspace']['x']=1
        self.e.publish_ui();self.assertIsNone(self.e.preselection)

    def test_move_creates_split_and_undo_redo_restore_topology(self):
        original=tile.strip_geometry(copy.deepcopy(self.tree()))
        self.d.focus=3;self.e.execute(['move','left'])
        moved=tile.strip_geometry(copy.deepcopy(self.tree()))
        self.assertNotEqual(original,moved);self.assertEqual(self.ids(),{1,2,3})
        self.e.execute(['undo']);self.assertEqual(tile.strip_geometry(self.tree()),original)
        self.e.execute(['redo']);self.assertEqual(tile.strip_geometry(self.tree()),moved)

    def test_undo_float_restores_tiling_and_redo_restores_geometry(self):
        self.e.execute(['toggle']);self.assertEqual(self.ids(),{2,3})
        geometry=copy.deepcopy(self.d.views[1]['geometry'])
        self.e.execute(['undo']);self.assertEqual(self.ids(),{1,2,3})
        self.e.execute(['redo']);self.assertEqual(self.ids(),{2,3})
        self.assertEqual(self.d.views[1]['geometry'],geometry)

    def test_undo_prunes_closed_windows_and_keeps_new_windows(self):
        self.e.execute(['ratio']);self.d.views.pop(2)
        self.d.trees[(1,0,0)]=tile.prune_tree(self.d.trees[(1,0,0)],{2})
        self.d.add(4);self.d.trees[(1,0,0)]=tile.insert_dwindle(self.d.trees[(1,0,0)],4)
        self.e.execute(['undo']);self.assertEqual(self.ids(),{1,3,4})

    def test_failed_layout_does_not_consume_history_or_mutate_tree(self):
        original=copy.deepcopy(self.tree());self.d.reject=True
        with self.assertRaises(RuntimeError):self.e.execute(['ratio'])
        self.assertEqual(self.tree(),original);self.assertEqual(self.e.history,{})
        self.d.reject=False;self.e.execute(['ratio']);self.d.reject=True
        with self.assertRaises(RuntimeError):self.e.execute(['undo'])
        self.assertEqual(len(self.e.history['1:0:0']['undo']),1)

    def test_modal_resize_keeps_target_when_layer_shell_owns_keyboard_focus(self):
        self.e.execute(['resize-mode']);self.d.focus=None
        self.e.execute(['key','right']);self.e.execute(['key','right'])
        self.assertAlmostEqual(self.tree()['vertical-split'][0]['percent'],.6)
        self.e.execute(['key','escape'])
        self.assertIsNone(self.e.modal);self.assertEqual(self.d.focus,1)
        self.assertEqual(len(self.e.history['1:0:0']['undo']),1)
        self.e.execute(['undo']);self.assertAlmostEqual(self.tree()['vertical-split'][0]['percent'],.5)

    def test_modal_preselect_and_move_share_protected_target(self):
        self.e.execute(['preselect-mode']);self.d.focus=None
        self.e.execute(['key','down']);self.assertIsNone(self.e.modal)
        self.assertEqual(self.e.preselection['anchor'],1)
        self.d.focus=3;self.e.execute(['move-mode']);self.d.focus=None
        self.e.execute(['key','left']);self.e.execute(['key','enter'])
        self.assertEqual(self.ids(),{1,2,3});self.assertIsNone(self.e.modal)

    def test_workspace_switch_exits_mode_without_pulling_focus_back(self):
        self.e.execute(['resize-mode']);self.e.execute(['key','right'])
        self.d.out['workspace']['x']=1;self.d.focus=3
        self.e.publish_ui()
        self.assertIsNone(self.e.modal);self.assertEqual(self.d.focus,3)
        self.assertEqual(len(self.e.history['1:0:0']['undo']),1)

    def test_favorite_matches_applications_after_window_ids_change(self):
        self.e.execute(['favorite','save'])
        saved=json.loads((self.base/'state/favorites.json').read_text())
        self.assertNotIn('view-id',json.dumps(saved))
        self.d.views={}
        for vid in (11,12,13):self.d.add(vid,f'app-{vid-10}')
        self.d.focus=11
        self.d.call('simple-tile/set-layout',{'layout':tile.dwindle_layout([13,12,11])})
        self.e.execute(['favorite','load'])
        self.assertEqual([vid for vid,_ in tile.leaves(self.tree())],[11,12,13])

    def test_scratchpad_hides_summons_on_current_workspace_and_releases(self):
        self.e.execute(['scratch','assign','1']);self.assertTrue(self.d.views[1]['minimized'])
        self.assertEqual(self.ids(),{2,3})
        self.d.out['workspace']['x']=1
        self.e.execute(['scratch','toggle','1'])
        self.assertFalse(self.d.views[1]['minimized']);self.assertTrue(self.d.views[1]['always-on-top'])
        self.assertEqual(self.d.views[1]['tiled-edges'],0)
        self.assertEqual(self.d.focus,1)
        self.e.execute(['scratch','toggle','1']);self.assertTrue(self.d.views[1]['minimized'])
        self.e.execute(['scratch','release','1']);self.assertFalse(self.d.views[1]['minimized'])
        self.assertFalse(self.d.views[1]['always-on-top']);self.assertEqual(self.ids(),{1})
        self.assertEqual(self.e.scratch,{})

    def test_scratchpad_never_overwrites_an_occupied_slot(self):
        self.e.execute(['scratch','assign','1']);self.d.focus=2
        self.e.execute(['scratch','assign','1']);self.assertEqual(self.e.scratch['1']['id'],1)
        self.assertFalse(self.d.views[2]['minimized'])

    def test_switching_workspace_mode_preserves_a_visible_scratchpad_as_floating(self):
        self.e.execute(['scratch','assign','1']);self.e.execute(['scratch','toggle','1'])
        self.d.focus=2;self.e.execute(['mode','float']);self.e.execute(['mode','tile'])
        self.assertEqual(self.ids(),{2,3});self.assertEqual(self.d.views[1]['tiled-edges'],0)

    def test_scratch_state_survives_service_restart_and_closed_window_is_removed(self):
        self.e.execute(['scratch','assign','2']);restarted=Engine(tile,self.d)
        self.assertEqual(restarted.scratch['2']['id'],1)
        self.d.views.pop(1);restarted.execute(['scratch','toggle','2']);self.assertEqual(restarted.scratch,{})

    def test_smart_gaps_restore_theme_values_and_follow_configuration_edits(self):
        self.e.update_gaps();self.assertEqual(self.d.options['simple-tile/inner_gap_size'],10)
        self.d.trees[(1,0,0)]=tile.dwindle_layout([1]);self.e.update_gaps()
        self.assertTrue(all(v==0 for v in self.d.options.values()))
        self.e.execute(['gaps','toggle']);self.assertEqual(self.d.options['simple-tile/outer_horiz_gap_size'],20)
        Path(tile.INI).write_text('[simple-tile]\ninner_gap_size = 6\nouter_horiz_gap_size = 14\nouter_vert_gap_size = 16\n')
        self.e.update_gaps();self.assertEqual(self.d.options['simple-tile/outer_horiz_gap_size'],14)

    def test_smart_gaps_keep_normal_spacing_if_another_monitor_has_multiple_tiles(self):
        other=copy.deepcopy(self.d.out);other.update(id=2,**{'wset-index':3})
        self.d.outputs.append(other)
        self.d.trees[(3,0,0)]=tile.dwindle_layout([2,3]);self.d.trees[(1,0,0)]=tile.dwindle_layout([1])
        self.e.update_gaps();self.assertEqual(self.d.options['simple-tile/inner_gap_size'],10)

    def test_hidden_workspace_set_windows_are_excluded(self):
        self.d.add(4);self.d.views[4]['wset-index']=2
        _,_,views=tile.current_views(self.d);self.assertNotIn(4,[v['id'] for v in views])

    def test_ratio_cycles_fifty_sixty_seventy_and_undo_is_workspace_local(self):
        shares=[]
        for _ in range(3):
            self.e.execute(['ratio']);shares.append(round(self.tree()['vertical-split'][0]['percent'],2))
        self.assertEqual(shares,[.6,.7,.5])
        self.d.out['workspace']['x']=1;self.e.execute(['undo'])
        self.assertEqual(self.ids(),set())

    def test_theme_reads_actual_desktop_tokens(self):
        config=self.base/'config';(config/'desktop-style/current').mkdir(parents=True)
        (config/'desktop-style/current/tokens.json').write_text(json.dumps({'radius':0,'font':'Inter','colors':{'primary':'#ffffff'}}))
        with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(config)}):
            tokens=ui.theme()
        self.assertEqual(tokens['radius'],0);self.assertEqual(tokens['colors']['primary'],'#ffffff')
        self.assertIn('on_surface',tokens['colors'])


if __name__=='__main__':unittest.main()
