"""House-style Workflow: SDD hand-off, scope fence, frame-plan supersession, direct-mode reuse.

Regression tests for nq-rdl/agent-extensions#369 and #367. They drive the real
native Workflow script with the deterministic host stub from
test_house_style_workflow (no agents, network or filesystem side effects), then
pin the matching skill-contract facts in the canonical and packaged SKILL.md.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from test_house_style_workflow import HOST, SCRIPT

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/rdl-workflow/SKILL.md'
PACKAGED = ROOT / 'plugins/rdl-team/skills/workflow'
STAGES = ['brainstorm', 'frame', 'specify', 'shape', 'execute', 'review', 'pr', 'archive']


def unit(name):
    return {'id': name, 'repo': '/repo/' + name, 'checkpoint': '/repo/' + name + '/state.json',
            'physicalWorktree': '/repo/' + name, 'branch': 'main', 'base': 'origin/main',
            'request': 'Implement feature'}


def response(status, **extra):
    return {'status': status, 'summary': status, 'artifacts': [], 'nextGate': '', **extra}


def direct_decision(scope='/repo/one', **overrides):
    decision = {'decision': 'generativeMode', 'value': 'direct', 'by': 'engineer',
                'at': '2026-09-24T10:00:00Z', 'scope': scope}
    decision.update(overrides)
    return {k: v for k, v in decision.items() if v is not None}


@unittest.skipUnless(shutil.which('node'), 'Node required for Workflow DSL contract tests')
class HouseStyleHandoffTest(unittest.TestCase):
    def run_workflow(self, stage, responses=None, units=None, decisions=None, mode=None):
        args = {'stage': stage, 'units': units or [unit('one')], 'decisions': decisions or []}
        if mode:
            args['generativeMode'] = mode
        result = subprocess.run(['node', '-e', HOST, json.dumps({'args': args, 'responses': responses}), str(SCRIPT)],
                                text=True, capture_output=True, check=True)
        data = json.loads(result.stdout)
        self.assertNotIn('error', data)
        return data

    # --- #369 (1): execute prepares, the main session drives SDD with Agent -------------
    def test_execute_prepares_then_hands_sdd_to_main_session(self):
        data = self.run_workflow('execute')
        self.assertEqual(len(data['calls']), 2)  # preflight + prepare; no implementation agent
        prepare = data['calls'][1]['prompt']
        self.assertIn('rdl-team:task-bridge', prepare)
        self.assertIn('hash', prepare)
        self.assertIn('Do not start implementation', prepare)
        result = data['result'][0]
        # A "complete" prepare must not read as implementation done.
        self.assertEqual(result['status'], 'needs-human')
        gate = result['nextGate']
        for token in ['main session', 'superpowers:subagent-driven-development', 'Agent',
                      'one implementer and one reviewer per tasks.md phase', 'commits', 'checkpoint']:
            self.assertIn(token, gate)
        self.assertIn('Never substitute superpowers:executing-plans', gate)

    def test_execute_prepare_never_runs_or_downgrades_sdd_in_workflow(self):
        prepare = self.run_workflow('execute')['calls'][1]['prompt']
        self.assertNotIn('then superpowers:subagent-driven-development', prepare)
        self.assertIn('no subagent-dispatch tool', prepare)
        self.assertIn('Never substitute superpowers:executing-plans', prepare)

    def test_execute_prepare_failures_pass_through(self):
        for status in ['blocked', 'needs-human']:
            with self.subTest(status=status):
                data = self.run_workflow('execute', [response('complete'), response(status, nextGate='fix it')])
                self.assertEqual(data['result'][0]['status'], status)
                self.assertEqual(data['result'][0]['nextGate'], 'fix it')

    def test_execute_handoff_keeps_prepared_artifacts(self):
        plan = '/repo/one/.superpowers/plans/feature.md'
        data = self.run_workflow('execute', [response('complete'), response('complete', artifacts=[plan])])
        self.assertEqual(data['result'][0]['artifacts'], [plan])

    def test_review_preflight_requires_recorded_sdd_phase_commits(self):
        preflight = self.run_workflow('review')['calls'][0]['prompt']
        self.assertIn('SDD phase commits recorded in the checkpoint', preflight)

    # --- #369 (2): default scope fence in every agent prompt ----------------------------
    def test_every_agent_prompt_carries_scope_fence(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                data = self.run_workflow(stage, units=[unit('one'), unit('two')])
                self.assertTrue(data['calls'])
                for call in data['calls']:
                    name = call['label'].split(':')[0]
                    other = '/repo/' + ('two' if name == 'one' else 'one')
                    self.assertIn('Scope fence', call['prompt'])
                    self.assertIn('Ignore other repositories', call['prompt'])
                    self.assertIn('relayed', call['prompt'])
                    self.assertNotIn(other, call['prompt'])

    # --- #369 (3): frame plans are background once clarify has run ---------------------
    def test_shape_treats_frame_plans_as_superseded_background(self):
        calls = self.run_workflow('shape')['calls']
        plan_tasks, analyze = calls[1]['prompt'], calls[2]['prompt']
        self.assertIn('background only', plan_tasks)
        self.assertIn('superseded by spec.md', plan_tasks)
        self.assertIn('contradiction', plan_tasks)
        self.assertIn('contradiction', analyze)

    # --- #367: ask for direct mode up front, record it, reuse it -----------------------
    def test_brainstorm_and_frame_ask_direct_mode_question_once(self):
        for stage in ['brainstorm', 'frame']:
            with self.subTest(stage=stage):
                prompt = self.run_workflow(stage)['calls'][1]['prompt']
                self.assertIn('Direct-mode question', prompt)
                self.assertIn('specify, plan, tasks and analyze', prompt)
                self.assertIn('recommend direct for agent-driven or cloud sessions', prompt)
                self.assertIn('who, when and the repo/worktree', prompt)

    def test_recorded_direct_decision_is_not_asked_again(self):
        for stage in ['brainstorm', 'frame']:
            with self.subTest(stage=stage):
                prompt = self.run_workflow(stage, decisions=[direct_decision()])['calls'][1]['prompt']
                self.assertNotIn('Direct-mode question', prompt)
                self.assertIn('Generative execution mode: direct', prompt)

    def test_recorded_direct_decision_selects_direct_mode_for_later_stages(self):
        for stage in ['specify', 'shape']:
            with self.subTest(stage=stage):
                data = self.run_workflow(stage, decisions=[direct_decision()])
                for call in data['calls']:
                    self.assertIn('Generative execution mode: direct', call['prompt'])

    def test_direct_decision_matches_physical_worktree_scope(self):
        data = self.run_workflow('shape', decisions=[direct_decision(scope='/repo/one')],
                                 units=[unit('one'), unit('two')])
        for call in data['calls']:
            mode = 'direct' if call['label'].startswith('one:') else 'invoke'
            self.assertIn('Generative execution mode: ' + mode, call['prompt'])

    def test_incomplete_or_foreign_direct_decision_is_not_reused(self):
        cases = {
            'other repo': direct_decision(scope='/repo/other'),
            'no who': direct_decision(by=None),
            'no when': direct_decision(at=None),
            'no scope': direct_decision(scope=None),
            'declined': direct_decision(value='invoke'),
        }
        for name, decision in cases.items():
            with self.subTest(case=name):
                prompt = self.run_workflow('shape', decisions=[decision])['calls'][1]['prompt']
                self.assertIn('Generative execution mode: invoke', prompt)

    def test_explicit_mode_argument_wins(self):
        prompt = self.run_workflow('shape', decisions=[direct_decision()], mode='invoke')['calls'][1]['prompt']
        self.assertIn('Generative execution mode: invoke', prompt)

    def test_generative_gates_and_no_agent_rerouting(self):
        prompt = self.run_workflow('shape', decisions=[direct_decision()])['calls'][1]['prompt']
        self.assertIn('not a workaround', prompt)
        self.assertIn('Codex', prompt)
        self.assertIn('analyze remediation', prompt)
        self.assertIn('frontmatter', prompt)


class HouseStyleSkillContractTest(unittest.TestCase):
    """Non-inferable rules the main session needs; pinned in canonical and packaged copies."""

    def texts(self):
        # Collapse whitespace so reflowing the prose does not break the pins.
        flat = lambda path: re.sub(r'\s+', ' ', path.read_text())
        return {'canonical': flat(SKILL), 'packaged': flat(PACKAGED / 'SKILL.md')}

    def test_main_session_drives_sdd_with_agent(self):
        for where, text in self.texts().items():
            with self.subTest(where=where):
                self.assertIn('no subagent-dispatch tool', text)
                self.assertIn('`Agent`', text)
                self.assertIn('one implementer and one reviewer per `tasks.md` phase', text)
                self.assertIn('subagent-driven TDD', text)
                self.assertIn('executing-plans', text)

    def test_direct_mode_asked_up_front_and_recorded(self):
        for where, text in self.texts().items():
            with self.subTest(where=where):
                self.assertIn('`brainstorm` or `frame`', text)
                self.assertIn('"decision": "generativeMode"', text)
                self.assertIn('"by"', text)
                self.assertIn('"at"', text)
                self.assertIn('"scope"', text)
                self.assertIn('agent-driven or cloud sessions', text)
                self.assertIn('not a workaround', text)

    def test_packaged_script_matches_canonical(self):
        self.assertEqual((PACKAGED / 'scripts/house-style.js').read_text(), SCRIPT.read_text())


if __name__ == '__main__':
    unittest.main()
