"""Exercise adapter output consumed by Task N / Global Constraints extractors."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/rdl-task-bridge/scripts/bridge.sh'


class BridgeTest(unittest.TestCase):
    def bridge(self, tasks, plan='# Design\nKeep transactions atomic.\n', spec='Acceptance: reject stale tokens.', constitution='All writes require tests.', analysis='Approved: preserve token expiry semantics.'):
        with tempfile.TemporaryDirectory(prefix='bridge space ') as directory:
            root = Path(directory)
            (root / 'tasks.md').write_text(tasks)
            (root / 'plan.md').write_text(plan)
            (root / 'spec.md').write_text(spec)
            (root / 'constitution.md').write_text(constitution)
            (root / 'analysis.md').write_text(analysis)
            return subprocess.run(['bash', str(SCRIPT), str(root / 'tasks.md'), str(root / 'plan.md'),
                                   str(root / 'spec.md'), str(root / 'constitution.md'), str(root / 'analysis.md')],
                                  text=True, capture_output=True)

    def test_metadata_context_and_extractable_boundaries(self):
        result = self.bridge('''# Tasks
## Phase 1: Setup
- [x] T001 Create schema
  Keep historical migrations.
## Phase 2: Story
- [ ] T009 [P] [US1] Add handler in `src/api.go`
  Validate empty input.
## Dependencies
T009 depends on T001.
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(re.findall(r'^## Task (\d+): (T\d+)', result.stdout, re.M),
                         [('1', 'T001'), ('2', 'T009')])
        task2 = result.stdout.split('## Task 2:', 1)[1]
        self.assertIn('Phase: ## Phase 2: Story', task2)
        self.assertIn('[P] [US1]', task2)
        self.assertIn('Validate empty input.', task2)
        self.assertIn('T009 depends on T001.', task2)
        self.assertIn('complete — verify only', result.stdout)
        self.assertIn('Keep transactions atomic.', result.stdout.split('## Task 1:')[0])

    def test_fenced_examples_do_not_become_tasks(self):
        result = self.bridge('```md\n- [ ] T099 Example\n```\n- [ ] T001 Real\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(re.findall(r'^## Task ', result.stdout, re.M)), 1)

    def test_empty_tasks_cannot_import_plan_checklist(self):
        result = self.bridge('', '- [ ] T001 Plan checklist\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no spec-kit tasks found', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_fences_require_matching_delimiter_length_and_empty_suffix(self):
        for opening, false_close, closing in [
            ('````md', '```', '````'),
            ('~~~md', '```', '~~~'),
            ('```md', '~~~', '```'),
            ('```md', '```not-a-close', '````'),
            ('~~~~md', '~~~', '~~~~~'),
        ]:
            with self.subTest(opening=opening, false_close=false_close):
                result = self.bridge(
                    f'{opening}\n{false_close}\n- [ ] T099 Example\n{closing}\n- [ ] T001 Real\n')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(re.findall(r'^## Task \d+: (T\d+)', result.stdout, re.M), ['T001'])

    def test_indented_fence_literal_cannot_close_outer_example(self):
        for spaces in [4, 5, 8]:
            for fence in ['~~~', '```']:
                with self.subTest(spaces=spaces, fence=fence):
                    result = self.bridge(f'{fence}md\n{" " * spaces}{fence}\n- [ ] T099 Example\n{fence}\n- [ ] T001 Real\n')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(re.findall(r'^## Task \d+: (T\d+)', result.stdout, re.M), ['T001'])

    def test_up_to_three_spaces_are_valid_fence_indentation(self):
        for spaces in range(4):
            result = self.bridge(f'{" " * spaces}~~~md\n- [ ] T099 Example\n{" " * spaces}~~~\n- [ ] T001 Real\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(re.findall(r'^## Task \d+: (T\d+)', result.stdout, re.M), ['T001'])

    def test_metadata_only_tasks_fail(self):
        for tags in ['[P]', '[US1]', '[P] [US1]', '[US1] [P]', '[P]\t[US12]   ']:
            with self.subTest(tags=tags):
                result = self.bridge(f'- [ ] T001 {tags}\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('no description', result.stderr)
                self.assertEqual(result.stdout, '')

    def test_all_context_sources_are_required_and_nonempty(self):
        for source in ['plan', 'spec', 'constitution', 'analysis']:
            for content in ['', ' \t\r\n  \n']:
                with self.subTest(source=source, content=content):
                    result = self.bridge('- [ ] T001 Real\n', **{source: content})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('empty source context', result.stderr)
                    self.assertEqual(result.stdout, '')

    def test_worker_constraints_include_acceptance_and_approved_decisions(self):
        result = self.bridge('- [ ] T001 Add handler\n- [ ] T002 Test handler\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        constraints = result.stdout.split('## Task 1:')[0]
        for required in ['Acceptance: reject stale tokens.', 'All writes require tests.',
                         'Approved: preserve token expiry semantics.', 'Every task worker must read all Global Constraints']:
            self.assertIn(required, constraints)

    def test_source_plan_task_headings_cannot_pollute_extraction(self):
        result = self.bridge('- [ ] T001 Actual\n', '## Task 99: example\n')
        self.assertEqual(re.findall(r'^## Task (\d+)', result.stdout, re.M), ['1'])

    def test_crlf_and_uppercase_completion(self):
        result = self.bridge('## Phase 1\r\n- [X] T010 Done\r\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('complete — verify only', result.stdout)

    def test_invalid_input_has_no_partial_output(self):
        for tasks in ['', '# no tasks\n', '- [ ] T001 One\n- [ ] T001 Duplicate\n',
                      '- [ ] Tbad Invalid\n', '- [ ] T001\n', '- [ ] T001   \n', '- [ ] T001\t \t\n']:
            with self.subTest(tasks=tasks):
                result = self.bridge(tasks)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_missing_sources_fail(self):
        result = subprocess.run(['bash', str(SCRIPT), '/missing/tasks.md', '/missing/plan.md',
                                 '/missing/spec.md', '/missing/constitution.md', '/missing/analysis.md'],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
