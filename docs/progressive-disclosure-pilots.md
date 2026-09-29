# Progressive-disclosure pilots (#304)

This record follows the pilot protocol in epic #312. It covers three pilots
from issue #304: `obsidian-bases`, `r-lib-cli`, and the Shiny theming overlap
between `shiny-bslib-theming` and `shiny-bslib`. The other family items receive
a written disposition only.

The pilot tasks, invariants, prompts, and expected outcomes below were recorded
**before** any skill edit, at source revision `d804884` (release v0.36.2).

## Baseline sizes

Measured with the #303 size report (`asctl repo-check --size-report`, built
from `origin/epic/skill-review` commit `2deeedc` in a temporary directory; that
code is not part of this branch). Approximate tokens are body bytes / 4, not
measured model usage.

| Skill | SKILL.md lines | Body lines | Approx. body tokens | References |
|---|---|---|---|---|
| obsidian-bases | 504 | 493 | 3152 | 1 |
| r-lib-cli | 475 | 457 | 2601 | 5 |
| r-lib-cran-extrachecks | 464 | 456 | 3573 | 0 |
| shiny-bslib-theming | 459 | 444 | 3518 | 2 |
| r-lib-mirai | 451 | 438 | 2970 | 0 |
| r-lib-cli-app | 433 | 421 | 2638 | 1 |
| r-lib-testing | 427 | 419 | 2681 | 5 |
| r-lib-package-dev | 373 | 358 | 3044 | 0 |
| r-lib-lifecycle | 256 | 242 | 1344 | 1 |
| shiny-bslib | 237 | 222 | 2281 | 14 |

## Pilot invariants

These must survive the change. "Where" names the file that owns the detail
after the change; a critical warning stays in `SKILL.md` beside its example.

### obsidian-bases

| ID | Invariant | Where |
|---|---|---|
| OB-1 | Convert a date difference to a numeric field (`.days`, `.hours`) **before** `round()`/`floor()`/`ceil()` | SKILL.md |
| OB-2 | Schema skeleton: `filters`, `formulas`, `properties`, `summaries`, `views` | SKILL.md |
| OB-3 | Filter shapes: a string, or an object with exactly one of `and`/`or`/`not`, nested recursively; view filters are ANDed with global filters | SKILL.md |
| OB-4 | YAML quoting: single-quote formulas that contain double quotes; quote values containing `:` and other YAML indicators | SKILL.md |
| OB-5 | At least one complete, useful example | SKILL.md |
| OB-6 | Guard optional properties with `if()`; define every `formula.X` that is referenced | SKILL.md |
| OB-7 | Supported view types (checked against the official docs, see "Factual checks") | SKILL.md |

### r-lib-cli

| ID | Invariant | Where |
|---|---|---|
| RC-1 | Double braces `{{ }}` print literal braces; interpolate data with `{x}`/`{.val {x}}` instead of pasting it into the format string | SKILL.md |
| RC-2 | Quantity semantics for `{?}`: which value is the quantity, `qty()`, `no()`, zero/one/many forms | SKILL.md |
| RC-3 | Caller attribution: helpers take `call = caller_env()` and pass it to `cli_abort(call = call)` | SKILL.md |
| RC-4 | Snapshot output: test cli conditions with `expect_snapshot(error = TRUE, ...)` | SKILL.md |
| RC-5 | The catalogue (inline classes, progress, themes, ANSI) stays reachable from explicit routes | references |

### Shiny theming (shiny-bslib-theming, shiny-bslib)

| ID | Invariant | Where |
|---|---|---|
| SH-1 | Preset differences: `bs_theme()` defaults to the `"shiny"` preset; `preset = "bootstrap"` is vanilla Bootstrap; Bootswatch is opt-in | theming SKILL.md |
| SH-2 | Sass declaration placement: a variable that references another Bootstrap variable needs `bs_add_variables(.where = "declarations")` | theming SKILL.md |
| SH-3 | thematic font behaviour: `thematic_shiny()` changes fonts only with `font = "auto"` (or a `font_spec()`); call it before `shinyApp()` | theming SKILL.md |
| SH-4 | Dashboard class placement: `bslib-page-dashboard` on `page_sidebar()`, or on individual `nav_panel()`s rather than `page_navbar()` | theming SKILL.md |
| SH-5 | Contrast checks with `bs_get_contrast()` and WCAG AA targets | theming SKILL.md |
| SH-6 | `shiny-bslib/references/best-practices.rst` is reachable with a clear route | shiny-bslib SKILL.md |
| SH-7 | Every incoming link to a consolidated reference is repaired in the same change | both skills |

## Behavioural protocol

**Harness.** `claude -p` (Claude Code CLI) with `--plugin-dir` pointing at a
temporary copy of the generated plugin tree. The **original** copy is
`plugins/<bundle>/` exported from `d804884`. The **revised** copy is
`plugins/<bundle>/` regenerated from this branch. Sibling skills in the same
bundle are present in both copies so sibling routing can be observed; only the
pilot skills differ. This does not install the marketplace. Runs use a scratch
working directory outside the repository, `--output-format stream-json
--verbose`, `--permission-mode dontAsk`, tools limited to `Skill Read Glob
Grep`, and `--settings '{"disableAllHooks": true}'`. `claude plugin eval` was
not used: it needs a per-plugin eval suite and measures with/without the
plugin, not original versus revised.

**Observed per run.** Which skills were invoked (`Skill` tool calls), which
reference files were read (`Read` tool calls into the plugin), the size of the
loaded skill body plus reference reads, turns, duration, and cost. Answers are
graded against the expected outcome below by deterministic checks where
possible, plus manual review. A case is repeated only when the two versions
disagree or the result looks unstable.

