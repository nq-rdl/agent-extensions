"""Read-only tagged-library inspection: API fixtures, not live library/model evidence."""
import base64
import copy
import json
import os
import tempfile
import unittest

from test_data_request_lifts import ledger
from test_sql_review_scripts import Project, REPO, run


class StaleLifts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.doc = ledger()
        self.doc['lifts'][0]['library'] = 'nq-rdl/query-builder'
        self.doc['lifts'][0]['units'] = [self.unit('Appointments')]
        self.path = self.p.write_json('pipeline.py', 'lifts.json', self.doc)
        self.fixtures = {}
        self.tag('nq-rdl/query-builder', 'v0.6.0', 'class Other: pass\n')
        self.tag('nq-rdl/query-builder', 'v0.7.0', 'class Appointments: pass\n')
        bin_dir = self.p.root / 'bin'
        bin_dir.mkdir()
        gh = bin_dir / 'gh'
        gh.write_text('#!/usr/bin/env bash\n'
                      '[ "$1" = api ] && [ "$#" = 2 ] || exit 9\n'
                      'printf "%s\\n" "$2" >> "$GH_CALLS"\n'
                      'jq -e --arg ep "$2" \'if has($ep) then .[$ep] else error("unavailable") end\' "$GH_FIXTURES"\n')
        gh.chmod(0o755)
        self.fixture_path = self.p.root / 'api.json'
        self.calls = self.p.root / 'calls.txt'
        self.env = dict(PATH=f'{bin_dir}:{os.environ["PATH"]}',
                        GH_FIXTURES=str(self.fixture_path), GH_CALLS=str(self.calls))

    def unit(self, symbol, tag='v0.6.0'):
        return dict(path='models/appointments.py', symbol=symbol, absent_tag=tag)

    def tag(self, library, tag, source, annotated=False, truncated=False):
        prefix = f'repos/{library}/git/'
        sha = ('6' if tag == 'v0.6.0' else '7') * 40
        tree = sha[:39] + 'a'
        blob = sha[:39] + 'b'
        self.fixtures[prefix + 'ref/tags/' + tag] = {'object': {'type': 'tag' if annotated else 'commit', 'sha': sha}}
        if annotated:
            self.fixtures[prefix + 'tags/' + sha] = {'object': {'type': 'commit', 'sha': sha}}
        self.fixtures[prefix + 'commits/' + sha] = {'tree': {'sha': tree}}
        self.fixtures[prefix + 'trees/' + tree + '?recursive=1'] = {
            'truncated': truncated, 'tree': [{'path': 'models/appointments.py', 'type': 'blob', 'mode': '100644', 'sha': blob}]}
        self.fixtures[prefix + 'blobs/' + blob] = {'encoding': 'base64', 'content': base64.b64encode(source.encode()).decode()}

    def command(self, tag='v0.7.0', expected=0):
        self.fixture_path.write_text(json.dumps(self.fixtures))
        before = {str(p): p.read_bytes() for p in (self.p.root / '.sqlreview').rglob('*') if p.is_file()}
        result = run(['lifts-stale', 'pipeline.py', '--tag', tag], self.p.root, env=self.env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        after = {str(p): p.read_bytes() for p in (self.p.root / '.sqlreview').rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'inspection must not edit ledgers/config/history/renders')
        return json.loads(result.stdout) if expected == 0 else result

    def test_newer_tag_names_nonrecurring_candidate_and_preserves_every_byte(self):
        result = self.command()
        self.assertEqual(result['entries'][0]['id'], 'LIFT-1')
        self.assertEqual(result['entries'][0]['result'], 'may-be-resolved')
        self.assertEqual(result['entries'][0]['units'][0]['result'], 'may-be-resolved')
        self.assertIn('LIFT-1 may be resolved in v0.7.0', result['entries'][0]['message'])
        self.assertEqual(json.loads(self.path.read_text())['lifts'][0]['status'], 'candidate')

    def test_older_equal_tags_and_absent_symbol_do_not_flag_resolution(self):
        for tag in ['v0.5.0', 'v0.6.0']:
            with self.subTest(tag=tag):
                self.assertEqual(self.command(tag)['entries'][0]['result'], 'not-newer')
        self.tag('nq-rdl/query-builder', 'v0.7.0', 'class AppointmentsExtra: pass\n')
        self.assertEqual(self.command()['entries'][0]['result'], 'absent')

    def test_multiple_entries_partial_shortfall_and_correct_library(self):
        self.doc['lifts'][0]['units'].append(self.unit('MissingColumn'))
        second = copy.deepcopy(self.doc['lifts'][0])
        second.update(id='LIFT-2', library='nq-rdl/query-builder-plugins', units=[self.unit('Appointments')])
        third = copy.deepcopy(second)
        third.update(id='LIFT-3')
        third.pop('units')
        self.doc['lifts'].extend([second, third])
        self.path.write_text(json.dumps(self.doc))
        self.tag('nq-rdl/query-builder-plugins', 'v0.6.0', 'class Other: pass\n')
        self.tag('nq-rdl/query-builder-plugins', 'v0.7.0', 'class Other: pass\n')
        results = self.command()['entries']
        self.assertEqual([e['result'] for e in results], ['partly-resolved', 'absent', 'untracked'])
        self.assertEqual([u['result'] for u in results[0]['units']], ['may-be-resolved', 'absent'])
        self.assertIn('repos/nq-rdl/query-builder-plugins/', self.calls.read_text())

    def test_missing_tag_access_or_truncated_tree_is_unknown_not_absence(self):
        endpoint = 'repos/nq-rdl/query-builder/git/ref/tags/v0.7.0'
        del self.fixtures[endpoint]
        self.assertEqual(self.command()['entries'][0]['result'], 'unknown')
        self.tag('nq-rdl/query-builder', 'v0.7.0', 'class Appointments: pass\n', truncated=True)
        self.assertEqual(self.command()['entries'][0]['result'], 'unknown')
        self.tag('nq-rdl/query-builder', 'v0.7.0', 'class Appointments: pass\n')
        del self.fixtures['repos/nq-rdl/query-builder/git/ref/tags/v0.6.0']
        self.assertEqual(self.command()['entries'][0]['result'], 'unknown')

    def test_annotated_tag_and_no_library_execution(self):
        self.tag('nq-rdl/query-builder', 'v0.7.0', 'class Appointments: pass\nraise RuntimeError("never execute")\n', annotated=True)
        self.assertEqual(self.command()['entries'][0]['result'], 'may-be-resolved')

    def test_absent_file_wrong_path_and_nonregular_blob(self):
        endpoint = 'repos/nq-rdl/query-builder/git/trees/' + '7' * 39 + 'a?recursive=1'
        self.fixtures[endpoint]['tree'][0]['path'] = 'unrelated/appointments.py'
        self.assertEqual(self.command()['entries'][0]['result'], 'absent')
        self.fixtures[endpoint]['tree'][0]['path'] = 'models/appointments.py'
        self.fixtures[endpoint]['tree'][0]['mode'] = '120000'
        self.assertEqual(self.command()['entries'][0]['result'], 'unknown')
        self.fixtures[endpoint]['tree'] = []
        self.assertEqual(self.command()['entries'][0]['result'], 'absent')

    def test_unreadable_blob_is_unknown_and_empty_ledger_is_read_only(self):
        del self.fixtures['repos/nq-rdl/query-builder/git/blobs/' + '7' * 39 + 'b']
        self.assertEqual(self.command()['entries'][0]['result'], 'unknown')
        self.doc['lifts'] = []
        self.path.write_text(json.dumps(self.doc))
        self.assertEqual(self.command()['entries'], [])

    def test_github_line_wrapped_base64_blob(self):
        endpoint = 'repos/nq-rdl/query-builder/git/blobs/' + '7' * 39 + 'b'
        source = 'class Appointments: pass\n' + '# padding\n' * 20
        self.fixtures[endpoint]['content'] = base64.encodebytes(source.encode()).decode()
        self.assertEqual(self.command()['entries'][0]['result'], 'may-be-resolved')

    def test_numeric_tag_order_not_lexical(self):
        self.tag('nq-rdl/query-builder', 'v0.10.0', 'class Appointments: pass\n')
        self.assertEqual(self.command('v0.10.0')['entries'][0]['result'], 'may-be-resolved')

    def test_already_present_at_absence_tag_is_not_resolution(self):
        self.tag('nq-rdl/query-builder', 'v0.6.0', 'class Appointments: pass\n')
        self.assertEqual(self.command()['entries'][0]['result'], 'absence-contradicted')

    def test_unsafe_or_unordered_tags_and_invalid_unit_refs(self):
        for tag in ['--help', '../bad', 'v0.7.0-rc1']:
            with self.subTest(tag=tag):
                self.command(tag, expected=2)
        for units in [None, [], [self.unit('')], [self.unit('A.*')],
                      [dict(self.unit('Appointments'), path='../escape.py')],
                      [dict(self.unit('Appointments'), absent_tag='main')]]:
            with self.subTest(units=units):
                self.doc['lifts'][0]['units'] = units
                self.path.write_text(json.dumps(self.doc))
                check = run(['check', str(self.path)], self.p.root)
                self.assertEqual(check.returncode, 4, check.stdout + check.stderr)

    def test_unit_evidence_changes_require_entry_revision(self):
        draft = self.p.write_json('pipeline.py', 'lifts.draft.json', self.doc)
        self.path.unlink()
        first = run(['publish', 'pipeline.py', 'lifts', str(draft)], self.p.root)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.doc['revision'] += 1
        self.doc['lifts'][0]['units'][0]['symbol'] = 'Other'
        draft.write_text(json.dumps(self.doc))
        changed = run(['publish', 'pipeline.py', 'lifts', str(draft)], self.p.root)
        self.assertEqual(changed.returncode, 4, changed.stdout + changed.stderr)


class StaleGuidance(unittest.TestCase):
    def test_triage_runs_check_and_reports_read_only_nudge(self):
        root = REPO / 'skills/data-request-triage'
        self.assertIn('read-only stale lift check', (root / 'SKILL.md').read_text())
        text = ' '.join((root / 'references/checks.rst').read_text().split())
        for token in ['lifts-stale', '--tag', 'latest', 'may be resolved', 'never edits']:
            self.assertIn(token, text)

    def test_lift_revisits_undelivered_nonrecurring_candidates_without_auto_adoption(self):
        text = (REPO / 'skills/data-request-lift/SKILL.md').read_text()
        for token in ['candidate', 'not yet delivered', 'recurring: false', 're-pin', 'clinician']:
            self.assertIn(token, text)
        self.assertNotIn('the baseline is v0.6.0', text)
        guard = (REPO / 'skills/data-request-guardrails/SKILL.md').read_text()
        self.assertNotIn('API baseline: nq-rdl/query-builder 0.6.0', guard)
        self.assertNotIn('The API baseline is', guard)
        policy = REPO / 'skills/data-request-guardrails/references/library.rst'
        self.assertIn('https://github.com/nq-rdl/query-builder/tags', policy.read_text())
        for path in (REPO / 'skills').glob('data-request-*/**/*'):
            if path.suffix in ('.md', '.rst'):
                text = path.read_text()
                self.assertNotRegex(text, r'(?i)(?:API baseline[: ]|the baseline is)[^\\n]*(?:v?0\\.[0-9]+\\.[0-9]+)')
                self.assertNotIn('postdate v0.6.0', text)


if __name__ == '__main__':
    unittest.main()
