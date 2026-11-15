"""Run only with RACCON_SNAP_RUNTIME=1 and an explicitly built plugin."""
import os
from pathlib import Path
import unittest

from snap_runtime import PrivateCompositor, wait_for


@unittest.skipUnless(os.environ.get('RACCON_SNAP_RUNTIME') == '1', 'private compositor opt-in required')
class SnapRuntimeTests(unittest.TestCase):
    def start(self, minimum=(200, 150), **bindings):
        build = os.environ.get('RACCON_SNAP_BUILD')
        self.assertTrue(build and (Path(build) / 'libsnap-tiling.so').is_file(), 'Build Snap first')
        session = PrivateCompositor(build, minimum, **bindings)
        self.addCleanup(session.close)
        return session

    def test_keyboard_place_restore_and_cancel(self):
        session = self.start()
        original = session.current()['geometry']
        session.open_selector()
        session.key('KEY_ESC')
        self.assertEqual(session.current()['geometry'], original)
        session.key('KEY_A')
        wait_for(lambda: 'KEY a' in (session.root / 'client.log').read_text())
        session.open_selector()
        session.key('KEY_1')
        session.key('KEY_ENTER')
        placed = wait_for(lambda: session.current()['geometry'] if
                          session.current()['geometry']['width'] == 635 else None)
        self.assertEqual(placed['x'], 0)
        self.assertEqual(placed['width'], 635)
        self.assertEqual(placed['height'], 800)
        session.key('KEY_SPACE', ('KEY_LEFTMETA', 'KEY_LEFTSHIFT'))
        wait_for(lambda: session.current()['geometry'] == original)
        self.assertEqual(session.current()['geometry'], original)

    def test_large_minimum_does_not_mutate_window(self):
        session = self.start((900, 600))
        original = session.current()['geometry']
        session.open_selector()
        session.key('KEY_1')
        session.key('KEY_ENTER')
        self.assertEqual(session.current()['geometry'], original)
        session.key('KEY_ESC')
        session.key('KEY_A')
        wait_for(lambda: 'KEY a' in (session.root / 'client.log').read_text())

    def test_repeated_snap_restores_pre_snap_geometry(self):
        session = self.start()
        original = session.current()['geometry']
        session.open_selector()
        session.key('KEY_1')
        session.key('KEY_ENTER')
        wait_for(lambda: session.current()['geometry']['width'] == 635)
        session.open_selector()
        session.key('KEY_2')
        session.key('KEY_ENTER')
        wait_for(lambda: session.current()['geometry']['width'] == 420)
        session.key('KEY_SPACE', ('KEY_LEFTMETA', 'KEY_LEFTSHIFT'))
        wait_for(lambda: session.current()['geometry'] == original)

    def test_pointer_selects_slot_and_applies(self):
        session = self.start()
        session.open_selector()
        session.click(379, 115)
        wait_for(lambda: session.current()['geometry']['width'] == 635)
        self.assertEqual(session.current()['geometry']['x'], 0)

    def test_only_selected_zone_is_previewed(self):
        from PIL import Image, ImageChops
        session = self.start()
        before = Image.open(session.screenshot('before.png')).convert('RGB')
        session.open_selector()
        during = Image.open(session.screenshot('during.png')).convert('RGB')
        untouched = (1000, 600, 1100, 700)
        self.assertIsNone(ImageChops.difference(before.crop(untouched), during.crop(untouched)).getbbox())
        card = (310, 24, 970, 268)
        self.assertIsNotNone(ImageChops.difference(before.crop(card), during.crop(card)).getbbox())
        session.key('KEY_ESC')

    def test_shift_tab_cycles_layouts_backwards(self):
        session = self.start()
        session.open_selector()
        session.key('KEY_1')
        session.key('KEY_TAB', ('KEY_LEFTSHIFT',))
        session.key('KEY_ENTER')
        wait_for(lambda: session.current()['geometry']['width'] == 635)
        self.assertEqual(session.current()['geometry']['height'], 395)

    def test_held_super_navigation_does_not_run_global_shortcuts(self):
        session = self.start()
        session.call('stipc/feed_key', {'key': 'KEY_LEFTMETA', 'state': True})
        session.key('KEY_Z')
        session.key('KEY_1')
        session.key('KEY_RIGHT')
        session.key('KEY_ENTER')
        session.call('stipc/feed_key', {'key': 'KEY_LEFTMETA', 'state': False})
        self.assertFalse((session.root / 'collision').exists())
        wait_for(lambda: session.current()['geometry']['x'] == 645)

    def test_toggle_closes_and_outside_click_does_not_reach_client(self):
        session = self.start()
        original = session.current()['geometry']
        session.open_selector()
        session.open_selector()
        session.key('KEY_A')
        wait_for(lambda: 'KEY a' in (session.root / 'client.log').read_text())
        session.open_selector()
        geometry = session.current()['geometry']
        session.click(geometry['x'] + 30, geometry['y'] + geometry['height'] - 30)
        self.assertEqual(session.current()['geometry'], original)
        self.assertNotIn('BUTTON', (session.root / 'client.log').read_text())
        session.key('KEY_B')
        wait_for(lambda: 'KEY b' in (session.root / 'client.log').read_text())

    def test_remapped_bindings_work_inside_selector(self):
        session = self.start(toggle='<super> KEY_X', detach='<super> <shift> KEY_R')
        original = session.current()['geometry']
        session.key('KEY_X', ('KEY_LEFTMETA',))
        session.key('KEY_X', ('KEY_LEFTMETA',))
        session.key('KEY_A')
        wait_for(lambda: 'KEY a' in (session.root / 'client.log').read_text())
        session.key('KEY_X', ('KEY_LEFTMETA',))
        session.key('KEY_1')
        session.key('KEY_ENTER')
        wait_for(lambda: session.current()['geometry']['width'] == 635)
        session.key('KEY_X', ('KEY_LEFTMETA',))
        session.key('KEY_R', ('KEY_LEFTMETA', 'KEY_LEFTSHIFT'))
        wait_for(lambda: session.current()['geometry'] == original)
