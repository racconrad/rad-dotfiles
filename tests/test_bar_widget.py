import re
import unittest
from collections import Counter
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / 'modules'
QUICKSHELL = MODULES / 'quickshell'
RACCON = QUICKSHELL / 'files/.config/quickshell/raccon'
SHELL = RACCON / 'shell.qml'
QMLDIR = RACCON / 'qmldir'


class BarWidgetTests(unittest.TestCase):
    def test_bar_registration_in_qmldir(self):
        manifest_text = QMLDIR.read_text()
        bar_declarations = {
            fields[-1]: fields[0]
            for line in manifest_text.splitlines()
            if (fields := line.partition('#')[0].split()) and fields[-1].startswith('Bar') and fields[-1].endswith('.qml')
        }
        self.assertIn('Bar.qml', bar_declarations)
        self.assertEqual(bar_declarations['Bar.qml'], 'Bar')

        bar_files = {p.name for p in RACCON.glob('Bar*.qml')}
        self.assertTrue(bar_files)
        self.assertEqual(set(bar_declarations.keys()), bar_files)

    def test_bar_lazy_loader_and_ipc_in_shell(self):
        source = SHELL.read_text()
        match_loader = re.search(r'LazyLoader\s*\{\s*id:\s*bar\b[^}]*active:\s*true', source, re.DOTALL)
        self.assertIsNotNone(match_loader, "Expected LazyLoader with id: bar and active: true in shell.qml")

        widgets_match = re.search(r'\bwidgets:\s*\(\{([^}]+)\}\)', source)
        self.assertIsNotNone(widgets_match)
        widget_keys = {k.strip() for k in widgets_match.group(1).split(',')}
        self.assertIn('bar', widget_keys)

    def test_no_bar_file_exceeds_150_lines(self):
        bar_files = list(RACCON.glob('Bar*.qml'))
        self.assertTrue(bar_files)
        for file_path in bar_files:
            line_count = len(file_path.read_text().splitlines())
            self.assertLessEqual(line_count, 150, f"{file_path.name} exceeds 150 lines ({line_count} lines)")


    def test_bar_never_animates_while_idle(self):
        # The bar is always visible: any endless animation keeps the compositor redrawing it forever.
        import re
        for file_path in RACCON.glob('Bar*.qml'):
            text = file_path.read_text()
            self.assertNotIn('Animation.Infinite', text, f"{file_path.name} has an endless animation")
            for spin in re.findall(r'\bspin:\s*([-\d.]+)', text):
                self.assertEqual(float(spin), 0, f"{file_path.name} spins a Spark at idle")


    def test_open_widgets_do_not_keep_the_render_loop_busy(self):
        # Endless animations redraw at the display rate even when nothing visibly changes.
        search = (RACCON / 'MenuSearch.qml').read_text()
        self.assertNotIn('Animation.Infinite', search, 'the caret blink must use a Timer')
        spectrum = (RACCON / 'Spectrum.qml').read_text()
        self.assertNotIn('Behavior on height', spectrum, 'spectrum bars must not animate between updates')
        tile = (RACCON / 'WallTile.qml').read_text()
        self.assertIn('img.status === Image.Loading', tile, 'placeholder pulses only while an image loads')


if __name__ == '__main__':
    unittest.main()
