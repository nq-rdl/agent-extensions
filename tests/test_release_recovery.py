"""Behavioural tests for the guarded release recovery verification drill."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERIFIER = REPO / "scripts" / "verify-release-recovery.sh"
VERSION = "1.2.3"
TAG = f"v{VERSION}"
MERGE_SHA = "a" * 40
PR_HEAD_SHA = "b" * 40
NOTES = "## Added\n\n- Recovery verification.\n"

FAKE_GH = r'''#!/usr/bin/env python3
import json
import os
import signal
import sys
import time
from pathlib import Path

state_path = Path(os.environ["FAKE_GH_STATE"])
state = json.loads(state_path.read_text())
args = sys.argv[1:]


def save():
    state_path.write_text(json.dumps(state))


def record(value):
    state.setdefault("calls", []).append(value)
    save()


def endpoint():
    return next((arg for arg in args if arg.startswith("repos/")), "")


def release_json():
    return {
        "id": state["release_id"],
        "tag_name": f"v{state['version']}",
        "name": state["release_name"],
        "body": state["release_body"],
        "draft": False,
        "prerelease": False,
        "immutable": state.get("immutable", False),
        "assets": state.get("assets", []),
        "discussion_url": state.get("discussion_url"),
        "target_commitish": state["target_commitish"],
        "author": {"login": state["author"]},
        "created_at": state["created_at"],
        "published_at": state["published_at"],
    }


def complete_pending():
    pending = state.get("pending")
    if not pending:
        return
    pending["polls"] += 1
    if pending["polls"] <= state.get("polls_before_complete", 0):
        save()
        return
    mode = "noop" if state["release_exists"] else "recovery"
    conclusion = "failure" if mode == "recovery" and state.get("fail_recovery") else "success"
    pending.update(mode=mode, conclusion=conclusion, completed=True)
    state.setdefault("attempts", {})[str(pending["attempt"])] = {
        "mode": mode,
        "conclusion": conclusion,
    }
    if mode == "recovery" and conclusion == "success":
        state["release_exists"] = True
        state["release_body"] = state["notes"]
        state["release_name"] = f"v{state['version']}"
        state["release_id"] += 1
        state["created_at"] = "2026-09-01T01:00:00Z"
        state["published_at"] = "2026-09-01T01:00:01Z"
        state["assets"] = state.get("recovery_assets", [])
        state["latest_tag"] = f"v{state['version']}"
        state.setdefault("calls", []).append("workflow_recreated")
    save()


if not args:
    sys.exit(2)

if args[0] == "api":
    route = endpoint()
    if "/contents/VERSION?ref=main" in route:
        index = state.get("main_version_calls", 0)
        versions = state.get("remote_versions", [state["version"]])
        print(versions[min(index, len(versions) - 1)])
        state["main_version_calls"] = index + 1
        save()
    elif route.endswith("/pulls"):
        print(json.dumps([{
            "number": 77,
            "merged_at": "2026-09-01T00:00:00Z",
            "merge_commit_sha": state["merge_sha"],
            "head": {"sha": state["pr_head_sha"]},
        }]))
    elif route.endswith("/actions/workflows/release-finalize.yml"):
        print(json.dumps({"id": state["workflow_id"]}))
    elif route.endswith("/actions/workflows/release-finalize.yml/runs"):
        print(json.dumps({"workflow_runs": [{
            "id": 42,
            "run_attempt": state["run_attempt"],
            "status": "completed",
            "conclusion": "success",
            "event": "pull_request",
            "head_branch": f"release/v{state['version']}",
            "head_sha": state["run_head_sha"],
            "path": state["run_path"],
            "workflow_id": state["run_workflow_id"],
        }]}))
    elif route.endswith("/actions/runs/42/rerun"):
        if state.get("pending") and not state["pending"].get("completed"):
            print("run already in progress", file=sys.stderr)
            sys.exit(1)
        state["run_attempt"] += 1
        state["pending"] = {"attempt": state["run_attempt"], "polls": 0, "completed": False}
        state.setdefault("calls", []).append("rerun")
        save()
    elif "/actions/runs/42/attempts/" in route and route.endswith("/jobs?per_page=100"):
        attempt = route.split("/attempts/", 1)[1].split("/", 1)[0]
        result = state["attempts"][attempt]
        mode = result["mode"]
        conclusion = result["conclusion"]
        if mode == "noop":
            tag, prepare, release = "skipped", "skipped", "skipped"
        else:
            tag, prepare, release = "skipped", "success", "success"
        print(json.dumps({"jobs": [{
            "name": "finalize",
            "conclusion": conclusion,
            "steps": [
                {"name": "Derive and verify version", "conclusion": "success"},
                {"name": "Tag the release commit", "conclusion": tag},
                {"name": "Prepare release notes", "conclusion": prepare},
                {"name": "Create GitHub release", "conclusion": release},
            ],
        }]}))
    elif route.endswith("/actions/runs/42"):
        complete_pending()
        pending = state.get("pending")
        if pending and not pending.get("completed"):
            status, conclusion = "in_progress", None
        elif pending:
            status, conclusion = "completed", pending["conclusion"]
        else:
            status, conclusion = "completed", "success"
        print(json.dumps({
            "run_attempt": state["run_attempt"],
            "status": status,
            "conclusion": conclusion,
            "event": "pull_request",
            "head_branch": f"release/v{state['version']}",
            "head_sha": state["run_head_sha"],
            "path": state["run_path"],
            "workflow_id": state["run_workflow_id"],
        }))
    elif "/releases/tags/" in route:
        if not state["release_exists"]:
            print("gh: Not Found (HTTP 404)", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(release_json()))
    elif route.endswith("/releases/latest"):
        latest = state.get("latest_tag", "")
        if not latest:
            print("gh: Not Found (HTTP 404)", file=sys.stderr)
            sys.exit(1)
        print(latest)
    else:
        print(f"unhandled gh api route: {route}", file=sys.stderr)
        sys.exit(2)
elif args[:2] == ["release", "delete"]:
    state["release_exists"] = False
    if state.get("latest_tag") == f"v{state['version']}":
        state["latest_tag"] = state.get("previous_latest", "")
    state.setdefault("calls", []).append("delete")
    save()
    mode = state.get("delete_mode")
    if mode == "ambiguous":
        print("connection reset after response", file=sys.stderr)
        sys.exit(1)
    if mode == "signal":
        os.kill(os.getppid(), signal.SIGTERM)
        time.sleep(0.2)
        sys.exit(1)
elif args[:2] == ["release", "edit"]:
    edited_tag = args[2]
    if edited_tag != f"v{state['version']}" and edited_tag not in state.get("other_releases", []):
        print("release not found", file=sys.stderr)
        sys.exit(1)
    state["latest_tag"] = edited_tag
    record(f"latest:{edited_tag}")
elif args[:2] == ["release", "create"]:
    if state.get("fail_restore"):
        print("restore failed", file=sys.stderr)
        sys.exit(1)
    notes_file = Path(args[args.index("--notes-file") + 1])
    state["release_exists"] = True
    state["release_body"] = notes_file.read_text()
    state["release_name"] = args[args.index("--title") + 1]
    state["target_commitish"] = args[args.index("--target") + 1]
    state["release_id"] += 1
    state["assets"] = []
    state["discussion_url"] = None
    if "--latest" in args:
        state["latest_tag"] = f"v{state['version']}"
    state.setdefault("calls", []).append("direct_restore")
    save()
else:
    print(f"unhandled gh invocation: {args}", file=sys.stderr)
    sys.exit(2)
'''

FAKE_GIT = f'''#!/usr/bin/env python3
import sys

if len(sys.argv) > 1 and sys.argv[1] == "ls-remote":
    print("{MERGE_SHA}\\trefs/tags/{TAG}^{{}}")
else:
    print(f"unhandled git invocation: {{sys.argv[1:]}}", file=sys.stderr)
    sys.exit(2)
'''


class ReleaseRecoveryVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.baseline = self.root / "baseline"
        (self.root / ".changes").mkdir()
        (self.root / "VERSION").write_text(f"{VERSION}\n")
        (self.root / ".changes" / f"{VERSION}.md").write_text(NOTES)
        self.summary = self.root / "summary.md"
        self.state_path = self.root / "state.json"
        self.gh = self._write_executable("fake-gh", FAKE_GH)
        self.git = self._write_executable("fake-git", FAKE_GIT)
        self.state = {
            "version": VERSION,
            "merge_sha": MERGE_SHA,
            "pr_head_sha": PR_HEAD_SHA,
            "run_head_sha": PR_HEAD_SHA,
            "run_path": ".github/workflows/release-finalize.yml@main",
            "workflow_id": 9001,
            "run_workflow_id": 9001,
            "notes": NOTES,
            "release_exists": True,
            "release_body": NOTES,
            "release_name": TAG,
            "release_id": 100,
            "target_commitish": "main",
            "author": "release-bot[bot]",
            "created_at": "2026-09-01T00:00:00Z",
            "published_at": "2026-09-01T00:00:01Z",
            "run_attempt": 1,
            "attempts": {},
            "calls": [],
            "assets": [],
            "immutable": False,
            "discussion_url": None,
            "latest_tag": TAG,
            "previous_latest": "v1.2.2",
            "other_releases": ["v1.2.2"],
            "remote_versions": [VERSION],
            "main_version_calls": 0,
            "polls_before_complete": 0,
        }
        self._save_state()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_executable(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(textwrap.dedent(content))
        path.chmod(0o755)
        return path

    def _save_state(self):
        self.state_path.write_text(json.dumps(self.state))

    def _load_state(self):
        return json.loads(self.state_path.read_text())

    def _run(self, command, confirmation=f"DELETE-AND-RECREATE-{TAG}"):
        jq = shutil.which("jq")
        self.assertIsNotNone(jq, "jq is required to exercise the workflow script")
        env = os.environ.copy()
        env.update(
            VERSION=VERSION,
            CONFIRMATION=confirmation,
            GITHUB_REPOSITORY="example/catalog",
            GITHUB_TOKEN="actions-token",
            RELEASE_TOKEN="release-token",
            GITHUB_STEP_SUMMARY=str(self.summary),
            GH_BIN=str(self.gh),
            GIT_BIN=str(self.git),
            JQ_BIN=jq,
            FAKE_GH_STATE=str(self.state_path),
            POLL_INTERVAL="0",
            POLL_ATTEMPTS="5",
        )
        return subprocess.run(
            ["bash", str(VERIFIER), command, str(self.baseline)],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _assert_ok(self, command):
        result = self._run(command)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def _through_noop(self):
        self._assert_ok("capture")
        self._assert_ok("queue-noop")
        self._assert_ok("verify-noop")

    def _through_recovery_queue(self):
        self._through_noop()
        self._assert_ok("queue-recovery")

    def test_exercises_noop_then_tag_only_recovery(self):
        self.state["polls_before_complete"] = 2
        self._save_state()
        self._through_recovery_queue()
        self.assertFalse(self._load_state()["release_exists"])
        result = self._assert_ok("verify-recovery")
        state = self._load_state()
        self.assertTrue(state["release_exists"])
        self.assertEqual(state["release_body"], NOTES)
        self.assertEqual(state["run_attempt"], 3)
        self.assertEqual(state["calls"], ["rerun", "rerun", "delete", "workflow_recreated"])
        self.assertIn("database ID changed", self.summary.read_text())
        self.assertIn("Verified both Finalize recovery paths", result.stdout)

    def test_rejects_incorrect_confirmation_without_side_effects(self):
        result = self._run("capture", "yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"confirmation must be exactly 'DELETE-AND-RECREATE-{TAG}'", result.stderr)
        self.assertEqual(self._load_state()["calls"], [])

    def test_binds_finalize_run_to_pr_head_and_workflow_path(self):
        self.state["run_head_sha"] = "c" * 40
        self._save_state()
        result = self._run("capture")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workflow 9001 and PR head", result.stderr)
        self.assertEqual(self._load_state()["calls"], [])

    def test_rejects_finalize_run_from_different_workflow_id(self):
        self.state["run_workflow_id"] = 9002
        self._save_state()
        result = self._run("capture")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bound to workflow 9001", result.stderr)
        self.assertEqual(self._load_state()["calls"], [])

    def test_ambiguous_delete_restores_baseline_immediately(self):
        self._through_noop()
        state = self._load_state()
        state["delete_mode"] = "ambiguous"
        self.state = state
        self._save_state()
        result = self._run("queue-recovery")
        self.assertNotEqual(result.returncode, 0)
        state = self._load_state()
        self.assertTrue(state["release_exists"])
        self.assertEqual(state["release_body"], NOTES)
        self.assertEqual(state["calls"][-2:], ["delete", "direct_restore"])
        self.assertEqual(state["latest_tag"], TAG)

    def test_sigterm_after_delete_runs_immediate_compensation(self):
        self._through_noop()
        state = self._load_state()
        state["delete_mode"] = "signal"
        self.state = state
        self._save_state()
        result = self._run("queue-recovery")
        self.assertNotEqual(result.returncode, 0)
        state = self._load_state()
        self.assertTrue(state["release_exists"])
        self.assertEqual(state["calls"][-2:], ["delete", "direct_restore"])
        self.assertEqual(state["latest_tag"], TAG)

    def test_newer_main_after_rerun_queue_prevents_deletion(self):
        self._through_noop()
        state = self._load_state()
        used = state["main_version_calls"]
        state["remote_versions"] = [VERSION] * (used + 2) + ["1.2.4"]
        self.state = state
        self._save_state()
        result = self._run("queue-recovery")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("main moved to VERSION 1.2.4", result.stderr)
        state = self._load_state()
        self.assertTrue(state["release_exists"])
        self.assertNotIn("delete", state["calls"])

    def test_recovery_metadata_drift_is_rejected(self):
        self._through_noop()
        state = self._load_state()
        state["recovery_assets"] = [{"name": "unexpected.tar.gz"}]
        self.state = state
        self._save_state()
        self._assert_ok("queue-recovery")
        result = self._run("verify-recovery")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supported metadata/body differs", result.stderr)

    def test_watchdog_restores_missing_release_without_displacing_newer_latest(self):
        self._assert_ok("capture")
        state = self._load_state()
        state["release_exists"] = False
        state["latest_tag"] = "v1.3.0"
        state["other_releases"].append("v1.3.0")
        state["remote_versions"] = ["1.3.0"]
        state["main_version_calls"] = 0
        self.state = state
        self._save_state()
        self._assert_ok("watchdog")
        state = self._load_state()
        self.assertTrue(state["release_exists"])
        self.assertEqual(state["release_body"], NOTES)
        self.assertEqual(state["latest_tag"], "v1.3.0")
        self.assertIn("direct_restore", state["calls"])

    def test_watchdog_repairs_latest_when_metadata_already_matches(self):
        self._assert_ok("capture")
        state = self._load_state()
        state["latest_tag"] = state["previous_latest"]
        self.state = state
        self._save_state()
        self._assert_ok("watchdog")
        state = self._load_state()
        self.assertEqual(state["latest_tag"], TAG)
        self.assertIn(f"latest:{TAG}", state["calls"])

    def test_watchdog_promotes_newer_main_instead_of_old_baseline(self):
        self._assert_ok("capture")
        state = self._load_state()
        state["remote_versions"] = ["1.3.0"]
        state["main_version_calls"] = 0
        state["latest_tag"] = TAG
        state["other_releases"].append("v1.3.0")
        self.state = state
        self._save_state()
        self._assert_ok("watchdog")
        state = self._load_state()
        self.assertEqual(state["latest_tag"], "v1.3.0")
        self.assertIn("latest:v1.3.0", state["calls"])

    def test_watchdog_surfaces_restoration_failure(self):
        self._assert_ok("capture")
        state = self._load_state()
        state["release_exists"] = False
        state["latest_tag"] = ""
        state["fail_restore"] = True
        self.state = state
        self._save_state()
        result = self._run("watchdog")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self._load_state()["release_exists"])
        self.assertIn("restore failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
