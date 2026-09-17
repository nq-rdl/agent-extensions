"""Exercise adapter output consumed by Task N / Global Constraints extractors."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/rdl-task-bridge/scripts/bridge.sh'


class BridgeTest(unittest.TestCase):
    def bridge(self, tasks, plan='# Design\nKeep transactions atomic.\n'):
        with tempfile.TemporaryDirectory(prefix='bridge space ') as directory:
            root = Path(directory)
            (root / 'tasks.md').write_text(tasks)
            (root / 'plan.md').write_text(plan)
            return subprocess.run(['bash', str(SCRIPT), str(root / 'tasks.md'), str(root / 'plan.md')],
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

    def test_source_plan_task_headings_cannot_pollute_extraction(self):
        result = self.bridge('- [ ] T001 Actual\n', '## Task 99: example\n')
        self.assertEqual(re.findall(r'^## Task (\d+)', result.stdout, re.M), ['1'])

    def test_crlf_and_uppercase_completion(self):
        result = self.bridge('## Phase 1\r\n- [X] T010 Done\r\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('complete — verify only', result.stdout)

    def test_invalid_input_has_no_partial_output(self):
        for tasks in ['', '# no tasks\n', '- [ ] T001 One\n- [ ] T001 Duplicate\n',
                      '- [ ] Tbad Invalid\n', '- [ ] T001\n']:
            with self.subTest(tasks=tasks):
                result = self.bridge(tasks)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_missing_sources_fail(self):
        result = subprocess.run(['bash', str(SCRIPT), '/missing/tasks.md', '/missing/plan.md'],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
