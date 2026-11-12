"""Home shortcuts can be edited without touching installed application entries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_raccon_menu import menu

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'modules/desktop/files/.local/lib/raccon_menu'


def app(name):
    key = name + '.desktop'
    return dict(id=key, token=hashlib.sha256(key.encode()).hexdigest(), name=name,
                icon='application-x-executable', has_file=False, file='', search=name.lower())


class HomeAppsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.catalog = [app(name) for name in ('Alpha', 'Beta', 'Gamma', 'Delta')]
        self.catalog_path = self.state / 'apps.json'
        self.catalog_path.write_text(json.dumps(self.catalog))
        change = patch.object(menu, 'STATE', self.state)
        change.start()
        self.addCleanup(change.stop)
        update = patch.object(menu, 'update')
        update.start()
        self.addCleanup(update.stop)

    def keys(self):
        return [item['key'] for row in menu.daily_apps(self.catalog) for item in row]

    def edit(self, *args):
        try:
            menu.main(['favorite', *args])
        except Exception as exc:
            self.fail('Home edit failed: ' + str(exc))

    def test_builtins_can_be_removed_readded_and_reordered(self):
        self.edit('remove', 'shortcut:browser')
        self.assertEqual(self.keys(), ['shortcut:files', 'shortcut:terminal'])
        self.edit('add', 'shortcut:browser')
        self.edit('move', 'shortcut:browser', 'previous')
        self.assertEqual(self.keys(), ['shortcut:files', 'shortcut:browser', 'shortcut:terminal'])
        self.edit('move', 'shortcut:files', 'previous')
        self.assertEqual(self.keys()[0], 'shortcut:files')
        self.edit('move', 'shortcut:browser', 'next')
        self.assertEqual(self.keys(), ['shortcut:files', 'shortcut:terminal', 'shortcut:browser'])

    def test_empty_selection_is_persistent_and_not_replaced_by_defaults(self):
        for key in ('shortcut:browser', 'shortcut:files', 'shortcut:terminal'):
            self.edit('remove', key)
        self.assertEqual(menu.daily_apps(self.catalog), [])
        self.assertEqual(json.loads((self.state/'home-apps.json').read_text())['items'], [])
        self.edit('reset')
        self.assertEqual(self.keys(), ['shortcut:browser', 'shortcut:files', 'shortcut:terminal'])

    def test_legacy_favorites_are_preserved_on_first_edit(self):
        legacy = self.state / 'favorites.json'
        legacy.write_text('["Alpha.desktop", "missing.desktop", "Alpha.desktop"]')
        self.edit('remove', 'shortcut:files')
        saved = json.loads((self.state / 'home-apps.json').read_text())
        self.assertEqual(saved, {'version': 1, 'items': [
            'shortcut:browser', 'shortcut:terminal', 'Alpha.desktop', 'missing.desktop']})
        self.assertEqual(legacy.read_text(), '["Alpha.desktop", "missing.desktop", "Alpha.desktop"]')
        self.assertEqual(self.keys(), ['shortcut:browser', 'shortcut:terminal', 'Alpha.desktop', 'missing.desktop'])

    def test_app_token_refs_add_pin_and_remove_without_shell_interpolation(self):
        token = self.catalog[0]['token']
        self.edit('add', token)
        self.edit('add', token)
        value = menu.catalogue(self.catalog)
        self.assertTrue(value['apps'][0]['pinned'])
        self.assertEqual(value['apps'][0]['ref'], token)
        tile = value['favorites'][1][0]
        self.assertEqual((tile['key'], tile['ref'], tile['position']), ('Alpha.desktop', token, 3))
        self.assertTrue(tile['can_move_previous'])
        self.assertFalse(tile['can_move_next'])
        self.assertTrue(all(item['pinned'] for item in value['shortcuts']))
        self.assertEqual((value['home_count'], value['home_limit']), (4, 6))
        self.edit('remove', token)
        self.assertFalse(menu.catalogue(self.catalog)['apps'][0]['pinned'])

    def test_invalid_edit_and_capacity_do_not_overwrite_state(self):
        for item in self.catalog[:3]:
            self.edit('add', item['token'])
        before = (self.state/'home-apps.json').read_bytes()
        for args in (('add', self.catalog[3]['token']), ('add', '; touch nope'),
                     ('move', 'shortcut:files', 'sideways'), ('remove', 'missing.desktop'),
                     ('add',), ('reset', 'extra')):
            with self.subTest(args=args), self.assertRaises(ValueError):
                menu.main(['favorite', *args])
            self.assertEqual((self.state/'home-apps.json').read_bytes(), before)
        self.assertFalse((self.state/'nope').exists())

    def test_uninstalled_app_ref_can_be_removed_without_discarding_other_keys(self):
        self.edit('add', self.catalog[0]['token'])
        self.catalog_path.write_text('[]')
        self.edit('remove', self.catalog[0]['token'])
        self.assertEqual(self.keys(), ['shortcut:browser', 'shortcut:files', 'shortcut:terminal'])

    def test_missing_full_selection_stays_visible_removable_and_ordered(self):
        keys = [f'missing-{index}.desktop' for index in range(6)]
        (self.state / 'home-apps.json').write_text(json.dumps({'version': 1, 'items': keys}))
        value = menu.catalogue(self.catalog)
        tiles = [item for row in value['favorites'] for item in row]
        self.assertEqual([item['key'] for item in tiles], keys)
        self.assertEqual([item['position'] for item in tiles], list(range(6)))
        self.assertEqual(value['home_count'], 6)
        for index, tile in enumerate(tiles):
            self.assertFalse(tile['available'])
            self.assertEqual(tile['name'], f'missing-{index}')
            self.assertEqual(tile['action'], 'launch')
            self.assertEqual(tile['value'], hashlib.sha256(keys[index].encode()).hexdigest())
            self.assertFalse(tile['has_file'])
            self.assertEqual(tile['file'], '')
        self.edit('remove', tiles[2]['ref'])
        self.assertEqual(self.keys(), keys[:2] + keys[3:])
        self.edit('add', self.catalog[0]['token'])
        value = menu.catalogue(self.catalog)
        tile = value['favorites'][1][-1]
        self.assertEqual(tile['name'], 'Alpha')
        self.assertTrue(tile['available'])
        self.edit('reset')
        self.assertTrue(all(item['available'] for row in menu.daily_apps(self.catalog) for item in row))

    def test_corrupt_saved_selection_is_not_silently_overwritten(self):
        saved = self.state / 'home-apps.json'
        saved.write_text('{broken')
        self.assertEqual([item['name'] for row in menu.daily_apps(self.catalog) for item in row],
                         ['Browser', 'Files', 'Terminal'])
        with self.assertRaises(ValueError):
            menu.main(['favorite', 'add', self.catalog[0]['token']])
        self.assertEqual(saved.read_text(), '{broken')

    def test_success_clears_error_but_missing_eww_does_not_undo_the_edit(self):
        feedback = {'error': 'Main menu is full.'}
        with patch.object(menu, 'update', side_effect=lambda **values: feedback.update(values)):
            self.edit('remove', 'shortcut:browser')
        self.assertEqual(feedback['error'], '')
        self.assertNotIn('shortcut:browser', self.keys())
        with patch.object(menu, 'update', side_effect=RuntimeError('Eww is not running.')):
            self.edit('add', self.catalog[0]['token'])
        self.assertIn('Alpha.desktop', self.keys())

    def test_concurrent_edits_preserve_both_additions(self):
        env = {**os.environ, 'HOME': str(self.state), 'XDG_STATE_HOME': str(self.state.parent),
               'XDG_CONFIG_HOME': str(self.state/'config'), 'XDG_RUNTIME_DIR': str(self.state/'run'),
               'PYTHONDONTWRITEBYTECODE': '1'}
        # The real CLI resolves its state below XDG_STATE_HOME/raccon-menu.
        directory = self.state/'raccon-menu'
        directory.mkdir()
        (directory/'apps.json').write_text(json.dumps(self.catalog))
        env['XDG_STATE_HOME'] = str(self.state)
        workers = [subprocess.Popen([sys.executable, str(LIB/'backend.py'), 'favorite', 'add', item['token']],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                   for item in self.catalog[:2]]
        for child in workers:
            output, errors = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 0, errors.decode())
        items = json.loads((directory/'home-apps.json').read_text())['items']
        self.assertEqual(set(items[3:]), {'Alpha.desktop', 'Beta.desktop'})
        self.assertEqual(len(items), 5)


class HomeCatalogueTests(unittest.TestCase):
    def test_atomic_edits_update_catalogue_without_reenumerating_apps(self):
        from test_desktop_events import Lines
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            data = home / 'data'
            applications = data / 'applications'
            applications.mkdir(parents=True)
            (applications / 'fixture.desktop').write_text(
                '[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true\nIcon=application-x-executable\n')
            env = {**os.environ, 'HOME': str(home), 'XDG_STATE_HOME': str(home/'state'),
                   'XDG_DATA_HOME': str(data), 'XDG_DATA_DIRS': str(home/'system'),
                   'PYTHONDONTWRITEBYTECODE': '1'}
            child = subprocess.Popen([sys.executable, '-u', str(LIB/'backend.py'), 'watch-catalogue'],
                                     env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                output = Lines(child)
                initial = output.until(lambda value: bool(value['apps']))
                token = initial['apps'][0]['ref']
                cache = home/'state/raccon-menu/apps.json'
                stamp = cache.stat().st_mtime_ns
                result = subprocess.run([sys.executable, str(LIB/'backend.py'), 'favorite', 'add', token],
                                        env=env, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                changed = output.until(lambda value: value['apps'][0]['pinned'])
                self.assertEqual(changed['favorites'][1][0]['name'], 'Fixture')
                self.assertEqual((changed['home_count'], changed['home_limit']), (4, 6))
                self.assertEqual(cache.stat().st_mtime_ns, stamp)
                result = subprocess.run([sys.executable, str(LIB/'backend.py'), 'favorite', 'remove',
                                         'shortcut:browser'], env=env, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                changed = output.until(lambda value: not value['shortcuts'][0]['pinned'])
                self.assertEqual(changed['home_count'], 3)
                self.assertEqual(cache.stat().st_mtime_ns, stamp)
            finally:
                child.terminate()
                child.communicate(timeout=3)
