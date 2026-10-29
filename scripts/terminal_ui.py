"""A small native terminal surface with a plain, scriptable fallback."""
import os
import sys
import textwrap


def fit(text, width):
    text = str(text).replace('\n', ' ')
    return text if len(text) <= width else text[:max(0, width - 3)] + '...'


def frame(version, page, tabs, rows, cursor, details, summary, notice='', width=80, height=24):
    """Pure renderer: the same layout is inspectable without a terminal session."""
    if width < 54 or height < 16:
        return [(fit('RACCON DOTS', width - 1), 'title'),
                (fit('Enlarge to 54 columns / 16 rows, or press q to quit.', width - 1), 'warning')]
    wide = width >= 110
    left = width // 2 if wide else width
    output = [('RACCON DOTS ' + version + '  /  PACK YOUR DEN', 'title'),
              (' '.join(f'[{key}]{label}' for key, label in tabs), 'tabs'),
              (page, 'title')]
    room = height - (7 if wide else 12)
    start = min(max(0, cursor - room + 1), max(0, len(rows) - room))
    visible = rows[start:start + room]
    detail_lines = []
    for text in details:
        detail_lines += textwrap.wrap(str(text), width=(width - left - 4 if wide else width - 2)) or ['']
    for i in range(max(len(visible), min(len(detail_lines), room)) if wide else len(visible)):
        if i < len(visible):
            row = visible[i]
            position = start + i
            mark = row.get('mark', ' ')
            prefix = '>' if position == cursor else ' '
            text = f'{prefix} {row.get("number", position + 1):2}. [{mark}] {row["label"]}'
            text = fit(text, left - 2 if wide else width - 1)
            style = 'focus' if position == cursor else 'normal'
        else:
            text, style = '', 'normal'
        if wide:
            text = text.ljust(left) + ' | ' + (detail_lines[i] if i < len(detail_lines) else '')
        output.append((text, style))
    if len(rows) > room:
        output.append((f'  Items {start + 1}-{start + len(visible)} of {len(rows)}. Use arrows to browse.', 'muted'))
    if not wide:
        output += [('-' * min(width - 1, 72), 'muted')]
        summary_lines = [details[1] if len(details) > 1 else details[0] if details else '',
                         next((line for line in details if line.startswith('Needs:')), ''),
                         next((line for line in details if line.startswith(('Status:', 'Packages:'))), '')]
        output += [(fit(line, width - 1), 'muted') for line in summary_lines]
    while len(output) < height - 4:
        output.append(('', 'normal'))
    output = output[:height - 4]
    output += [(fit(summary, width - 1), 'muted'),
               ('Arrows move | Space select | ? details | v review | i install', 'help'),
               ('w save profile | h restore | q quit', 'help'),
               (fit(notice, width - 1), 'warning' if notice else 'normal')]
    return [(fit(text, width - 1), style) for text, style in output]


