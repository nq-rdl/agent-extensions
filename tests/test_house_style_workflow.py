"""Run native Workflow JS with deterministic host stubs; no agent/network side effects."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/rdl-workflow/scripts/house-style.js'
HOST = r'''
const fs = require('fs');
const input = JSON.parse(process.argv[1]);
const calls = [];
let queue = input.responses || [];
const agent = async (prompt, opts) => {
  calls.push({prompt, ...opts});
  return queue.length ? queue.shift() : {status:'complete', summary:'ok', artifacts:[], nextGate:''};
};
const parallel = tasks => Promise.all(tasks.map(t => t().catch(() => null)));
const pipeline = (items, ...stages) => Promise.all(items.map(async item => {
  let value = item;
  for (const stage of stages) value = await stage(value, item);
  return value;
}));
const source = fs.readFileSync(process.argv[2], 'utf8').replace('export const meta', 'const meta');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('args','agent','parallel','pipeline','phase', source)(input.args,agent,parallel,pipeline,()=>{})
.then(result => process.stdout.write(JSON.stringify({result,calls})))
.catch(error => process.stdout.write(JSON.stringify({error:error.message,calls})));
'''


@unittest.skipUnless(shutil.which('node'), 'Node required for Workflow DSL contract tests')
class WorkflowTest(unittest.TestCase):
    def run_workflow(self, stage='execute', responses=None, units=None):
        args = {'stage': stage, 'units': units or [self.unit('one')], 'decisions': []}
        result = subprocess.run(['node', '-e', HOST, json.dumps({'args': args, 'responses': responses}), str(SCRIPT)],
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    @staticmethod
    def unit(name):
        return {'id': name, 'repo': '/repo/' + name, 'checkpoint': '/repo/' + name + '/state.json',
                'physicalWorktree': '/repo/' + name, 'branch': 'main', 'base': 'origin/main', 'request': 'Implement feature'}

    @staticmethod
    def response(status):
        return {'status': status, 'summary': status, 'artifacts': [], 'nextGate': ''}

    def test_preflight_block_stops_implementation(self):
        data = self.run_workflow(responses=[self.response('needs-human')])
        self.assertEqual(len(data['calls']), 1)
        self.assertEqual(data['result'][0]['status'], 'needs-human')

    def test_cancel_is_not_success(self):
        data = self.run_workflow(responses=[None])
        self.assertEqual(data['result'][0]['status'], 'blocked')
        self.assertEqual(len(data['calls']), 1)

    def test_shaping_gates_and_models(self):
        data = self.run_workflow('shape')
        self.assertEqual([c['model'] for c in data['calls']], ['sonnet', 'sonnet', 'opus'])
        data = self.run_workflow('shape', [self.response('complete'), self.response('needs-human')])
        self.assertEqual(len(data['calls']), 2)

    def test_independent_units_use_their_own_paths(self):
        data = self.run_workflow(units=[self.unit('one'), self.unit('two')])
        self.assertEqual([r['unit'] for r in data['result']], ['one', 'two'])
        for call in data['calls']:
            name = call['label'].split(':')[0]
            self.assertIn('/repo/' + name, call['prompt'])

    def test_shared_worktree_rejected_before_dispatch(self):
        other = self.unit('two'); other['repo'] = '/repo/one'; other['checkpoint'] = '/repo/one/two.json'; other['physicalWorktree'] = '/repo/one'
        data = self.run_workflow(units=[self.unit('one'), other])
        self.assertIn('separate worktrees', data['error'])
        self.assertEqual(data['calls'], [])

    def test_worktree_aliases_rejected_before_dispatch(self):
        for alias in ['/repo/one/.', '/repo/one/', '/repo/link-to-one']:
            with self.subTest(alias=alias):
                other = self.unit('two')
                other.update(repo=alias, checkpoint='/repo/one/two.json', physicalWorktree='/repo/one')
                data = self.run_workflow(units=[self.unit('one'), other])
                self.assertIn('separate worktrees', data['error'])
                self.assertEqual(data['calls'], [])

    def test_missing_or_noncanonical_identity_rejected_before_dispatch(self):
        for identity in [None, '', 'relative', '/repo/one/.', '/repo//one', '/repo/one/']:
            with self.subTest(identity=identity):
                one = self.unit('one')
                one['physicalWorktree'] = identity
                data = self.run_workflow(units=[one])
                self.assertIn('canonical physicalWorktree', data['error'])
                self.assertEqual(data['calls'], [])

    def test_duplicate_ids_rejected(self):
        one = self.unit('one'); other = self.unit('two'); other['id'] = 'one'
        data = self.run_workflow(units=[one, other])
        self.assertIn('unique', data['error'])
        self.assertEqual(data['calls'], [])

    def test_checkpoint_escape_rejected(self):
        one = self.unit('one'); one['checkpoint'] = '/repo/one/../outside.json'
        data = self.run_workflow(units=[one])
        self.assertIn('repo-local checkpoint', data['error'])
        self.assertEqual(data['calls'], [])

    def test_exhaustion_cannot_be_reported_as_clean(self):
        statuses = ['complete'] + ['findings', 'complete'] * 3 + ['complete']
        data = self.run_workflow('review', [self.response(s) for s in statuses])
        self.assertEqual(data['result'][0]['status'], 'needs-human')

    def test_review_low_then_high(self):
        data = self.run_workflow('review')
        self.assertIn('/code-review low', data['calls'][1]['prompt'])
        self.assertIn('/code-review high', data['calls'][2]['prompt'])
        self.assertEqual(data['calls'][2]['model'], 'opus')

    def test_review_repairs_are_rechecked(self):
        statuses = ['complete', 'complete', 'findings', 'complete', 'complete', 'complete']
        data = self.run_workflow('review', [self.response(s) for s in statuses])
        self.assertIn('/code-review low', data['calls'][4]['prompt'])
        self.assertIn('/code-review high', data['calls'][5]['prompt'])

    def test_review_exhaustion_does_not_publish(self):
        statuses = ['complete'] + ['findings', 'complete'] * 3 + ['needs-human']
        data = self.run_workflow('review', [self.response(s) for s in statuses])
        self.assertEqual(len(data['calls']), 8)
        self.assertEqual(data['result'][0]['status'], 'needs-human')
        self.assertNotIn('PR', [c['phase'] for c in data['calls']])

    def test_all_stages_parse_and_dispatch(self):
        for stage in ['brainstorm', 'frame', 'specify', 'shape', 'execute', 'review', 'pr', 'archive']:
            with self.subTest(stage=stage):
                data = self.run_workflow(stage)
                self.assertNotIn('error', data)
                self.assertTrue(data['result'])
