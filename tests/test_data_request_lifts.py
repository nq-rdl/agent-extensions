"""Lift ledger publication, confirmation isolation, and opt-in hook behaviour."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest

from test_sql_review_scripts import Project, run, review_doc, item, REPO


def ledger():
    return {
        'schemaVersion': 2, 'kind': 'lifts', 'slug': 'pipeline%2Epy',
        'sql_path': 'pipeline.py', 'revision': 1, 'recurring': False,
        'lifts': [{
            'id': 'LIFT-1', 'revision': 1, 'need': 'Current labelled status',
            'library': 'nq-rdl/query-builder-plugins', 'pinned_version': 'v0.1.1',
            'looked_in': [{'path': 'qb_plugins/iemr/resolver.py', 'revision': 'v0.1.1'},
                          {'path': 'tests/test_iemr.py', 'revision': 'v0.1.1'}],
            'shortfall': 'No active-current predicate',
            'workaround': {'file': 'pipeline.py', 'lines': [1, 2]},
            'classification': None, 'status': 'candidate', 'issue_url': None,
            'confirmed_by': None, 'confirmed_at': None, 'confirmed_revision': None,
        }],
    }


class Lifts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql('pipeline.py', 'db.query("SELECT 1")\n')
        self.doc = ledger()

    def command(self, *args, expected=0):
        r = run(list(args), self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r

    def publish(self, expected=0):
        draft = self.p.write_json(self.doc['slug'], 'lifts.draft.json', self.doc)
        return self.command('publish', self.doc['slug'], 'lifts', str(draft), expected=expected)

    def confirm(self):
        e = self.doc['lifts'][0]
        e.update(classification='existing-unit-gap', revision=2, status='confirmed',
                 confirmed_by='Test human', confirmed_at='2026-09-22T00:00:00Z', confirmed_revision=2)
        self.doc['revision'] += 1

    def test_capture_render_status_and_move_pipeline(self):
        self.assertEqual(self.command('slug', 'pipeline.py').stdout.strip(), self.doc['slug'])
        self.publish()
        self.command('render', self.doc['slug'], 'lifts')
        text = (self.p.review_dir(self.doc['slug']) / 'lifts.md').read_text()
        self.assertIn('Current labelled status', text)
        self.assertIn('candidate', text)
        status = json.loads(self.command('status', '--json').stdout)
        self.assertEqual(status['reviews'][0]['lifts'], {'candidate': 1})
        self.command('move', 'pipeline.py', 'next.py')
        moved = json.loads((self.p.review_dir('next%2Epy') / 'lifts.json').read_text())
        self.assertEqual(moved['sql_path'], 'next.py')
        self.assertFalse((self.p.review_dir('next%2Epy') / 'lifts.md').exists())

    def test_candidate_rejects_manufactured_confirmation_and_missing_evidence(self):
        for field, value in [('confirmed_by', 'Robot'), ('pinned_version', ''),
                             ('looked_in', []), ('classification', 'everything-reusable'),
                             ('workaround', {'file': '../escape.py', 'lines': [1, 2]})]:
            with self.subTest(field=field):
                self.doc = ledger()
                self.doc['lifts'][0][field] = value
                self.publish(expected=4)

    def test_evidence_change_requires_new_entry_revision_and_confirmation(self):
        self.publish()
        self.confirm()
        self.publish()
        self.doc['revision'] += 1
        self.doc['lifts'][0]['shortfall'] = 'Different semantics'
        self.publish(expected=4)
        self.doc['lifts'][0]['revision'] += 1
        self.publish(expected=4)
        self.doc['lifts'][0]['confirmed_revision'] += 1
        self.publish()

    def test_append_candidate_preserves_existing_human_answer(self):
        self.publish()
        self.confirm()
        self.publish()
        original = copy.deepcopy(self.doc['lifts'][0])
        e = ledger()['lifts'][0]
        e['id'] = 'LIFT-2'
        self.doc['revision'] += 1
        self.doc['lifts'].append(e)
        self.publish()
        self.assertEqual(self.doc['lifts'][0], original)
        self.command('render', self.doc['slug'], 'lifts')

    def test_library_lifecycle_and_review_limitation_match(self):
        self.publish()
        self.confirm()
        self.publish()
        e = self.doc['lifts'][0]
        self.doc['revision'] += 1
        e['status'] = 'filed'
        self.publish(expected=4)
        e['issue_url'] = 'https://github.com/nq-rdl/query-builder-plugins/issues/26'
        self.publish()
        text = f"{e['need']} resolved with in-repo SQL. Library unit tracked in {e['issue_url']}. Not backported."
        review = review_doc(slug=self.doc['slug'], sql_path='pipeline.py', schemaVersion=2,
                            assumptions=[], limitations=[item('L1', text, lift_id=e['id'])])
        review['sql_sha256'] = hashlib.sha256((self.p.root / 'pipeline.py').read_bytes()).hexdigest()
        draft = self.p.write_json(self.doc['slug'], 'review.draft.json', review)
        self.command('publish', self.doc['slug'], 'review', str(draft))
        review['revision'] = 2
        review['limitations'][0].update(confirmed_revision=2, text='Wrong issue or need')
        draft.write_text(json.dumps(review))
        self.command('publish', self.doc['slug'], 'review', str(draft), expected=4)
        status = json.loads(self.command('status', '--json').stdout)
        self.assertEqual(status['reviews'][0]['lifts'], {'filed': 1})

    def test_cannot_skip_lifecycle_and_rejected_entries_retain_history(self):
        self.publish()
        self.confirm()
        e = self.doc['lifts'][0]
        e.update(status='filed', issue_url='https://github.com/nq-rdl/query-builder-plugins/issues/26')
        self.publish(expected=4)
        e.update(status='confirmed', issue_url=None)
        self.publish()
        self.doc['revision'] += 1
        self.doc['lifts'] = []
        self.publish()
        history = self.p.review_dir(self.doc['slug']) / 'history/lifts/2.json'
        self.assertEqual(json.loads(history.read_text())['lifts'][0]['status'], 'confirmed')

    def test_released_and_recomposed_require_evidence(self):
        self.publish()
        self.confirm()
        self.publish()
        e = self.doc['lifts'][0]
        self.doc['revision'] += 1
        e.update(status='filed', issue_url='https://github.com/nq-rdl/query-builder-plugins/issues/26')
        self.publish()
        self.doc['revision'] += 1
        e['status'] = 'released'
        self.publish(expected=4)
        e['release_evidence'] = {'version': 'v0.2.0', 'url': 'https://github.com/nq-rdl/query-builder-plugins/releases/tag/v0.2.0'}
        self.publish()
        self.doc['revision'] += 1
        e['status'] = 'recomposed'
        self.publish(expected=4)
        e['recomposition_evidence'] = {'pin': 'v0.2.0', 'sql_sha256': 'a' * 64, 'review_revision': 2}
        self.publish()

    def enable(self, value=True):
        path = self.p.root / '.sqlreview/config.json'
        cfg = json.loads(path.read_text())
        cfg['guard'] = {'require_lift_for_string_sql': value}
        path.write_text(json.dumps(cfg))

    def hook(self, content, native=False, path='pipeline.py', move_to=None):
        env = dict(os.environ)
        if native:
            env['PLUGIN_ROOT'] = str(REPO / 'dist/codex/plugins/data-request')
            cmd = ['bash', str(REPO / 'hooks/codex/adapter.sh'), 'data-request-guard']
            move = f'*** Move to: {move_to}\n' if move_to else ''
            event = {'tool_name': 'apply_patch', 'cwd': str(self.p.root), 'tool_input': {
                'patch': f'*** Begin Patch\n*** Update File: {path}\n{move}@@\n+{content}\n*** End Patch'}}
        else:
            env['CLAUDE_PLUGIN_ROOT'] = str(REPO / 'plugins/data-request')
            cmd = ['bash', str(REPO / 'hooks/data-request-guard.sh')]
            event = {'tool_name': 'Write', 'cwd': str(self.p.root), 'tool_input': {
                'file_path': path, 'content': content}}
        r = subprocess.run(cmd, input=json.dumps(event), text=True, capture_output=True,
                           cwd=self.p.root, env=env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)['hookSpecificOutput']['permissionDecision'] if r.stdout else None

    def test_hook_off_by_default_and_explicit_boolean_only(self):
        for flag in (None, False, 'true'):
            if flag is not None:
                self.enable(flag)
            self.assertIsNone(self.hook('db.query(f"SELECT * FROM {table}")'))

    def test_hook_requires_valid_coverage_for_same_file_on_both_hosts(self):
        self.enable()
        for native in (False, True):
            with self.subTest(native=native):
                self.assertEqual(self.hook('db.query(f"SELECT * FROM {table}")', native), 'deny')
                self.assertEqual(self.hook('cursor.execute("SELECT * FROM " + table)', native), 'deny')
                self.assertIsNone(self.hook('db.query("SELECT * FROM table WHERE id = ?", [id])', native))
                self.assertIsNone(self.hook('print(f"SELECT {example}")', native))
        self.assertEqual(self.hook('db.query(f"SELECT * FROM {table}")', True, str(self.p.root / 'pipeline.py')), 'deny')
        self.assertEqual(self.hook('db.query(f"SELECT * FROM {table}")', True, './pipeline.py'), 'deny')
        self.publish()
        for native in (False, True):
            self.assertIsNone(self.hook('db.query(f"SELECT * FROM {table}")', native))
            self.assertEqual(self.hook('db.query(f"SELECT * FROM {table}")', native, 'other.py'), 'deny')
        self.assertEqual(self.hook('db.query(f"SELECT * FROM {table}")', True, move_to='other.py'), 'deny')
        (self.p.review_dir(self.doc['slug']) / 'lifts.json').write_text('{}')
        self.assertEqual(self.hook('db.query(f"SELECT * FROM {table}")'), 'deny')

    def test_direct_authoritative_writes_cannot_bypass_publication(self):
        self.assertEqual(self.hook(json.dumps(self.doc), path='.sqlreview/reviews/pipeline%2Epy/lifts.json'), 'deny')
        review = review_doc(limitations=[item('L1', 'wrong text', lift_id='LIFT-1')])
        self.assertEqual(self.hook(json.dumps(review), path='.sqlreview/reviews/reports__monthly/review.json'), 'deny')

    def test_schema_one_review_and_config_still_work(self):
        cfgpath = self.p.root / '.sqlreview/config.json'
        cfg = json.loads(cfgpath.read_text())
        cfg['schemaVersion'] = 1
        cfg.pop('guard')
        cfgpath.write_text(json.dumps(cfg))
        self.command('roles', 'Engineer', 'Analyst')
        doc = review_doc()
        self.p.sql(doc['sql_path'], 'SELECT 1')
        draft = self.p.write_json(doc['slug'], 'review.json', doc)
        self.command('check', str(draft))
        self.assertIsNone(self.hook('db.query(f"SELECT * FROM {table}")'))
