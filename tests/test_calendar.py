"""Agenda migration preserves user data and passes text through stdin, never a shell."""
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'modules/desktop/files/.local/lib/raccon_menu/calendar_data.py'
spec=importlib.util.spec_from_file_location('calendar_data',SOURCE)
calendar=importlib.util.module_from_spec(spec);spec.loader.exec_module(calendar)


class CalendarTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        for key,value in [('ROOT',self.root/'runtime'),('EVENTS',self.root/'events.json'),('PLANNER',self.root/'planner')]:
            p=patch.object(calendar,key,value);p.start();self.addCleanup(p.stop)
        self.original=[dict(id='old',date='2026-10-29',title='Evento existente')]
        calendar.store(calendar.EVENTS,self.original)
        calendar.action(['select','29','10','2026'])

    def test_add_and_remove_preserve_legacy_records_and_literal_text(self):
        title="Revisión 'equipo' · $(touch nope); café"
        with patch('sys.stdin',io.StringIO(title)):calendar.action(['add'])
        rows=calendar.events();self.assertEqual(rows[0],self.original[0]);self.assertEqual(rows[1]['title'],title)
        frame=calendar.snapshot();self.assertEqual(len(frame['events']),2)
        calendar.action(['remove',frame['events'][1]['token']])
        self.assertEqual(calendar.events(),self.original)

    def test_corrupt_agenda_is_never_overwritten(self):
        calendar.EVENTS.write_text('{incomplete')
        with patch('sys.stdin',io.StringIO('New')):
            with self.assertRaises(json.JSONDecodeError):calendar.action(['add'])
        self.assertEqual(calendar.EVENTS.read_text(),'{incomplete')

    def test_invalid_dates_and_overlong_events_preserve_storage(self):
        before=calendar.EVENTS.read_bytes()
        with self.assertRaises(ValueError):calendar.action(['select','31','2','2026'])
        with patch('sys.stdin',io.StringIO('x'*501)):
            with self.assertRaises(ValueError):calendar.action(['add'])
        self.assertEqual(calendar.EVENTS.read_bytes(),before)

    def test_agenda_keeps_today_tasks_and_chronological_upcoming_events(self):
        today=dt.date.today();calendar.store(calendar.ROOT/'calendar-date.json',today.isoformat())
        rows=self.original+[dict(id='future',title='Después',date=(today+dt.timedelta(days=2)).isoformat())]
        calendar.store(calendar.EVENTS,rows)
        task=dict(token='abc',title='Una tarea',done=False)
        self.assertEqual(calendar.snapshot([task])['tasks'],[task])
        calendar.store(calendar.ROOT/'calendar-date.json',(today+dt.timedelta(days=1)).isoformat())
        frame=calendar.snapshot([task]);self.assertEqual(frame['tasks'],[]);self.assertEqual(frame['upcoming'][0]['title'],'Después')


if __name__=='__main__':unittest.main()
