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
