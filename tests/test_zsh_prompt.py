"""Exercise the native prompt against real Git states in disposable directories."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'modules/zsh/files/.oh-my-zsh/custom/themes/raccon.zsh-theme'
ANSI = re.compile(r'\x1b\[[0-9;]*m')


@unittest.skipUnless(shutil.which('zsh') and shutil.which('git'), 'requires zsh and git')
class RacconPromptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='raccon-prompt-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / 'repo'
        self.repo.mkdir()
        self.env = {**os.environ, 'TERM': 'xterm-256color', 'HOME': str(self.home),
                    'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_AUTHOR_NAME': 'Prompt Test', 'GIT_COMMITTER_NAME': 'Prompt Test',
                    'GIT_AUTHOR_EMAIL': 'prompt@example.test',
                    'GIT_COMMITTER_EMAIL': 'prompt@example.test'}
        for key in ('SSH_CONNECTION', 'SSH_TTY', 'RACCON_PROMPT_GIT', 'RACCON_PROMPT_ASCII'):
            self.env.pop(key, None)
        self.git('init', '-q', '-b', 'main')
        (self.repo / 'file').write_text('initial\n')
        self.git('add', 'file')
        self.git('commit', '-qm', 'initial')

    def git(self, *args, check=True):
        return subprocess.run(['git', *args], cwd=self.repo, env=self.env,
                              text=True, capture_output=True, check=check)

    def prompt(self, script='true; _raccon_precmd', cwd=None):
        run = subprocess.run(['zsh', '-dfc',
                              'source "$1"\nCOLUMNS=100\n' + script +
                              '\nprint -P -- "$PROMPT"', 'prompt-test', str(THEME)],
                             cwd=cwd or self.repo, env=self.env, text=True,
                             capture_output=True, check=True)
        self.assertEqual(run.stderr, '')
        return ANSI.sub('', run.stdout)

    def test_clean_repo_and_failed_command_duration(self):
        output = self.prompt('_raccon_started=$((SECONDS - 65)); (exit 7); _raccon_precmd')
        self.assertIn('raccon', output)
        self.assertIn('git:main', output)
        self.assertIn('exit 7', output)
        self.assertIn('1m5s', output)
        self.assertEqual(len(output.splitlines()), 2)
        self.assertNotIn('exit ', self.prompt())
        self.assertNotIn('1m5s', self.prompt())

    def test_staged_modified_and_untracked_files(self):
        (self.repo / 'file').write_text('staged\n')
        self.git('add', 'file')
        (self.repo / 'file').write_text('modified again\n')
        (self.repo / 'new').write_text('untracked\n')
        self.assertIn('git:main +*?', self.prompt())

    def test_unborn_and_detached_branches(self):
        self.git('checkout', '-q', '--orphan', 'unborn')
        self.assertIn('git:unborn', self.prompt())
        self.git('checkout', '-q', '--detach', 'main')
        short_oid = self.git('rev-parse', '--short=7', 'HEAD').stdout.strip()
        self.assertIn('git:@' + short_oid[:7], self.prompt())

    def test_ahead_behind_and_conflict(self):
        self.git('branch', 'other')
        self.git('branch', '--set-upstream-to=other', 'main')
        (self.repo / 'file').write_text('main change\n')
        self.git('commit', '-qam', 'main change')
        self.git('checkout', '-q', 'other')
        (self.repo / 'file').write_text('other change\n')
        self.git('commit', '-qam', 'other change')
        self.git('checkout', '-q', 'main')
        self.assertIn('↑1 ↓1', self.prompt())
        self.assertNotEqual(self.git('merge', 'other', check=False).returncode, 0)
        self.assertIn('git:main !', self.prompt())

    def test_literal_branch_and_directory_names(self):
        branch = 'p%F{red}$(>OWNED)'
        self.git('checkout', '-qb', branch)
        output = self.prompt()
        self.assertIn('git:' + branch, output)
        self.assertFalse((self.repo / 'OWNED').exists())
        directory = self.home / 'd%F{red}$(>OWNED)'
        directory.mkdir()
        self.assertIn(directory.name, self.prompt(cwd=directory))
        self.assertFalse((directory / 'OWNED').exists())

    def test_narrow_ascii_prompt_and_git_opt_out(self):
        self.env['RACCON_PROMPT_ASCII'] = '1'
        self.env['RACCON_PROMPT_GIT'] = '0'
        output = self.prompt('COLUMNS=32; true; _raccon_precmd')
        self.assertTrue(output.startswith('+- '))
        self.assertNotIn('git:', output)
        self.assertNotIn('raccon', output)
        self.assertTrue(all(len(line) <= 32 for line in output.splitlines()))

    def test_no_repository_and_repeat_sourcing(self):
        output = self.prompt('source "$1"; source "$1"; '
                             'print -r -- ${#${(M)precmd_functions:#_raccon_precmd}} '
                             '${#${(M)preexec_functions:#_raccon_preexec}}; '
                             'true; _raccon_precmd', cwd=self.home)
        self.assertTrue(output.startswith('1 1\n'))
        self.assertNotIn('git:', output)

    def test_long_path_branch_and_metadata_fit_terminal(self):
        self.git('checkout', '-qb', 'a-very-long-branch-name-for-a-narrow-terminal')
        directory = self.repo / ('long-directory-' * 5)
        directory.mkdir()
        self.env['SSH_CONNECTION'] = 'test'
        for width in (32, 40, 60, 80, 100):
            with self.subTest(width=width):
                output = self.prompt(f'COLUMNS={width}; _raccon_started=$((SECONDS - 5)); '
                                     '(exit 123); _raccon_precmd', cwd=directory)
                self.assertIn('exit 123', output)
                self.assertTrue(all(len(line) <= width for line in output.splitlines()), output)


if __name__ == '__main__':
    unittest.main()
