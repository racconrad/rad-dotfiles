"""Unified results and opt-in recent apps stay local and preserve Home."""
import json
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_raccon_menu import menu
from test_home_apps import app


class SearchRecentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / 'state'
        self.state.mkdir()
        self.apps = [app('Alpha'), app('Beta')]
        (self.state / 'apps.json').write_text(json.dumps(self.apps))
        change = patch.object(menu, 'STATE', self.state)
        change.start()
        self.addCleanup(change.stop)

    def test_search_catalogue_keeps_app_pins_and_adds_categorized_safe_targets(self):
        value = menu.catalogue(self.apps)
        self.assertEqual([row['id'] for row in value['apps']], ['Alpha.desktop', 'Beta.desktop'])
        rows = value['search']
        self.assertEqual(rows[0]['category'], 'Application')
        self.assertEqual((rows[0]['action'], rows[0]['value']), ('launch', self.apps[0]['token']))
        audio = next(row for row in rows if row['name'] == 'Audio settings')
        self.assertEqual((audio['action'], audio['value'], audio['category']), ('search-action', 'audio', 'Setting'))
        self.assertIn('sonido', audio['search'])
        self.assertFalse(audio['pinnable'])
        self.assertTrue(all(row['category'] in ('Application', 'Setting', 'Action') for row in rows))

    def test_search_actions_use_existing_allowlists_and_reject_input(self):
        with patch.object(menu, 'native_send', return_value=True) as send, patch.object(menu, 'shortcut') as shortcut:
            menu.main(['search-action', 'audio'])
            send.assert_called_once_with('tab 4', str(menu.RUNTIME))
            menu.main(['search-action', 'lock'])
            shortcut.assert_called_once_with('lock')
            for value in ('; touch nope', 'poweroff', 'launch', '$(id)'):
                with self.assertRaises(ValueError):
                    menu.main(['search-action', value])

    def test_cli_query_and_first_match_use_the_same_safe_unified_results(self):
        with patch.object(menu, 'update') as update:
            menu.main(['query', 'sonido'])
        rows = update.call_args.kwargs['apps']
        self.assertEqual([(row['action'], row['value']) for row in rows], [('search-action', 'audio')])
        with patch.object(menu, 'native_send', return_value=True) as send:
            menu.main(['launch-first', 'sonido'])
        send.assert_called_once_with('tab 4', str(menu.RUNTIME))
        with patch.object(menu, 'shortcut') as shortcut:
            menu.main(['launch-first', 'bloquear pantalla'])
        shortcut.assert_called_once_with('lock')
        self.assertEqual(menu.filter_search('$(touch nope)'), [])

    def test_recents_default_off_and_no_launch_history_created(self):
        value = menu.catalogue(self.apps)
        self.assertFalse(value['recent_enabled'])
        self.assertEqual(value['recent'], [])
        self.launch(True)
        self.assertFalse((self.state / 'recent-apps.json').exists())

    def launch(self, result):
        desktop = types.SimpleNamespace(launch=lambda *args: result)
        gio = types.SimpleNamespace(DesktopAppInfo=types.SimpleNamespace(new=lambda app_id: desktop), AppLaunchContext=lambda: None)
        with patch.dict(sys.modules, {'gi.repository': types.SimpleNamespace(Gio=gio)}), patch.object(menu, 'close'):
            menu.launch_app(self.apps[0]['token'])

    def test_recents_only_record_successful_launches_and_keep_favorites(self):
        with patch.object(menu, 'update'):
            menu.main(['recent', 'enable'])
        self.launch(False)
        self.assertEqual(menu.catalogue(self.apps)['recent'], [])
        self.launch(True)
        self.assertEqual([row['id'] for row in menu.catalogue(self.apps)['recent']], ['Alpha.desktop'])
        self.assertFalse((self.state / 'home-apps.json').exists())
        self.assertEqual(stat.S_IMODE((self.state / 'recent-apps.json').stat().st_mode), 0o600)
        with patch.object(menu, 'update'):
            menu.main(['recent', 'disable'])
        self.assertFalse(menu.catalogue(self.apps)['recent_enabled'])
        self.assertEqual(menu.catalogue(self.apps)['recent'], [])
        with patch.object(menu, 'update'):
            menu.main(['recent', 'enable'])
        self.assertEqual(len(menu.catalogue(self.apps)['recent']), 1)
        with patch.object(menu, 'update'):
            menu.main(['recent', 'clear'])
        self.assertEqual(menu.catalogue(self.apps)['recent'], [])
        self.assertTrue(menu.catalogue(self.apps)['recent_enabled'])

    def test_builtin_app_spawns_are_recorded_and_resolve_safe_recent_actions(self):
        import recent_apps
        recent_apps.edit(self.state, 'enable')
        with patch.object(menu, 'close'), patch.object(menu.subprocess, 'Popen') as spawn:
            for name in ('browser', 'files', 'terminal'):
                menu.shortcut(name)
            rows = menu.catalogue(self.apps)['recent']
            self.assertEqual([(row['id'], row['action'], row['value']) for row in rows], [
                ('shortcut:terminal', 'shortcut', 'terminal'),
                ('shortcut:files', 'shortcut', 'files'),
                ('shortcut:browser', 'shortcut', 'browser')])
            self.assertTrue(all(not row['has_file'] for row in rows))
            menu.main([rows[0]['action'], rows[0]['value']])
            self.assertEqual(spawn.call_args.args[0], ['kitty'])
        self.assertFalse((self.state / 'home-apps.json').exists())

    def test_failed_builtin_spawns_and_nonapp_actions_are_not_recorded(self):
        import recent_apps
        recent_apps.edit(self.state, 'enable')
        before = (self.state / 'recent-apps.json').read_bytes()
        with patch.object(menu, 'close'), patch.object(menu.subprocess, 'Popen', side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                menu.shortcut('browser')
        with patch.object(menu, 'close'), patch.object(menu.subprocess, 'Popen'):
            for name in ('lock', 'notifications', 'audio', 'connections', 'calendar'):
                menu.shortcut(name)
        self.assertEqual((self.state / 'recent-apps.json').read_bytes(), before)

    def test_disabled_builtin_history_creates_no_state(self):
        with patch.object(menu, 'close'), patch.object(menu.subprocess, 'Popen'):
            menu.shortcut('browser')
        self.assertFalse((self.state / 'recent-apps.json').exists())
        self.assertFalse((self.state / 'recent-apps.lock').exists())

    def test_mixed_builtin_and_desktop_history_shares_the_bound(self):
        import recent_apps
        recent_apps.edit(self.state, 'enable')
        for key in ('Alpha.desktop', '1.desktop', '2.desktop', '3.desktop', '4.desktop', '5.desktop'):
            recent_apps.record(self.state, key)
        with patch.object(menu, 'close'), patch.object(menu.subprocess, 'Popen'):
            menu.shortcut('browser')
        self.launch(True)
        saved = json.loads((self.state / 'recent-apps.json').read_text())
        self.assertEqual(saved['items'], ['Alpha.desktop', 'shortcut:browser', '5.desktop', '4.desktop', '3.desktop', '2.desktop'])
        rows = menu.catalogue(self.apps)['recent']
        self.assertEqual([(row['action'], row['value']) for row in rows], [
            ('launch', self.apps[0]['token']), ('shortcut', 'browser')])
        root = Path(__file__).resolve().parents[1]
        source = (root / 'modules/desktop/files/.config/raccon-menu/apps.yuck').read_text()
        recent_source = source.split('(defwidget menu-recent []', 1)[1].split('(defwidget menu-home []', 1)[0]
        self.assertIn('desktop-menu ${app.action} ${app.value}', recent_source)

    def test_history_is_bounded_deduplicated_and_corruption_disables_it(self):
        import recent_apps
        recent_apps.edit(self.state, 'enable')
        for index in range(20):
            recent_apps.record(self.state, str(index) + '.desktop')
        recent_apps.record(self.state, '15.desktop')
        saved = json.loads((self.state / 'recent-apps.json').read_text())
        self.assertEqual(saved['items'], ['15.desktop', '19.desktop', '18.desktop', '17.desktop', '16.desktop', '14.desktop'])
        (self.state / 'recent-apps.json').write_text('{broken')
        recent_apps.record(self.state, 'Alpha.desktop')
        self.assertFalse(menu.catalogue(self.apps)['recent_enabled'])
        self.assertEqual((self.state / 'recent-apps.json').read_text(), '{broken')
        with self.assertRaises(ValueError):
            recent_apps.edit(self.state, '$(touch nope)')

    def test_menu_renders_unified_rows_and_explicit_recent_controls(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'modules/desktop/files/.config/raccon-menu/apps.yuck').read_text()
        self.assertIn('jq(catalogue.search,', source)
        self.assertIn('desktop-menu ${app.action} ${app.value}', source)
        self.assertIn(':text {app.category}', source)
        self.assertIn('for app in {catalogue.recent}', source)
        self.assertIn('desktop-menu recent ${catalogue.recent_enabled ? \'disable\' : \'enable\'}', source)
        self.assertIn('desktop-menu recent clear', source)

    def test_history_can_be_cleared_without_enabling_tracking(self):
        import recent_apps
        recent_apps.edit(self.state, 'enable')
        recent_apps.record(self.state, 'Alpha.desktop')
        recent_apps.edit(self.state, 'disable')
        recent_apps.edit(self.state, 'clear')
        saved = json.loads((self.state / 'recent-apps.json').read_text())
        self.assertEqual(saved, {'version': 1, 'enabled': False, 'items': []})
        root = Path(__file__).resolve().parents[1]
        source = (root / 'modules/desktop/files/.config/raccon-menu/apps.yuck').read_text()
        self.assertNotIn(':class "recent-clear" :visible', source)
        self.assertIn('No recent apps yet. Launch an app from Raccon Menu to add it.', source)
        self.assertIn('Only launches from Raccon Menu are recorded.', source)

    def test_query_does_not_persist_search_text(self):
        with patch.object(menu, 'update'):
            menu.main(['query', 'private search'])
        self.assertFalse((self.state / 'query.json').exists())


if __name__ == '__main__':
    unittest.main()
