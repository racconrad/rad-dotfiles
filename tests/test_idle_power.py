import sys
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'modules/power/files/.local/lib'))
from desktop_power import controller, storage
from desktop_power.occlusion import covered

class IdlePowerTests(unittest.TestCase):
    def test_only_unchanged_healthy_ac_uses_long_interval(self):
        with patch.object(storage,'CONFIG',ROOT/'modules/power/files/.config/desktop-power'):
            config=storage.load_config()
        base={'battery':{'plugged':True,'percent':80,'batteries':1},'errors':{},'mode':'balanced','source':'auto'}
        self.assertEqual(controller.poll_interval(config,base,base),15)
        self.assertEqual(controller.poll_interval(config,base,{}),5)
        for battery in ({'plugged':False,'percent':80},{'plugged':None,'percent':80},{'plugged':True,'percent':79}):
            self.assertEqual(controller.poll_interval(config,dict(base,battery=battery),base),5)
        self.assertEqual(controller.poll_interval(config,dict(base,errors={'cpu':'failed'}),base),5)

    def test_coverage_respects_outputs_workspaces_and_gaps(self):
        out={'id':1,'wset-index':0,'workarea':{'x':0,'y':0,'width':100,'height':100}}
        def view(x=0,width=100,**kw):
            return dict({'role':'toplevel','mapped':True,'output-id':1,'wset-index':0,'tiled-edges':15,
                         'geometry':{'x':x,'y':0,'width':width,'height':100}},**kw)
        self.assertTrue(covered([out],[view()]))
        self.assertTrue(covered([out],[view(width=50),view(x=50,width=50)]))
        self.assertFalse(covered([out],[view(width=49),view(x=50,width=50)]))
        self.assertFalse(covered([out],[view(minimized=True)]))
        self.assertFalse(covered([out],[view(**{'wset-index':1})]))
        self.assertFalse(covered([out],[view(x=100)]))
        self.assertFalse(covered([out,dict(out,id=2)],[view()]))
        self.assertFalse(covered([],[]));self.assertFalse(covered(None,None))

    def test_suspension_preserves_profile_and_restores_on_next_reconcile(self):
        with patch.object(storage,'CONFIG',ROOT/'modules/power/files/.config/desktop-power'):
            config=storage.load_config()
        battery={'plugged':True,'percent':80,'batteries':1}
        status=controller.build_status(config,battery,{}, {'mode':'complete'})
        with patch('desktop_power.occlusion.suspended',return_value=True):
            controller.widget_visibility(status)
        self.assertFalse(status['policy']['widgets'])
        self.assertTrue(config['profiles']['complete']['widgets'])
        restored=controller.build_status(config,battery,status,{'mode':'complete'})
        with patch('desktop_power.occlusion.suspended',return_value=False):
            controller.widget_visibility(restored)
        self.assertTrue(restored['policy']['widgets'])

    def test_coverage_is_not_a_desktop_profile_transition(self):
        with patch.object(storage,'CONFIG',ROOT/'modules/power/files/.config/desktop-power'):
            config=storage.load_config()
        status=controller.build_status(config,{'plugged':True,'percent':80},{},{'mode':'complete'})
        before=controller.fingerprint(config,status)
        status['policy']['widgets']=False
        self.assertEqual(controller.fingerprint(config,status),before)
