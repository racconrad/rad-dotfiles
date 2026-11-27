import fcntl
import json
from desktop_style.context import Context


def widget_frame(style=None, ctx=None):
    c = Context(ctx)
    state = c.read(c.STATE / 'widget-frame.json', {})
    choices = state.get('styles', {})
    frame = choices.get('collage', 'none') if isinstance(choices, dict) and 'styles' in state else state.get('frame', 'none')
    return frame if frame in c.WIDGET_FRAMES else 'none'


def with_widget_frame(tokens, ctx=None):
    c = Context(ctx)
    data = json.loads(tokens)
    frame = c.widget_frame(data.get('style'))
    if frame != 'auto':
        data['widgets']['frame'] = frame
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def set_widget_frame(frame, style=None, ctx=None):
    c = Context(ctx)
    if frame not in c.WIDGET_FRAMES:
        raise ValueError('Unknown frame')
    c.STATE.mkdir(parents=True, exist_ok=True)
    with (c.STATE / 'widget-frame.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        c.save(c.STATE / 'widget-frame.json', dict(version=2, styles={'collage': frame}))
    tokens = c.CURRENT / 'tokens.json'
    if tokens.exists():
        from desktop_style.appearance import resolve
        data = json.loads(tokens.read_text())
        data['widgets']['frame'] = resolve('collage', c.PROFILES['collage'], data['colors'])['widgets']['frame']
        c.write(tokens, c.with_widget_frame(json.dumps(data)))
        if c.widgets_available():
            general = json.loads(c.run([c.BIN / 'widgetctl', 'style']).stdout)
            if isinstance(general, dict) and 'frame' in general:
                resolved = frame if frame != 'auto' else 'none'
                c.run([c.BIN / 'widgetctl', 'style', '--frame', resolved])

