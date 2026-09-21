# Claude plugin evals

Suites for `claude plugin eval` (Claude Code `>= 2.1.269`), which measures whether a
plugin's skills improve Claude's answers by running each case with and without the
plugin. Every run **makes real model calls** on your `claude` login: it costs money
and its scores vary between runs. It complements the packaging checks; it does not
replace them.

## Why suites live here

`claude plugin eval` only finds a suite inside the plugin root, but
`plugins/<plugin>/` is generated, copied verbatim to users on install, and has a
Codex twin under `dist/codex/plugins/`. Suites are therefore authored in
`evals/claude/<plugin>/`, and `scripts/eval-claude-plugin.sh` stages a throwaway
copy of the plugin with its suite and evaluates that. Neither shipped tree changes,
so the Codex packages and their gates are unaffected. Do not put a suite under
`skills/<name>/`: hidden directories there are copied into both targets.

## Running

```bash
scripts/eval-claude-plugin.sh go \
  --model claude-sonnet-5 --judge-model claude-haiku-4-5 --threshold 0.8
```

The script always passes `--trust-plugin`, `--no-publish`, and
`--max-cost-usd "${EVAL_MAX_COST_USD:-5}"`; anything after the plugin name is
forwarded. A manual run evaluates the **working tree**, uncommitted edits included;
set `EVAL_REV=<commit>` to evaluate a revision instead. `report.html` and `aggregate-result.json` land in `.eval-results/<plugin>/`
(gitignored). While iterating on graders, `--runs 1 --ablation none` cuts the calls
from six agent runs per case to one. A suite that grants `Bash` needs `bubblewrap`
and `socat` installed on Linux.

| Exit | Meaning |
|---|---|
| 0 | every case met `--threshold` |
| 1 | a case scored below it, or the suite failed to load |
| 2 | partial run: cost ceiling hit, or credentials rejected (`partialReason` in the JSON) |

## Git hook (local only, opt-in)

Evals run only on contributor machines; there is deliberately no GitHub Actions
workflow. The lefthook `pre-push` job `claude-plugin-eval` calls
`scripts/eval-changed-plugins.sh`, which **does nothing unless
`CLAUDE_EVAL_ENABLE=1`** — installing the hooks never starts paid model calls by
itself. Export it in your shell profile to opt in.

When enabled, it evaluates plugins whose `evals/claude/<plugin>/` suite or
`plugins/<plugin>/` tree changed in the update.
For existing refs, the hook compares the remote tip with the pushed commit.
For new refs or absent input, it compares the merge-base with `origin/main` with the pushed commit.
The hook stages the plugin and suite from that commit.
It sets `EVAL_REV` from git's pre-push input, or uses `HEAD` when input is absent.
Uncommitted edits never affect the score.

When several refs share a commit, the hook evaluates each selected plugin once.
It combines plugin selections across those refs, even when their remote tips differ.
If a comparison base is unavailable locally, the hook skips that update and reports an incomplete evaluation.
Strict mode then fails the push.

Reports for each commit go in `.eval-results/<plugin>/<commit>/`,
where `revision.txt` records the evaluated commit. Deletion-only pushes skip evaluation.
Set `EVAL_OUTPUT_DIR` to override the report directory for manual runs.
The hook appends the commit to this override to keep reports separate.

Things to know before opting in:

- The job runs in parallel with the hard pre-push gates, so a push they reject
  still spends, and every retry spends again (nothing is cached).
- `EVAL_MAX_COST_USD` is checked before each run starts; runs already in flight
  finish, so a run can overshoot the cap.

| Variable | Effect |
|---|---|
| `CLAUDE_EVAL_ENABLE=1` | required; without it the job is a no-op |
| `CLAUDE_EVAL_STRICT=1` | block the push on a score below threshold or a partial run (default: report only) |
| `CLAUDE_EVAL_ARGS` | replace the default `--model claude-sonnet-5 --judge-model claude-haiku-4-5 --threshold 0.8` |
| `EVAL_MAX_COST_USD` | per-plugin spend cap (default `5`; the `go` suite costs about $2.20 a run) |

