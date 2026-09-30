"""Real persistence/resume tests for #435; synthetic evidence, no live model pilot."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / 'skills/data-request-setup/scripts/sqlreview.sh'
TICKET = 'rdl-service-desk/service-desk#903'


def entry(ticket=TICKET):
    return dict(ticket=ticket, enquiry='ENQ9003', repo='rdl-service-desk/THHSAQUIRE-9903',
                approval='THHSAQUIRE-9903', branch='triage/903', owner='engineer-handle',
                stage='validate', stages_done=['intake', 'map', 'draft'],
                evidence_revision={'ticket': '2026-09-29', 'sql': 'abc123'},
                stage_evidence={'intake': {'sources': ['ticket'], 'artifacts': []},
                                'map': {'sources': ['ticket'], 'artifacts': []},
                                'draft': {'sources': ['sql'], 'artifacts': []}},
                decisions=[{'decision': 'Use supplied cohort',
                            'decided': {'by': 'analyst-handle', 'role': 'Requester',
                                        'at': '2026-09-29', 'source': 'unlinked (verbal)'}}],
                blockers=[], depends_on=[], next_action='engineer: validate',
                verification={'status': 'partial', 'commands': ['mapping check: pass'], 'at': '2026-09-29'})


class Ledger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ledger project ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, SQLREVIEW_ROOT=str(self.root), XDG_STATE_HOME=str(self.root / 'state'))
        self.dest = self.root / '.sqlreview/ledger.json'
        self.draft = self.root / 'entry.json'

    def run_helper(self, *args, ok=True, env=None, script=SCRIPT):
        result = subprocess.run(['bash', str(script), 'ledger', *args], cwd=self.root,
                                env=env or self.env, text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def save(self, doc=None, session=False, ok=True):
        self.draft.write_text(json.dumps(doc if doc is not None else entry()))
        return self.run_helper(*(['--session'] if session else []), 'set', TICKET, str(self.draft), ok=ok)

    def test_new_session_loads_stored_entry_before_work(self):
        self.save()
        self.assertEqual(json.loads(self.run_helper('get', TICKET).stdout), entry())
        self.run_helper('check', str(self.dest))
        self.assertEqual(json.loads(self.dest.read_text())['schemaVersion'], 1)

    def test_ticket_isolation_and_wrong_ticket_rejected(self):
        self.save()
        other = 'rdl-service-desk/service-desk#904'
        self.draft.write_text(json.dumps(entry(other)))
        self.run_helper('set', other, str(self.draft))
        before = self.dest.read_bytes()
        self.run_helper('set', TICKET, str(self.draft), ok=False)
        self.assertEqual(self.dest.read_bytes(), before)
        self.assertEqual(json.loads(self.run_helper('get', TICKET).stdout), entry())
        self.assertEqual(json.loads(self.run_helper('get', other).stdout)['ticket'], other)

    def test_session_file_survives_without_child_writes(self):
        self.save(session=True)
        self.assertFalse((self.root / '.sqlreview').exists())
        session = self.root / 'state/rdl-agent-extensions/data-request/ledger.json'
        self.assertTrue(session.exists())
        self.assertEqual(session.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.run_helper('--session', 'get', TICKET).stdout), entry())

    def test_missing_is_explicit_and_read_does_not_create(self):
        result = self.run_helper('get', TICKET, ok=False)
        self.assertEqual(result.returncode, 6)
        self.assertFalse(self.dest.parent.exists())

    def test_schema_rejects_bad_entries_without_overwriting(self):
        self.save()
        before = self.dest.read_bytes()
        mutations = [('stage', 'unknown'), ('stages_done', ['draft', 'draft']),
                     ('stage_evidence', {}), ('evidence_revision', {'sql': 1}),
                     ('owner', 'someone@example.com'), ('decisions', [{'decision': 'x', 'decided': {'by': 'a'}}]),
                     ('verification', {'status': 'verified'}), ('ticket', '../bad#1')]
        for key, value in mutations:
            with self.subTest(key=key):
                bad = entry(); bad[key] = value
                self.save(bad, ok=False)
                self.assertEqual(self.dest.read_bytes(), before)
        self.draft.write_text('{bad')
        self.run_helper('set', TICKET, str(self.draft), ok=False)
        self.assertEqual(self.dest.read_bytes(), before)

    def test_duplicate_and_invalid_store_fail_visibly(self):
        self.save()
        doc = json.loads(self.dest.read_text()); doc['entries'].append(copy.deepcopy(doc['entries'][0]))
        self.dest.write_text(json.dumps(doc))
        self.run_helper('get', TICKET, ok=False)
        self.save(ok=False)
        self.run_helper('check', str(self.dest), ok=False)

    def test_changed_evidence_rechecks_only_affected_completed_stages(self):
        self.save()
        current = self.root / 'current.json'
        current.write_text(json.dumps({'ticket': '2026-09-30', 'sql': 'abc123'}))
        result = json.loads(self.run_helper('get', TICKET, '--against', str(current)).stdout)
        self.assertEqual(result['recheck'], ['intake', 'map'])
        self.assertEqual(result['entry']['owner'], 'engineer-handle')
        self.assertEqual(result['unchanged'], ['draft'])
        current.write_text(json.dumps(entry()['evidence_revision']))
        self.assertEqual(json.loads(self.run_helper('get', TICKET, '--against', str(current)).stdout)['recheck'], [])
        current.write_text('{}')
        self.assertEqual(json.loads(self.run_helper('get', TICKET, '--against', str(current)).stdout)['recheck'], ['intake', 'map', 'draft'])

    def test_missing_or_changed_artifacts_recheck_their_stage(self):
        artifact = self.root / 'query.sql'; artifact.write_text('SELECT 1;')
        doc = entry(); doc['stage_evidence']['draft']['artifacts'] = [
            {'path': 'query.sql', 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]
        self.save(doc)
        current = self.root / 'current.json'; current.write_text(json.dumps(doc['evidence_revision']))
        def recheck():
            return json.loads(self.run_helper('get', TICKET, '--against', str(current)).stdout)['recheck']
        self.assertEqual(recheck(), [])
        artifact.write_text('SELECT 2;'); self.assertEqual(recheck(), ['draft'])
        artifact.unlink(); self.assertEqual(recheck(), ['draft'])

    def test_unsafe_paths_and_symlinks_are_refused(self):
        doc = entry(); doc['stage_evidence']['draft']['artifacts'] = [{'path': '../outside', 'sha256': 'a' * 64}]
        self.save(doc, ok=False)
        outside = self.root / 'outside'; outside.mkdir()
        (self.root / '.sqlreview').symlink_to(outside, target_is_directory=True)
        self.save(ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_lock_and_atomic_failure_preserve_old_store(self):
        self.save(); before = self.dest.read_bytes()
        lock = self.dest.parent / '.ledger.lock'; lock.mkdir()
        self.save(ok=False); self.assertEqual(self.dest.read_bytes(), before)
        lock.rmdir()
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        mv = bin_dir / 'mv'; mv.write_text('#!/bin/sh\nexit 1\n'); mv.chmod(0o755)
        self.draft.write_text(json.dumps(entry()))
        self.run_helper('set', TICKET, str(self.draft), ok=False,
                        env=dict(self.env, PATH=str(bin_dir) + ':' + self.env['PATH']))
        self.assertEqual(self.dest.read_bytes(), before)
        self.assertFalse(lock.exists())
        self.assertEqual(list(self.dest.parent.glob('.ledger.*')), [])

    def test_legacy_decisions_and_direct_mode_keep_date_precision(self):
        doc = entry(); doc['decisions'] += [
            {'date': '2026-09-29', 'who': 'analyst', 'decision': 'Cohort', 'source': 'doc#12'},
            {'decision': 'generativeMode', 'value': 'direct', 'by': 'engineer',
             'at': '2026-09-29', 'scope': 'nq-rdl/query-builder'}]
        self.save(doc)
        self.assertEqual(json.loads(self.run_helper('get', TICKET).stdout), doc)

    def test_installed_helpers_work_from_paths_with_spaces(self):
        import shutil
        for target in ('plugins', 'dist/codex/plugins'):
            with self.subTest(target=target):
                installed = self.root / ('installed ' + target.replace('/', '-'))
                shutil.copytree(REPO / target / 'data-request/skills/setup', installed)
                self.draft.write_text(json.dumps(entry()))
                script = installed / 'scripts/sqlreview.sh'
                self.run_helper('set', TICKET, str(self.draft), script=script)
                self.assertEqual(json.loads(self.run_helper('get', TICKET, script=script).stdout), entry())

    def test_json_stream_and_incomplete_stage_metadata_are_rejected(self):
        self.draft.write_text(json.dumps(entry()) + '\n' + json.dumps(entry()))
        self.run_helper('set', TICKET, str(self.draft), ok=False)
        for mutation in ({'intake': {'sources': ['unknown'], 'artifacts': []}},
                         {'intake': {'sources': [], 'artifacts': []}}):
            doc = entry(); doc['stage_evidence'] = mutation
            self.save(doc, ok=False)
        self.assertFalse(self.dest.exists())

    def test_session_state_inside_a_repository_is_refused(self):
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        self.save(session=True, ok=False)
        self.assertFalse((self.root / 'state').exists())

    def test_symlink_artifact_and_session_ancestor_are_refused(self):
        doc = entry(); artifact = self.root / 'artifact'; artifact.write_text('original')
        link = self.root / 'link'; link.symlink_to(artifact)
        doc['stage_evidence']['draft']['artifacts'] = [
            {'path': 'link', 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]
        self.save(doc)
        current = self.root / 'current.json'; current.write_text(json.dumps(doc['evidence_revision']))
        self.run_helper('get', TICKET, '--against', str(current), ok=False)
        state = self.root / 'state'; state.symlink_to(self.root)
        self.save(session=True, ok=False)

    def test_final_repository_ledger_write_edit_is_guard_denied(self):
        for tool in ('Write', 'Edit'):
            with self.subTest(tool=tool):
                event = {'tool_name': tool, 'cwd': str(self.root),
                         'tool_input': {'file_path': '.sqlreview/ledger.json', 'content': '{}'}}
                result = subprocess.run(['bash', str(REPO / 'hooks/data-request-guard.sh')],
                                        input=json.dumps(event), text=True, capture_output=True,
                                        cwd=self.root, env=self.env, check=True)
                self.assertTrue(result.stdout, 'final ledger bypassed guarded publication')
                self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
                self.assertIn('ledger', result.stdout)

    def test_guard_denies_ledger_path_aliases(self):
        self.save()
        (self.root / 'state').symlink_to('.sqlreview', target_is_directory=True)
        (self.root / 'alias.json').symlink_to('.sqlreview/ledger.json')
        (self.root / '.sqlreview/subdir').mkdir()
        for hook in ('hooks/data-request-guard.sh',
                     'plugins/data-request/hooks/data-request-guard.sh',
                     'dist/codex/plugins/data-request/hooks/data-request-guard.sh'):
            for tool in ('Write', 'Edit'):
                for path in ('state/ledger.json', 'state/subdir/../ledger.json',
                             str(self.root / 'state/ledger.json'), 'alias.json'):
                    with self.subTest(hook=hook, tool=tool, path=path):
                        event = {'tool_name': tool, 'cwd': str(self.root),
                                 'tool_input': {'file_path': path, 'content': '{}'}}
                        result = subprocess.run(['bash', str(REPO / hook)],
                                                input=json.dumps(event), text=True, capture_output=True,
                                                cwd=self.root, env=self.env, check=True)
                        self.assertTrue(result.stdout, 'ledger alias bypassed guarded publication')
                        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_backslash_artifact_paths_preserve_unchanged_completion(self):
        artifact = self.root / 'query\\cohort.sql'
        artifact.write_text('SELECT 1;')
        doc = entry(); doc['stage_evidence']['draft']['artifacts'] = [
            {'path': artifact.name, 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]
        self.save(doc)
        current = self.root / 'current.json'; current.write_text(json.dumps(doc['evidence_revision']))
        result = json.loads(self.run_helper('get', TICKET, '--against', str(current)).stdout)
        self.assertEqual(result['recheck'], [])
        self.assertEqual(result['unchanged'], doc['stages_done'])
        artifact.write_text('SELECT 2;')
        self.assertEqual(json.loads(self.run_helper('get', TICKET, '--against', str(current)).stdout)['recheck'], ['draft'])

    def test_init_completes_ledger_only_directory_without_changing_ledger(self):
        self.save(); before = self.dest.read_bytes()
        def init(*args):
            return subprocess.run(['bash', str(SCRIPT), 'init', *args], cwd=self.root,
                                  env=self.env, text=True, capture_output=True)
        diff = init('--diff', '--json')
        self.assertEqual(diff.returncode, 10, diff.stderr)
        self.assertFalse((self.dest.parent / 'config.json').exists())
        created = init('--json')
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertTrue(json.loads(created.stdout)['created'])
        for path in ('config.json', 'templates/scope.md', 'templates/review.md',
                     'templates/lifts.md', 'reviews/.gitkeep'):
            self.assertTrue((self.dest.parent / path).is_file(), path)
        self.assertEqual(self.dest.read_bytes(), before)
        roles = subprocess.run(['bash', str(SCRIPT), 'roles', 'Engineer', 'Requester'], cwd=self.root,
                               env=self.env, text=True, capture_output=True)
        self.assertEqual(roles.returncode, 0, roles.stderr)
        config = self.dest.parent / 'config.json'; config.write_text('{"custom": true}')
        self.assertEqual(init().returncode, 10)
        self.assertEqual(config.read_text(), '{"custom": true}')
        config.unlink()
        self.assertEqual(init().returncode, 10)
        self.assertFalse(config.exists(), 'partial existing setup must remain report-only')

    def test_source_free_decisions_are_only_exact_spec_kit_direct_mode(self):
        self.save(); before = self.dest.read_bytes()
        direct = {'decision': 'generativeMode', 'value': 'direct', 'by': 'engineer',
                  'at': '2026-09-29', 'scope': 'nq-rdl/query-builder'}
        for mutation in ({'decision': 'Choose cohort'}, {'value': 'cohort A'},
                         {'decision': 'generativeMode', 'value': 'spec-kit'},
                         {'role': 'Requester'}, {'cohort': 'A'}):
            with self.subTest(mutation=mutation):
                doc = entry(); doc['decisions'] = [dict(direct, **mutation)]
                self.assertEqual(self.save(doc, ok=False).returncode, 4)
                self.assertEqual(self.dest.read_bytes(), before)

    def test_invalid_current_evidence_fails_instead_of_rechecking_everything(self):
        self.save(); current = self.root / 'current.json'; current.write_text('{bad')
        self.run_helper('get', TICKET, '--against', str(current), ok=False)


if __name__ == '__main__':
    unittest.main()
