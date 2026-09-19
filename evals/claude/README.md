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
`--max-cost-usd "${EVAL_MAX_COST_USD:-2}"`; anything after the plugin name is
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

When enabled, it evaluates each plugin whose `evals/claude/<plugin>/` suite or
`plugins/<plugin>/` tree changed between the merge-base with `origin/main` and the
commit being pushed. Both the plugin and the suite are staged from that pushed
commit (`EVAL_REV`, taken from git's pre-push input, else `HEAD`), so uncommitted
edits never affect the score; `.eval-results/<plugin>/revision.txt` records what
was evaluated. Things to know before opting in:

- The job runs in parallel with the hard pre-push gates, so a push they reject
  still spends, and every retry spends again (nothing is cached).
- `EVAL_MAX_COST_USD` is checked before each run starts; runs already in flight
  finish, so a run can overshoot the cap.

| Variable | Effect |
|---|---|
| `CLAUDE_EVAL_ENABLE=1` | required; without it the job is a no-op |
| `CLAUDE_EVAL_STRICT=1` | block the push on a score below threshold or a partial run (default: report only) |
| `CLAUDE_EVAL_ARGS` | replace the default `--model claude-sonnet-5 --judge-model claude-haiku-4-5 --threshold 0.8` |
| `EVAL_MAX_COST_USD` | per-plugin spend cap (default `2`) |

## Writing a suite

`claude plugin eval init` interviews you in a terminal and writes cases into the
plugin root. Run it on a scratch copy, then move the result:

```bash
tmp="$(mktemp -d)" && cp -R plugins/go "$tmp/go" && (cd "$tmp/go" && claude plugin eval init)
mkdir -p evals/claude && cp -R "$tmp/go/evals" evals/claude/go
```

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

Read Δ only with enough runs: this case measured −0.22 at 3 runs per arm and +0.10
at 10 on the same skill, so it sets `runs: 5` and conclusions were drawn at 10.
