"""No-echo audit: a LEAK-CANARY value fed through each input must not reach stdout, stderr or argv.

Each case records what happened instead of failing fast, so one run reports every leaking path.
Run: python3 -I rehearsal-notes/test_no_echo_canary.py   (the repo is this file's parent directory)
Known leaks are expected: this harness reports them and does not fail. It is not part of tests/.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
S = REPO / "skills/data-request-setup/scripts"
SR, RL, RD = S / "sqlreview.sh", S / "release.sh", S / "recurring-decisions.sh"
GUARD, PREFLIGHT = REPO / "hooks/data-request-guard.sh", REPO / "hooks/data-request-preflight.sh"
CANARY = "LEAK-CANARY"
FRAGS = ("LEAK-C", "CANARY")

def seen(text):
    return any(f in text for f in FRAGS)
RESULTS = []


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


class Box:
    """A throwaway project with an argv-logging jq and git on PATH."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="canary-"))
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.argv = self.tmp / "argv.log"
        for name in ("jq", "git"):
            real = shutil.which(name)
            w = self.bin / name
            w.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "{self.argv}"\nexec "{real}" "$@"\n')
            w.chmod(0o755)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.org")
        git(self.root, "config", "user.name", "t")
        self.run(SR, "init")

    def env(self):
        e = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        e["PATH"] = f"{self.bin}{os.pathsep}{e['PATH']}"
        return e

    def run(self, script, *args, stdin=None):
        return subprocess.run(["bash", str(script), *map(str, args)], cwd=self.root, env=self.env(),
                              input=stdin, capture_output=True, text=True, timeout=120)

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data if isinstance(data, str) else json.dumps(data, indent=2))
        return p

    def commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "x", "--allow-empty")

    def done(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def item(i, text="Plain text", **o):
    d = {"id": i, "text": text, "rationale": "because", "location": None, "status": "confirmed",
         "confirmed_by": "eng-login", "confirmed_at": "2026-11-01T00:00:00Z", "confirmed_revision": 1}
    d.update(o)
    return d


def review(**o):
    d = {"schemaVersion": 1, "kind": "review", "slug": "q", "sql_path": "q.sql", "title": "T", "revision": 1,
         "recorded_at": "2026-11-01T00:00:00Z", "recorded_by": "eng-login", "sql_sha256": "0" * 64,
         "git_commit": None, "git_dirty": False, "purpose": "p", "inputs": [{"name": "a", "description": "b"}],
         "outputs": [{"name": "c", "description": "d"}], "grain": "g",
         "logic": [{"step": 1, "title": "t", "lines": [1, 1], "description": "d"}],
         "assumptions": [item("A1")], "limitations": [item("L1")], "open_questions": [],
         "changes": [{"revision": 1, "at": "2026-11-01T00:00:00Z", "by": "eng-login", "summary": "s"}]}
    d.update(o)
    return d


def scope(**o):
    d = {"schemaVersion": 1, "kind": "scope", "slug": "q", "sql_path": "q.sql", "title": "T", "revision": 1,
         "recorded_at": "2026-11-01T00:00:00Z", "recorded_by": "eng-login", "git_commit": None, "sql_sha256": None,
         "intent": "i", "inputs": [{"name": "a", "description": "b"}], "outputs": [{"name": "c", "description": "d"}],
         "assumptions": [item("A1")], "limitations": [], "open_questions": []}
    d.update(o)
    return d


STAMP = {"confirmed_by": "analyst-login", "confirmed_role": "analyst", "confirmed_at": "2026-11-01T00:00:00Z"}


def sidecar(text="Adults", approval="THHSAQUIRE-99187", reason="Narrowed"):
    return {"schemaVersion": 2, "approval_number": approval, "open_questions": [],
            "decisions": [{"id": "age", "topic": "cohort", "text": text, "rationale": "r", **STAMP}],
            "criteria": [{"id": "I1", "kind": "inclusion", "text": "Aged 18 " + text, **STAMP},
                         {"id": "E1", "kind": "exclusion", "text": "Old", **STAMP,
                          "withdrawn": {"reason": reason, "at": "2026-11-01"}}],
            "fingerprints": {k: "sha256:" + "a" * 64 for k in
                             ("cohort_entry_event", "inclusion_criteria", "exclusion_criteria", "requested_data_elements")}}


def case(name, input_desc, fn, by_design=False):
    box = Box()
    try:
        r = fn(box)
        out = (r.stdout if r else "") + "\n" + (r.stderr if r else "")
        argv = box.argv.read_text() if box.argv.exists() else ""
        RESULTS.append({"case": name, "input": input_desc, "exit": r.returncode if r else None,
                        "stdout": seen(r.stdout if r else ""), "stderr": seen(r.stderr if r else ""),
                        "argv": seen(argv), "by_design": by_design,
                        "sample": next((l.strip()[:140] for l in out.splitlines() if seen(l)), "")})
    except Exception as exc:  # a broken case is a finding about the harness, not a pass
        RESULTS.append({"case": name, "input": input_desc, "error": repr(exc)})
    finally:
        box.done()


def guard_write(box, rel, doc):
    ev = {"tool_name": "Write", "cwd": str(box.root),
          "tool_input": {"file_path": str(box.root / ".sqlreview" / rel), "content": json.dumps(doc)}}
    return box.run(GUARD, stdin=json.dumps(ev))


# --- sqlreview.sh check / guard ------------------------------------------------------------------------
case("check: sql_sha256 array", "review.sql_sha256", lambda b: b.run(SR, "check", b.write("d.json", review(sql_sha256=[CANARY]))))
case("check: status value", "item.status", lambda b: b.run(SR, "check", b.write("d.json", review(assumptions=[item("A1", status=CANARY)]))))
case("check: kind value", "doc.kind", lambda b: b.run(SR, "check", b.write("d.json", review(kind=CANARY))))
case("check: item id object", "item.id", lambda b: b.run(SR, "check", b.write("d.json", review(assumptions=[item({"t": CANARY})]))))
case("check: criteria text in item (valid doc)", "item.text", lambda b: b.run(SR, "check", b.write("d.json", review(assumptions=[item("A1", CANARY)]))))
case("check --stdin: invalid JSON with canary", "file contents", lambda b: b.run(SR, "check", "--stdin", stdin='{"purpose": "' + CANARY + '" ,,}'))
case("guard Write review.json: sql_sha256 array", "review.sql_sha256", lambda b: guard_write(b, "reviews/q/review.json", review(sql_sha256=[CANARY])))
case("guard Write review.json: status value", "item.status", lambda b: guard_write(b, "reviews/q/review.json", review(assumptions=[item("A1", status=CANARY)])))
case("guard Write review.json: unconfirmed item with canary text", "item.text", lambda b: guard_write(b, "reviews/q/review.json", review(assumptions=[item("A1", CANARY, status="proposed")])))
case("guard Write explain.json: canary key", "explain key", lambda b: guard_write(b, "reviews/q/explain.json", {CANARY: {"by": "a@b.org"}}))


def status_verbose(b):
    b.write(".sqlreview/reviews/q/review.json", review(schemaVersion=CANARY))
    return b.run(SR, "status", "--verbose")


case("status --verbose: invalid schemaVersion", "review.schemaVersion", status_verbose)


def status_json(b):
    b.write(".sqlreview/reviews/q/review.json", review(schemaVersion=CANARY))
    return b.run(SR, "status", "--json", "--verbose")


case("status --json --verbose: invalid schemaVersion", "review.schemaVersion", status_json)


# --- intake / criteria ---------------------------------------------------------------------------------
case("intake: missing FILE with DRAFT", "any file contents", lambda b: b.run(SR, "intake", "/nonexistent.json", "1", b.write("secret.txt", CANARY + "\n")))
case("intake: invalid sidecar", "intake decision text", lambda b: b.run(SR, "intake", b.write("answers.intake.json", dict(sidecar(CANARY), schemaVersion="x")), "1"))


def criteria_case(b, **kw):
    b.write("answers.intake.json", sidecar(**kw))
    b.write("q.sql", "SELECT 1;\n")
    b.commit()
    d = b.write(".sqlreview/reviews/q/scope.draft.json", scope(criteria_status=[
        {"criterion": "I1", "state": "bogus", "confirmed_by": "e", "confirmed_at": "2026-11-01T00:00:00Z", "confirmed_revision": 1}]))
    return b.run(SR, "criteria", d)


case("criteria DRAFT: canary in criteria text", "intake criteria text", lambda b: criteria_case(b, text=CANARY))
case("criteria DRAFT: canary approval number", "approval number", lambda b: criteria_case(b, approval="THHSAQUIRE-" + CANARY))
case("criteria DRAFT: canary withdrawn reason", "withdrawn reason", lambda b: criteria_case(b, reason=CANARY))

# --- SQL-bearing commands ------------------------------------------------------------------------------
case("notes: bad header line", "SQL header text", lambda b: b.run(SR, "notes", b.write("q.sql", "/*\nassumptions:\n  - Grain is one row\n" + CANARY + " stray\n*/\nSELECT 1;\n")))


def fingerprint_dirty(b):
    b.write("q.sql", f"SELECT '{CANARY}';\n")
    return b.run(SR, "fingerprint", "q.sql")


case("fingerprint: uncommitted SQL with literal", "SQL literal", fingerprint_dirty)


def lint_ste(b):
    return b.run(SR, "lint", "--ste", b.write("d.json", review(assumptions=[item("A1", f"It {CANARY}n't work")])))


case("lint --ste: contraction", "item.text", lint_ste)


def carryover_bad(b):
    b.write(".sqlreview/reviews/q/scope.json", scope())
    return b.run(SR, "carryover", "q", b.write("d.json", review(assumptions=CANARY + " text")))


case("carryover: assumptions is a string", "draft text", carryover_bad)
case("carryforward: unsafe sql_path", "draft sql_path", lambda b: b.run(SR, "carryforward", "q", "review", b.write("d.json", review(sql_path="/" + CANARY))))


def render_bad_upstream(b):
    b.write(".sqlreview/reviews/q/review.json", review(assumptions=[item("A1", upstream={"source": "analyst-intake", "file": {"x": CANARY}})]))
    return b.run(SR, "render", "q", "review")


case("render: upstream.file object", "upstream field", render_bad_upstream)


def render_valid(b):
    b.write(".sqlreview/reviews/q/review.json", review(assumptions=[item("A1", CANARY)]))
    return b.run(SR, "render", "q", "review")


case("render: valid review (argv only)", "item.text", render_valid)


def delta_case(b):
    b.write("q.sql", f"SELECT '{CANARY}';\n")
    b.commit()
    fp = json.loads(b.run(SR, "fingerprint", "q.sql").stdout)
    fp.pop("sql_path")
    b.write(".sqlreview/reviews/q/review.json", review(**fp))
    b.write("q.sql", f"SELECT '{CANARY}2';\n")
    b.commit()
    return b.run(SR, "delta", "q")


case("delta: changed SQL", "SQL literal", delta_case, by_design=True)

# --- recurring decisions -------------------------------------------------------------------------------
case("recurring match: text object", "draft text", lambda b: b.run(RD, "match", b.write("d.json", scope(assumptions=[item("A1", {"x": CANARY})]))))

# --- release.sh ----------------------------------------------------------------------------------------
case("release check: claim id", "claim id", lambda b: b.run(RL, "check", "--stdin", stdin=json.dumps({"schemaVersion": 1, "tag": "v1.0.0", "status": "draft", "claims": [{"id": CANARY}]})))
case("release check: invalid JSON", "file contents", lambda b: b.run(RL, "check", "--stdin", stdin='{"x":"' + CANARY + '",,}'))


def release_criteria(b):
    b.write("answers.intake.json", sidecar(CANARY))
    b.write(".sqlreview/reviews/q/scope.json", scope(criteria_status=[
        {"criterion": "I1", "state": "applied", "confirmed_by": "e", "confirmed_at": "2026-11-01T00:00:00Z", "confirmed_revision": 1}]))
    b.commit()
    git(b.root, "tag", "v1.0.0")
    return b.run(RL, "criteria", "v1.0.0")


case("release criteria: canary criteria text (held table)", "intake criteria text", release_criteria)


def release_evidence_invalid(b):
    b.write(".sqlreview/reviews/q/review.json", review(kind=CANARY))
    b.commit()
    git(b.root, "tag", "v1.0.0")
    return b.run(RL, "evidence", "v1.0.0")


case("release evidence: invalid kind", "doc.kind", release_evidence_invalid)

# --- report --------------------------------------------------------------------------------------------
w = max(len(r["case"]) for r in RESULTS)
for r in RESULTS:
    if "error" in r:
        print(f"{r['case']:<{w}}  HARNESS ERROR {r['error']}")
        continue
    leak = [k for k in ("stdout", "stderr", "argv") if r[k]]
    tag = "by-design" if r["by_design"] else ("LEAK" if leak else "clean")
    print(f"{r['case']:<{w}}  exit={r['exit']!s:<4} {tag:<9} {','.join(leak) or '-':<20} {r['sample']}")
out = Path(tempfile.gettempdir()) / "no_echo_canary_results.json"
json.dump(RESULTS, open(out, "w"), indent=2)
print(f"results: {out}")
