#!/usr/bin/env python3
"""Export the owner's portable widget layouts and appearance, never private content."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISUAL_OPTIONS = {'skin', 'fx', 'background', 'border', 'width', 'height', 'workspace', 'always',
    'anim', 'anim_out', 'header', 'padding', 'card_style', 'chars', 'accent', 'opacity',
    'font', 'font_size', 'radius', 'align', 'format', 'seconds', 'orientation',
    'window_frame', 'frame_controls', 'frame_folded'}
PRIVATE_KINDS = {'command', 'api', 'photo', 'image', 'note', 'obsidian'}


def portable_layout(document, name=None):
    widgets = []
    for raw in document.get('widgets', []):
        kind = raw.get('window', '')
        options = {k: v for k, v in raw.get('opts', {}).items() if k in VISUAL_OPTIONS and isinstance(v, (str, int, float, bool))}
        if kind == 'disks':
            options['mounts'] = '/'
        if kind in ('chest', 'apps'):
            # Launchers list the owner's installed apps; each user adds their own.
            options['launchers'] = '[]'
        widgets.append({'id': raw['id'], 'window': kind,
            'show': bool(raw.get('show', True)) and kind not in PRIVATE_KINDS,
            'anchor': raw.get('anchor', 'top-left'), 'x': int(raw.get('x', 0)),
            'y': int(raw.get('y', 0)), 'opts': options})
    return {'version': 1, 'name': name or document.get('name', 'Personal'),
            'desc': document.get('desc', 'Personal desktop layout'),
            'animation': document.get('animation', {}), 'widgets': widgets}


def put(module, relative, document):
    path = ROOT / 'modules' / module / 'files' / '.config/eww' / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')


def capture(home):
    config = home / '.config/eww'
    profiles = {}
    descriptions = {'Trabajo': 'Work: clock, tasks, habits, system and app chest.',
        'Gaming': 'Gaming: compact hardware and music in the corners.',
        'Dashboard': 'Dashboard: clock, music, app chest, system and disks.',
        'Cyberpunk': 'Cyberpunk: clock, processes, cat, GitHub and system.',
        'silly': 'Playful layout; command and photo widgets start disabled.',
        'Personal': 'Main layout. Command, photo and note widgets start disabled.'}
    sources = [(p.stem, json.loads(p.read_text())) for p in sorted((config / 'profiles').glob('*.json'))]
    personal = json.loads((config / 'instances.json').read_text())
    personal['animation'] = json.loads((config / 'animation.json').read_text())
    sources.append(('Personal', personal))
    for name, source in sources:
        data = portable_layout(source, name)
        data['desc'] = descriptions.get(name, 'Personal saved layout.')
        put('widgets-profiles', f'profiles/{name}.json', data)
        kinds = {w['window'] for w in data['widgets'] if w['show']}
        required = [key for kind, key in [('music', 'widgets-music'), ('github', 'widgets-github'),
                     ('minecraft', 'widgets-minecraft')] if kind in kinds]
        profiles[name] = {'label': name, 'description': data['desc'], 'widgets': len(data['widgets']),
            'active_widgets': sum(w['show'] for w in data['widgets']), 'requires': required}
    preferred = ['Personal', 'Trabajo', 'Gaming', 'Dashboard', 'Cyberpunk', 'silly']
    profiles = {name: profiles[name] for name in [*preferred, *profiles] if name in profiles}
    style = json.loads((config / 'style.json').read_text())
    motion = json.loads((config / 'animation.json').read_text())
    editor = json.loads((config / 'editor.json').read_text())
    put('widgets-profiles', 'editor.json', {k: v for k, v in editor.items() if k in ('grid', 'step', 'sizes')})
    themes = {'personal': {'label': 'Personal raccoon', 'description': 'Your current global widget appearance.', 'style': style},
              'quiet': {'label': 'Quiet', 'description': 'Minimal cards, no ambient effects.', 'style': {'skin': 'minimal', 'fx': 'none', 'background': 'surface'}},
              'pixel': {'label': 'Pixel', 'description': 'Pixel skin with a subtle accent and deep background.', 'style': {'skin': 'pixel', 'fx': 'glow', 'background': 'deep'}},
              'terminal': {'label': 'Terminal', 'description': 'Terminal-style widgets with no ambient motion.', 'style': {'skin': 'terminal', 'fx': 'none', 'background': 'deep'}}}
    motions = {'personal': {'label': 'Personal / 60 FPS', 'description': 'Your current entry/exit effects, workspace timing and concurrency.', 'settings': motion},
               'balanced': {'label': 'Balanced / 24 FPS', 'description': 'Short fades and lower refresh rate.', 'settings': {**motion, 'anim_in': 'fade', 'anim_out': 'fade', 'type': 'fade', 'fps': 24, 'duration_in': 220, 'duration_out': 180}},
               'quiet': {'label': 'Quiet / no transitions', 'description': 'Disable transitions for a quieter desktop.', 'settings': {**motion, 'anim_in': 'none', 'anim_out': 'none', 'type': 'none', 'when': 'never', 'fps': 12, 'palette_animation': False}}}
    for key, data in themes.items():
        put('widgets-themes', f'presets/themes/{key}.json', data['style'])
    for key, data in motions.items():
        put('widgets-motion', f'presets/motion/{key}.json', data['settings'])
    put('widgets', 'style.json', style)
    put('widgets', 'animation.json', motion)
    bundle = {'profiles': profiles, 'themes': {k: {a: b for a, b in v.items() if a != 'style'} for k, v in themes.items()},
              'motions': {k: {a: b for a, b in v.items() if a != 'settings'} for k, v in motions.items()},
              'defaults': {'profile': 'keep', 'profiles': list(profiles), 'theme': 'personal', 'motion': 'personal', 'install': 'auto',
                'components': ['widgets-profiles', 'widgets-themes', 'widgets-motion', 'widgets-palette']}}
    (ROOT / 'widget-presets.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported {len(profiles)} portable layouts, {len(themes)} themes and {len(motions)} motion presets.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-home', type=Path, required=True)
    capture(parser.parse_args().from_home.resolve())
