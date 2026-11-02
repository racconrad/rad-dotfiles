"""Sidebar lifecycle, interruption, fixed geometry and portable installation."""
import importlib.util
import json
import os
import struct
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from test_install import installer
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'modules/kitty/files/.local/lib/raccon_terminal.py'
spec=importlib.util.spec_from_file_location('terminal',SOURCE);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
ORIGINAL_GEOMETRY=t.geometry
OPTIONS=dict(t.DEFAULTS,duration_in=120,duration_out=80,fps=60)
GEO=dict(width=600,height=900,top=80,shown_x=1306,output='eDP-1')

class Backend:
 def __init__(self):self.live=False;self.shown=False;self.calls=[];self.wf_calls=[];self.starts=0;self.now=0;self.interrupt=None;self.geo=dict(GEO,x=GEO["shown_x"],y=GEO["top"])
 def remote(self,cmd,payload=None):
  self.calls.append((cmd,payload))
  if cmd=='ls':return '[{"tabs":[{}]}]' if self.live else '[]'
  if cmd=='close-window':self.live=False;self.shown=False;return
  if not self.live:raise OSError('closed')
  if cmd=='resize-os-window' and payload['action'] in ('show','hide'):self.shown=payload['action']=='show'
 def wf(self,method,payload=None):
  self.wf_calls.append((method,payload))
  if method=='window-rules/list-views':
   return [dict(id=17,**{'app-id':t.APP_ID},role='toplevel',mapped=True,minimized=not self.shown,geometry=self.geo)] if self.live else []
  assert payload['view_id' if method.startswith('wm-actions') else 'view-id' if method.startswith('wf/alpha') else 'id']==17
  if method=='wm-actions/set-minimized':self.shown=not payload['state']
  if method=='window-rules/configure-view' and 'geometry' in payload:
   assert self.shown,'Never configure a minimized view'
   g=payload['geometry'];self.geo=dict(g);assert 0<g['width']<2**31 and 0<g['height']<2**31
   assert 0<=g['x'] and g['x']+g['width']<=1920,'Never move outside the output'
  if method=='window-rules/configure-view' and self.interrupt:
   callback=self.interrupt;self.interrupt=None;callback()
  return {'result':'ok'}
 def start(self,geo):self.live=True;self.starts+=1
 def sleep(self,delay):
  self.now+=delay
  if self.interrupt:
   callback=self.interrupt;self.interrupt=None;callback()

class LifecycleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.b=Backend()
  logs=patch.object(t,'LOG',self.root/'panel.log');logs.start();self.addCleanup(logs.stop)
  self.p=t.Panel(self.root,self.b.remote,lambda:self.b.now,self.b.sleep,compositor=self.b.wf)
  self.p.start=self.b.start
  ctx=patch.object(t,'geometry',return_value=GEO);ctx.start();self.addCleanup(ctx.stop)
 def command(self,name):self.p.command(name,OPTIONS)
 def state(self):return t.read(self.p.state)
 def test_show_hide_show_preserves_one_shell_and_close_creates_fresh_one(self):
  self.command('show');self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,1)
  self.command('hide');self.assertFalse(self.b.shown);self.assertTrue(self.b.live)
  self.command('show');self.assertEqual(self.b.starts,1)
  self.command('close');self.assertFalse(self.b.live);self.assertEqual(self.state()['target'],'closed')
  self.command('show');self.assertEqual(self.b.starts,2)
 def test_fade_keeps_geometry_fixed_without_hidden_mutations(self):
  self.command('show')
  edits=[p['geometry'] for c,p in self.b.wf_calls if c=='window-rules/configure-view' and 'geometry' in p]
  self.assertEqual(len(edits),1)
  self.assertEqual(edits[-1]['x'],GEO['shown_x'])
  self.assertTrue(all(e['width']==GEO['width'] and e['height']==GEO['height'] and e['y']==GEO['top'] for e in edits))
  self.assertFalse(any(c=='resize-os-window' for c,p in self.b.calls))
  alphas=[p['alpha'] for c,p in self.b.wf_calls if c=='wf/alpha/set-view-alpha']
  self.assertEqual(alphas[0],0.0)
  self.assertEqual(alphas[-1],1.0)
  self.assertGreater(len(set(alphas)),3)
  self.assertEqual(alphas,sorted(alphas))
  self.command('hide')
  self.assertEqual(self.b.wf_calls[-1],('wm-actions/set-minimized',{'view_id':17,'state':True}))
 def test_rapid_toggle_is_coalesced_during_entrance(self):
  other=t.Panel(self.root,self.b.remote)
  self.b.interrupt=lambda:other.command('toggle',OPTIONS)
  self.command('show');self.assertTrue(self.b.shown);self.assertTrue(self.b.live)
  self.assertEqual(self.state()['target'],'visible')
 def test_key_repeat_after_completion_is_throttled_then_next_press_works(self):
  self.command('toggle');seq=t.read(self.p.intent)['seq']
  self.command('toggle');self.assertTrue(self.b.shown)
  self.assertEqual(t.read(self.p.intent)['seq'],seq)
  self.b.now+=t.TOGGLE_INTERVAL
  self.command('toggle');self.assertFalse(self.b.shown)
 def test_stale_focus_loss_cannot_hide_new_reveal(self):
  self.command('show');seq=t.read(self.p.intent)['seq']
  self.command('hide');self.command('show')
  before=list(self.b.wf_calls)
  self.p.command('hide',OPTIONS,expected_seq=seq)
  self.assertTrue(self.b.shown);self.assertEqual(before,self.b.wf_calls)
 def test_repeated_reveals_have_one_placement_and_no_layer_changes(self):
  for _ in range(40):self.command('show');self.command('hide')
  self.assertEqual(self.b.starts,1)
  edits=[p for c,p in self.b.wf_calls if c=='window-rules/configure-view' and 'geometry' in p]
  self.assertEqual(len(edits),40)
  self.assertEqual(len({json.dumps(p['geometry'],sort_keys=True) for p in edits}),1)
  self.assertFalse(any(c=='wm-actions/set-always-on-top' for c,p in self.b.wf_calls))
 def test_hide_interrupts_fade_without_moving_window(self):
  self.command('show');self.command('hide')
  other=t.Panel(self.root,self.b.remote)
  self.b.interrupt=lambda:other.command('hide',OPTIONS)
  self.command('show')
  self.assertFalse(self.b.shown);self.assertTrue(self.b.live)
  self.assertEqual(self.state()['target'],'hidden')
 def test_damaged_state_and_intent_recover_without_duplicate_shell(self):
  self.command('show')
  t.store(self.p.state,dict(visible=True,progress='broken',geometry=GEO))
  t.store(self.p.intent,dict(seq='broken',last_toggle='NaN'))
  self.command('hide');self.command('show')
  self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,1)
  self.assertEqual(self.state()['error'],'')
 def test_close_during_placement_does_not_wait_or_reveal(self):
  other=t.Panel(self.root,self.b.remote)
  self.b.interrupt=lambda:other.command('close',OPTIONS)
  self.command('show')
  self.assertFalse(self.b.live)
  self.assertLess(self.b.now,.03)
  self.assertFalse(any(c=='wf/alpha/set-view-alpha' and p['alpha']>0 for c,p in self.b.wf_calls))
 def test_zero_duration_finishes_with_correct_opacity(self):
  options=dict(OPTIONS,duration_in=0,duration_out=0)
  self.p.command('show',options);self.assertTrue(self.b.shown)
  self.p.command('hide',options);self.assertFalse(self.b.shown)
  self.assertEqual(self.state()['progress'],0)
 def test_native_minimize_then_toggle_reopens_instead_of_hiding_again(self):
  self.command('show');self.b.shown=False
  self.command('toggle');self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,1)
 def test_concurrent_shortcut_burst_owns_one_worker_and_one_shell(self):
  gate=threading.Barrier(32)
  def press(_):
   panel=t.Panel(self.root,self.b.remote,compositor=self.b.wf)
   panel.start=self.b.start
   gate.wait(timeout=5)
   panel.command('toggle',OPTIONS)
  with ThreadPoolExecutor(max_workers=32) as pool:list(pool.map(press,range(32)))
  self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,1)
  self.assertEqual(t.read(self.p.intent)['seq'],1)
  self.assertEqual(len([1 for c,p in self.b.wf_calls if c=='window-rules/configure-view' and 'sticky' in p]),1)
 def test_close_interrupts_entrance_and_only_closes_this_panel(self):
  other=t.Panel(self.root,self.b.remote)
  self.b.interrupt=lambda:other.command('close',OPTIONS)
  self.command('show');self.assertFalse(self.b.live)
  close=[p for c,p in self.b.calls if c=='close-window']
  self.assertEqual(close,[dict(match='all',ignore_no_match=True)])
  self.assertFalse(any(c=='wm-actions/set-minimized' and p['state'] for c,p in self.b.wf_calls))
 def test_hide_and_close_never_spawn_a_missing_terminal(self):
  self.command('hide');self.command('close');self.assertEqual(self.b.starts,0)
 def test_exit_then_toggle_starts_a_fresh_session(self):
  self.command('show');self.b.live=False
  self.command('toggle');self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,2)
 def test_hiding_an_exited_session_clears_stale_visible_state(self):
  self.command('show');self.b.live=False
  self.command('hide');self.assertFalse(self.state()['visible']);self.assertEqual(self.state()['error'],'')
 def test_first_launch_waits_for_its_own_socket_instead_of_duplicate_error(self):
  child=unittest.mock.Mock();child.poll.return_value=None
  remote=unittest.mock.Mock(side_effect=[OSError('not ready'),'[{"tabs":[{}]}]'])
  self.p.remote=remote
  with patch.object(t.subprocess,'Popen',return_value=child),patch.object(self.p,'bind_view',return_value={'id':17}),patch.object(self.p,'alive',side_effect=AssertionError('duplicate guard used during owned startup')):
   t.Panel.start(self.p,GEO)
  self.assertEqual(remote.call_count,2);child.terminate.assert_not_called()
 def test_busy_socket_never_launches_over_existing_panel(self):
  self.command('show')
  self.p.remote=lambda *args:(_ for _ in ()).throw(OSError('timeout'))
  with self.assertRaisesRegex(RuntimeError,'still running'):self.command('show')
  self.assertEqual(self.b.starts,1)
 def test_panel_never_uses_above_or_sticky(self):
  self.command('show');self.command('hide')
  self.assertFalse(any(c=='wm-actions/set-always-on-top' and p['state'] for c,p in self.b.wf_calls))
  self.assertFalse(any(c=='window-rules/configure-view' and p.get('sticky') for c,p in self.b.wf_calls))
 def test_explicit_show_is_idempotent(self):
  self.command('show');self.command('show');self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,1)
 def test_start_failure_is_reported_in_state(self):
  self.p.start=lambda geo:(_ for _ in ()).throw(RuntimeError('startup failed'))
  with self.assertRaisesRegex(RuntimeError,'startup failed'):self.command('show')
  self.assertEqual(self.state()['error'],'startup failed')
 def test_geometry_uses_output_local_coordinates_and_bar_insets(self):
  out={'name':'test','geometry':dict(x=1920,y=0,width=1366,height=768)}
  views=[{'app-id':'waybar','mapped':True,'output-name':'test','geometry':dict(x=0,y=0,width=1366,height=48)}]
  g=ORIGINAL_GEOMETRY(OPTIONS,out,views)
  self.assertEqual(g['top'],148);self.assertEqual(g['shown_x'],1366-14-520)
  self.assertNotIn('hidden_x',g);self.assertEqual(g['height'],520)
 def test_launch_avoids_auto_hide_and_owns_no_exclusive_desktop_space(self):
  args=t.launch_args(GEO,self.root/'kitty.sock')
  self.assertEqual(args[0],'kitty')
  self.assertNotIn('panel',args)
  self.assertIn('initial_window_width='+str(GEO['width']),args)
  self.assertIn('initial_window_height='+str(GEO['height']),args)
  self.assertNotIn('--hide-on-focus-loss',args);self.assertNotIn('--single-instance',args)
  self.assertFalse(any(a.startswith(('--margin-','--edge','--start-as')) for a in args))


