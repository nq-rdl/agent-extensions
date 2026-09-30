"""Execute the shipped OpenCode companion with a credential-free local SDK stub.

The earlier OpenCode tests cover prose only. These regressions exercise real
parent/worker processes, persisted CLI responses and delayed I/O in installed
copies (including install paths with spaces), without fetching SDK packages.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIES = [
    ROOT / 'skills/opencode-delegate/assets/companion.skeleton.mjs',
    ROOT / 'plugins/opencode-dev/skills/delegate/assets/companion.skeleton.mjs',
    ROOT / 'dist/codex/plugins/opencode-dev/skills/delegate/assets/companion.skeleton.mjs',
]
SDK = r'''
import fs from 'node:fs';
const record = (call, args) => fs.appendFileSync(process.env.STUB_CALLS,
  JSON.stringify({call, args, pid: process.pid}) + '\n');
const wait = async phase => {
  record(phase, {});
  if (process.env.STUB_HOLD === phase)
    while (!fs.existsSync(process.env.STUB_RELEASE))
      await new Promise(resolve => setTimeout(resolve, 10));
};
export function createOpencodeClient(options) {
  record('client', options);
  return {session: {
    create: async args => {
      await wait('create');
      if (process.env.STUB_CREATE === 'reject') throw new Error('create rejected');
      if (process.env.STUB_CREATE === 'error') return {error: {name:'CreateError', data:{message:'create denied'}}};
      if (process.env.STUB_CREATE === 'empty') return {data:{}};
      return {data:{id:'session_' + process.pid}};
    },
    prompt: async args => {
      record('promptArgs', args);
      await wait('prompt');
      if (process.env.STUB_PROMPT === 'reject') throw new Error('prompt rejected');
      if (process.env.STUB_PROMPT === 'error') return {error:{name:'PromptError', data:{message:'prompt denied'}}};
      if (process.env.STUB_PROMPT === 'empty') return {};
      if (process.env.STUB_PROMPT === 'malformed') return {data:{}};
      if (process.env.STUB_PROMPT === 'assistant') return {data:{info:{error:{name:'PermissionDenied', data:{message:'explicit deny'}}},parts:[]}};
      return {data:{info:{id:'message'},parts:[{type:'text',text:'worker answer'}]}};
    },
    abort: async args => {
      record('abort', args);
      if (process.env.STUB_ABORT === 'reject') throw new Error('abort rejected');
      if (process.env.STUB_ABORT === 'error') return {error:{name:'AbortError', data:{message:'abort denied'}}};
      return {data:true};
    }
  }};
}
'''
# Delay the parent store write to expose worker-before-dispatch and stale parent
# overwrite races deterministically, instead of depending on CPU scheduling.
SLOW_FS = r'''
const fs = require('node:fs');
const {syncBuiltinESMExports} = require('node:module');
const write = fs.writeFileSync;
fs.writeFileSync = (...args) => {
  if (process.argv[2] === 'task')
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 200);
  return write(...args);
};
syncBuiltinESMExports();
'''


class Harness:
    def __init__(self, source, **settings):
        self.temp = tempfile.TemporaryDirectory(prefix='companion installed ')
        self.root = Path(self.temp.name)
        self.script = self.root / 'companion.mjs'
        shutil.copyfile(source, self.script)
        package = self.root / 'node_modules/@opencode-ai/sdk'
        package.mkdir(parents=True)
        (package / 'package.json').write_text(json.dumps({'type':'module', 'exports':'./index.mjs'}))
        (package / 'index.mjs').write_text(SDK)
        (self.root / 'slow.cjs').write_text(SLOW_FS)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.store = self.home / '.cache/cc-opencode/jobs.json'
        self.calls = self.root / 'calls.jsonl'
        self.release = self.root / 'release'
        self.env = {k:v for k,v in os.environ.items() if not k.startswith(('OPENCODE_', 'NODE_'))}
        self.env.update(HOME=str(self.home), STUB_CALLS=str(self.calls), STUB_RELEASE=str(self.release), **settings)
        self.processes = []

    def close(self):
        self.release.touch()
        for job in self.jobs().values():
            try:
                os.kill(job['pid'], 15)
            except (KeyError, ProcessLookupError):
                # Best-effort teardown: a job may have no PID yet, or its
                # detached worker may already have exited. Continue cleanup.
                pass
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=2)
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
        self.temp.cleanup()

    def run(self, *args, check=True):
        return subprocess.run(['node', str(self.script), *args], env=self.env,
                              text=True, capture_output=True, timeout=3, check=check)

    def jobs(self):
        return json.loads(self.store.read_text()) if self.store.exists() else {}

    def task(self, text='review task'):
        return json.loads(self.run('task', text).stdout)['id']

    def status(self, id):
        return json.loads(self.run('status', id).stdout)

    def result(self, id):
        return json.loads(self.run('result', id).stdout)

    def wait(self, predicate, message='worker did not settle'):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.015)
        raise AssertionError(message)

    def events(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def called(self, name):
        return any(e['call'] == name for e in self.events())


@unittest.skipUnless(shutil.which('node'), 'Node.js required for executable companion tests')
class CompanionTest(unittest.TestCase):
    def each_copy(self, check, **settings):
        for source in COPIES:
            with self.subTest(copy=str(source.relative_to(ROOT))):
                h = Harness(source, **settings)
                try:
                    check(h)
                finally:
                    h.close()

    def failed(self, h, expected):
        id = h.task()
        h.wait(lambda: h.jobs().get(id, {}).get('status') == 'failed', 'failure remained running/prompting')
        status = h.status(id)
        self.assertEqual(status['phase'], 'failed')
        self.assertIn(expected, json.dumps(status['error']))
        self.assertEqual(h.result(id)['error'], status['error'])
        self.assertEqual(status['request'], 'review task')
        h.run('cancel', id)
        self.assertEqual(h.status(id), status)
        self.assertFalse(h.called('abort'))

    def test_rejected_session_creation_persists_failure(self):
        self.each_copy(lambda h: self.failed(h, 'create rejected'), STUB_CREATE='reject')

    def test_rejected_prompt_persists_failure(self):
        self.each_copy(lambda h: self.failed(h, 'prompt rejected'), STUB_PROMPT='reject')

    def test_sdk_create_error_response_persists_failure(self):
        self.each_copy(lambda h: self.failed(h, 'create denied'), STUB_CREATE='error')

    def test_sdk_prompt_error_response_persists_failure(self):
        self.each_copy(lambda h: self.failed(h, 'prompt denied'), STUB_PROMPT='error')

    def test_assistant_permission_error_is_failure(self):
        self.each_copy(lambda h: self.failed(h, 'explicit deny'), STUB_PROMPT='assistant')

    def test_malformed_session_response_is_failure(self):
        self.each_copy(lambda h: self.failed(h, 'session'), STUB_CREATE='empty')

    def test_malformed_prompt_response_is_failure(self):
        self.each_copy(lambda h: self.failed(h, 'response data'), STUB_PROMPT='empty')

    def test_malformed_prompt_success_data_is_failure(self):
        self.each_copy(lambda h: self.failed(h, 'prompt message'), STUB_PROMPT='malformed')

    def test_success_persists_actual_result_before_done(self):
        def check(h):
            id = h.task('preserve exact request')
            h.wait(lambda: h.jobs()[id].get('status') == 'done')
            status = h.status(id)
            self.assertEqual(status['phase'], 'complete')
            result = h.result(id)
            self.assertEqual(result['sessionID'], status['sessionID'])
            self.assertEqual(result['result']['parts'][0]['text'], 'worker answer')
            self.assertEqual(status['request'], 'preserve exact request')
            args = next(e['args'] for e in h.events() if e['call'] == 'promptArgs')
            self.assertEqual(args['body'], {'parts':[{'type':'text','text':'preserve exact request'}]})
        self.each_copy(check)

    def test_worker_cannot_run_before_parent_dispatch_or_be_overwritten(self):
        def check(h):
            # NODE_OPTIONS tokenises paths; quote the preloader install path.
            h.env['NODE_OPTIONS'] = '--require="' + str(h.root / 'slow.cjs') + '"'
            id = h.task()
            h.wait(lambda: h.jobs()[id].get('status') == 'done', 'parent overwrote worker terminal state')
            self.assertEqual(h.status(id)['id'], id)
            self.assertEqual(h.result(id)['result']['parts'][0]['text'], 'worker answer')
        self.each_copy(check)

    def test_parallel_jobs_preserve_all_records(self):
        def check(h):
            processes = [subprocess.Popen(['node', str(h.script), 'task', str(i)], env=h.env,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(8)]
            h.processes.extend(processes)
            ids = []
            for process in processes:
                out, err = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, err)
                ids.append(json.loads(out)['id'])
            self.assertEqual(len(set(ids)), 8)
            h.wait(lambda: all(h.jobs().get(id, {}).get('status') == 'done' for id in ids), 'concurrent store updates lost jobs')
        self.each_copy(check)

    def test_detached_worker_outlives_task_and_cancel_prevents_prompt(self):
        def check(h):
            id = h.task()
            h.wait(lambda: h.called('create'))
            self.assertEqual(h.status(id)['status'], 'running')
            h.run('cancel', id)
            self.assertEqual(h.status(id)['status'], 'cancelled')
            self.assertEqual(h.result(id)['status'], 'cancelled')
            before = h.status(id)
            h.run('cancel', id)
            self.assertEqual(h.status(id), before)
            h.release.touch()
            h.wait(lambda: h.called('abort'), 'session created during cancellation was not aborted')
            self.assertFalse(h.called('prompt'))
        self.each_copy(check, STUB_HOLD='create')

    def test_abort_error_after_cancelled_creation_is_persisted(self):
        def check(h):
            id = h.task()
            h.wait(lambda: h.called('create'))
            h.run('cancel', id)
            h.release.touch()
            h.wait(lambda: 'error' in h.jobs()[id], 'abort failure after cancelled creation was discarded')
            self.assertEqual(h.status(id)['status'], 'cancelled')
            self.assertIn('abort rejected', json.dumps(h.result(id)['error']))
            self.assertFalse(h.called('prompt'))
        self.each_copy(check, STUB_HOLD='create', STUB_ABORT='reject')

    def test_cancel_before_worker_start_skips_session_creation(self):
        def check(h):
            id = 'job_pre_cancelled'
            log = h.home / '.cache/cc-opencode/pre-cancelled.log'
            h.store.parent.mkdir(parents=True)
            h.store.write_text(json.dumps({id:{'id':id,'status':'cancelled','phase':'cancelled','logFile':str(log),'request':'unused'}}))
            before = h.status(id)
            h.run('__worker', id, str(log), 'unused')
            self.assertEqual(h.status(id), before)
            self.assertFalse(h.called('create'))
        self.each_copy(check)

    def test_cancel_during_prompt_wins_over_late_success_or_rejection(self):
        for mode in ('success', 'reject'):
            def check(h):
                id = h.task()
                h.wait(lambda: h.called('prompt'))
                h.run('cancel', id)
                self.assertEqual(h.status(id)['status'], 'cancelled')
                self.assertTrue(h.called('abort'))
                h.release.touch()
                time.sleep(.15)
                self.assertEqual(h.status(id)['status'], 'cancelled')
                self.assertEqual(h.result(id)['status'], 'cancelled')
            self.each_copy(check, STUB_HOLD='prompt', STUB_PROMPT=mode)

    def test_cancel_is_idempotent_and_does_not_replace_done(self):
        def check(h):
            id = h.task()
            h.wait(lambda: h.jobs()[id].get('status') == 'done')
            before = h.status(id)
            h.run('cancel', id)
            self.assertEqual(h.status(id), before)
            self.assertFalse(h.called('abort'))
        self.each_copy(check)

    def test_abort_errors_are_persisted_without_late_completion(self):
        for mode in ('reject', 'error'):
            def check(h):
                id = h.task()
                h.wait(lambda: h.called('prompt'))
                h.run('cancel', id, check=False)
                self.assertIn('abort', json.dumps(h.status(id)['error']))
                self.assertEqual(h.result(id)['error'], h.status(id)['error'])
                h.release.touch()
                time.sleep(.1)
                self.assertEqual(h.status(id)['status'], 'cancelled')
            self.each_copy(check, STUB_HOLD='prompt', STUB_ABORT=mode)

    def test_client_preserves_authorization_and_server_selection(self):
        def check(h):
            id = h.task()
            h.wait(lambda: h.jobs()[id].get('status') == 'done')
            options = next(e['args'] for e in h.events() if e['call'] == 'client')
            self.assertEqual(options['baseUrl'], 'http://127.0.0.1:12345')
            self.assertNotIn('permission', options)
            self.assertNotIn('auto', options)
            self.assertNotIn('permission', next(e['args'] for e in h.events() if e['call'] == 'promptArgs')['body'])
        self.each_copy(check, OPENCODE_BASE_URL='http://127.0.0.1:12345')

    def test_unknown_job_remains_an_error(self):
        def check(h):
            for verb in ('status', 'result', 'cancel'):
                self.assertEqual(json.loads(h.run(verb, 'missing').stdout), {'error':'unknown job'})
        self.each_copy(check)