class Terminal:
    def __init__(self, plain=False):
        self.native = (not plain and sys.stdin.isatty() and sys.stdout.isatty() and
                       os.environ.get('TERM', '') not in ('', 'dumb'))
        self.window = None

    def __enter__(self):
        if self.native:
            try:
                import curses
            except ImportError:
                self.native = False
                return self
            self.curses = curses
            try:
                self.window = curses.initscr()
            except curses.error:
                self.native = False
                return self
            curses.noecho()
            curses.cbreak()
            self.window.keypad(True)
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            self.colors = curses.has_colors() and 'NO_COLOR' not in os.environ
            if self.colors:
                try:
                    curses.start_color()
                    curses.use_default_colors()
                    curses.init_pair(1, curses.COLOR_YELLOW, -1)
                    curses.init_pair(2, curses.COLOR_CYAN, -1)
                except curses.error:
                    self.colors = False
        return self

    def __exit__(self, *_):
        if self.window is not None:
            self.window.keypad(False)
            self.curses.nocbreak()
            self.curses.echo()
            self.curses.endwin()

    def render(self, **data):
        self.data = data
        if not self.native:
            print('\nRACCON DOTS ' + data['version'] + ' / PACK YOUR DEN')
            print(' '.join(f'[{key}]{label}' for key, label in data['tabs']))
            print(data['page'])
            for i, row in enumerate(data['rows'], 1):
                print(f'  {row.get("number", i)}. [{row.get("mark", " ")}] {row["label"]}')
            print('\n' + '\n'.join(data['details'][:4]))
            print(data['summary'])
            print('Numbers toggle | ? details | v preview | i install | w save | h restore | q quit')
            if data['notice']:
                print(data['notice'])
            return
        height, width = self.window.getmaxyx()
        lines = frame(**data, width=width, height=height)
        self.window.erase()
        for y, (text, style) in enumerate(lines):
            attribute = self.curses.A_NORMAL
            if style == 'focus':
                attribute |= self.curses.A_REVERSE
            if style == 'title':
                attribute |= self.curses.A_BOLD
            if self.colors and style in ('title', 'warning'):
                attribute |= self.curses.color_pair(1)
            elif self.colors and style in ('tabs', 'help'):
                attribute |= self.curses.color_pair(2)
            try:
                self.window.addnstr(y, 0, text, max(0, width - 1), attribute)
            except self.curses.error:
                pass
        self.window.refresh()

    def read(self):
        if not self.native:
            return input('Select > ').strip().lower()
        key = self.window.get_wch()
        mapping = {self.curses.KEY_UP: 'up', self.curses.KEY_DOWN: 'down',
                   self.curses.KEY_PPAGE: 'pageup', self.curses.KEY_NPAGE: 'pagedown',
                   self.curses.KEY_RESIZE: 'resize', self.curses.KEY_ENTER: 'toggle',
                   self.curses.KEY_BTAB: 'backtab', '\t': 'tab', ' ': 'toggle', '\n': 'toggle', '\r': 'toggle'}
        return mapping.get(key, key.lower() if isinstance(key, str) else '')

    def prompt(self, text):
        if not self.native:
            return input(text)
        height, width = self.window.getmaxyx()
        self.window.move(height - 2, 0)
        self.window.clrtoeol()
        self.window.addnstr(height - 2, 0, text, width - 1)
        self.window.move(height - 1, 0)
        self.window.clrtoeol()
        self.curses.echo()
        try:
            try:
                self.curses.curs_set(1)
            except self.curses.error:
                pass
            return self.window.getstr(height - 1, 0, max(1, width - 2)).decode('utf-8').strip()
        finally:
            self.curses.noecho()
            try:
                self.curses.curs_set(0)
            except self.curses.error:
                pass

    def show(self, title, lines):
        if not self.native:
            print('\n' + title + '\n' + '\n'.join(lines))
            input('Press Enter to return: ')
            return
        offset = 0
        while True:
            height, width = self.window.getmaxyx()
            wrapped = [part for line in lines for part in (textwrap.wrap(str(line), max(1, width - 2)) or [''])]
            self.window.erase()
            try:
                self.window.addnstr(0, 0, title, width - 1, self.curses.A_BOLD)
                for y, line in enumerate(wrapped[offset:offset + max(1, height - 3)], 2):
                    self.window.addnstr(y, 0, line, width - 1)
                self.window.addnstr(height - 1, 0, 'Up/Down scroll | Enter / Esc return', width - 1)
            except self.curses.error:
                pass
            self.window.refresh()
            key = self.read()
            if key in ('toggle', '\x1b', 'q'):
                return
            if key in ('down', 'pagedown'):
                offset = min(max(0, len(wrapped) - height + 3), offset + (height - 3 if key == 'pagedown' else 1))
            elif key in ('up', 'pageup'):
                offset = max(0, offset - (height - 3 if key == 'pageup' else 1))

    def suspend(self, callback):
        if not self.native:
            return callback()
        self.curses.def_prog_mode()
        self.curses.endwin()
        try:
            return callback()
        finally:
            self.curses.reset_prog_mode()
            self.window.refresh()
