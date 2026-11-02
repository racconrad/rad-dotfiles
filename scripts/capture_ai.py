"""Record which skills.sh skills are installed, and reinstall them with `npx skills add`.

Only skill names and their public sources are kept: no MCP servers, app
settings, instructions or skill files.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL_LOCK = '.agents/.skill-lock.json'
MANIFEST = '.config/raccon-dots/ai-skills.json'
SOURCE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+$')
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
# Kept for master.py, which scans captured text before writing.
SECRET = re.compile(
    r'-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----|'
    r'\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|'
    r'gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|'
    r'AIza[0-9A-Za-z-_]{35}|AKIA[A-Z0-9]{16}|'
    r'xox[baprs]-[0-9A-Za-z]{10,})\b|'
    r'(?i:\bBearer\s+[A-Za-z0-9._-]{20,})|'
    r'(?i:(?:api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\'\"][A-Za-z0-9._-]{16,}[\'\"])'
)


def manifest_from_lock(lock):
    """Group installed skills by GitHub source; anything else cannot be re-downloaded."""
    sources = {}
    for name, info in sorted(lock.get('skills', {}).items()):
        if not isinstance(info, dict):
            continue
        source = info.get('source', '')
        if info.get('sourceType') == 'github' and SOURCE.match(source) and NAME.match(name):
            sources.setdefault(source, []).append(name)
    agents = [a for a in lock.get('lastSelectedAgents', []) if isinstance(a, str) and NAME.match(a)]
    return {'schema': 1, 'agents': agents or ['claude-code', 'codex'], 'sources': sources}


def install_commands(manifest):
    agents = manifest.get('agents', [])
    if not agents or not all(isinstance(a, str) and NAME.match(a) for a in agents):
        raise ValueError('Invalid agent list in manifest')
    commands = []
    for source, names in manifest.get('sources', {}).items():
        # Validated so a manifest entry can never become an npx flag.
        if not SOURCE.match(source) or not names or not all(isinstance(n, str) and NAME.match(n) for n in names):
            raise ValueError(f'Invalid skill entry in manifest: {source}')
        commands.append(['npx', '--yes', 'skills', 'add', source, '--global', '--yes', '--agent', *agents, '--skill', *names])
    return commands


def capture_ai(home, root=ROOT):
    lock = home / SKILL_LOCK
    if not lock.is_file():
        raise ValueError(f'No {SKILL_LOCK} in this HOME; previous snapshot kept')
    data = json.dumps(manifest_from_lock(json.loads(lock.read_text())), indent=2) + '\n'
    destination = root / 'modules/ai/files'
    target = destination / MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data)
    # The module holds only the manifest; drop anything an older exporter left.
    for old in destination.rglob('*'):
        if old.is_file() and old != target:
            old.unlink()
    for folder in sorted((p for p in destination.rglob('*') if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    return [{'module': 'ai', 'path': MANIFEST}]


def main(argv):
    if len(argv) != 1:
        raise SystemExit('usage: capture_ai.py MANIFEST  (installs the listed skills with npx skills)')
    for command in install_commands(json.loads(Path(argv[0]).read_text())):
        print('+ ' + ' '.join(command), flush=True)
        subprocess.run(command, stdin=subprocess.DEVNULL, check=True)


if __name__ == '__main__':
    main(sys.argv[1:])