### Prompts and expected outcomes

**obsidian** plugin (`bases`, `cli`, `markdown`):

| Case | Kind | Prompt | Expected |
|---|---|---|---|
| O1 | positive routing, normal task | "In my Obsidian vault, write the full contents of `Projects.base`: include notes tagged #project, show status, due date and days until due, group by status, and add a second cards view. Reply with the YAML only; do not create files." | `obsidian:bases` invoked; YAML parses; every filter object has one key; days-until-due uses `.days` and is guarded with `if()`; referenced formulas are defined |
| O2 | negative / sibling routing | "Write an Obsidian note that has a warning callout, a tag in the frontmatter, and embeds the 'Summary' heading from the note 'Q3 Plan'. Reply with the Markdown only; do not create files." | `obsidian:markdown` invoked; `obsidian:bases` not invoked |
| O3 | known gotcha (OB-1) | "My Obsidian base formula `((now() - file.ctime) / 86400000).round(0)` errors. Rewrite it to show the note age in whole days, and add a second formula with age in hours rounded to one decimal." | `.days`/`.hours` taken before `round()`; no division of the date difference |
| O4 | known gotcha (OB-3, OB-4) | "Give me a `.base` view named Current that hides notes whose status is \"done\" or that are tagged archived, and shows the status column with the display name Status: Current. Reply with the YAML only." | YAML parses; `displayName` quoted; formula strings with inner double quotes are single-quoted; one key per filter object |

**r** plugin (all eight R skills):

| Case | Kind | Prompt | Expected |
|---|---|---|---|
| C1 | positive routing, normal task | "In my R package, write a helper `check_columns(data, cols)` that errors with cli when required columns are missing. List the missing columns with correct singular/plural wording, report the error as coming from the user-facing function that called the helper, and add a testthat snapshot test. Reply with code only; do not create files." | `r:lib-cli` invoked; `cli_abort()` with `call = caller_env()` (or equivalent) on the helper; no `{?}` in a bullet without a quantity; `expect_snapshot(error = TRUE)` |
| C2 | negative / sibling routing | "Turn my R script into a command-line tool with `--input` and `--verbose` options that I can ship in my package's exec/ directory. Reply with code only." | `r:lib-cli-app` invoked; `r:lib-cli` not required |
| C3 | known gotcha (RC-1) | "`cli_abort(paste0(\"Invalid template: \", tmpl))` crashes with 'Could not evaluate cli {} expression' when `tmpl` is `\"{name}.csv\"`. Fix it, and show how to print the literal text `{placeholder}` with `cli_text()`." | interpolates `tmpl` (for example `{.val {tmpl}}`) instead of pasting; uses `{{placeholder}}` |
| C4 | known gotcha (RC-2) | "`cli_text(\"Element{?s} {bad} {?is/are} not positive.\")` fails with 'length(object) == 1 is not TRUE' when `bad <- which(x <= 0)` has two elements. Why, and how do I fix it?" | explains a numeric value is used as the quantity and must be length 1; fixes with `qty(length(bad))` plus non-numeric display, or by converting to character |

**shiny** plugin (`bslib`, `bslib-theming`):

| Case | Kind | Prompt | Expected |
|---|---|---|---|
| S1 | positive routing, normal task | "Theme my bslib Shiny dashboard: primary colour #1a5276, Google font Inter for body text, ggplot2 plots should match the app colours and fonts, and set the Sass variable progress-bar-bg to $secondary. Reply with code only." | `shiny:bslib-theming` invoked; `bs_add_variables(..., .where = "declarations")` for `$secondary`; `thematic_shiny(font = "auto")` before `shinyApp()` |
| S2 | ambiguous sibling routing | "Convert my fluidPage app that uses tabsetPanel and wellPanel into a modern bslib page_navbar layout with cards. Reply with code only." | `shiny:bslib` invoked; theming reference not needed |
| S3 | known gotcha (SH-4) | "My page_navbar app has a Dashboard tab and a Report tab. I want the grey dashboard background only on the Dashboard tab. Show the code." | `class = "bslib-page-dashboard"` on the Dashboard `nav_panel()`, not on `page_navbar()` |
| S4 | known gotcha (SH-1, SH-5) | "What is the difference between `bs_theme()` with no preset and `bs_theme(preset = \"bootstrap\")`, and how do I check that my custom primary colour has readable text on it?" | shiny preset versus vanilla Bootstrap; uses `bs_get_contrast()` and/or a WCAG AA ratio check |

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **obsidian-bases** — MODERATE: body holds three complete examples, four
  view-type snippets, the default-summary table, and a full troubleshooting
  section that repeats the duration and quoting warnings. MODERATE: no
  `compatibility:` pin and no verify-canonical guard, although Bases syntax
  changes between app releases. Recommendation: COMPRESS.
- **r-lib-cli** — MODERATE: most of the body restates public cli docs
  (inline class tour, headers, alerts, lists, progress basics); the
  non-inferable items (RC-2, RC-3, RC-4) are absent or buried in references.
  CRITICAL: a SKILL.md example (`check_required_columns`) uses `{?s}` in a
  bullet without a quantity (verified below). MODERATE: no version pin.
  Recommendation: COMPRESS and fix.
- **shiny-bslib-theming / shiny-bslib** — MODERATE: `shiny-bslib/references/theming.rst`
  duplicates a subset of `shiny-bslib-theming`; the thematic placement advice
  differs between the two skills ("before `shinyApp()`" versus "in the
  server"). MINOR: `best-practices.rst` is listed but has no route.
  Recommendation: consolidate, COMPRESS the theming body.
