"""Agenda migration preserves user data and passes text through stdin, never a shell."""
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
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

    def test_month_navigation_clamps_days_and_handles_year_and_leap_boundaries(self):
        for start,offset,expected in [('2026-01-31',1,'2026-02-28'),('2028-01-31',1,'2028-02-29'),
                                      ('2026-12-15',1,'2027-01-15'),('2026-01-15',-1,'2025-12-15')]:
            calendar.action(['select',start]);calendar.action(['move',str(offset)])
            self.assertEqual(calendar.selected().isoformat(),expected)

    def test_grid_uses_explicit_dates_and_marks_events_without_month_conversion(self):
        calendar.action(['select','2026-10-29'])
        frame=calendar.snapshot();cells=[day for week in frame['weeks'] for day in week]
        self.assertEqual(len(cells),42)
        self.assertEqual(cells[0]['iso'],'2026-09-28')
        selected=[day for day in cells if day['selected']]
        self.assertEqual([day['iso'] for day in selected],['2026-10-29'])
        self.assertTrue(selected[0]['event']);self.assertFalse(selected[0]['other'])
        self.assertEqual(frame['month_title'],'October 2026')

    def test_add_captures_visible_date_even_if_selection_changes(self):
        calendar.action(['select','2026-11-01'])
        with patch('sys.stdin',io.StringIO('Meeting')):calendar.action(['add','2026-10-29'])
        self.assertEqual(calendar.events()[-1]['date'],'2026-10-29')

    def test_invalid_runtime_selection_recovers_without_changing_events(self):
        calendar.store(calendar.ROOT/'calendar-date.json',{'invalid':'shape'})
        self.assertEqual(calendar.selected(),dt.date.today())
        self.assertEqual(calendar.events(),self.original)

    def test_invalid_event_dates_are_not_overwritten(self):
        calendar.store(calendar.EVENTS,[dict(id='bad',date='2026-02-31',title='Keep me')])
        before=calendar.EVENTS.read_bytes()
        with patch('sys.stdin',io.StringIO('New')):
            with self.assertRaises(ValueError):calendar.action(['add'])
        self.assertEqual(calendar.EVENTS.read_bytes(),before)

    def test_listener_emits_grid_and_observes_atomic_selection_replacements(self):
        runtime=self.root/'runtime/raccon-menu';runtime.mkdir(parents=True)
        (runtime/'page').write_text('7');(runtime/'visible').write_text('1')
        # Resolve the bundle root explicitly rather than relying on the host's imports.
        base=Path(__file__).resolve().parents[1]/'modules/base/files/.local/lib'
        env=dict(os.environ,HOME=str(self.root),XDG_RUNTIME_DIR=str(runtime.parent),PYTHONPATH=str(base))
        proc=subprocess.Popen([sys.executable,str(SOURCE),'watch'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(select.select([proc.stdout],[],[],3)[0])
            first=json.loads(proc.stdout.readline());self.assertEqual(len(first['weeks']),6)
            temporary=runtime/'.date';temporary.write_text('"2028-02-29"');temporary.replace(runtime/'calendar-date.json')
            self.assertTrue(select.select([proc.stdout],[],[],3)[0])
            frame=json.loads(proc.stdout.readline());self.assertEqual(frame['iso'],'2028-02-29')
        finally:
            proc.terminate();_,errors=proc.communicate(timeout=3)
        self.assertEqual(errors,'')


if __name__=='__main__':unittest.main()
