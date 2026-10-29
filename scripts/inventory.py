#!/usr/bin/env python3
"""Generate the exact list of files available in the dotfiles installer."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / 'modules.json').read_text())
lines = ['# Raccon Dots files', '',
         'Paths are relative to the target HOME. Only selected modules and their dependencies are installed.', '',
         'The installer also generates `~/.rdot` and `~/.config/raccon-dots/profile.json` with the version and setup selection.', '']
total = 0
for module, metadata in catalog['modules'].items():
    base = ROOT / 'modules' / module / 'files'
    files = sorted(p for p in base.rglob('*') if p.is_file()
                   and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo'))
    total += len(files)
    lines += ['## ' + module, '', metadata['label'] + '.', '']
    for path in files:
        lines.append('- `~/' + path.relative_to(base).as_posix() + '`')
    if not files:
        lines.append("Uses its dependencies' files and/or installs its application package.")
    lines.append('')
lines += ['## Exclusions', '',
          'Orbit (plugin, configuration, hooks and templates), credentials, SSH/GPG keys, application sessions,',
          'browser profiles, histories, caches, databases, backups, personal tasks and notes,',
          'Git identity/authentication, private widget data and machine-specific hardware rules.', '']
(ROOT / 'INVENTORY.md').write_text('\n'.join(lines))
print(f'{total} files available in {len(catalog["modules"])} modules. INVENTORY.md updated.')
