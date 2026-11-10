"""Working policy contracts without touching running desktop services."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'modules/power/files'
sys.dont_write_bytecode = True
sys.path.insert(0, str(PAYLOAD / '.local/lib'))
from desktop_power import controller, policy, storage


class WorkingModeTests(unittest.TestCase):
    def setUp(self):
        with patch.object(storage, 'CONFIG', PAYLOAD / '.config/desktop-power'):
            self.config = storage.load_config()

    def test_manual_working_survives_ac_and_critical_battery(self):
        for plugged in (True, False, None):
            battery = {'plugged': plugged, 'percent': 5, 'batteries': 1}
            state = controller.build_status(self.config, battery, {}, {'mode': 'working'})
            self.assertEqual(state['mode'], 'working')
            self.assertEqual(state['policy']['animation_factor'], 0)
            self.assertFalse(policy.should_suspend(battery, {'mode': 'working'}))
            state['transition'] = True
            data = controller.bar_data(state)
            self.assertEqual(data['alt'], 'working')
            self.assertNotIn('applying', data['class'])
            self.assertIn(self.config['profiles']['working']['label'], data['tooltip'])
        self.assertEqual(self.config['profiles']['working']['cpu_profile'], 'balanced')

    def test_leaving_working_restores_idle_battery_policy(self):
        for mode in ('auto', 'balanced', 'complete', 'performance'):
            self.assertTrue(policy.should_suspend({'plugged': False, 'batteries': 1}, {'mode': mode}))
            self.assertFalse(policy.should_suspend({'plugged': True, 'batteries': 1}, {'mode': mode}))
            self.assertFalse(policy.should_suspend({'plugged': None, 'batteries': 0}, {'mode': mode}))

    def test_working_reconcile_never_fades_windows(self):
        battery = {'plugged': False, 'percent': 20, 'batteries': 1}
        with patch.object(controller, 'load_config', return_value=self.config), \
             patch.object(controller, 'read_battery', return_value=battery), \
             patch.object(controller, 'read_json', return_value={'mode': 'working'}), \
             patch.object(controller, 'publish'), \
             patch.object(controller.effects, 'widget_policy'), \
             patch.object(controller.effects, 'wayfire'), \
             patch.object(controller.effects, 'cpu'), \
             patch.object(controller.effects, 'focus_fx'), \
             patch.object(controller.effects, 'widgets') as widgets, \
             patch.object(controller.effects, 'widgets_need_install', return_value=False), \
             patch.object(controller.effects, 'wallpaper'), \
             patch.object(controller.effects, 'run'), \
             patch.object(controller.effects, 'desktop_transition') as transition:
            state, _, _ = controller.reconcile({})
            transition.assert_not_called()
            widgets.assert_called_once()
            self.assertEqual(state['errors'], {})


if __name__ == '__main__':
    unittest.main()
