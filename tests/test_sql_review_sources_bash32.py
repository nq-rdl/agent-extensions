"""Real committed adapters under host Bash and the strict Bash 3.2 fixture."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_sql_review_scripts import Project, review_doc, item, REPO
from bash32_fixture import container_runtime, static_jq, run_container

SCENARIO = r'''
set -euo pipefail
cd "$PROJECT"
S="$FIXTURE/setup/scripts"
# Config argv contains a spaced literal argument. Adapter checks it and normalized paths.
bash "$S/sqlreview.sh" fingerprint sql/request.sql > "$FIXTURE/fingerprint.json"
jq -s '.[0] * .[1]' "$FIXTURE/base.json" "$FIXTURE/fingerprint.json" > .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" publish sql__request review .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" snapshot sql__request sql/request.sql
test ! -e sql/request.sql
printf 'SET NOCOUNT ON;\nSELECT 2;\nSELECT 3;\n' > payload
git add payload
git -c commit.gpgsign=false commit -qm 'builder shift'
bash "$S/sqlreview.sh" fingerprint sql/request.sql > "$FIXTURE/fingerprint.json"
jq -s '.[0] * .[1] | .revision=2' .sqlreview/reviews/sql__request/review.json "$FIXTURE/fingerprint.json" > .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" remap sql__request .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" carryforward sql__request review .sqlreview/reviews/sql__request/review.draft.json > "$FIXTURE/carry.json"
jq -e '.carry[0].basis=="lines-unchanged" and .carry[0].set.confirmed_revision==1' "$FIXTURE/carry.json"
jq --slurpfile carry "$FIXTURE/carry.json" '.assumptions[0] += $carry[0].carry[0].set' .sqlreview/reviews/sql__request/review.draft.json > "$FIXTURE/draft.json"
cp "$FIXTURE/draft.json" .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" publish sql__request review .sqlreview/reviews/sql__request/review.draft.json
jq -e '.revision==1' .sqlreview/reviews/sql__request/history/review/1.json
T="$(mktemp -d /tmp/sqlreview-fixture.XXXXXX)"
trap 'rm -rf "$T"' EXIT
bash "$S/sqlreview.sh" materialize sql__request review 1 "$T/old.sql"
printf 'SELECT 1;\nSELECT 3;\n' > "$T/expected.sql"
cmp "$T/old.sql" "$T/expected.sql"
set +e
bash "$S/sqlreview.sh" materialize sql__request review 9 "$T/missing.sql"
rc=$?
set -e
test "$rc" = 6
test ! -e "$T/missing.sql"
test -z "$(find .sqlreview -name '*.sql' -print)"
printf 'source-contract-ok\n'
'''


def fixture(directory):
    tmp = Path(directory)
    shutil.copytree(REPO / "skills/data-request-setup", tmp / "setup")
    project = tmp / "project"
    project.mkdir()
    p = Project(project)
    (project / "sql").mkdir()
    (project / ".gitignore").write_text("sql/request.sql\n")
    (project / "payload").write_text("SELECT 1;\nSELECT 3;\n")
    (project / "render.sh").write_text('''#!/usr/bin/env bash
set -eu
[ "$1" = 'literal argument' ] && [ "$2" = --sql-path ] && [ "$3" = sql/request.sql ]
[ "$4" = --output ]
case "$5" in /*) ;; *) exit 2;; esac
cat payload > "$5"
''')
    config = project / ".sqlreview/config.json"
    d = json.loads(config.read_text())
    d["sql_render"] = {"command": ["bash", "render.sh", "literal argument"]}
    config.write_text(json.dumps(d))
    (project / "sql/provenance.json").write_text(json.dumps({"schema": 1, "requests": {
        "sql/request.sql": {"source": "builder"}}}))
    p.commit()
    p.review_dir("sql__request")
    (tmp / "base.json").write_text(json.dumps(review_doc("sql__request", "sql/request.sql",
        assumptions=[item("A1", "Retain this range", location={"lines": [2, 2]})],
        limitations=[], logic=[], open_questions=[])))
    return project


class HostSources(unittest.TestCase):
    def test_adapter_historical_publish_and_carry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(tmp)
            r = subprocess.run(["bash", "-c", SCENARIO], text=True, capture_output=True,
                env={**os.environ, "PROJECT": str(project), "FIXTURE": tmp}, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("source-contract-ok", r.stdout)


class Bash32Sources(unittest.TestCase):
    def setUp(self):
        if not container_runtime() or not static_jq():
            self.skipTest("needs pinned Bash 3.2 image and verified jq; see docs/bash32-portability.md")

    def test_adapter_historical_publish_and_carry(self):
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            fixture(tmp)
            shutil.copyfile(static_jq(), Path(tmp) / "jq")
            (Path(tmp) / "jq").chmod(0o755)
            copy_host_git(Path(tmp), "/w")
            command = 'export PATH=/w/bin:/w:$PATH PROJECT=/w/project FIXTURE=/w; ' + SCENARIO
            r = run_container(tmp, "/w", command)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("source-contract-ok", r.stdout)


class HostGitFixture(unittest.TestCase):
    def test_real_git_copy_is_self_contained(self):
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            copy_host_git(Path(tmp), tmp)
            r = subprocess.run([str(Path(tmp) / "bin/git"), "--version"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("git version "))


if __name__ == "__main__":
    unittest.main()
