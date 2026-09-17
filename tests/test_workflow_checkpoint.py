"""Validate checkpoint paths against real Git worktrees and filesystem aliases."""
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/rdl-workflow/scripts/checkpoint.sh'


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='checkpoint space ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.checkpoint = self.root / '.superpowers/rdl-workflow/one.json'
        self.exclude = self.root / '.git/info/exclude'

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args],
                              check=True, capture_output=True, text=True).stdout

    def validate(self, checkpoint=None):
        return subprocess.run(['bash', str(SCRIPT), str(self.root), str(checkpoint or self.checkpoint)],
                              capture_output=True, text=True)

    def ignore(self):
        self.exclude.write_text('/.superpowers/rdl-workflow/one.json\n')

    def test_ignored_checkpoint_preserves_clean_status(self):
        self.ignore()
        self.assertEqual(self.validate().returncode, 0)
        self.assertFalse(self.checkpoint.parent.exists())  # validator is read-only
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_text('{}')
        self.assertEqual(self.validate().returncode, 0)
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=all'), '')

    def test_unignored_and_tracked_state_rejected(self):
        self.assertIn('must be ignored', self.validate().stderr)
        self.ignore()
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_text('{}')
        self.git('add', '-f', str(self.checkpoint))
        self.assertIn('must not be tracked', self.validate().stderr)

    def test_shared_symlink_parent_rejected_without_writing(self):
        self.ignore()
        shared = self.root.parent / 'shared'
        shared.mkdir()
        (self.root / '.superpowers').symlink_to(shared, target_is_directory=True)
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stderr)
        self.assertEqual(list(shared.iterdir()), [])

    def test_final_and_dangling_symlinks_rejected(self):
        self.ignore()
        self.checkpoint.parent.mkdir(parents=True)
        target = self.root.parent / 'state.json'
        self.checkpoint.symlink_to(target)
        self.assertIn('symlink', self.validate().stderr)
        target.write_text('preserve')
        self.assertIn('symlink', self.validate().stderr)
        self.assertEqual(target.read_text(), 'preserve')

    def test_outside_and_traversal_paths_rejected(self):
        for path in [self.root.parent / 'outside.json', str(self.root) + '/state/../one.json']:
            self.assertNotEqual(self.validate(path).returncode, 0)

    def test_linked_worktree_uses_local_git_exclusion(self):
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.org',
                 'commit', '--allow-empty', '-qm', 'Initial')
        linked = self.root.parent / 'linked'
        self.git('worktree', 'add', '-qb', 'feature', str(linked))
        self.ignore()
        self.root = linked
        self.checkpoint = linked / '.superpowers/rdl-workflow/one.json'
        self.assertEqual(self.validate().returncode, 0)
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_text('{}')
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=all'), '')
