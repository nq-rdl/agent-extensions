"""PR 297 regressions: containment, persistence failures, and resumable history."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from test_sql_review_scripts import Project, SQL_V1, SQL_V2, review_doc, run, item
from test_sql_review_hooks import GUARD, PREFLIGHT, env_for, run_hook, write_event, decision


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql('q.sql', SQL_V1)
        self.d = self.p.review_dir('q')

    def reviewed(self):
        self.p.write_json('q', 'review.json', review_doc('q', 'q.sql'))
        self.assertEqual(run(['snapshot', 'q', 'q.sql'], self.p.root).returncode, 0)

    def test_unsafe_paths_and_slugs_are_rejected(self):
        for slug in ['', '.', '..', '../../outside', '/tmp/outside']:
            for command in [['snapshot', slug, 'q.sql'], ['render', slug, 'review'], ['delta', slug], ['impact', slug]]:
                with self.subTest(command=command):
                    self.assertNotEqual(run(command, self.p.root).returncode, 0)
        for command in [['slug', '../outside.sql'], ['fingerprint', '../outside.sql'],
                        ['move', '../outside.sql', 'q.sql'], ['move', 'q.sql', '../outside.sql'],
                        ['init', '--apply', '../../scripts/sqlreview.sh']]:
            with self.subTest(command=command):
                self.assertNotEqual(run(command, self.p.root).returncode, 0)
        self.assertFalse((self.p.root / 'scripts').exists())

    def test_slug_encoding_is_distinct_and_usable(self):
        paths = ['a/b.sql', 'a__b.sql', '.sql', '..sql', '...sql', 'odd name (1).sql', 'odd-name--1-.sql', 'a%20b.sql', 'a b.sql', '~user.sql', "quote's.sql"]
        slugs = []
        for path in paths:
            result = run(['slug', path], self.p.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            slug = result.stdout.strip()
            slugs.append(slug)
            doc = review_doc(slug, path)
            self.assertEqual(run(['check', '--stdin'], self.p.root, stdin=json.dumps(doc)).returncode, 0)
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_nested_cwd_resolves_project_paths(self):
        nested = self.p.root / 'nested'
        nested.mkdir()
        result = run(['fingerprint', 'q.sql'], nested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['sql_sha256'], hashlib.sha256(SQL_V1.encode()).hexdigest())

    def test_symlinks_cannot_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'secret.sql'
            target.write_text('secret')
            (self.p.root / 'alias.sql').symlink_to(target)
            self.assertEqual(run(['fingerprint', 'alias.sql'], self.p.root).returncode, 2)
            (self.d / 'source.sql').symlink_to(target)
            self.p.write_json('q', 'review.json', review_doc('q', 'q.sql'))
            self.assertNotEqual(run(['delta', 'q'], self.p.root).returncode, 0)
            self.assertNotIn('secret', run(['delta', 'q'], self.p.root).stdout)

    def test_checker_rejects_malformed_shapes_and_json_streams(self):
        for key, value in [('revision', 1.5), ('sql_path', '../../outside.sql'), ('slug', '..'),
                           ('slug', 'wrong'), ('inputs', 'bad'), ('outputs', [{}]),
                           ('logic', 'bad'), ('logic', [{'step': 1, 'lines': [5, 3]}]),
                           ('open_questions', 'bad'), ('changes', 'bad'),
                           ('assumptions', [item('A1', 'x', rationale=None)]),
                           ('limitations', [item('L1', 'x', location={'lines': 'bad'})])]:
            with self.subTest(key=key, value=value):
                doc = review_doc('q', 'q.sql', **{key: value}) if key not in ('slug', 'sql_path') else dict(review_doc('q', 'q.sql'), **{key: value})
                self.assertEqual(run(['check', '--stdin'], self.p.root, stdin=json.dumps(doc)).returncode, 4)
        stream = json.dumps(review_doc('q', 'q.sql')) * 2
        self.assertEqual(run(['check', '--stdin'], self.p.root, stdin=stream).returncode, 4)

    def test_failed_write_or_changed_fingerprint_does_not_advance_baseline(self):
        self.reviewed()
        (self.p.root / 'q.sql').write_text(SQL_V2)
        # Final Write did not happen: the old final document cannot authorize new bytes.
        result = run(['snapshot', 'q', 'q.sql'], self.p.root)
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.d / 'source.sql').read_text(), SQL_V1)
        self.assertEqual(run(['delta', 'q'], self.p.root).returncode, 10)
        # A final Write succeeds but snapshot has not run: never report current.
        self.p.write_json('q', 'review.json', review_doc('q', 'q.sql', revision=2))
        self.assertEqual(run(['delta', 'q'], self.p.root).returncode, 10)
        self.assertEqual(run(['snapshot', 'q', 'q.sql'], self.p.root).returncode, 0)
        self.assertEqual((self.d / 'history/1.sql').read_text(), SQL_V1)
        self.assertEqual((self.d / 'history/2.sql').read_text(), SQL_V2)
        self.assertEqual(run(['delta', 'q'], self.p.root).returncode, 0)

    def test_move_invalidates_unchanged_sql_and_removes_render(self):
        self.reviewed()
        self.assertEqual(run(['render', 'q', 'review'], self.p.root).returncode, 0)
        (self.p.root / 'q.sql').rename(self.p.root / 'renamed.sql')
        result = run(['move', 'q.sql', 'renamed.sql'], self.p.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(run(['delta', 'renamed'], self.p.root).returncode, 10)
        self.assertFalse((self.p.root / '.sqlreview/reviews/renamed/review.md').exists())
        status = json.loads(run(['status', '--json'], self.p.root).stdout)
        self.assertEqual(status['reviews'][0]['state'], 'stale')

    def test_copy_and_render_failures_are_reported(self):
        self.reviewed()
        bindir = self.p.root / 'bin'
        bindir.mkdir()
        cp = bindir / 'cp'
        cp.write_text('#!/bin/sh\nexit 1\n')
        cp.chmod(0o755)
        env = {'PATH': str(bindir) + os.pathsep + os.environ['PATH']}
        self.assertNotEqual(run(['snapshot', 'q', 'q.sql'], self.p.root, env=env).returncode, 0)
        self.assertNotEqual(run(['init', '--apply', 'config.json'], self.p.root, env=env).returncode, 0)
        with tempfile.TemporaryDirectory() as fresh:
            self.assertNotEqual(run(['init'], fresh, env=env).returncode, 0)
        (self.d / 'review.md').mkdir()
        self.assertNotEqual(run(['render', 'q', 'review'], self.p.root).returncode, 0)

    def test_markdown_table_escapes_cells(self):
        doc = review_doc('q', 'q.sql', assumptions=[item('A1', 'a|b\nc', rationale='x|y', confirmed_by='a\nb')])
        self.p.write_json('q', 'review.json', doc)
        self.assertEqual(run(['render', 'q', 'review'], self.p.root).returncode, 0)
        md = (self.d / 'review.md').read_text()
        self.assertIn('a&#124;b<br>c', md)
        row = next(line for line in md.splitlines() if line.startswith('| A1 |'))
        self.assertEqual(row.count('|'), 7)

    def test_drafts_are_resumable_and_missing_cwd_is_silent(self):
        (self.d / 'scope.draft.json').write_text('{}')
        status = json.loads(run(['status', '--json'], self.p.root).stdout)
        self.assertEqual(status['counts']['draft'], 1)
        result = run_hook(PREFLIGHT, {'cwd': str(self.p.root)}, env_for())
        self.assertIn('resume', result.stdout)
        for event in [{}, 'bad json', {'cwd': ''}]:
            self.assertEqual(run_hook(PREFLIGHT, event, env_for(), cwd=self.p.root).stdout, '')

    def test_guard_without_any_parser_denies(self):
        bindir = self.p.root / 'bin'
        bindir.mkdir()
        (bindir / 'bash').symlink_to(shutil.which('bash'))
        result = run_hook(GUARD, {}, env_for(PATH=str(bindir)))
        self.assertEqual(decision(result)['permissionDecision'], 'deny')

    def test_guard_remediation_and_destination_binding(self):
        result = run_hook(GUARD, write_event(self.d / 'scope.md', '', self.p.root), env_for())
        reason = decision(result)['permissionDecisionReason']
        self.assertIn('scope.json', reason)
        self.assertNotIn('scope.md.json', reason)
        result = run_hook(GUARD, write_event(self.d / 'scope.json', '{}', self.p.root), env_for())
        self.assertIn('scope.draft.json', decision(result)['permissionDecisionReason'])
        result = run_hook(GUARD, write_event(self.d / 'review.json', json.dumps(review_doc()), self.p.root), env_for())
        self.assertEqual(decision(result)['permissionDecision'], 'deny')
