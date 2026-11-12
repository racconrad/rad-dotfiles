"""Opt-in, bounded application history; search text is never accepted here."""
import fcntl
import json
import os
import tempfile

import home_apps

LIMIT = 6
NAME = 'recent-apps.json'


def load(state):
    try:
        path = state / NAME
        if path.stat().st_size > 16384:
            return dict(enabled=False, items=[])
        data = json.loads(path.read_text())
        if (not isinstance(data, dict) or data.get('version') != 1
                or type(data.get('enabled')) is not bool or not isinstance(data.get('items'), list)
                or len(data['items']) > LIMIT or any(not isinstance(key, str) or not key or len(key) > 1024 for key in data['items'])
                or len(set(data['items'])) != len(data['items'])):
            raise ValueError('Invalid recent applications.')
        return data
    except (OSError, ValueError):
        return dict(enabled=False, items=[])


def change(state, action, key=None):
    if action not in ('enable', 'disable', 'clear', 'record'):
        raise ValueError('Invalid recent applications action.')
    if action == 'record':
        if not load(state)['enabled']:
            return
        if not isinstance(key, str) or not key or len(key) > 1024:
            raise ValueError('Invalid recent application.')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(state / 'recent-apps.lock', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = load(state)
        if action == 'record':
            if not value['enabled']:
                return
            value['items'] = [key] + [item for item in value['items'] if item != key][:LIMIT - 1]
        elif action == 'clear':
            value['items'] = []
        else:
            value['enabled'] = action == 'enable'
        value['version'] = 1
        descriptor, temporary = tempfile.mkstemp(prefix='.recent-apps-', dir=state)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, state / NAME)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def record(state, key):
    change(state, 'record', key)


def edit(state, action):
    if action not in ('enable', 'disable', 'clear'):
        raise ValueError('Invalid recent applications action.')
    change(state, action)


def presentation(state, catalog):
    value = load(state)
    by_id = {app['id']: dict(app, action='launch', value=app['token']) for app in catalog}
    by_id.update({key: dict(item, id=key, has_file=False, file='') for key, item in home_apps.SHORTCUTS.items()})
    items = [by_id[key] for key in value['items'] if key in by_id] if value['enabled'] else []
    return dict(recent_enabled=value['enabled'], recent=items)
