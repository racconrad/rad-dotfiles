"""Sidebar lifecycle, interruption, fixed geometry and portable installation."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_install import installer
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'modules/kitty/files/.local/lib/raccon_terminal.py'
spec=importlib.util.spec_from_file_location('terminal',SOURCE);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
ORIGINAL_GEOMETRY=t.geometry
OPTIONS=dict(t.DEFAULTS,duration_in=120,duration_out=80,fps=60)
GEO=dict(width=600,height=900,top=80,shown_x=1306,hidden_x=1934,output='eDP-1')

class Backend:
 def __init__(self):self.live=False;self.shown=False;self.calls=[];self.wf_calls=[];self.starts=0;self.now=0;self.interrupt=None
 def remote(self,cmd,payload=None):
  self.calls.append((cmd,payload))
  if cmd=='ls':return '[{"tabs":[{}]}]' if self.live else '[]'
  if cmd=='close-window':self.live=False;self.shown=False;return
  if not self.live:raise OSError('closed')
  if cmd=='resize-os-window' and payload['action'] in ('show','hide'):self.shown=payload['action']=='show'
 def wf(self,method,payload=None):
  self.wf_calls.append((method,payload))
  if method=='window-rules/list-views':
   return [dict(id=17,**{'app-id':t.APP_ID},role='toplevel',mapped=True)] if self.live else []
  if method=='wm-actions/set-minimized':self.shown=not payload['state']
  if method=='window-rules/configure-view' and 'geometry' in payload:
   g=payload['geometry'];assert 0<g['width']<2**31 and 0<g['height']<2**31
  return {'result':'ok'}
 def start(self,geo):self.live=True;self.starts+=1
 def sleep(self,delay):
  self.now+=delay
  if self.interrupt:
   callback=self.interrupt;self.interrupt=None;callback()

class LifecycleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.b=Backend()
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
 def test_slide_moves_without_resizing_the_pty_and_settles_at_exact_edge(self):
  self.command('show')
  edits=[p['geometry'] for c,p in self.b.wf_calls if c=='window-rules/configure-view' and 'geometry' in p]
  self.assertGreater(len(edits),3)
  self.assertEqual(edits[-1]['x'],GEO['shown_x'])
  self.assertTrue(all(e['width']==GEO['width'] and e['height']==GEO['height'] and e['y']==GEO['top'] for e in edits))
  self.assertFalse(any(c=='resize-os-window' for c,p in self.b.calls))
 def test_rapid_toggle_interrupts_entrance(self):
  other=t.Panel(self.root,self.b.remote)
  self.b.interrupt=lambda:other.command('toggle',OPTIONS)
  self.command('show');self.assertFalse(self.b.shown);self.assertTrue(self.b.live)
  self.assertEqual(self.state()['target'],'hidden')
 def test_close_interrupts_entrance_and_only_closes_this_panel(self):
  other=t.Panel(self.root,self.b.remote)
  self.b.interrupt=lambda:other.command('close',OPTIONS)
  self.command('show');self.assertFalse(self.b.live)
  close=[p for c,p in self.b.calls if c=='close-window']
  self.assertEqual(close,[dict(match='all',ignore_no_match=True)])
 def test_hide_and_close_never_spawn_a_missing_terminal(self):
  self.command('hide');self.command('close');self.assertEqual(self.b.starts,0)
 def test_exit_then_toggle_starts_a_fresh_session(self):
  self.command('show');self.b.live=False
  self.command('toggle');self.assertTrue(self.b.shown);self.assertEqual(self.b.starts,2)
 def test_hiding_an_exited_session_clears_stale_visible_state(self):
  self.command('show');self.b.live=False
  self.command('hide');self.assertFalse(self.state()['visible']);self.assertEqual(self.state()['error'],'')
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
  self.assertEqual(g['top'],62);self.assertEqual(g['shown_x'],1366-14-640)
  self.assertEqual(g['hidden_x'],1380);self.assertEqual(g['height'],768-14-62)
 def test_launch_avoids_auto_hide_and_owns_no_exclusive_desktop_space(self):
  args=t.launch_args(GEO,self.root/'kitty.sock')
  self.assertEqual(args[0],'kitty')
  self.assertNotIn('panel',args)
  self.assertIn('initial_window_width='+str(GEO['width']),args)
  self.assertIn('initial_window_height='+str(GEO['height']),args)
  self.assertNotIn('--hide-on-focus-loss',args);self.assertNotIn('--single-instance',args)
  self.assertFalse(any(a.startswith(('--margin-','--edge','--start-as')) for a in args))


class IntegrationTests(unittest.TestCase):
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
                if terminal=='kitty':self.assertIn('python',installer.packages_for(modules))

    def test_menu_shortcut_launches_panel_after_closing_menu(self):
        spec=importlib.util.spec_from_file_location('quick_menu',ROOT/'modules/desktop/files/.local/lib/raccon_menu/backend.py')
        menu=importlib.util.module_from_spec(spec);spec.loader.exec_module(menu)
        with patch.object(menu,'close') as close,patch.object(menu.subprocess,'Popen') as spawn:
            menu.shortcut('quick-terminal')
        close.assert_called_once_with()
        self.assertEqual(spawn.call_args.args[0],[str(menu.BIN/'raccon-term')])



if __name__=='__main__':unittest.main()
