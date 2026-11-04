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
        self.p.commit()
        fp = json.loads(run(['fingerprint', 'q.sql'], self.p.root).stdout)
        self.p.write_json('q', 'review.json', review_doc('q', **fp))
        self.assertEqual(run(['snapshot', 'q', 'q.sql'], self.p.root).returncode, 0)

    def test_snapshot_after_reassessment_clears_the_move_marker(self):
        self.reviewed()
        self.assertEqual(run(['move', 'q.sql', 'renamed.sql'], self.p.root).returncode, 0)
        moved = self.d.parent / 'renamed'
        self.assertTrue((moved / 'rebind-required').is_file())
        (self.p.root / 'q.sql').rename(self.p.root / 'renamed.sql')
        # Before reassessment the recorded commit has no SQL at the new path: snapshot fails
        # and the marker stays.
        self.p.commit('move sql')
        self.assertNotEqual(run(['snapshot', 'renamed', 'renamed.sql'], self.p.root).returncode, 0)
        self.assertTrue((moved / 'rebind-required').is_file())
        fp = json.loads(run(['fingerprint', 'renamed.sql'], self.p.root).stdout)
        self.p.write_json('renamed', 'review.json', review_doc('renamed', **fp))
        self.p.commit('reassessed review')
        result = run(['snapshot', 'renamed', 'renamed.sql'], self.p.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((moved / 'rebind-required').exists())
        rows = json.loads(run(['status', '--json'], self.p.root).stdout)['reviews']
        self.assertNotEqual({r['slug']: r['state'] for r in rows}['renamed'], 'stale')

    def test_moved_reviews_keep_every_recorded_revision_readable(self):
        outside = tempfile.TemporaryDirectory()  # drafts and outputs stay out of the project
        self.addCleanup(outside.cleanup)
        out = Path(outside.name)

        def publish(slug, revision, path):
            fp = json.loads(run(['fingerprint', path], self.p.root).stdout)
            draft = out / 'draft.json'
            draft.write_text(json.dumps(review_doc(slug, revision=revision, **fp)))
            result = run(['publish', slug, 'review', str(draft)], self.p.root)
            self.assertEqual(result.returncode, 0, result.stderr)

        def moved(old, new, slug):
            self.assertEqual(run(['move', old, new], self.p.root).returncode, 0)
            (self.p.root / old).rename(self.p.root / new)
            self.p.commit(f'move to {new}')
            # Carry evidence comes from the archived binding before reassessment, too.
            draft = out / 'carry.json'
            current = json.loads((self.d.parent / slug / 'review.json').read_text())
            draft.write_text(json.dumps(dict(current, revision=current['revision'] + 1)))
            carry = run(['carryforward', slug, 'review', str(draft)], self.p.root)
            self.assertEqual(carry.returncode, 0, carry.stderr)

        self.p.commit()
        publish('q', 1, 'q.sql')
        self.p.sql('q.sql', SQL_V2)
        self.p.commit('v2')
        publish('q', 2, 'q.sql')
        moved('q.sql', 'renamed.sql', 'renamed')
        publish('renamed', 3, 'renamed.sql')
        moved('renamed.sql', 'again.sql', 'again')
        publish('again', 4, 'again.sql')
        for revision, sql in ((1, SQL_V1), (2, SQL_V2), (3, SQL_V2), (4, SQL_V2)):
            with self.subTest(revision=revision):
                target = out / f'{revision}.sql'
                result = run(['materialize', 'again', 'review', str(revision), str(target)], self.p.root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(target.read_text(), sql)
        archived = json.loads((self.d.parent / 'again/history/review/2.json').read_text())
        self.assertEqual((archived['slug'], archived['sql_path']), ('q', 'q.sql'))

    def test_materialize_output_resolves_symlinked_directories_but_not_links_into_the_repo(self):
        self.p.commit()
        fp = json.loads(run(['fingerprint', 'q.sql'], self.p.root).stdout)
        self.p.write_json('q', 'review.json', review_doc('q', **fp))
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        o = Path(outside.name)
        (o / 'real').mkdir()
        (o / 'tmp-link').symlink_to(o / 'real')      # as /tmp and /var/folders are on macOS
        (o / 'into-repo').symlink_to(self.p.root)
        (o / 'real' / 'final-link.sql').symlink_to(o / 'elsewhere.sql')

        def materialize(target):
            return run(['materialize', 'q', 'review', '1', str(target)], self.p.root)

        ok = materialize(o / 'tmp-link' / 'reviewed.sql')
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual((o / 'real' / 'reviewed.sql').read_text(), SQL_V1)
        refused = materialize(o / 'into-repo' / 'leak.sql')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('outside the git tree', refused.stderr)
        self.assertFalse((self.p.root / 'leak.sql').exists())
        self.assertEqual(materialize(o / 'real' / 'final-link.sql').returncode, 2)
        self.assertFalse((o / 'elsewhere.sql').exists())
        self.assertEqual(materialize(o / 'missing' / 'x.sql').returncode, 2)

    def test_symlinked_tmpdir_is_resolved_for_helper_workspaces(self):
        self.p.commit()
        outside = tempfile.TemporaryDirectory()  # outside the project, which is self.tmp
        self.addCleanup(outside.cleanup)
        real = Path(outside.name) / 'real-tmp'
        real.mkdir()
        link = Path(outside.name) / 'link-tmp'
        link.symlink_to(real)
        env = {'TMPDIR': str(link)}
        fp = run(['fingerprint', 'q.sql'], self.p.root, env=env)
        self.assertEqual(fp.returncode, 0, fp.stderr)
        self.p.write_json('q', 'review.json', review_doc('q', **json.loads(fp.stdout)))
        snap = run(['snapshot', 'q', 'q.sql'], self.p.root, env=env)
        self.assertEqual(snap.returncode, 0, snap.stderr)
        self.assertEqual(list(real.iterdir()), [], 'helper workspaces are removed')

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
        self.p.commit()
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

    def test_failed_write_or_changed_fingerprint_does_not_advance_provenance(self):
        self.reviewed()
        final = self.d / 'review.json'
        original = final.read_bytes()
        (self.p.root / 'q.sql').write_text(SQL_V2)
        self.p.commit("body change")
        # The published old JSON cannot authorize the new body.
        result = run(['snapshot', 'q', 'q.sql'], self.p.root)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(final.read_bytes(), original)
        self.assertEqual(run(['delta', 'q'], self.p.root).returncode, 10)
        self.assertFalse(list(self.d.rglob('*.sql')))
        fp = json.loads(run(['fingerprint', 'q.sql'], self.p.root).stdout)
        draft = self.p.write_json('q', 'review.draft.json', review_doc('q', revision=2, **fp))
        self.assertEqual(run(['publish', 'q', 'review', str(draft)], self.p.root).returncode, 0)
        self.assertEqual(run(['delta', 'q'], self.p.root).returncode, 0)
        self.assertEqual(run(['snapshot', 'q', 'q.sql'], self.p.root).returncode, 0)
        self.assertEqual((self.d / 'history/review/1.json').read_bytes(), original)
        self.assertFalse(list(self.d.rglob('*.sql')))

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
        self.assertEqual(row.count('|'), 8)  # seven columns, including decision origin

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

    def test_snapshot_verification_does_not_modify_legacy_destination_directory(self):
        self.reviewed()
        (self.d / 'source.sql').mkdir()
        result = run(['snapshot', 'q', 'q.sql'], self.p.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list((self.d / 'source.sql').iterdir()), [])

    def test_move_refuses_symlink_marker_before_mutation(self):
        self.reviewed()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'marker'
            target.write_text('unchanged')
            (self.d / 'rebind-required').symlink_to(target)
            before = target.stat().st_mtime_ns
            result = run(['move', 'q.sql', 'renamed.sql'], self.p.root)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(self.d.is_dir())
            self.assertFalse((self.d.parent / 'renamed').exists())
            self.assertEqual(target.stat().st_mtime_ns, before)

    def test_snapshot_verification_never_touches_legacy_symlink_history(self):
        self.reviewed()
        with tempfile.TemporaryDirectory() as outside:
            (self.d / 'history').symlink_to(outside)
            result = run(['snapshot', 'q', 'q.sql'], self.p.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(outside).iterdir()), [])
            self.assertFalse((self.d / 'source.sql').exists())
            self.assertEqual(list(self.d.glob('.snapshot.*')), [])
