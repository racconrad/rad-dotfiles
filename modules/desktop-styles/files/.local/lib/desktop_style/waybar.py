"""Reversible compact layouts without discarding JSONC comments or custom actions."""
import json
import re

DELETE = object()
STRINGS_COMMENTS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/')


def clean(text):
    text = STRINGS_COMMENTS.sub(lambda m: m[0] if m[0].startswith('"') else
                                ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)
    return re.sub(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])',
                  lambda m: ' ' if m[0] == ',' else m[0], text)


class Document:
    def __init__(self, text):
        self.text = text
        self.source = clean(text)
        self.data = json.loads(self.source)
        if not isinstance(self.data, dict):
            raise ValueError('The Raccon bar layout requires a single Waybar object')

    def members(self, path=()):
        start = self.source.index('{')
        decoder = json.JSONDecoder()
        for part in (*path, None):
            fields = {}
            pos = start + 1
            while True:
                while self.source[pos].isspace() or self.source[pos] == ',': pos += 1
                if self.source[pos] == '}': break
                member_start = pos
                key, pos = decoder.raw_decode(self.source, pos)
                while self.source[pos].isspace() or self.source[pos] == ':': pos += 1
                value_start = pos
                value, pos = decoder.raw_decode(self.source, pos)
                fields[key] = (member_start, value_start, pos, value)
            if part is None: return fields, start
            if part not in fields or not isinstance(fields[part][3], dict):
                raise ValueError('Missing Waybar section: ' + str(part))
            start = fields[part][1]

    def patch(self, path, value):
        fields, start = self.members(path[:-1])
        field = fields.get(path[-1])
        if field:
            member_start, a, b, _ = field
            if value is DELETE:
                a = member_start
                after = b
                while self.source[after].isspace(): after += 1
                if self.source[after] == ',': b = after + 1
                else:
                    before = a - 1
                    while self.source[before].isspace(): before -= 1
                    if self.source[before] == ',': a = before
                replacement = ''
            else: replacement = json.dumps(value, ensure_ascii=False)
            return self.text[:a] + replacement + self.text[b:]
        if value is DELETE: return self.text
        addition = '\n' + '  ' * len(path) + json.dumps(path[-1]) + ': ' + json.dumps(value, ensure_ascii=False)
        return self.text[:start+1] + addition + (',' if fields else '') + self.text[start+1:]


def compact(text, vertical, saved):
    """Remember only fields we own, so returning horizontal restores user formats."""
    document = Document(text)
    if not vertical:
        for entry in saved:
            # A module removed by the user while vertical must stay removed.
            if len(entry['path']) > 1 and entry['path'][0] not in Document(text).data: continue
            text = Document(text).patch(entry['path'], entry['value'] if entry['exists'] else DELETE)
        return text, []
    changes = {('width',): 64, ('height',): 0}
    for key, value in document.data.items():
        if key.startswith('group/') and isinstance(value, dict): changes[(key, 'orientation')] = 'vertical'
    formats = {
        'clock': {'format': '{:%H\n%M}', 'format-alt': '{:%d\n%b}'},
        'wireplumber': {'format': '{icon}'},
        'backlight': {'format': '{icon}', 'tooltip-format': 'Brightness: {percent}%'},
        'network': {'format-wifi': '󰤨'},
        'bluetooth': {'format-connected': '󰂱'},
        'custom/desktop-mode': {'format': '{icon}'},
        'custom/updates': {'format': '󰚰\n{}'},
        'cpu': {'format': '󰻠\n{usage}%'},
        'memory': {'format': '󰍛\n{percentage}%'},
        'temperature': {'format': '󰔄\n{temperatureC}°'},
        'battery': {'format': '{icon}\n{capacity}%', 'format-charging': '󰂄\n{capacity}%',
                    'format-plugged': '\n{capacity}%', 'format-alt': '{capacity}%'},
    }
    for key in document.data:
        if key.startswith('disk'): formats[key] = {'format': '󰋊\n{percentage_used}%'}
    for module, values in formats.items():
        if isinstance(document.data.get(module), dict):
            for key, value in values.items(): changes[(module, key)] = value
    saved = list(saved)
    known = {tuple(entry['path']) for entry in saved}
    for path, value in changes.items():
        if path not in known:
            fields, _ = document.members(path[:-1])
            saved.append(dict(path=list(path), exists=path[-1] in fields,
                              value=fields[path[-1]][3] if path[-1] in fields else None))
        text = Document(text).patch(path, value)
    return text, saved
