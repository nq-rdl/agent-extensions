# Tools and docs skills review (#305–#309)

This record follows the pilot protocol in epic #312 for the tools and docs
family: `bitwarden`, `starrocks`, `rust-explain`, `quarto-authoring`,
`quarto-alt-text`, `writerside`, `obsidian-markdown`, `obsidian-cli`,
`obsidian-bases` (follow-ups only), `ansible`, `go-naming`, `go-secure`,
`charm-tui`, `sops`, `argo-cd`, `defuddle`, and `pixi`. The earlier
[progressive-disclosure pilots](../progressive-disclosure-pilots.md) (#304) set
the evidence standard; `obsidian-bases` keeps the structure that #423 gave it.

The tasks, invariants, prompts, and expected outcomes below were recorded
**before** any skill content edit, at source revision `4817a19`
(`epic/skill-review`, v0.36.2 plus #301, #303, and #304).

## Baseline sizes

Measured with `asctl repo-check --size-report` at `4817a19`. Approximate tokens
are body bytes / 4, not measured model usage.

| Skill | Body lines | Approx. body tokens | References |
|---|---|---|---|
| quarto-authoring | 311 | 1634 | 19 |
| go-secure | 297 | 2124 | 1 |
| ansible | 294 | 2380 | 1 |
| obsidian-bases | 261 | 2127 | 2 |
| starrocks | 251 | 2154 | 3 |
| bitwarden | 248 | 1919 | 3 |
| obsidian-markdown | 192 | 1268 | 3 |
| quarto-alt-text | 192 | 1679 | 0 |
| charm-tui | 164 | 1885 | 8 |
| argo-cd | 162 | 1159 | 0 |
| go-naming | 114 | 831 | 0 |
| obsidian-cli | 102 | 669 | 0 |
| rust-explain | 100 | 1261 | 4 |
| writerside | 98 | 1558 | 10 |
| sops | 87 | 1188 | 2 |
| pixi | 71 | 621 | 24 |
| defuddle | 37 | 184 | 0 |

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **bitwarden**: CRITICAL: three divergent implementations of the same shell
  functions (SKILL.md, `references/shell-functions.rst`, `scripts/bw-env.sh`);
  only the script adds the `export` prefix, so the SKILL.md `bwc` stores a note
  that `bwe` cannot export. MODERATE: Quick-start puts a token on the command
  line (`--arg secret "ghp_xxxx"`). MODERATE: Pattern 2 uses GNU-only
  `grep -oP`. Recommendation: route to the script, COMPRESS.
- **starrocks**: MODERATE: body repeats the references' SQL examples; decision
  tables are the non-inferable part. MODERATE: no minimum version while
  examples use version-gated features. Recommendation: COMPRESS, pin.
- **rust-explain**: KEEP. The audit's proposal to drop the reading-vocabulary
  reference is tested below rather than accepted.
- **quarto-authoring**: MODERATE: body duplicates the reference examples
  (figures, tables, callouts, citations, workflows); cell-option syntax and
  label prefixes are the non-inferable part. MINOR: description is a topic list.
- **quarto-alt-text**: MODERATE: written for one book project ("this project",
  `numeric-splines.qmd`, chapter prose); the only verification is a
  `#| label: fig-` grep that misses Markdown images and unlabelled cells.
- **writerside**: MODERATE: the builder tag is repeated about ten times in
  three references with no owner or provenance.
- **obsidian-markdown**: MODERATE: description triggers on generic
  "frontmatter" and "tags"; body restates generic Markdown/LaTeX/Mermaid.
- **ansible**: MODERATE: "Before writing any Ansible content, read
  `role-reference.rst`" loads role scaffolding for non-role work. MINOR:
  description is 690 characters.
- **go-naming / go-secure**: MINOR: descriptions over 400 characters; go-secure
  cites a CVE whose wording needs checking.
- **charm-tui, sops, argo-cd, defuddle, obsidian-cli**: MODERATE each:
  requirements and examples not checked against the actual tool.
- **pixi**: MODERATE: 24 converted upstream pages without provenance; decision
  deferred to #309 evidence.

## Invariants

"Where" names the file that owns the detail after the change.

### bitwarden (#305)

| ID | Invariant | Where |
|---|---|---|
| BW-1 | Personal Password Manager `bw`, not Secrets Manager `bws` | SKILL.md |
| BW-2 | One shell implementation, `scripts/bw-env.sh`; other files route to it | script |
| BW-3 | `bwc` then `bwe` round-trips a `.env` (comments, quoted and unquoted values, existing `export`) | script, tested |
| BW-4 | No function prints stored values, except `bwf` (for capture) and `bwdotenv` (explicit plaintext file) | script, tested |
| BW-5 | `BW_SESSION` stays in memory; prefer item IDs in scripts; `bw sync` for stale data; CI uses API key login | SKILL.md |
| BW-6 | `bwdotenv` writes plaintext: delete after use, never commit | script + SKILL.md |

### starrocks (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| SR-1 | Table-type, loading-method, and index decision tables | SKILL.md |
| SR-2 | Primary Key for mutable/CDC data, Duplicate Key for append-only | SKILL.md |
| SR-3 | Collect CBO statistics after bulk loads | SKILL.md |
| SR-4 | Each version-gated feature states its minimum version; no blanket 3.x claim | SKILL.md + compatibility |
| SR-5 | Repeated SQL examples are reachable in references | references |

### rust-explain (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| RE-1 | Verify-canonical guard and the compile trust boundary (`env!`/`include_str!`) | SKILL.md, tooling.rst |
| RE-2 | Silent-bug radar for numeric code | numeric-idioms.rst |
| RE-3 | Tested toolchain context is stated | tooling.rst |

### quarto (#305, #306, #307, #308)

| ID | Invariant | Where |
|---|---|---|
| QA-1 | Cell options use the language comment plus `|` (`#|`, `%%|`, `//|`) and dashes, not dots | quarto-authoring SKILL.md |
| QA-2 | Cross-reference label prefixes `fig-`, `tbl-`, `sec-`, `eq-` | quarto-authoring SKILL.md |
| QA-3 | Every task in the routing table reaches its reference | quarto-authoring SKILL.md |
| QT-1 | Alt text: chart type first, variables, key insight, complements `fig-cap` | quarto-alt-text SKILL.md |
| QT-2 | Figures are found without assuming labels or one project layout | quarto-alt-text SKILL.md |
| QT-3 | Verification inspects the rendered HTML `alt` attributes when Quarto is available, with a source-only fallback | quarto-alt-text SKILL.md |

### writerside (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| WR-1 | One owner for the builder image and tag, with provenance | docker-deployment.rst |
| WR-2 | Build examples run as written | docker-deployment.rst |
| WR-3 | `MODULE_INSTANCE` is `Module/instance`; group builds need `IS_GROUP` | docker-deployment.rst |

### obsidian (#305, #306, #308)

| ID | Invariant | Where |
|---|---|---|
| OM-1 | Routing needs an Obsidian or vault signal, or an explicit request; generic frontmatter or tags do not suffice | description |
| OM-2 | Naming Obsidian is enough; no special syntax needed to route | description |
| OM-3 | Wikilinks vs Markdown links, embeds, callouts, block IDs, comments, highlights | SKILL.md |
| OM-4 | Feature applicability (properties, CLI) is stated from the official help source | SKILL.md / compatibility |

### ansible, go (#306, #307)

| ID | Invariant | Where |
|---|---|---|
| AN-1 | FQCN, lean roles, `import_tasks` default, check-then-apply, `no_log` on secrets | SKILL.md |
| AN-2 | `role-reference.rst` is read for role work, not for every Ansible task | SKILL.md |
| GO-1 | go-naming and go-secure keep their current routing on the existing `go` suite prompts | descriptions |

### sops, charm-tui, argo-cd, defuddle (#308)

| ID | Invariant | Where |
|---|---|---|
| SO-1 | Every command example runs against the tested sops/age versions | SKILL.md, references |
| CT-1 | Quick start compiles against the tested Charm v2 modules; Go minimum matches their `go.mod` | SKILL.md |
| AC-1 | Examples use live repositories and documented fields | SKILL.md |
| DF-1 | Install and flags match the published CLI | SKILL.md |

### pixi (#309)

A decision record, not a content rewrite. Tasks: consumer environment
creation, existing-project maintenance, and one less common workflow. Criteria:
network availability, provenance, broken links, maintenance burden. No
unconditional deletion.

## Behavioural protocol

Same harness as #304: `claude -p` (Claude Code CLI) with `--plugin-dir` on a
temporary copy of the generated plugin tree. The **original** copy is
`plugins/<bundle>/` exported from `4817a19`; the **revised** copy is regenerated
from this branch. Runs use a scratch working directory outside the repository,
`--output-format stream-json --verbose`, `--permission-mode dontAsk`,
`--settings '{"disableAllHooks": true}'`, model `claude-sonnet-5`, and tools
limited to `Skill Read Glob Grep` unless a case says otherwise. The
marketplace is not installed. Observed per run: `Skill` calls, reference
`Read` calls, loaded characters, turns, cost, and a graded answer.

### Prompts and expected outcomes

| Case | Plugin | Kind | Prompt (abridged; full text in the results) | Expected |
|---|---|---|---|---|
| B1 | bitwarden | normal | Store the `.env` in this folder in Bitwarden and load it in new shells | routes to `secrets`; uses or points to `scripts/bw-env.sh`; no secret on the command line |
| B2 | bitwarden | negative | Use Bitwarden Secrets Manager `bws` machine accounts | does not present `bw` Password Manager commands as `bws` |
| O1 | obsidian | positive, no syntax | "Write an Obsidian note for today's stand-up with links to the Alpha and Beta project notes" | `obsidian:markdown`; wikilinks |
| O2 | obsidian | negative | "Add YAML frontmatter with title, tags and date to this README.md for our MkDocs site" | not `obsidian:markdown`; no wikilinks |
| O3 | obsidian | ambiguous | "In my vault, make the note link to its sources and hide the draft paragraph" | `obsidian:markdown`; `%%` comment |
| Q1 | quarto | normal | Write a `.qmd` with an R figure cell: label, caption, hidden code, cross-reference | `quarto:authoring`; `#|` options with dashes; `fig-` label; `@fig-` |
| Q2 | quarto | normal | Add alt text to the figures in the provided `analysis.qmd` (fixture with a labelled cell, an unlabelled cell and a Markdown image) | `quarto:alt-text`; all three figures handled |
| Q3 | quarto | negative | Convert this Markdown table to HTML | no quarto skill |
| A1 | ansible | normal, role | Scaffold a role that installs and configures chrony | `ansible`; reads `role-reference.rst` |
| A2 | ansible | normal, non-role | Fix this playbook task that uses `dnf` short name and add group_vars for NTP servers | `ansible`; no `role-reference.rst` read |
| G1 | go | routing | The four `evals/claude/go` prompts | naming/secure routed as at baseline |
| S1 | starrocks | gotcha | "Our StarRocks cluster is 3.3. Plan bulk export over Arrow Flight SQL" | states 3.5+ requirement |
| W1 | writerside | normal | GitHub Actions step to build the `hi` instance with Docker | pinned builder image from one owner; valid command |
| R1 | rust | explanation | Explain a closure/iterator ownership snippet, with and without `reading-vocabulary.rst` | equal or better correctness with the reference |
| P1–P3 | pixi | #309 | New Python env with a C library; update a lockfile in an existing project; build a pixi-pack bundle | correct commands; reference use observed |

---

Everything below was recorded **after** the edits, on branch
`epic312/tools-docs`.

## Status at hand-off (2026-09-29)

Work stopped on a coordinator wind-down request. Nothing below is claimed
beyond what is listed as run.

### Behavioural results so far

Harness: `claude -p` 2.1.284, `claude-sonnet-5`, `--plugin-dir` on a temporary
copy (original = `plugins/<bundle>` at `4817a19`, revised = working tree),
`--setting-sources project,local --strict-mcp-config`, tools `Skill Read Glob
Grep`. Graded by the regexes in the scratch `grade.py` plus manual reading.
Paid spend: **USD 7.02** over 111 recorded runs, plus a few runs aborted
twice (a staging race, then the wind-down) whose cost was not captured
(estimate under USD 0.5).

| Case | Original | Revised | Note |
|---|---|---|---|
| B1 bitwarden normal | 2/2 hand-rolled functions, `export` prefix left to a `sed` hack | 2/2 route to `scripts/bw-env.sh` | routing `secrets` in all runs |
| B2 Secrets Manager negative | not routed, answered with `bitwarden/sm-action` | same | grader regex (`bws`) too strict; manual pass |
| O1 "write an Obsidian note" | routed 2/3 | final wording 3/3 (first rewrite 0/3, fixed) | |
| O2 docs-site README frontmatter (negative) | 0/2 routed | 0/11 routed across wordings | |
| O3 vault fixture, no "Obsidian" word | 1/1 | 3/3 (d2), 3/3 (d4) | wikilink, heading link, `%%` in all |
| O4 table in "my Obsidian vault" | routed 2/6 | 1/6 (final wording) | escaped pipes correct in all 12 without the skill; noise |
| Q1 quarto cell options | pass 1/1 | pass 1/1 | body 6,908 → 4,883 chars loaded |
| Q2 alt text, Jupyter doc | **0/3**: multi-line `fig-alt: \|` (breaks under Jupyter) | **3/3** one-line values, all three figures | |
| Q3 negative | not routed | not routed | |
| A1 role scaffold | pass, read role-reference | pass, no reference read | |
| A2 playbook fix | pass, no reference read | pass, no reference read | |
| G1/G2/G3 go routing | naming / secure / none | same | 1 run each |
| S1 StarRocks 3.3 export | pass 2/2 | pass 2/2 | model already knew; no regression |
| W1 Writerside CI | 0/2 avoided `grep ERROR` gate | 2/2 exit code or report | |
| SO1 sops `.env.enc` decrypt | **0/2** dotenv type flags | **2/2** | |
| C1 teatest golden test | **0/2** (wrong import path, `KeyRunes`) | **2/2** | |
| R1/R2 rust-explain with vs without `reading-vocabulary.rst` | original 3/3 (R1) | variant runs **incomplete** (killed at wind-down) | not evidence |
| P1–P3 pixi with skill vs no plugin | not run | not run | |

### Per-issue dispositions

| Issue | Candidate | Disposition | Evidence |
|---|---|---|---|
| #305 | bitwarden | Changed | `bw-env.sh` owner, tests `tests/test_bitwarden_bw_env.py` (12 of 16 failed before the fix; all 18 pass after; also run in zsh 5.9 + BusyBox awk), B1 |
| #305 | starrocks | Changed | decision tables kept; ANALYZE/MV SQL routed; commit `982cd8c` |
| #305 | rust-explain | **Retained** | completed R1/R2 comparison below; no demonstrated task/loading benefit from removal |
| #305 | quarto-authoring | Changed | body 311 → about 110 lines, routes per task; Q1 |
| #305 | writerside | Changed | one owner for builder tag; runnable examples; W1 |
| #305 | obsidian-markdown | Changed | vault gotchas (verified against obsidian-help `bc5b4f2`), generic examples dropped |
| #306 | ansible, go-secure, go-naming, quarto-authoring, obsidian-markdown | Changed | descriptions 640/573/466/466/262 → 385/370/373/385/395 chars; O1–O4, A1–A2, G1–G3 |
| #307 | ansible | Changed | role-reference scoped; A1/A2 |
| #307 | quarto-alt-text | Changed | origin assumptions removed; `scripts/check-alt.sh` + `tests/test_quarto_alt_text_check.py` (failed before, 12 pass); Q2 |
| #308 | charm-tui | Separate factual fix | compiled against bubbletea v2.0.10 etc.; Go 1.26+; C1 |
| #308 | Quarto/Obsidian applicability | Changed | tested Quarto 1.9.38/1.10.18; Obsidian 1.9+ properties, CLI 1.12.7+ |
| #308 | sops/age | Separate factual fix | executed with sops 3.13.3, age 1.3.2, Vault 2.1.1 dev; SO1 |
| #308 | StarRocks | Separate factual fix | per-feature minimums, v3.3.5+ as written |
| #308 | argo-cd | Separate factual fix | `install-cli.sh` always failed (no `.sha256` assets); obsolete Helm repo, missing chart version |
| #308 | Writerside provenance | Changed | builder 2026.09.0357 documented, examples run with 2026.02.8644 |
| #308 | defuddle, rust-explain | Changed | tested versions recorded; `let … else` example corrected |
| #308 | pixi | **Changed** | 0.78.0 baseline, provenance, canonical/offline guard and executed consumer checks; see decision below |
| #308 | obsidian-bases follow-up | Changed | guard now covers older version / unreachable help |
| #309 | pixi and 24 references | **Retained** | P1–P3 with/without comparisons and targeted repeat fixes; offline pack/unpack executed |
| — | obsidian-bases date subtraction | Deferred | obsidian-help `bc5b4f2`: `Bases syntax.md` (last changed `ed4f6f4`, 2026-03-26) still says milliseconds; `Functions.md` documents `duration()` but no `.days`; needs an Obsidian instance |

### Not done / next steps

1. Rerun R1/R2 (`orig` vs `novocab` variant, 3 each) and record the
   rust-explain reference decision (#305). R1 is a false-premise case: the
   snippet does not compile (E0505, checked with rustc 1.97.1).
2. Run P1–P3 (`orig` = current skill vs `none`), then write the #309 pixi
   decision record; add `compatibility:` (pixi 0.78.0 checked), provenance
   (converted pixi.prefix.dev pages, vendored by 2026-04-26 via
   agent-skills v0.6.0) and a verify-canonical guard.
3. Fill in the per-run table above with loaded-content numbers for each
   case (available in the scratch `all-summary.jsonl`).
4. Codex copies were regenerated by `sync-plugins.sh`; the Codex smoke test
   was not run.

### Where the scratch material lives

`/tmp/claude-1001/-home-rudolfjs-dev-rdl-nq-rdl-agent-extensions/15b2cf65-4e02-4635-9f01-fd1df4014e8d/scratchpad/`:
`runs/` (runner `run.py`, `cases.json`, `grade.py`, `out/*.jsonl`,
`all-summary.jsonl`, fixtures), `verify/` (sops, charm, writerside, misc,
docs, bw logs and fixtures).

### Known issues

- The bitwarden npm check created `~/.config/Bitwarden CLI/` (an empty
  data file) on the host; removal was refused by the permission system and is
  left to the user.
- A broad `pkill -f run.py` during a restart may have stopped other agents'
  runner processes that shared the name.

## Rust vocabulary decision (#305, 2026-09-29)

**Retain** `reading-vocabulary.rst`; reject deletion in this PR. Compared the
original `4817a19` plugin with the saved `novocab` variant (file and its routes
removed). The two original R1/R2 prompts above ran twice per variant in Claude
Code 2.1.284 / claude-sonnet-5 with Skill/Read/Glob/Grep, no shell, hooks disabled,
and independent temporary workspaces. All eight invoked `rust:explain`.

| Task | Original | Without vocabulary | Reference loading |
|---|---|---|---|
| R1: borrowed word slices used after `drop(s)` | 2/2 identify E0505 and give a valid lifetime/owned-string fix | 2/2 same core diagnosis/fix | Vocabulary read 0/2 in both; tooling read 1/2 original, 0/2 variant |
| R2: map value reference used after `clear()` | 2/2 identify E0502 and use `.copied()` | 2/2 same core diagnosis/fix | Tooling read 2/2 in both; vocabulary read 0/2 |

The archived, previously ungraded R2 variant runs 1 and 3 also give the right
E0502 diagnosis and `.copied()` fix; variant run 2 and all archived R1 variant
runs were incomplete and are not successes. The new run replaces that missing
comparison. Rustc 1.97.1, edition 2021, `--crate-type lib` reproduced both errors
and compiled the minimal fixes. These were trusted, self-contained snippets;
no Cargo build scripts or runtime execution were involved.

The comparison does **not** demonstrate that removing the reference reduces
loaded context: the originals never read it. Some R1 answers in both variants
also overstate the need for an explicit `+ 'a` bound: the item type already
mentions `'a`, and the fixed example compiled without that bound. The core
borrow-diagnostic score is not a claim that every explanatory aside is correct.
The reference's removal has no demonstrated task or loading benefit and these
two tasks do not cover its full ownership/closure/iterator content. Retention
preserves the existing offline resource and public route; no incoming link,
registry member or grouping changes. A broader deletion needs better task
coverage, not a line-count argument.

## Pixi decision and verification (#308/#309, 2026-09-29)

**Retain** `pixi:env` and all 24 references. The consumer scope remains general
Pixi work, not this catalog's tooling. Both Claude and Codex publish `pixi:env`;
there are no hooks, preloads, grouping changes or public removals. No replacement
or migration is needed. Reference reading works offline; solving, package
fetches and tool installation need a connected build machine unless cached.

Provenance is now explicit: the pages were converted from pixi.prefix.dev and
vendored through agent-skills v0.6.0 at `659c438` (2026-04-26); the upstream
snapshot revision was not recorded. Compatibility names the checked Pixi 0.78.0
CLI, keeps the pixi-build preview requirement, and does not claim every old
example was tested. The canonical-source guard includes version mismatches and
unavailable sources. The pack page records its local delta and pixi-pack 0.7.11
verification. The previous scan found 0 broken links / 76 redirects; redirects
are not evidence that old API examples remain valid.

Predeclared consumer prompts, each run twice with the skill and twice without:

1. P1: create a Python 3.12 workspace with NumPy and the GDAL C library, plus a
   pytest task; provide commands and manifest, execute nothing.
2. P2: in the fixture (Python 3.12, NumPy `>=1.26,<2`, pandas, linux-64 and
   osx-arm64, no lockfile), upgrade NumPy, isolate ruff in dev and refresh the
   lock without installing; provide commands and manifest changes only.
3. P3: ship that environment to an offline linux-64 server without Pixi;
   provide packaging/unpacking commands only.

Claude Code 2.1.284 / claude-sonnet-5, Skill/Read/Glob/Grep, hooks disabled,
independent workspaces. “Initial skill” is the unchanged reference tree plus
provenance/guard lines. The consumer corrections followed those baselines.

| Task | Without skill | Initial skill | After targeted correction |
|---|---|---|---|
| P1 | 2/2 include a usable pytest task and dependency | 1/2; other run omitted pytest | 2/2 include pytest after clarifying that task registration adds no executable dependency |
| P2 | One usable plan; one combines mutually exclusive feature/environment flags | Both isolate ruff and avoid installation; one falsely says a named env excludes default | 2/2 preserve default-feature inheritance and use valid separate flags |
| P3 | 0/2: invented `pixi-pack pack/unpack` commands | 0/2 complete: right tool/flags but missing lockfile | Final 2/2 include lock, default environment, consistent `pixi exec`, Bash self-extraction |

An intermediate P3 rewrite added the lock prerequisite but both repeats copied
an absent `prod` environment from the reference; one also assumed `pixi exec`
installed a global tool. Both failed. The final reference uses the fixture's
default environment and one runnable recipe. An intermediate P1 repeat still
omitted pytest (1/2); its final explicit task-dependency check then passed 2/2.
These failures are part of the decision, not discarded successes.

Execution evidence, separate from model answers:

- Pixi 0.78.0 rejects `add --feature dev --environment dev --no-install` (exit 2).
  A two-feature lock probe confirms dev includes default dependencies unless
  `no-default-feature=true`; default remains free of the dev-only dependency.
- pixi-pack 0.7.11 fails without `pixi.lock` (exit 1). `pixi lock`, followed by
  `pixi exec pixi-pack --platform linux-64 --create-executable pixi.toml`, succeeds.
- The resulting archive unpacked in a node:22-bookworm container with
  `--network=none` and no Pixi. Its Python imported NumPy 1.26.4 and pandas 3.0.6.
  The self-extractor needs Bash: the evaluator's first attempt with `sh` failed
  on pipefail; `bash environment.sh` succeeded. No user project changed.

Both final P3 runs read only `pixi_pack.rst`, not all 24 pages. Initial P3 loaded
about 3.2k skill-body characters; final about 4.0k (including injected arguments),
plus the selected reference. This is a correctness improvement with more loaded
content, not a compression claim. Other pages were not all behaviourally tested;
the observed offline-packaging benefit supports selective retention, not a
claim that every converted page is current. Version strings in generated model
manifests are illustrative until solved; the GDAL environment was not installed
in this review.
