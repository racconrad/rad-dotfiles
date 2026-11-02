import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import capture_ai


class AiSkillsTests(unittest.TestCase):
    def test_capture_keeps_only_skill_sources_and_removes_old_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, repo = Path(tmp, 'home'), Path(tmp, 'repo')
            lock = home / capture_ai.SKILL_LOCK
            lock.parent.mkdir(parents=True)
            lock.write_text(json.dumps({'version': 3, 'lastSelectedAgents': ['claude-code', '--evil'], 'skills': {
                'b': {'source': 'me/pack', 'sourceType': 'github'},
                'a': {'source': 'me/pack', 'sourceType': 'github'},
                'local': {'source': '/home/me/skill', 'sourceType': 'local'},
            }}))
            (home / '.claude.json').write_text('{"mcpServers": {"x": {}}}')
            old = repo / 'modules/ai/files/.claude/settings.json'
            old.parent.mkdir(parents=True)
            old.write_text('{}')
            capture_ai.capture_ai(home, repo)
            files = [p.relative_to(repo).as_posix() for p in repo.rglob('*') if p.is_file()]
            self.assertEqual(files, ['modules/ai/files/' + capture_ai.MANIFEST])
            manifest = json.loads((repo / 'modules/ai/files' / capture_ai.MANIFEST).read_text())
            self.assertEqual(manifest, {'schema': 1, 'agents': ['claude-code'], 'sources': {'me/pack': ['a', 'b']}})

    def test_install_commands_reject_flag_injection(self):
        good = {'agents': ['claude-code'], 'sources': {'me/pack': ['a', 'b']}}
        self.assertEqual(capture_ai.install_commands(good), [[
            'npx', '--yes', 'skills', 'add', 'me/pack', '--global', '--yes',
            '--agent', 'claude-code', '--skill', 'a', 'b']])
        for bad in ({'agents': ['claude-code'], 'sources': {'me/pack': ['--all']}},
                    {'agents': ['claude-code'], 'sources': {'-x/pack': ['a']}},
                    {'agents': [], 'sources': {'me/pack': ['a']}}):
            with self.assertRaises(ValueError):
                capture_ai.install_commands(bad)


if __name__ == '__main__':
    unittest.main()
