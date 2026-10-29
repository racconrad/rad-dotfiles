"""Serialized tiling actions. The compositor remains the authority for live IDs."""
import copy
import json
import os
from pathlib import Path
import time

DIRECTIONS = ('left', 'right', 'up', 'down')
EMPTY = {'vertical-split': []}


def read_json(path, fallback):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return copy.deepcopy(fallback)


def session_dir(tile):
    path = tile.runtime_file('wf-tile')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def state_dir():
    return Path(os.environ.get('WF_TILE_STATE_DIR',
                str(Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'wf-tile')))


class FocusedIPC:
    """Layer-shell keyboard focus must not change the window being edited."""
    def __init__(self, ipc, view_id, out_id):
        self.ipc, self.view_id, self.out_id = ipc, view_id, out_id

    def call(self, method, data=None):
        if method == 'window-rules/get-focused-view':
            return self.ipc.call('window-rules/view-info', {'id': self.view_id})
        if method == 'window-rules/get-focused-output':
            out = self.ipc.call('window-rules/output-info', {'id': self.out_id})
            return out if 'info' in out else {'info': out}
        return self.ipc.call(method, data)


class Engine:
    def __init__(self, tile, ipc):
        self.t, self.ipc = tile, ipc
        self.runtime = session_dir(tile)
        self.state = state_dir()
        self.history = read_json(self.runtime/'history.json', {})
        self.scratch = read_json(self.runtime/'scratch.json', {})
        self.preferences = read_json(self.state/'preferences.json', {'smart_gaps': True})
        self.preselection = None
        self.modal = None
        self.hint = None
        self.last_ui = None
        self.applied_gaps = None
        self.gap_mtime = None
        self.base_gaps = None
        self.last_context = None
        self.gap_error = None
        self.refresh_gap_config()

    def checked(self, method, data):
        result = self.ipc.call(method, data)
        if isinstance(result, dict) and result.get('error'):
            raise RuntimeError(result['error'])
        return result

    def output(self):
        return self.ipc.call('window-rules/get-focused-output').get('info') or {}

    def context(self, out):
        ws = out['workspace']
        return self.t.ws_key(out['wset-index'], ws['x'], ws['y'])

    def tip(self, text, seconds=2):
        self.hint = {'text': text, 'expires': time.monotonic() + seconds}

    def effective_ipc(self):
        if self.modal:
            return FocusedIPC(self.ipc, self.modal['view'], self.modal['output'])
        return self.ipc

    def snapshot(self, ipc=None):
        ipc = ipc or self.ipc
        out, focus, views = self.t.current_views(ipc)
        ws, layout = self.t.get_layout(ipc, out)
        return {'key': self.context(out), 'tree': self.t.strip_geometry(copy.deepcopy(layout or EMPTY)),
                'focus': focus.get('id'), 'floating': self.context(out) in self.t.load_floating(),
                'views': {str(v['id']): {'geometry': copy.deepcopy(v['geometry']),
                          'tiled': v['id'] in dict(self.t.leaves(layout or {}))}
                          for v in views if not v.get('fullscreen') and not self.is_scratch(v['id'])}}

    def remember(self, before):
        history = self.history.setdefault(before['key'], {'undo': [], 'redo': []})
        if not history['undo'] or history['undo'][-1] != before:
            history['undo'].append(before)
        history['undo'] = history['undo'][-30:]
        history['redo'] = []
        self.t.atomic_json(self.runtime/'history.json', self.history)

    @staticmethod
    def changed(before, after):
        # Merely changing focus must never consume an undo step.
        return any(before[k] != after[k] for k in ('tree', 'views', 'floating'))

    def restore(self, saved):
        out, _, views = self.t.current_views(self.ipc)
        if saved['key'] != self.context(out):
            raise ValueError('This layout belongs to another workspace')
        ws, current = self.t.get_layout(self.ipc, out)
        available = {v['id']: v for v in views if not v.get('fullscreen') and not self.is_scratch(v['id'])}
        desired = self.t.prune_tree(saved['tree'], set(dict(self.t.leaves(saved['tree']))) - available.keys())
        # Windows opened after this snapshot keep their current tiled status.
        for vid, _ in self.t.leaves(current or {}):
            if str(vid) not in saved['views'] and vid in available:
                desired = self.t.insert_dwindle(desired, vid)
        self.t.set_layout(self.ipc, out, ws, self.t.strip_geometry(desired) if desired else copy.deepcopy(EMPTY))
        for key, item in saved['views'].items():
            vid = int(key)
            if vid in available and not item['tiled']:
                self.checked('window-rules/configure-view', {'id': vid, 'tiled-edges': 0,
                             'geometry': self.clamp_geometry(item['geometry'], out['workarea'])})
        modes = self.t.load_floating()
        (modes.add if saved['floating'] else modes.discard)(saved['key'])
        self.t.save_floating(modes)
        if saved.get('focus') in available:
            self.checked('window-rules/focus-view', {'id': saved['focus']})

    def undo(self, redo=False):
        current = self.snapshot()
        history = self.history.get(current['key'], {'undo': [], 'redo': []})
        source, target = ('redo', 'undo') if redo else ('undo', 'redo')
        if not history[source]:
            self.tip('Nothing to redo' if redo else 'Nothing to undo')
            return
        saved = history[source][-1]
        self.restore(saved)  # Keep the entry if native validation rejects it.
        history[source].pop()
        history[target].append(current)
        self.t.atomic_json(self.runtime/'history.json', self.history)
        self.tip('Layout restored')

    def move(self, direction, ipc=None):
        ipc = ipc or self.ipc
        out, focus, views = self.t.current_views(ipc)
        ws, layout = self.t.get_layout(ipc, out)
        if self.t.floating_target(ipc, out, focus, layout):
            self.t.float_move(ipc, out, focus, direction)
            return
        ids = dict(self.t.leaves(layout or {}))
        if focus.get('id') not in ids or focus.get('fullscreen'):
            return
        target = self.t.pick_neighbor(focus['geometry'], [(v['id'], v['geometry']) for v in views
                                      if v['id'] in ids and v['id'] != focus['id']], direction)
        if target is None:
            return
        tree = self.t.insert_dwindle(layout, focus['id'], target, direction)
        self.t.set_layout(ipc, out, ws, self.t.strip_geometry(tree))
        ipc.call('window-rules/focus-view', {'id': focus['id']})

    def ratio(self):
        out, focus, _ = self.t.current_views(self.ipc)
        ws, tree = self.t.get_layout(self.ipc, out)
        path = dict(self.t.leaves(tree or {})).get(focus.get('id'))
        if not path or focus.get('fullscreen'):
            return
        parent = self.t.node_at(tree, path[:-1]); key, index = path[-1]
        kids = parent[key]
        if len(kids) < 2:
            return
        current = kids[index].get('percent', 1/len(kids))
        wanted = next((r for r in (.5, .6, .7) if r > current + .025), .5)
        others = sum(c.get('percent', 1/len(kids)) for i, c in enumerate(kids) if i != index)
        for i, child in enumerate(kids):
            child['percent'] = wanted if i == index else child.get('percent', 1/len(kids)) * (1-wanted) / others
        self.t.set_layout(self.ipc, out, ws, self.t.strip_geometry(tree))
        self.tip(f'{round(wanted*100)} / {round((1-wanted)*100)}')

    def preselect(self, direction, ipc=None):
        if direction == 'cancel':
            self.preselection = None
            return
        out, focus, _ = self.t.current_views(ipc or self.ipc)
        ws, layout = self.t.get_layout(self.ipc, out)
        if focus.get('id') not in dict(self.t.leaves(layout or {})):
            self.tip('Select a tiled window first')
            return
        self.preselection = {'direction': direction, 'anchor': focus['id'], 'output': out['id'],
                             'key': self.context(out), 'expires': time.monotonic()+20}

    def adopt(self, vid, anchors):
        view = self.ipc.call('window-rules/view-info', {'id': vid}).get('info')
        if not view:
            return
        selection = self.preselection
        direction = None
        if selection:
            out = self.ipc.call('window-rules/output-info', {'id': view['output-id']})
            out = out.get('info', out)
            ws = self.t.workspace_for(out, view)
            key = self.t.ws_key(view['wset-index'], ws['x'], ws['y'])
            _, tree = self.t.get_layout(self.ipc, dict(out, workspace=dict(out['workspace'], **ws)))
            if (key == selection['key'] and out['id'] == selection['output'] and
                    vid in dict(self.t.leaves(tree or {})) and time.monotonic() < selection['expires']):
                direction = selection['direction']
                anchors = [selection['anchor'], *anchors]
        if self.is_scratch(vid):
            return
        self.t.cmd_adopt(self.ipc, vid, anchors, direction)
        if direction:
            self.preselection = None

    def begin_modal(self, mode):
        if self.modal:
            self.end_modal()
            return
        out, focus, _ = self.t.current_views(self.ipc)
        if not focus or focus.get('minimized') or focus.get('fullscreen') or focus.get('role') != 'toplevel':
            self.tip('Select a window first')
            return
        self.modal = {'mode': mode, 'view': focus['id'], 'output': out['id'], 'key': self.context(out),
                      'before': self.snapshot(), 'dirty': False, 'expires': time.monotonic()+60}

    def end_modal(self):
        if not self.modal:
            return
        modal = self.modal
        self.modal = None
        try:
            out = self.output()
            here = bool(out and out['id']==modal['output'] and self.context(out)==modal['key'])
            changed = (self.changed(modal['before'], self.snapshot(FocusedIPC(self.ipc, modal['view'], modal['output'])))
                       if here else modal['dirty'])
            if changed:
                self.remember(modal['before'])
            info = self.ipc.call('window-rules/view-info', {'id': modal['view']}).get('info')
            if here and info and not info.get('minimized'):
                self.checked('window-rules/focus-view', {'id': modal['view']})
        except (RuntimeError, KeyError, TypeError):
            pass  # The edited window/output may have been closed.

    def modal_key(self, key):
        if not self.modal:
            return
        if key in ('escape', 'enter'):
            self.end_modal()
            return
        if key not in DIRECTIONS:
            return
        ipc = self.effective_ipc()
        mode = self.modal['mode']
        if mode == 'preselect':
            self.preselect(key, ipc)
            self.end_modal()
        elif mode == 'resize':
            self.t.cmd_resize(ipc, key)
        elif mode == 'move':
            self.move(key, ipc)
        if self.modal:
            self.modal['dirty'] = self.changed(self.modal['before'], self.snapshot(ipc))
            self.modal['expires'] = time.monotonic()+60

    def favorite(self, operation):
        out, _, views = self.t.current_views(self.ipc)
        ws, tree = self.t.get_layout(self.ipc, out)
        key = self.context(out)
        path = self.state/'favorites.json'
        favorites = read_json(path, {})
        eligible = sorted((v for v in views if not v.get('fullscreen') and not self.is_scratch(v['id'])), key=lambda v:v['id'])
        indexed = {}
        for view in eligible:
            indexed.setdefault(view.get('app-id', ''), []).append(view['id'])
        def encode(node):
            if 'view-id' in node:
                vid = node['view-id']
                app = next((app for app, ids in indexed.items() if vid in ids), None)
                if app is None:
                    return None
                return {'app': app, 'ordinal': indexed[app].index(vid), 'weight': node.get('percent', node.get('weight', 1.0))}
            result = {k: copy.deepcopy(v) for k,v in node.items() if k in ('percent','weight')}
            for axis in ('vertical-split', 'horizontal-split'):
                if axis in node:
                    result[axis] = [n for child in node[axis] if (n := encode(child)) is not None]
            return result
        if operation == 'save':
            if not tree or not dict(self.t.leaves(tree)):
                self.tip('No tiled layout to save')
                return
            favorites[key] = encode(tree)
            self.t.atomic_json(path, favorites)
            self.tip('Workspace layout saved')
            return
        if key not in favorites:
            self.tip('Save a layout with Super+Ctrl+S first')
            return
        def decode(node):
            if 'app' in node:
                ids = indexed.get(node['app'], [])
                ordinal = node['ordinal']
                return {'view-id': ids[ordinal], 'weight': float(node.get('weight', 1))} if ordinal < len(ids) else None
            result = {}
            for axis in ('vertical-split', 'horizontal-split'):
                if axis in node:
                    result[axis] = [n for child in node[axis] if (n := decode(child)) is not None]
            result['weight'] = float(node.get('percent', node.get('weight', 1)))
            return result
        desired = self.t.prune_tree(decode(favorites[key]))
        if not desired:
            self.tip('Open the saved applications first')
            return
        for vid, _ in self.t.leaves(tree or {}):
            if vid not in dict(self.t.leaves(desired)):
                desired = self.t.insert_dwindle(desired, vid)
        self.t.set_layout(self.ipc, out, ws, self.t.strip_geometry(desired))
        self.tip('Workspace layout loaded')

    def is_scratch(self, vid):
        return any(item['id'] == vid for item in self.scratch.values())

    @staticmethod
    def clamp_geometry(geometry, area):
        g = dict(geometry)
        for axis, size in (('x', 'width'), ('y', 'height')):
            g[size] = max(1, min(int(g[size]), area[size]))
            g[axis] = max(area[axis], min(int(g[axis]), area[axis]+area[size]-g[size]))
        return g

    def save_scratch(self):
        self.t.atomic_json(self.runtime/'scratch.json', self.scratch)

    def detach(self, view):
        out = self.ipc.call('window-rules/output-info', {'id': view['output-id']})
        out = out.get('info', out)
        out['wset-index'] = view['wset-index']
        ws = self.t.workspace_for(out, view)
        tree = self.ipc.call('simple-tile/get-layout', {'wset-index': view['wset-index'], 'workspace': ws}).get('layout')
        if view['id'] in dict(self.t.leaves(tree or {})):
            rest = self.t.prune_tree(tree, {view['id']})
            self.t.set_layout(self.ipc, out, ws, self.t.strip_geometry(rest) if rest else copy.deepcopy(EMPTY))
        return out

    def scratch_action(self, operation, slot='1'):
        if not slot.isdigit() or not 1 <= int(slot) <= 9:
            raise ValueError('Scratchpad slot must be 1..9')
        if operation == 'assign':
            _, focus, _ = self.t.current_views(self.ipc)
            if not focus or focus.get('fullscreen') or focus.get('parent', -1) != -1 or self.is_scratch(focus['id']):
                self.tip('Select a normal application window')
                return
            if slot in self.scratch:
                self.tip(f'Slot {slot} is occupied; release it first')
                return
            out = self.detach(focus)
            geometry = (focus['geometry'] if not focus.get('tiled-edges') else self.t.float_geometry(out, focus, 0))
            self.checked('window-rules/configure-view', {'id': focus['id'], 'tiled-edges': 0, 'geometry': geometry})
            # Persist ownership before hiding, so a service restart can recover it.
            self.scratch[slot] = {'id': focus['id'], 'geometry': geometry, 'above': focus.get('always-on-top', False)}
            self.save_scratch()
            self.checked('wm-actions/set-minimized', {'view_id': focus['id'], 'state': True})
            self.tip(f'Scratchpad {slot} saved · Super+F{5+int(slot)}' if int(slot)<=3 else f'Scratchpad {slot} saved')
            return
        item = self.scratch.get(slot)
        if not item:
            self.tip(f'Slot {slot} is empty · Super+Shift+F{5+int(slot)} to assign' if int(slot)<=3 else f'Slot {slot} is empty')
            return
        view = self.ipc.call('window-rules/view-info', {'id': item['id']}).get('info')
        if not view or not view.get('mapped'):
            self.scratch.pop(slot, None); self.save_scratch()
            self.tip('Scratchpad window was closed')
            return
        out = self.output()
        here = (view.get('output-id') == out['id'] and view.get('wset-index') == out['wset-index']
                and self.t.workspace_for(out, view) == {k: out['workspace'][k] for k in ('x','y')})
        if operation == 'toggle' and not view.get('minimized') and here:
            item['geometry'] = view['geometry']; self.save_scratch()
            self.checked('wm-actions/set-minimized', {'view_id': view['id'], 'state': True})
            return
        self.detach(view)
        geometry = self.clamp_geometry(item['geometry'], out['workarea'])
        if view['output-id'] != out['id']:
            self.checked('window-rules/configure-view', {'id': view['id'], 'output_id': out['id'], 'geometry': geometry})
        if view['wset-index'] != out['wset-index']:
            self.checked('wsets/send-view-to-wset', {'view-id': view['id'], 'wset-index': out['wset-index']})
        self.checked('vswitch/send-view', {'view-id': view['id'], 'x': out['workspace']['x'], 'y': out['workspace']['y']})
        # Moving across outputs/wsets can auto-tile a previously floating window.
        fresh = self.ipc.call('window-rules/view-info', {'id': view['id']}).get('info')
        if fresh:
            self.detach(fresh)
        self.checked('window-rules/configure-view', {'id': view['id'], 'tiled-edges': 0, 'geometry': geometry})
        self.checked('wm-actions/set-minimized', {'view_id': view['id'], 'state': False})
        self.checked('wm-actions/set-always-on-top', {'view_id': view['id'], 'state': operation != 'release' or item['above']})
        self.checked('window-rules/focus-view', {'id': view['id']})
        if operation == 'release':
            self.scratch.pop(slot); self.save_scratch()
            if self.context(out) not in self.t.load_floating() and out['wset-index'] != 2:
                ws, tree = self.t.get_layout(self.ipc, out)
                self.t.set_layout(self.ipc, out, ws, self.t.strip_geometry(self.t.insert_dwindle(tree, view['id'])))
            self.tip(f'Scratchpad {slot} released')

    def refresh_gap_config(self):
        try:
            stamp = Path(self.t.INI).stat().st_mtime_ns
        except OSError:
            stamp = 0
        if stamp == self.gap_mtime:
            return
        self.gap_mtime = stamp
        defaults = {'inner_gap_size': 10, 'outer_horiz_gap_size': 20, 'outer_vert_gap_size': 20}
        gaps = {}
        for key, default in defaults.items():
            try:
                value = self.t.get_ini_option('simple-tile', key)
                gaps['simple-tile/'+key] = max(0, int(value)) if value is not None else default
            except (OSError, ValueError):
                gaps['simple-tile/'+key] = default
        self.base_gaps = gaps
        self.applied_gaps = None

    def update_gaps(self, restore=False):
        self.refresh_gap_config()
        wanted = dict(self.base_gaps)
        if not restore and self.preferences.get('smart_gaps', True):
            # Wayfire gap options are global. Keep normal gaps on all monitors
            # whenever any visible output has multiple tiles.
            multiple = False
            for out in self.ipc.call('window-rules/list-outputs'):
                _, tree = self.t.get_layout(self.ipc, out)
                if len(dict(self.t.leaves(tree or {}))) > 1:
                    multiple = True; break
            if not multiple:
                wanted = {key: 0 for key in wanted}
        if wanted != self.applied_gaps:
            self.checked('wayfire/set-config-options', wanted)
            self.applied_gaps = wanted
        self.gap_error = None

    def publish_ui(self):
        now = time.monotonic()
        out = self.output()
        if not out:
            return
        key = self.context(out)
        if self.modal and (self.modal['expires'] < now or self.modal['key'] != key or self.modal['output'] != out['id']):
            self.end_modal()
        selection = self.preselection
        if selection and (selection['expires'] < now or selection['key'] != key or selection['output'] != out['id']):
            self.preselection = selection = None
        if self.hint and self.hint['expires'] < now:
            self.hint = None
        ui = {'mode': self.modal['mode'] if self.modal else None, 'preview': None, 'hint': self.hint['text'] if self.hint else None,
              'output': out.get('name'), 'output_geometry': out['geometry']}
        if selection:
            view = self.ipc.call('window-rules/view-info', {'id': selection['anchor']}).get('info')
            if (not view or view.get('minimized') or view.get('fullscreen') or
                    view.get('output-id')!=out['id'] or view.get('wset-index')!=out['wset-index'] or
                    self.t.workspace_for(out,view)!={k:out['workspace'][k] for k in ('x','y')} or
                    not view.get('tiled-edges')):
                self.preselection = None
            else:
                g = dict(view['geometry']); d = selection['direction']
                if d in ('left','right'):
                    g['width'] //= 2
                    if d == 'right': g['x'] += g['width']
                else:
                    g['height'] //= 2
                    if d == 'down': g['y'] += g['height']
                ui['preview'] = dict(geometry=g, direction=d)
        if self.modal:
            view = self.ipc.call('window-rules/view-info', {'id': self.modal['view']}).get('info')
            if not view or view.get('minimized'):
                self.end_modal(); ui['mode'] = None
        if ui != self.last_ui:
            self.t.atomic_json(self.runtime/'ui.json', ui)
            self.last_ui = ui

    def execute(self, args):
        if not args:
            raise ValueError('Missing action')
        action, rest = args[0], args[1:]
        before = None
        if action in ('move','swap','resize','toggle','arrange','togglesplit','mode','ratio') or args == ['favorite','load']:
            if self.modal:
                self.end_modal()
            before = self.snapshot()
        if action in ('focus','swap','resize','move') and len(rest)==1 and rest[0] in DIRECTIONS:
            if action == 'move': self.move(rest[0])
            else: {'focus': self.t.cmd_focus, 'swap': self.t.cmd_swap, 'resize': self.t.cmd_resize}[action](self.ipc, rest[0])
        elif action in ('toggle','arrange','repair','retile','togglesplit') and not rest:
            getattr(self.t, 'cmd_'+action)(self.ipc)
        elif action == 'mode' and len(rest)==1 and rest[0] in ('tile','float','toggle'):
            self.t.cmd_mode(self.ipc, rest[0], skip_ids={item['id'] for item in self.scratch.values()})
        elif action == 'preselect' and len(rest)==1 and rest[0] in (*DIRECTIONS, 'cancel'):
            self.preselect(rest[0])
        elif action in ('resize-mode','move-mode','preselect-mode') and not rest:
            self.begin_modal(action.removesuffix('-mode'))
        elif action == 'key' and len(rest)==1:
            self.modal_key(rest[0])
        elif action == 'cancel' and not rest:
            self.end_modal(); self.preselection = None
        elif action in ('undo','redo') and not rest:
            self.end_modal(); self.undo(action=='redo')
        elif action == 'ratio' and not rest:
            self.ratio()
        elif action == 'favorite' and len(rest)==1 and rest[0] in ('save','load'):
            self.favorite(rest[0])
        elif action == 'scratch' and 1 <= len(rest) <= 2 and rest[0] in ('assign','toggle','release'):
            self.scratch_action(rest[0], rest[1] if len(rest)>1 else '1')
        elif args == ['gaps','toggle']:
            self.preferences['smart_gaps'] = not self.preferences.get('smart_gaps', True)
            self.t.atomic_json(self.state/'preferences.json', self.preferences)
            self.update_gaps(); self.tip('Smart gaps on' if self.preferences['smart_gaps'] else 'Theme gaps restored')
        elif action == 'adopt' and len(rest)==1 and rest[0].isdigit():
            self.adopt(int(rest[0]), [])
        elif args == ['status']:
            return {'pid': os.getpid(), 'version': 2, 'resident': True, 'smart_gaps': self.preferences.get('smart_gaps', True),
                    'gap_error': self.gap_error, 'mode': self.modal['mode'] if self.modal else None,
                    'preselection': self.preselection, 'scratchpads': self.scratch,
                    'workspace': self.context(self.output())}
        else:
            raise ValueError('Unknown action: '+' '.join(args))
        if before:
            after = self.snapshot()
            if self.changed(before, after):
                self.remember(before)
        self.publish_ui()
        return None
