"""User-owned home shortcuts with atomic edits and legacy favorites migration."""
import fcntl
import hashlib
import json
import os

SHORTCUTS = {
    'shortcut:browser': dict(name='Browser', icon='web-browser', action='shortcut', value='browser'),
    'shortcut:files': dict(name='Files', icon='system-file-manager', action='shortcut', value='files'),
    'shortcut:terminal': dict(name='Terminal', icon='utilities-terminal', action='shortcut', value='terminal'),
}
LIMIT = 6


def load(state, strict=False):
    path = state / 'home-apps.json'
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('items'), list):
            raise ValueError('Invalid main-menu shortcut settings.')
        keys = data['items']
        if len(keys) > LIMIT or any(not isinstance(key, str) or not key or len(key) > 1024 for key in keys):
            raise ValueError('Invalid main-menu shortcut settings.')
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate main-menu shortcut settings.')
        return keys
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        if strict:
            raise ValueError('Cannot edit saved main-menu shortcuts. Restore defaults to recover.') from None
        return list(SHORTCUTS)
    try:
        legacy = json.loads((state / 'favorites.json').read_text())
    except (OSError, ValueError):
        legacy = []
    keys = list(SHORTCUTS)
    if isinstance(legacy, list):
        for key in legacy:
            if isinstance(key, str) and key and key not in keys and len(keys) < LIMIT:
                keys.append(key)
    return keys


def reference(key):
    return key if key in SHORTCUTS else hashlib.sha256(key.encode()).hexdigest()


def presentation(state, catalog):
    keys = load(state)
    by_id = {app['id']: app for app in catalog}
    items = []
    for position, key in enumerate(keys):
        if key in SHORTCUTS:
            item = dict(SHORTCUTS[key], has_file=False, file='', available=True)
        elif key in by_id:
            app = by_id[key]
            item = dict(name=app['name'], icon=app['icon'], action='launch', value=app['token'],
                        has_file=app.get('has_file', False), file=app.get('file', ''), available=True)
        else:
            item = dict(name=key.removesuffix('.desktop'), icon='application-x-executable',
                        action='launch', value=reference(key), has_file=False, file='', available=False)
        items.append(dict(item, key=key, ref=reference(key), position=position,
                          can_move_previous=position > 0, can_move_next=position < len(keys) - 1))
    return dict(home_count=len(keys), home_limit=LIMIT,
                apps=[dict(app, key=app['id'], ref=reference(app['id']), pinned=app['id'] in keys) for app in catalog],
                favorites=[items[i:i+3] for i in range(0, len(items), 3)],
                shortcuts=[dict(item, key=key, ref=key, pinned=key in keys) for key, item in SHORTCUTS.items()])


def edit(state, catalog, args):
    if not args or args[0] not in ('add', 'remove', 'move', 'reset'):
        raise ValueError('Invalid main-menu shortcut action.')
    action = args[0]
    count = {'add': 2, 'remove': 2, 'move': 3, 'reset': 1}[action]
    if len(args) != count or action == 'move' and args[2] not in ('previous', 'next'):
        raise ValueError('Invalid main-menu shortcut arguments.')
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'home-apps.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        keys = load(state, strict=action != 'reset')
        if action == 'reset':
            updated = list(SHORTCUTS)
        else:
            candidates = set(keys) | set(SHORTCUTS) | {app['id'] for app in catalog}
            key = args[1] if args[1] in candidates else next((key for key in candidates if reference(key) == args[1]), None)
            if key is None:
                raise ValueError('Application is no longer available.')
            updated = keys.copy()
            if action == 'add':
                if key not in SHORTCUTS and not any(app['id'] == key for app in catalog):
                    raise ValueError('Application is no longer available.')
                if key in updated:
                    return
                if len(updated) >= LIMIT:
                    raise ValueError('Main menu is full. Remove a shortcut before adding another.')
                updated.append(key)
            else:
                if key not in updated:
                    raise ValueError('Shortcut is not in the main menu.')
                index = updated.index(key)
                if action == 'remove':
                    updated.pop(index)
                else:
                    target = index + (-1 if args[2] == 'previous' else 1)
                    if 0 <= target < len(updated):
                        updated[index], updated[target] = updated[target], updated[index]
        path = state / 'home-apps.json'
        temporary = path.with_name(f'.home-apps-{os.getpid()}.json')
        try:
            temporary.write_text(json.dumps(dict(version=1, items=updated), ensure_ascii=False))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