## Writing a suite

`claude plugin eval init` interviews you in a terminal and writes cases into the
plugin root. Run it on a scratch copy, then move the result:

```bash
tmp="$(mktemp -d)" && cp -R plugins/go "$tmp/go" && (cd "$tmp/go" && claude plugin eval init)
mkdir -p evals/claude/go
cp -R "$tmp/go/evals/." evals/claude/go/
```

### Generated regex graders

A case that asks for a rewritten file is graded on that file only. Doing that in one
regex needs a long shared prefix, so write a readable `graders.spec.yaml` beside
`prompt.md` (the file's `package`, then per grader the code that must appear, `need`,
and must not, `forbid`) and generate `graders/*.md` from it:

```bash
pixi run python3 scripts/generate_eval_graders.py .          # write
pixi run python3 scripts/generate_eval_graders.py . --check  # fail on drift (pre-commit + unit tests)
```

Add `fixtures:` to the spec — a `good` rewrite plus `cases` that each `replace` text and
name the graders that must then fail. `tests/test_eval_regex_graders.py` grades them in
Python and Node, and also checks that the case's unchanged original fails every grader
and that a before/after reply quoting the original still passes. Hand-written graders of
other types (`tool_used`, `llm`) in the same directory are left alone.

Sync strips `name:` from packaged skills, so a `tool_used: Skill` grader matches
the leaf: `input_match: '"skill"\s*:\s*"(?:[\w-]+:)?naming"'` for `/go:naming`.
Prefer `regex`, `tool_used`, and `file_exists` graders (free, deterministic) and
keep `llm` graders for short outputs.

Lessons from `go/naming-rewrite`, all covered by `tests/test_eval_go_naming_graders.py`:

- **Scope a regex to the artefact, not the whole reply.** Replies routinely quote
  the original identifiers in their explanation, so a `not_contains` or negative
  lookahead over `last_message` fails correct answers (a small judge model made the
  same mistake). Its graders anchor on the last fenced go block (` ``` ` or `~~~`,
  matched at a line start with a backreference for the closer) that opens with the
  package clause, and skip Go comments and literals inside it.
- **Never let a grader pass on an empty reply.** Pair every absence check with a
  presence check.
- **Test graders in the engine that runs them.** Patterns are JavaScript regexes;
  the fixtures grade every reply in Node as well as Python and require agreement.
- **Guard against catastrophic backtracking.** A skippable token that can also be
  read character by character backtracks exponentially and would hang a run; make
  it atomic with `(?=(token))\N` and keep a many-comments fixture with a time limit.

What the `go` suite currently measures (sonnet-5, 5 runs per arm):

| Case | WITH | W/OUT | Δ | What the no-plugin arm gets wrong |
|---|---|---|---|---|
| `expensive-getter` | 1.00 | 0.50 | +0.50 | names the DB query `Products()`, only dropping `Get` (5/5) |
| `naming-rewrite` | 1.00 | 0.73 | +0.27 | keeps the stuttering `account.AccountHTTPClient` (4/5) |
| `errors-and-constants` | 1.00 | 0.80 | +0.20 | keeps the error *type* named `ErrInvalidPayload` (3/5) |
| `interfaces-and-types` | 1.00 | 1.00 | 0.00 | nothing — tagged `saturated` |

A Δ of 0 means the model already does this without the skill, so that guidance is a
candidate for cutting under CONTRIBUTING's "non-inferable delta" rule; the case is kept
as a regression guard. One model and five runs is evidence, not proof.

Read Δ only with enough runs: this case measured −0.22 at 3 runs per arm and +0.10
at 10 on the same skill, so it sets `runs: 5` and conclusions were drawn at 10.
