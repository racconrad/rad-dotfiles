"""Master-to-repository review, filtering and rollback in disposable directories."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import master


class MasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='raccon master ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.repo = self.base / 'repo'
        self.staged = self.base / 'staged'
        self.backups = self.base / 'backups'
        for directory in (self.home, self.repo, self.staged):
            directory.mkdir()

    def write(self, root, relative, text, mode=0o644):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)
        return path

    def test_review_normalizes_source_and_does_not_write_to_repo(self):
        self.write(self.home, '.zshrc', 'export SECRET_PROJECT=1\n')
        self.write(self.home, '.zprofile', 'export PATH="' + str(self.home) + '/.local/bin:$PATH"\n')
        repo_path = 'modules/zsh/files/.zprofile'
        original = self.write(self.repo, repo_path, 'uncommitted user work\n')
        master.snapshot(self.home, self.staged, {'zsh'})
        changes = master.compare(self.repo, self.staged, {'zsh'})
        # The personal .zshrc is never captured; the repo keeps its own base.
        self.assertEqual([c.path for c in changes], [repo_path])
        self.assertIn(b'@RDOT_HOME@/.local/bin', changes[0].after)
        self.assertNotIn(str(self.home).encode(), changes[0].after)
        self.assertEqual(changes[0].before, b'uncommitted user work\n')
        self.assertEqual(original.read_text(), 'uncommitted user work\n')
        self.assertEqual(master.desktop.ROOT, ROOT)

    def test_capture_add_modify_delete_and_back_up_previous_work(self):
        original = self.write(self.repo, 'modules/ai/files/old', 'old skill')
        changed = self.write(self.repo, 'modules/ai/files/settings', 'local uncommitted setting', 0o600)
        self.write(self.staged, 'modules/ai/files/settings', 'master setting', 0o600)
        self.write(self.staged, 'modules/ai/files/script', '#!/bin/sh\ntrue\n', 0o755)
        changes = master.compare(self.repo, self.staged, {'ai'})
        self.assertEqual({c.status for c in changes}, {'added', 'modified', 'deleted'})
        backup = master.apply_changes(self.repo, changes, self.backups)
        self.assertFalse(original.exists())
        self.assertEqual(changed.read_text(), 'master setting')
        self.assertEqual((backup / 'files/modules/ai/files/settings').read_text(), 'local uncommitted setting')
        self.assertEqual((backup / 'files/modules/ai/files/old').read_text(), 'old skill')
        self.assertTrue((self.repo / 'modules/ai/files/script').stat().st_mode & 0o111)
        self.assertEqual(master.compare(self.repo, self.staged, {'ai'}), [])
        self.assertIsNone(master.apply_changes(self.repo, [], self.backups))

    def test_write_failure_rolls_back_previous_files(self):
        first = self.write(self.repo, 'modules/zsh/files/first', 'first original')
        second = self.write(self.repo, 'modules/zsh/files/second', 'second original')
        self.write(self.staged, 'modules/zsh/files/first', 'first master')
        self.write(self.staged, 'modules/zsh/files/second', 'second master')
        changes = master.compare(self.repo, self.staged, {'zsh'})
        original_write = master.atomic_write
        failed = False

        def fail_once(path, data, mode):
            nonlocal failed
            if path == second and not failed:
                failed = True
                raise OSError('simulated full disk')
            original_write(path, data, mode)

        with patch.object(master, 'atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError):
                master.apply_changes(self.repo, changes, self.backups)
        self.assertEqual(first.read_text(), 'first original')
        self.assertEqual(second.read_text(), 'second original')

    def test_concurrent_edit_and_repository_links_are_rejected(self):
        relative = 'modules/zsh/files/.zshrc'
        current = self.write(self.repo, relative, 'old')
        self.write(self.staged, relative, 'master')
        changes = master.compare(self.repo, self.staged, {'zsh'})
        current.write_text('new local edit')
        with self.assertRaises(ValueError):
            master.apply_changes(self.repo, changes, self.backups)
        self.assertEqual(current.read_text(), 'new local edit')
        current.unlink()
        outside = self.write(self.home, 'private', 'private')
        current.symlink_to(outside)
        with self.assertRaises(ValueError):
            master.compare(self.repo, self.staged, {'zsh'})
        with self.assertRaises(ValueError):
            master.safe_path(self.repo, '../outside')

    def test_ai_capture_filters_credentials_and_other_modules(self):
        self.write(self.home, '.claude/settings.json', json.dumps({'model': 'opus', 'env': {'TOKEN': 'private'}}))
        self.write(self.home, '.claude/.credentials.json', 'private')
        self.write(self.home, '.agents/.skill-lock.json', json.dumps(
            {'skills': {'a': {'source': 'me/pack', 'sourceType': 'github'}}}))
        master.snapshot(self.home, self.staged, {'ai'})
        self.write(self.staged, 'modules/zsh/files/irrelevant', 'ignore')
        changes = master.compare(self.repo, self.staged, {'ai'})
        self.assertTrue(changes)
        self.assertTrue(all(c.module == 'ai' for c in changes))
        self.assertNotIn(b'private', b''.join(c.after or b'' for c in changes))

    def test_cli_register_json_capture_and_repeat_capture(self):
        self.write(self.home, '.zshrc', 'export EDITOR=nvim\n')
        self.write(self.home, '.zprofile', '# profile\n')
        self.write(self.home, '.oh-my-zsh/custom/themes/raccon.zsh-theme', 'PROMPT=hello\n')
        with patch.object(master, 'ROOT', self.repo), patch.dict(os.environ, {'HOME': str(self.home)}):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(master.main(['master']), 0)
            settings = json.loads((self.home / '.config/raccon-dots/master.json').read_text())
            self.assertEqual(settings['home'], str(self.home))
            output = io.StringIO()
            with redirect_stdout(output):
                master.main(['changes', '--modules', 'zsh', '--json'])
            report = json.loads(output.getvalue())
            self.assertEqual(len(report['changes']), 2)
            self.assertFalse((self.repo / 'modules').exists())
            with redirect_stdout(io.StringIO()):
                master.main(['capture', '--modules', 'zsh'])
                master.main(['capture', '--modules', 'zsh'])
            self.assertEqual((self.repo / 'modules/zsh/files/.zprofile').read_text(), '# profile\n')
            self.assertFalse((self.repo / 'modules/zsh/files/.zshrc').exists())


if __name__ == '__main__':
    unittest.main()
