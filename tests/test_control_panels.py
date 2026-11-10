"""Control panel service contracts. Never change host connectivity or volume."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]/'modules/desktop/files/.local/lib/raccon_menu'
sys.path.insert(0,str(SOURCE))
spec=importlib.util.spec_from_file_location('control_panels',SOURCE/'panels.py')
panels=importlib.util.module_from_spec(spec);spec.loader.exec_module(panels)


class PanelTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)
        for name in ('STATE','ROOT'):
            path=self.base/name;path.mkdir()
            obj=patch.object(panels,name,path);obj.start();self.addCleanup(obj.stop)

    def test_providers_follow_their_attached_menu_page(self):
        (panels.ROOT/'visible').write_text('1')
        for kind,index in panels.SERVICE_PAGES.items():
            (panels.ROOT/'page').write_text(str(index))
            self.assertTrue(panels.active(kind))
            self.assertFalse(any(panels.active(other) for other in panels.PAGES if other!=kind))
        (panels.ROOT/'visible').write_text('0')
        self.assertFalse(any(panels.active(kind) for kind in panels.PAGES))

    def test_reopening_before_deadline_refreshes_immediately(self):
        calls=[]
        class Waiter:
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def wait(self,timeout):
                calls.append(timeout)
                if len(calls)==3:raise KeyboardInterrupt
            def close(self):pass
        with patch.object(panels,'active',side_effect=[True,False,True]), \
             patch.object(panels,'FileWatch',Waiter,create=True), \
             patch.object(panels.time,'sleep',side_effect=Waiter().wait), \
             patch.object(panels,'refresh',return_value=panels.defaults('audio')) as refresh, \
             patch.object(panels.time,'monotonic',return_value=10), \
             patch('sys.stdout',io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):panels.listen('audio')
        self.assertEqual(refresh.call_count,2)

    def test_wifi_uses_cached_scan_and_preserves_connected_bssid_over_stronger_ap(self):
        calls=[]
        rows=(' :Cafe\\:casa:AA\\:BB\\:CC\\:DD\\:EE\\:00:98:WPA2:wlan0\n'
              '*:Cafe\\:casa:AA\\:BB\\:CC\\:DD\\:EE\\:01:35:WPA2:wlan0\n'
              ':Cafe\\:casa:AA\\:BB\\:CC\\:DD\\:EE\\:02:99:WPA2:wlan0\n')
        def command(argv,*args,**kwargs):
            calls.append(argv)
            return 'enabled' if argv==['nmcli','radio','wifi'] else rows
        with patch.object(panels,'command',side_effect=command):data=panels.wifi_snapshot()
        self.assertEqual(len(data['networks']),1)
        self.assertTrue(data['networks'][0]['active'])
        self.assertEqual(data['networks'][0]['title'],'Cafe:casa')
        self.assertEqual(data['networks'][0]['bssid'],'AA:BB:CC:DD:EE:01')
        self.assertIn('--rescan',calls[1]);self.assertEqual(calls[1][-1],'no')

    def test_audio_reads_default_devices_and_hides_monitor_sources(self):
        def device(name,vol):return dict(name=name,description=name,volume={'left':{'value_percent':str(vol)+'%'}},mute=False)
        def command(argv,*args,**kwargs):
            if argv[-1]=='info':return json.dumps(dict(default_sink_name='speakers',default_source_name='mic'))
            if argv[-1]=='sinks':return json.dumps([device('headset',20),device('speakers',41)])
            return json.dumps([device('mic',75),device('speakers.monitor',50)])
        with patch.object(panels,'command',side_effect=command):data=panels.audio_snapshot()
        self.assertEqual(data['output']['name'],'speakers');self.assertEqual(data['output']['volume'],41)
        self.assertEqual([x['name'] for x in data['inputs']],['mic'])

    def test_service_failure_has_bounded_error_without_blocking_other_services(self):
        with patch.object(panels,'wifi_snapshot',side_effect=RuntimeError('test service down')):
            data=panels.refresh('connections')
        self.assertTrue(data['ready']);self.assertFalse(data['available'])
        self.assertIn('NetworkManager',data['error'])
        self.assertTrue((panels.STATE/'connections.json').exists())

    def test_bluetooth_keeps_unpaired_devices_and_sorts_connections_first(self):
        objects={
            '/org/bluez/hci0':{'org.bluez.Adapter1':{'Powered':True,'Discovering':False}},
            '/org/bluez/hci0/dev_01':{'org.bluez.Device1':{'Alias':'Nearby','Paired':False}},
            '/org/bluez/hci0/dev_02':{'org.bluez.Device1':{'Alias':'Headset','Connected':True,'Paired':True},'org.bluez.Battery1':{'Percentage':70}},
        }
        with patch.object(panels,'bluez',return_value=(objects,)):data=panels.bluetooth_snapshot()
        self.assertEqual([x['title'] for x in data['devices']],['Headset','Nearby'])
        self.assertEqual(data['devices'][0]['battery'],'70%')

    def test_paginated_lists_preserve_every_item_and_clamp_after_shrink(self):
        rows = [dict(token=f'{i:024x}') for i in range(11)]
        data = dict(networks=rows)
        seen = []
        for page in range(3):
            (panels.ROOT/'list-page-connections').write_text(str(page))
            frame = panels.presentation('connections', data)
            self.assertEqual(frame['page_count'], 3)
            self.assertLessEqual(len(frame['rows']), 4)
            seen += frame['rows']
        self.assertEqual(seen, rows)
        frame = panels.presentation('connections', dict(networks=rows[:1]))
        self.assertEqual(frame['list_page'], 0)
        self.assertEqual(frame['rows'], rows[:1])

    def test_page_navigation_never_queries_network_services(self):
        (panels.STATE/'connections.json').write_text(json.dumps(dict(networks=[dict(token=str(i)) for i in range(9)])))
        with patch.object(panels, 'command') as command, patch.object(panels, 'wake') as wake:
            panels.action(['wifi-page', 'next'])
            self.assertEqual((panels.ROOT/'list-page-connections').read_text(), '1')
            command.assert_not_called();wake.assert_not_called()

    def test_bluetooth_detail_tracks_refresh_and_recovers_missing_selection(self):
        row = dict(token='b'*24, title='Headset', connected=True, battery='0%')
        (panels.ROOT/'bt-selected').write_text(row['token'])
        frame = panels.presentation('bluetooth', dict(devices=[row]))
        self.assertEqual(frame['detail']['battery'], '0%')
        self.assertTrue(frame['detail']['connected'])
        row.update(battery='25%', connected=False)
        self.assertEqual(panels.presentation('bluetooth', dict(devices=[row]))['detail']['battery'], '25%')
        self.assertEqual(panels.presentation('bluetooth', dict(devices=[]))['detail']['token'], '')

    def test_bluetooth_metadata_and_missing_or_invalid_battery(self):
        props = {'Address':'01:02:03:04:05:06', 'Icon':'audio-headset', 'RSSI':-55, 'Trusted':True}
        objects = {'/org/bluez/hci0/dev_01':{'org.bluez.Device1':props, 'org.bluez.Battery1':{'Percentage':0}}}
        with patch.object(panels,'bluez',return_value=(objects,)):
            row = panels.bluetooth_snapshot()['devices'][0]
            self.assertEqual((row['battery'],row['kind'],row['signal']), ('0%','Headphones','-55 dBm'))
            self.assertEqual(row['address'], props['Address'])
            self.assertTrue(row['trusted'])
            objects['/org/bluez/hci0/dev_01']['org.bluez.Battery1']['Percentage'] = 101
            self.assertEqual(panels.bluetooth_snapshot()['devices'][0]['battery'], '')
            del objects['/org/bluez/hci0/dev_01']['org.bluez.Battery1']
            self.assertEqual(panels.bluetooth_snapshot()['devices'][0]['battery'], '')

    def test_inspecting_bluetooth_does_not_connect_or_disconnect(self):
        row = dict(token='c'*24, title='Headset', connected=True)
        (panels.STATE/'bluetooth.json').write_text(json.dumps(dict(devices=[row])))
        with patch.object(panels, 'command') as command, patch.object(panels, 'bluez') as bluez:
            panels.action(['bt-select', row['token']])
            self.assertEqual(panels.presentation('bluetooth', dict(devices=[row]))['detail']['token'], row['token'])
            panels.action(['bt-back'])
            self.assertEqual(panels.presentation('bluetooth', dict(devices=[row]))['detail']['token'], '')
            command.assert_not_called();bluez.assert_not_called()

    def network(self):
        row=dict(token='a'*24,title='Test',bssid='00:11:22:33:44:55',device='wlan-test',active=False,secured=True)
        (panels.STATE/'connections.json').write_text(json.dumps({'networks':[row]}))
        return row

    def test_wifi_password_uses_stdin_and_never_appears_in_arguments_or_state(self):
        row=self.network();secret='fixture secret ; $(touch nope)'
        with patch.object(panels.shell,'eww',return_value=json.dumps({'token':row['token']})), \
             patch.object(panels.shell,'update'),patch.object(sys,'stdin',io.StringIO(secret)), \
             patch.object(panels,'command') as command,patch.object(panels,'wake'):
            panels.action(['wifi-connect'])
        argv=command.call_args.args[0]
        self.assertNotIn(secret,argv);self.assertEqual(command.call_args.kwargs['stdin'],secret+'\n')
        self.assertTrue(all(secret not in p.read_text() for p in panels.STATE.iterdir()))

    def test_invalid_selectors_never_run_service_commands(self):
        self.network()
        with patch.object(panels,'command') as command:
            for args in (['wifi-select','; reboot'],['wifi-power','maybe'],['audio-device','bad','a'*24],['bt-power','; reboot']):
                with self.assertRaises(ValueError):panels.action(args)
            command.assert_not_called()

    def test_failed_wifi_connect_clears_busy_state(self):
        row=self.network()
        with patch.object(panels.shell,'eww',return_value=json.dumps({'token':row['token']})), \
             patch.object(panels.shell,'update') as update,patch.object(sys,'stdin',io.StringIO('fixture')), \
             patch.object(panels,'command',side_effect=subprocess.TimeoutExpired('nmcli',25)):
            with self.assertRaises(subprocess.TimeoutExpired):panels.action(['wifi-connect'])
        self.assertEqual(update.call_args.kwargs,{'wifi_busy':False})


if __name__=='__main__':unittest.main()