class IntegrationTests(unittest.TestCase):
    def test_corrupt_json_shapes_use_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'config.json'
            for value in ('null','[]','42','"text"','{broken'):
                path.write_text(value)
                self.assertEqual(t.read(path),{})
                with patch.object(t,'CONFIG',path):
                    self.assertEqual(t.settings()['width'],t.DEFAULTS['width'])
    def test_failed_ipc_is_discarded_without_replaying_mutation(self):
        client=t.Wayfire();stream=unittest.mock.Mock();client.sock=stream
        stream.recv.side_effect=TimeoutError('late reply')
        with self.assertRaises(TimeoutError):client('wm-actions/set-minimized',{'view_id':17,'state':True})
        stream.sendall.assert_called_once();stream.close.assert_called_once()
        self.assertIsNone(client.sock)
    def test_failed_notification_does_not_mask_controller_failure(self):
        with patch.object(t,'Panel') as panel,patch.object(t.shutil,'which',return_value='/bin/notify-send'),patch.object(t.subprocess,'run',side_effect=t.subprocess.TimeoutExpired('notify-send',2)):
            panel.return_value.command.side_effect=OSError('unavailable')
            self.assertEqual(t.main(['show']),1)
    def test_wayfire_reuses_framed_connection_with_partial_reads(self):
        class Stream:
            def __init__(self):self.data=b'';self.sent=[];self.connections=0;self.closed=False
            def settimeout(self,seconds):pass
            def connect(self,path):self.connections+=1
            def sendall(self,packet):
                size=struct.unpack('<I',packet[:4])[0]
                message=json.loads(packet[4:]);self.sent.append(message)
                self.assert_size=size==len(packet[4:])
                body=json.dumps({'result':message['method']}).encode()
                self.data+=struct.pack('<I',len(body))+body
            def recv(self,n):
                chunk=self.data[:min(n,2)];self.data=self.data[len(chunk):];return chunk
            def close(self):self.closed=True
        stream=Stream()
        with patch.object(t.socket,'socket',return_value=stream),patch.dict(os.environ,{'WAYFIRE_SOCKET':'/mock/wayfire.socket'}):
            client=t.Wayfire()
            self.assertEqual(client('first')['result'],'first')
            self.assertEqual(client('second',{'id':17})['result'],'second')
            client.close()
        self.assertEqual(stream.connections,1);self.assertTrue(stream.closed)
        self.assertTrue(stream.assert_size);self.assertEqual(len(stream.sent),2)

    def test_native_header_is_scoped_to_the_sidebar(self):
        import configparser
        config=configparser.ConfigParser(interpolation=None)
        config.read(ROOT/'modules/wayfire/files/.config/wayfire.ini')
        self.assertNotIn('decoration',config['core']['plugins'].split())
        self.assertIn('quick_terminal_initial_alpha',config['window-rules'])

    def test_indicator_reads_liveness_and_native_minimize_and_empties_dead_controls(self):
        panel=unittest.mock.Mock()
        panel.state=Path('/nonexistent/raccon-term-state.json')
        panel.alive.return_value=True;panel.bind_view.return_value={'minimized':True}
        with patch.object(t,'Panel',return_value=panel):
            self.assertEqual(t.indicator()['class'],'hidden')
            self.assertTrue(t.indicator('close')['text'])
            panel.bind_view.return_value={'minimized':False}
            self.assertEqual(t.indicator()['class'],'visible')
            panel.alive.return_value=False
            self.assertEqual(t.indicator()['class'],'closed')
            self.assertEqual(t.indicator('hide')['text'],'')
            self.assertEqual(t.indicator('close')['text'],'')
    def test_installer_keeps_quick_panel_binding_with_kitty_only(self):
        with tempfile.TemporaryDirectory(prefix='quick terminal ') as tmp:
            home=Path(tmp)/'home with spaces'
            for terminal in ('kitty','alacritty'):
                choices={k:v['default'] for k,v in installer.CATALOG['choices'].items()}
                choices['terminal']=terminal
                modules=installer.resolve_modules(['wayfire','terminal'],choices)
                plan=installer.file_plan(home,modules,choices)
                config=plan['.config/wayfire.ini'][0].decode()
                self.assertIn('command_terminal = '+terminal,config)
                self.assertEqual('binding_quick_terminal = <super> KEY_F12' in config,terminal=='kitty')
                self.assertEqual('.local/bin/raccon-term' in plan,terminal=='kitty')
                self.assertEqual('.local/lib/raccon_terminal.py' in plan,terminal=='kitty')
                self.assertEqual('binding_quick_terminal_close = <super> <shift> KEY_F12' in config,terminal=='kitty')
                self.assertEqual('quick_terminal_initial_alpha =' in config,terminal=='kitty')
                if terminal=='kitty':self.assertIn('!(app_id is "raccon-quick-terminal" | ',config)
                self.assertEqual('.config/kitty/raccon-panel.conf' in plan,terminal=='kitty')
                bar=json.loads(installer.render('.config/waybar/config.jsonc',
                    (ROOT/'modules/waybar/files/.config/waybar/config.jsonc').read_bytes(),home,modules,choices))
                self.assertEqual('group/quick-terminal' in bar['modules-right'],terminal=='kitty')
                if terminal=='kitty':self.assertIn('python',installer.packages_for(modules))

    def test_menu_shortcut_launches_panel_after_closing_menu(self):
        spec=importlib.util.spec_from_file_location('quick_menu',ROOT/'modules/desktop/files/.local/lib/raccon_menu/backend.py')
        menu=importlib.util.module_from_spec(spec);spec.loader.exec_module(menu)
        with patch.object(menu,'close') as close,patch.object(menu.subprocess,'Popen') as spawn:
            menu.shortcut('quick-terminal')
        close.assert_called_once_with()
        self.assertEqual(spawn.call_args.args[0],[str(menu.BIN/'raccon-term')])



if __name__=='__main__':unittest.main()
