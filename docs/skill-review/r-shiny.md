# R and Shiny skill review (#304–#308)

This record follows the pilot protocol in epic #312 and continues
[the #304 pilots](../progressive-disclosure-pilots.md), which covered
`r-lib-cli` and the Shiny theming consolidation. It covers the remaining R and
Shiny items:

- **#304**: `r-lib-cran-extrachecks`, `r-lib-mirai`, `r-lib-cli-app`,
  `r-lib-testing`, `r-lib-package-dev`, and `r-lib-lifecycle`.
- **#306**: descriptions for `r-lib-cli`, `r-lib-package-dev`, `r-lib-lifecycle`,
  `r-lib-mirai`, `shiny-bslib`, `r-lib-testing`, and `r-expert`. Also two routing
  cases: R expert versus the specialists, and Shiny theming versus bslib.
- **#308**: the R cli/Rapp/mirai/testthat/package-tool rows and the Shiny
  bslib minimum versions.
- **#305/#307**: only the rows that name R skills, which are the authorization
  scope of `r-lib-cran-extrachecks` and `r-lib-package-dev`.

The pilot tasks, invariants, prompts, and expected outcomes below were recorded
**before** any skill edit, at source revision `4817a19` (branch
`epic/skill-review`).

## Baseline sizes

Measured with `asctl repo-check --size-report` at `4817a19`. Approximate tokens
are body bytes / 4. They are not measured model usage. Description length is the
folded YAML `description` in characters.

| Skill | Body lines | Approx. body tokens | References | Description chars |
|---|---|---|---|---|
| r-lib-cran-extrachecks | 456 | 3573 | 0 | 442 |
| r-lib-mirai | 438 | 2970 | 0 | 397 |
| r-lib-cli-app | 421 | 2638 | 1 | 344 |
| r-lib-testing | 419 | 2681 | 5 | 314 |
| r-lib-package-dev | 358 | 3044 | 0 | 526 |
| r-lib-lifecycle | 242 | 1344 | 1 | 452 |
| shiny-bslib | 231 | 2390 | 13 | 411 |
| shiny-bslib-theming | 212 | 2055 | 4 | 373 |
| r-lib-cli | 181 | 1790 | 5 | 689 |
| r-expert | 47 | 575 | 0 | 362 |

## Pilot invariants

These invariants must survive the change. "Where" names the file that owns the
detail after the change.

### r-lib-cran-extrachecks

| ID | Invariant | Where |
|---|---|---|
| CX-1 | Correct pass/fail reasoning: separate what `R CMD check --as-cran` reports from recurring CRAN reviewer requests and from organisation conventions. Each mandatory claim is verified against CRAN policy, Writing R Extensions, or execution | SKILL.md |
| CX-2 | Checklist coverage: Title, Description, `\value`/`@return`, examples (`\dontrun{}` vs `\donttest{}`, commented-out code, unexported functions), URLs (redirects, file URIs), `cph`, LICENSE year, method references | SKILL.md checklist; detail in a reference |
| CX-3 | Repository context: edit `README.Rmd` rather than `README.md` when it exists; leave aspirational CRAN URLs alone | SKILL.md |
| CX-4 | Authorization scope: a review request gets findings and no edits; a fix request may edit within the requested scope without asking again; the skill never submits to CRAN | SKILL.md |

### r-lib-mirai

| ID | Invariant | Where |
|---|---|---|
| MI-1 | Explicit dependency passing: `.args` (local environment) versus `...` (daemon global environment) | SKILL.md |
| MI-2 | Known mistakes: missing dependencies, unqualified package functions, reading `$data` before it resolves, mismatched `.args` names | SKILL.md |
| MI-3 | Daemon lifecycle: `daemons(n)`/`daemons(0)`, `with(daemons(n), ...)`, `onStop()` in Shiny | SKILL.md |
| MI-4 | `mirai_map()` needs daemons; `[.flat]`, `[.progress]`, `[.stop]` collection options | SKILL.md |
| MI-5 | The Shiny `ExtendedTask` example runs: every `input$` it reads is defined in the UI | SKILL.md or reference |
| MI-6 | Error values: timeouts, cancellation, and code errors are told apart correctly | SKILL.md |

### r-lib-cli-app

| ID | Invariant | Where |
|---|---|---|
| CA-1 | Type mapping table (R top-level assignment to CLI surface) | SKILL.md |
| CA-2 | `#|` annotations (front matter and per-argument) | SKILL.md |
| CA-3 | NA versus NULL for optional options and positional arguments | SKILL.md |
| CA-4 | Subcommands with `switch()` | SKILL.md |
| CA-5 | Shipping in `exec/` and `Rapp::install_pkg_cli_apps()` | SKILL.md |

### r-lib-testing

| ID | Invariant | Where |
|---|---|---|
| TT-1 | Setup versus helper semantics: which files `load_all()` sources and which the test runners source | SKILL.md |
| TT-2 | Modern testthat features carry correct version conditions | SKILL.md and references |
| TT-3 | Fixtures and mocking are reachable with "read when" routes | SKILL.md |
| TT-4 | Snapshot error tests use `expect_snapshot(error = TRUE)` | SKILL.md |

### r-lib-package-dev

| ID | Invariant | Where |
|---|---|---|
| PD-1 | Formatter policy: `air format .` only when `air.toml`/`.air.toml` exists; otherwise keep the project's formatter | SKILL.md |
| PD-2 | NEWS.md rules: user-facing only, single line, function name early, issue in parentheses, ordering | SKILL.md |
| PD-3 | Documentation and check requirements: complete roxygen blocks with `@returns`, `document()`, `check()`, pkgdown index | SKILL.md |
| PD-4 | Sibling routes resolve in the installed `r` bundle | SKILL.md |
| PD-5 | Stay within the requested edit scope; do not switch formatters or add files unasked | SKILL.md |

### r-lib-lifecycle

| ID | Invariant | Where |
|---|---|---|
| LC-1 | Badge conditions: only badge a stage that differs from the package's stage | SKILL.md |
| LC-2 | Release sweep: `deprecate_stop()` → remove, `deprecate_warn()` → `stop`, `deprecate_soft()` → `warn` | SKILL.md |
| LC-3 | Deprecation helpers with `user_env` | SKILL.md |
| LC-4 | `I()` for custom `what`/`with` text that reads correctly with "was deprecated in" | SKILL.md |
| LC-5 | Testing deprecations with snapshots and `lifecycle_verbosity` | SKILL.md |

### Routing and versions (#306, #308)

| ID | Invariant |
|---|---|
| RT-1 | Generic R language work stays with `r:expert`; package, cli, testing, and async tasks route to the specialist |
| RT-2 | Named routes resolve in the installed bundles (`r:lib-*`, `shiny:bslib*`) |
| RT-3 | Shiny theming requests go to `shiny:bslib-theming`; layout and component requests go to `shiny:bslib`; explicit invocation still works |
| RT-4 | Unrelated requests (Python) load no R or Shiny skill |
| SB-1 | `compatibility:` minimums match the functions each Shiny skill documents; features that need a newer version say so |

## Behavioural protocol

The harness matches the #304 pilots. It runs `claude -p` (Claude Code CLI) with
`--plugin-dir` pointing at a temporary copy of the generated plugin tree. The
**original** copy is `plugins/r` and `plugins/shiny` exported from `4817a19`.
The **revised** copy is regenerated from this branch. It does not install the
marketplace. Runs use a scratch working directory, model `claude-sonnet-5`,
`--output-format stream-json --verbose`, `--permission-mode dontAsk`, and
`--settings '{"disableAllHooks": true}'`. Tools are limited to
`Skill Read Glob Grep`. K1 and K2 also allow `Edit Write`, so the authorization
behaviour is observable. Their working directory is a copy of a fixture package
(`tidyclean`, described below). Files are hashed before and after each run.

Recorded for each run: the `Skill` calls, reads into the plugin, the injected
skill body size, whether files changed, turns, peak input tokens, and cost.

**Fixture `tidyclean`.** A minimal package with known problems. The Title starts
with the package name, reads "a toolkit ... in R", and is not in title case. The
Description is one sentence that starts "This package" and names dplyr
unquoted. The URL uses `http://`. There is no `cph` role and the LICENSE year is
2023. The exported `drop_empty_rows()` has no `@return` and no examples. The
internal `norm_names()` has an `@examples` block whose only line is commented
out. The README links to a `.Rbuildignore`d `CODE_OF_CONDUCT.md`.

### Prompts and expected outcomes

Prompts are stored verbatim in the harness (`harness/prompts.py`) and
summarised here.

| Case | Plugin | Kind | Prompt (summary) | Expected |
|---|---|---|---|---|
| K1 | r | normal, unauthorized edit | Review the package in the cwd for CRAN readiness; say whether `R CMD check --as-cran` or reviewers flag each item; "Do not change any files." | `lib-cran-extrachecks`; no file changes; finds Title, Description, `@return`/examples, commented-out example, http URL, file URI, `cph`; Title/Description attributed to the check (NOTE), `@return` to reviewers (CX-1, CX-2, CX-4) |
| K2 | r | authorized edit | Fix Title and Description so they pass CRAN review; only edit DESCRIPTION | Only DESCRIPTION changes, without asking again; Title without the package name, "toolkit" or "in R", in title case; Description does not start with "This package" and quotes 'dplyr' (CX-2, CX-4) |
| K3 | r | known gotcha | Check is clean, but exported functions lack `@return` and an internal helper has a commented-out example; will CRAN care? | Yes: reviewers ask for `\value` on exported functions and reject commented-out examples; use `@noRd` or remove examples on the unexported helper (CX-1) |
| M1 | r | normal (Shiny + mirai) | bslib app: pick a sample size, button runs `rnorm` on a mirai worker without blocking, then a histogram | `lib-mirai`; `ExtendedTask` + `mirai(..., .args =)`; every `input$` read is defined in the UI; daemons cleaned up (MI-1, MI-3, MI-5) |
| M2 | r | known gotcha | Fix `mirai(my_func(my_data))` failing about `my_func` | Passes `my_func` and `my_data` explicitly; the fixed code runs and returns 55 (MI-1) |
| M3 | r | known gotcha | Does `.timeout` work with `dispatcher = FALSE`; is the task cancelled; how to tell timeout or cancellation from an error | Timeout resolves (errorValue 5) without dispatcher but the task is not cancelled; `is_mirai_error()` is only for code errors; `is_error_value()` covers timeouts and cancellation (MI-6) |
| A1 | r | normal | Rapp `csvhead` with positional path, `--n`/`-n`, optional `--sep`, `--header/--no-header`; where to ship it | `lib-cli-app`; `NULL` positional, `5L`, `NA_character_`, `TRUE`, `#| short: n`; the script runs under `Rapp::run()`; `exec/` + `install_pkg_cli_apps()` (CA-1–CA-3, CA-5) |
| A2 | r | known gotcha | `out <- NULL` makes a required positional; want an optional `--out` | `out <- NA_character_` and `!is.na(out)` (CA-3) |
| T1 | r | known gotcha | Which of setup-db.R and helper-data.R does `load_all()` make available; does `devtools::test()` run setup? | Helpers are sourced by `load_all()` and by the test runners; setup files are not sourced by `load_all()` but are sourced by `devtools::test()` and `R CMD check` (TT-1) |
| T2 | r | known gotcha | Suggests `testthat (>= 3.1.0)`; can I use `expect_contains()`, `expect_all_equal()`, `expect_shape()`? | Needs a bump: `expect_contains()` 3.1.9, the other two 3.3.0; `expect_shape(m, dim = c(10, 5))` with a named argument (TT-2) |
| P1 | r | normal, formatter gotcha | Write the NEWS bullet for `fit_model()` gaining `weights` (#88); no air.toml; CI runs styler; which formatter? | `lib-package-dev`; one line, function first, `(#88)`; styler, not air; no file changes (PD-1, PD-2, PD-5) |
| L1 | r | normal | Deprecate `write_file(path)` for `file` in 1.4.0; how often is the warning shown? | `lib-lifecycle`; `deprecated()` + `is_present()` + `deprecate_warn("1.4.0", "write_file(path)", "write_file(file)")`; once per session (LC-*) |
| R1 | r | routing, generic R | Why is growing a vector in a loop slow; rewrite | `r:expert` or no skill, not a `lib-*` specialist (RT-1) |
| R2 | r | routing | cli error helper with plural wording, caller attribution, snapshot test (C1 from #304) | `r:lib-cli` (it did not route in #304) (RT-1) |
| R3 | r | negative | pandas groupby | No skill (RT-4) |
| R4 | r | routing | Parallelise `lapply(files, read_and_summarise)` over 4 workers | `lib-mirai`; helpers passed explicitly; `readr::` qualified; daemons reset (RT-1, MI-1) |
| S1 | shiny | routing | Light/dark toggle plus ggplot2 plots follow the app colours | `shiny:bslib-theming`; `input_dark_mode()`; thematic (RT-3) |
| S2 | shiny | routing, version | Toast on Save; which bslib version? | `shiny:bslib`; `toast()`/`show_toast()`; bslib ≥ 0.10.0 (RT-3, SB-1) |
| S3 | shiny | explicit invocation | `/shiny:bslib-theming` primary colour and Google font | Skill is used; `bs_theme(primary =, base_font = font_google("Inter"))` (RT-3) |

Each case runs once per version. A case is repeated when the two versions
disagree or the result looks unstable.

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **r-lib-cran-extrachecks**: MAJOR. Several "required" and "will be rejected"
  claims are reviewer anecdotes, not policy, and the skill does not say which is
  which. MODERATE: "Common Fix Patterns" repeats the Title, Description, and
  `@return` examples, and the final checklist repeats the body. MODERATE: the
  workflow says "make edits only when user approves" even when the user asked
  for the fix (#307). There is no verify-canonical guard. Recommendation:
  COMPRESS to one checklist and move the detail into a reference.
- **r-lib-mirai**: CRITICAL. The Shiny `ExtendedTask` example reads `input$n`,
  but the UI has no `n` input (found by reading; to be executed). MODERATE:
  remote/HPC, migration tables, and nested parallelism can be routed.
  Recommendation: fix, then COMPRESS.
- **r-lib-cli-app**: MODERATE. Two complete examples plus repeated installation
  prose; `R ≥ 4.1.0` and `v0.3.0` pins without provenance. Recommendation:
  COMPRESS; move the todo example to the existing reference.
- **r-lib-testing**: MAJOR. Version conditions look inconsistent (for example
  `expect_contains()` "v3.2.0+"), and the setup-file description conflicts with
  `references/fixtures.rst`. MODERATE: a generic BDD tour, "Common Patterns",
  and a Quick Reference restate testthat documentation. Recommendation: fix
  versions, then COMPRESS.
- **r-lib-package-dev**: MODERATE. A generic package tree and a delegation list
  repeated three times. MINOR: sibling names use canonical names (`r-lib-testing`)
  rather than the installed `r:lib-testing`. Recommendation: COMPRESS lightly.
  Keep the formatter and NEWS policy.
- **r-lib-lifecycle**: MINOR. The reference has no "read when" route. The
  "warns once per 8 hours" claim is to be checked. Recommendation: KEEP, with
  fixes.
- **r-expert**: MINOR. Delegation names are canonical rather than installed
  names; Shiny routes are in another plugin. Recommendation: KEEP; fix routes.
- **shiny-bslib**: MINOR. `compatibility:` says bslib ≥ 0.9.0 while the skill
  documents toasts and the code editor (to be checked). Recommendation: KEEP;
  fix the pin.

---

Everything below was recorded **after** the edits (revised = `c2cf95c`).

## Factual checks

Executed on 2026-09-29 in a scratch pixi environment: conda-forge R 4.5.3
with cli 3.6.6, rlang 1.3.0, testthat 3.3.2, withr 3.0.3, devtools 2.5.2,
pkgload 1.5.3, usethis 3.2.1, roxygen2 8.1.0, mirai 2.7.2, nanonext 1.10.3,
promises 1.5.0, shiny 1.14.0, bslib 0.12.0, lifecycle 1.0.5, Rapp 0.3.0,
styler 1.11.0, pkgdown 2.2.1, and air 0.11.0. bslib 0.9.0 was installed
from the CRAN archive. The source documents were fetched the same day.

| Skill | Finding | Source | Action |
|---|---|---|---|
| r-lib-mirai | The Shiny `ExtendedTask` example read `input$n`, but no such input existed. Under `testServer()` the task status was `error`, with "Error in rnorm(n): invalid arguments". With the UI fixed the status was `success`, with 50 values | executed | Fixed (`388bde3`) |
| r-lib-mirai | `.timeout` resolves to errorValue 5 even with `dispatcher = FALSE`. Only cancellation needs dispatcher: `stop_mirai()` returns FALSE without it | executed; `?mirai`, `?stop_mirai` | Fixed |
| r-lib-mirai | A cancelled mirai is errorValue 20, and `is_mirai_interrupt()` returns FALSE for it | executed; `?is_mirai_error` | Fixed |
| r-lib-mirai | The nested example failed on the daemon with `could not find function "daemons"`. It works once the calls use `mirai::` | executed | Fixed |
| r-lib-testing | `setup-*.R` is sourced by `devtools::test()` and `test_dir()` as well as by R CMD check, but not by `load_all()`. Helper files are sourced by both | executed; testthat special-files vignette | Fixed |
| r-lib-testing | `expect_contains()` and `expect_in()` need testthat 3.1.9, not 3.2.0. `expect_shape(m, c(10, 5))` errors, so the argument must be named (`dim =`). Shuffle and the slow reporter need 3.3.0. `with_mock()` has been defunct since 3.3.0 | testthat NEWS; executed | Fixed |
| r-lib-lifecycle | Since lifecycle 1.0.5, warnings are issued once per session rather than every 8 hours, and `signal_stage()` does nothing | lifecycle NEWS; executed | Fixed |
| r-lib-cran-extrachecks | On the fixture, `R CMD check --as-cran` flags the Title (package name, title case), the start of the Description, and the http→https redirect. It does not flag the missing `\value`, the commented-out example, the "toolkit ... in R" wording, the unquoted dplyr, or the missing `cph`. Default `devtools::check()` reports no NOTEs; with `remote = TRUE` it reports them. The file URI to an ignored file appears only with `_R_CHECK_CRAN_INCOMING_CHECK_FILE_URIS_=true` | executed | Labels for which tool catches each item |
| r-lib-cran-extrachecks | "HTTP rejected" was overstated: the URL check flags redirects. Sole-author `cph` is a reviewer request, not policy. Advice to use `pkg:::fun()` in examples was removed (a 2025 review asked for such examples to be removed, or the function exported) | URL_checks.html; policy revision 6875; extrachecks `a37e1ee`; shapr PR #442 | Fixed |
| r-lib-cli-app | Rapp 0.3.0 declares no R dependency, so the "R ≥ 4.1.0" claim was unsupported. The help output shown was stale. The first `#|` block becomes the front matter | Rapp DESCRIPTION; executed | Fixed; gotcha added |
| r-lib-package-dev | The NEWS example broke the skill's own ordering rule. `test_active_file(desc =)`, `use_air()`, styler, pkgdown, and `air format` were executed | executed | Fixed; the rest retained |
| r-expert | `|>` and `\(x)` need R 4.1, the `_` placeholder needs 4.2, and `_$col` needs 4.3 | R NEWS; executed | Retained |
| shiny-bslib | 90 of 98 used bslib exports exist in bslib 0.9.0. Toasts, `input_code_editor()`, `input_submit_textarea()`, and their updaters need 0.10.0 | executed | Marked |

## After sizes

| Skill | Body lines | References | Description chars |
|---|---|---|---|
| r-lib-cran-extrachecks | 456 → 119 | 0 → 1 | 442 → 336 |
| r-lib-mirai | 438 → 300 | 0 → 4 | 397 → 343 |
| r-lib-cli-app | 421 → 298 | 1 | 344 |
| r-lib-testing | 419 → 175 | 5 | 314 → 335 |
| r-lib-package-dev | 358 → 166 | 0 | 526 → 371 |
| r-lib-lifecycle | 242 → 247 | 1 | 452 → 343 |
| shiny-bslib | 231 → 231 | 13 | 411 → 399 |
| r-lib-cli | 181 | 5 | 689 → 372 |
| r-expert | 47 → 54 | 0 | 362 → 354 |

## Behavioural results

Conditions: Claude Code 2.1.284 with `claude-sonnet-5`. Original is `4817a19`
and revised is `c2cf95c`. There were 54 runs, costing USD 7.27 in total.
Executed grading covered M1 (inputs defined), M2 (returns 55), A1
(`Rapp::run()`), and K2 (re-checked with `R CMD check`). K1 labels and M3 were
checked by reading the answers.

| Case | Orig | Revised | Loaded content (skill body chars + reads) |
|---|---|---|---|
| K1 | 0/2 labels correct; 2/2 no edits | 2/2 labels correct; 2/2 no edits | 14.5k → 7.4k + cran-details.rst 9.5k (**more** in total) |
| K2 | 1/1 (DESCRIPTION only) | 1/1 | 14.5k → 7.4k |
| K3 | 1/1 | 1/1 | 14.5k → 7.5k |
| M1 | 2/2 | 2/2 | 12.3k → 9.9k + 2.0k reference read |
| M2 | 1/1 (no skill) | 1/1 (no skill) | — |
| M3 | 0/2 | 2/2 | 12.3k → 10.0k; orig made denied web calls |
| A1, A2 | 1/1 each | 1/1 each | 10.7k → 9.3–9.5k |
| T1 | 1/1 (read fixtures.rst 8.4k) | 1/1 (no reads) | 19.4k → 7.4k |
| T2 | 0/2 | 2/2 | 11.0k → 7.2–7.5k |
| P1 | 1/1 | 1/1 | 12.5k → 6.8k |
| L1 | 0/2 ("8 hours") | 2/2 | 5.6k → 5.8k |
| R1 | r:expert | r:expert | ~2.7k |
| R2 | 0/3 routed to lib-cli | 3/3 routed | 0 → 7–15k |
| R3 | no skill | no skill | — |
| R4 | lib-mirai | lib-mirai | 12.0k → 9.8k |
| S1 | bslib-theming | bslib-theming | ~8.4k + dark-mode.rst |
| S2 | 0/2 give the version | 2/2 say 0.10.0 | ~9.8k + toasts.rst |
| S3 (explicit) | 1/1 | 1/1 | not emitted |

## Dispositions

| Issue | Candidate | Disposition |
|---|---|---|
| #304 | r-lib-cran-extrachecks | Changed, plus separate factual fixes |
| #304 | r-lib-mirai | Separate factual fix (`388bde3`), then changed |
| #304 | r-lib-cli-app | Changed, plus a factual fix |
| #304 | r-lib-testing | Factual fix (`90d4a00`), then changed |
| #304 | r-lib-package-dev | Changed; formatter and NEWS policy retained |
| #304 | r-lib-lifecycle | Structure retained; factual fix and route added |
| #306 | r-lib-cli, r-lib-package-dev, r-lib-lifecycle, r-lib-mirai, shiny-bslib, r-lib-testing, r-expert | Descriptions changed, all ≤ 400 characters |
| #306 | Routing: R expert vs specialists; Shiny theming vs bslib | Resolved (R1, R2, R4, S1, S2) |
| #307 | cran-extrachecks / package-dev authorization | Changed: a review makes no edits, a fix stays in scope without asking again, and nothing is submitted |
| #308 | R cli/Rapp/mirai/testthat/package tools; Shiny bslib | Changed: verified pins and feature versions |
| #305 | none for R | Not applicable |

## Limitations

- One model and one host, with 1–3 repetitions per case.
- K1 loads more content after the change, because the new reference is read.
- R2 routing now loads 7–15k characters of skill for a task the model already
  answered correctly without it.
- In M3 revised run 1 the model invented `m$data$message` for an errorValue.
  This did not come from the skill.
- Remote and HPC mirai launchers were not exercised. No `evals/claude` suite
  was added.

## Status at hand-off

- **Done**: every row in the disposition table is committed on
  `epic312/r-shiny` and the plugins are synced. At `c2cf95c`, these passed:
  `validate-plugins.sh`, `asctl repo-check`, the unit tests, the `--check`
  generators, and the `check_*` scripts.
- **Not done**: reusable `evals/claude/r` and `evals/claude/shiny` suites,
  and more repetitions of S1, K2, and A1.
- **Scratch** (this session's scratchpad, shared with other agents):
  `harness/` (run_case.sh, batch.sh, summarise.py, grade.py, prompts.py with
  the verbatim prompts), `runs/<case>-<orig|rev>-<n>/`, `verify/*.R` and
  `*.out`, `renv/`, `lib-bslib090/`, and `fixtures/tidyclean/`.
- **Next steps**: port K1, K2, M3, T2, L1, and R2 into `evals/claude/r/` with
  deterministic graders and a unit test.
