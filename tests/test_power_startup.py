"""Power mode startup regression: widget policy uses the public profile API."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'modules/power/files'
sys.dont_write_bytecode = True
sys.path.insert(0, str(PAYLOAD / '.local/lib'))
from desktop_power import effects, storage


class StartupTests(unittest.TestCase):
    def setUp(self):
        with patch.object(storage, 'CONFIG', PAYLOAD / '.config/desktop-power'):
            self.config = storage.load_config()

    def test_widget_policy_is_sent_through_the_public_profile_api(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);ctl=home/'.local/bin/widgetctl';ctl.parent.mkdir(parents=True);ctl.touch()
            state=home/'state';state.mkdir();status=state/'status.json';status.write_text('{"policy":{"widgets":false}}')
            with patch.object(effects,'HOME',home),patch.object(effects,'STATE',state),patch.object(effects,'run',side_effect=[json.dumps({'frame':'none'}),'']) as run:
                effects.widget_policy()
            self.assertEqual(run.call_args.args[0],[str(ctl),'--config',str(home/'.config/eww'),'policy',str(status)])


if __name__ == '__main__':
    unittest.main()
