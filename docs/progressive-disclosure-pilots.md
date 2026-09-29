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

---

Everything below was recorded **after** the edits.

## Factual checks

Each claim was checked against a primary source before it was kept, changed,
or moved. R examples were executed in a throwaway pixi environment
(conda-forge R with cli 3.6.6, rlang 1.3.0, testthat 3.3.2, bslib 0.12.0,
shiny 1.14.0, thematic 0.1.8, sass) on 2026-09-29.

| Skill | Finding | Source | Action |
|---|---|---|---|
| obsidian-bases | Schema skeleton listed `and`, `or`, and `not` side by side; a filter object takes exactly one | obsidian-help `en/Bases/Bases syntax.md` at `bc5b4f2`; upstream kepano/obsidian-skills fix `9b736ba` | Fixed |
| obsidian-bases | View types: table and cards 1.9, list 1.10, map 1.10 plus the official Maps plugin, Kanban 1.14 early access | obsidian-help `en/Bases/Views.md` | Pinned in `compatibility:`; Kanban not added (its YAML `type` value is undocumented; #298 decision retained) |
| obsidian-bases | `random()` missing from the functions reference | obsidian-help `en/Bases/Functions.md` | Added |
| obsidian-bases | The help page says date subtraction gives a millisecond difference and documents no `.days` field; the skill (and upstream kepano/obsidian-skills) documents a Duration with `.days` | Same pages | **Not changed**: OB-1 retained as the issue requires; not verifiable without Obsidian. Open question below |
| r-lib-cli | `check_required_columns` used `{?s}` in bullets with no quantity: "Cannot pluralize without a quantity" | executed | Fixed |
| r-lib-cli | `inline-markup.rst`: zero/one/many and verb-agreement examples had no quantity (error); zero form printed "No files is ready"; possessive `{?'s/'s'}` failed with "Unterminated quote" | executed | Fixed with executed replacements |
| r-lib-cli | `conditions.rst` showed the pre-3e `Error <rlang_error>` snapshot format | testthat 3.3.2 snapshot | Replaced with generated output |
| r-lib-cli | A length-2 numeric in a pluralized string fails with `length(object) == 1 is not TRUE`, even after `qty()`; `qty()` inside the string needs cli attached or imported | executed | New Rule 2 text |
| shiny-bslib-theming | `bs_get_contrast()` returns the contrasting text colour (`#FFFFFF`/`#000000`), not a ratio | bslib 0.12.0 help and execution | Fixed |
| shiny-bslib-theming | `$secondary` in `bs_theme(...)` or default `bs_add_variables()` fails with `Undefined variable`; `.where = "declarations"` compiles | executed | Retained, now shows the error |
| shiny-bslib-theming | `"shiny"` preset `$primary` `#007bc2` versus `"bootstrap"` `#0d6efd` | executed | Added as evidence of SH-1 |
| shiny-bslib-theming | `thematic_shiny(font = NA)` by default; Google Fonts for plots need `ragg` or `showtext` | thematic 0.1.8 help | Stated explicitly |
| shiny-bslib | "call before `shinyApp()`" versus "in the server" | thematic help: `session` scopes cleanup, so both work | Not a defect; other references left unchanged |

## What moved where

| Skill | Stays in SKILL.md | Moved to |
|---|---|---|
| obsidian-bases | Schema, filter shapes, properties, formulas, duration rule with WRONG/CORRECT, guards, view table, quoting rules with WRONG/CORRECT, task-tracker example, embedding | `references/examples.rst` (new, with contents): reading list, daily notes, table/cards/list/map snippets. `references/FUNCTIONS_REFERENCE.rst`: default summary table; gained a contents line and `random()` |
| r-lib-cli | Routing table, common calls, Rules 1–4 (interpolation and `{{ }}`, quantities, `call =`, snapshots) with executed examples, short migration recipe | Existing references, now routed by task: inline class tour, headers/alerts/lists, progress walkthroughs, full migration examples (all already covered there) |
| shiny-bslib-theming | Routing table, presets, workflow, `bs_theme()` signature, colours, font essentials, Sass placement, thematic, dashboard class, contrast, best practices | `references/typography.rst` (new): font helpers. `references/theme-tools.rst` (new): common Sass variables, `bs_add_rules()` details, functions/mixins, `bs_bundle()`, themer tools, `bs_get_variables()`, `theme.R` |
| shiny-bslib | Theming essentials (preset, colours, dashboard class, thematic) and a route to shiny-bslib-theming; a "read when" route to `best-practices.rst` | `references/theming.rst` **deleted** (strict subset of shiny-bslib-theming). Incoming links repaired: SKILL.md section and list, `references/page-layouts.rst` |

## After sizes

| Skill | SKILL.md lines | Body lines | Approx. body tokens | References |
|---|---|---|---|---|
| obsidian-bases | 504 → 276 | 493 → 261 | 3152 → 2127 | 1 → 2 |
| r-lib-cli | 475 → 203 | 457 → 181 | 2601 → 1790 | 5 → 5 |
| shiny-bslib-theming | 459 → 228 | 444 → 212 | 3518 → 2055 | 2 → 4 |
| shiny-bslib | 237 → 246 | 222 → 231 | 2281 → 2390 | 14 → 13 |

All four bodies are under the 300-line target. shiny-bslib grew by 9 lines
because it now carries the theming essentials and the best-practices route
that the deleted reference and the sibling skill held; the S3 results below
justify it.

## Behavioural results

**Conditions.** Claude Code 2.1.284, model `claude-sonnet-5` (default
effort), Linux, OAuth login; the same user-level plugins (codex, pixi, git,
worktrunk, frontend-design, none of them in these bundles) were present for
both versions. Original = `d804884`. Revised = `de9be36` for obsidian and
shiny; `r-lib-cli` was run at `de9be36` ("rev") and again at `97c7413`
("rev2") after the regression fix below. 59 runs, USD 5.92 in total.

**Grading.** C1 and C4 answers were executed in R (cli 3.6.6): C1 sources
`check_columns()`, calls it through a wrapper with one and two missing
columns, and checks wording, the reported call, and a snapshot test. C4 runs
the answer's final `cli_text()` with `bad` of length 2 and 1. O1/O4 answers
are parsed as YAML and checked structurally. Shiny answers were checked by
pattern and read manually. Manual overrides are marked (m).

**Loaded content.** "Body" is the skill text injected after a `Skill` tool
call, in characters, from `stream-json`. For explicit `/r:lib-cli` prompts
the CLI does not emit the expansion, so only total input tokens are shown.

| Case | Version | Routed skill | Body chars | Reference reads (chars) | Passed | Median input tokens |
|---|---|---|---|---|---|---|
| O1 normal | orig / rev | bases 1/1 · 1/1 | 12,770 / 8,676 | none / none | 1/1 · 1/1 | 84k / 81k |
| O2 negative | orig / rev | markdown 1/1 · 1/1, bases 0 | — | none | 1/1 · 1/1 | 80k / 80k |
| O3 gotcha OB-1 | orig / rev | bases 1/1 · 1/1 | 12,770 / 8,676 | none / none | 1/1 · 1/1 | 129k / 83k |
| O4 gotcha OB-3/4 | orig / rev | bases 2/2 · 2/2 | 12,770 / 8,676 | none / none | 0/2 · 2/2 | 83k / 82k |
| C1 normal | orig / rev | **none 0/3 · 0/3** | 0 | none | 3/3 · 3/3 (m: rev r2 grader false negative) | 39k / 39k |
| C1x explicit | orig / rev | explicit | not emitted | none | 1/2 · 2/2 | 43k / 42k |
| C2 sibling | orig / rev | lib-cli-app 1/1 · 1/1, lib-cli 0 | — | none | routing only | 125k / 83k |
| C3 gotcha RC-1 | orig / rev / rev2 | lib-cli 1/1 each | 10,687 / 7,029 / 7,589 | none | 1/1 each | 85k / 80k / 83k |
| C4 gotcha RC-2 | orig | lib-cli 3/3 | ~10,700 | inline-markup.rst 29,541 (1 of 3) | 0/3 | 188k |
| | rev | lib-cli 2/3 | ~7,100 | none | 1/3 | 85k |
| | rev2 | lib-cli 3/3 | ~7,500 | none | 3/3 | 127k |
| C4x explicit | orig | explicit | not emitted | inline-markup.rst 29,541 and 3,575 | 0/2 | 283k |
| | rev | explicit | not emitted | none | 1/2 | 41k |
| | rev2 | explicit | not emitted | none | 3/3 | 42k |
| S1 normal | orig / rev | bslib-theming 1/1 · 1/1 | 14,248 / 8,407 | none / none | 1/1 · 1/1 | 85k / 83k |
| S2 ambiguous | orig / rev | bslib 1/3 · 2/3, theming 0 | 9,400 / ~9,900 | none / none | see notes | 79k / 83k |
| S3 gotcha SH-4 | orig | bslib 3/3 | ~9,300 | navigation 14,453 (3/3), page-layouts 2,996, filling 14,609 | 1/3 | 141k |
| | rev | bslib 3/3 | ~9,750 | none | 3/3 | 83k |
| S4 gotcha SH-1/5 | orig / rev | bslib-theming 2/2 · 2/2 | ~14,300 / 8,407 | none / none | 0/2 (m) · 2/2 | 84k / 82k |

Notes:

- **C4 regression and fix.** The first revision still let the model offer
  `{qty(length(bad))}Element{?s} {bad} {?is/are}` as a working alternative
  in 2 of the 4 revised runs that loaded the skill (a third hinted at it);
  cli rejects it. The rule now marks
  that form WRONG (`97c7413`). rev2 passed 6/6 with no broken alternative.
  The original skill never produced a working fix (0/5) and its reference
  read did not help.
- **C1x original r1** copied the original SKILL.md's defective
  `"Required column{?s} missing ..."` bullet and failed with "Cannot
  pluralize without a quantity". This is direct evidence that the defect
  propagated.
- **C1 routing.** Neither version routed the C1 prompt to `r:lib-cli` (0/6);
  the model answered from its own knowledge and passed. The description was
  not changed in this pilot (#306 owns descriptions).
- **S2** asked to convert an app without supplying it. In 4 of 6 runs the
  model asked for the code, which is a reasonable blocked outcome. It is
  inconclusive as a task and was used for routing only. No run in either
  version read a theming reference.
- **S3** is the clearest disclosure effect: the original `shiny:bslib` had no
  route to the dashboard class, so the model read unrelated references
  (14–29k characters). One run invented custom CSS and one wrongly claimed
  that `page_navbar(fillable = "Dashboard")` adds the grey background; the
  run that passed found the class in `page-layouts.rst`. The revised skill
  keeps the class in its theming essentials: 3/3 correct, no reads.
- **S4 original** stated in both runs that `bs_get_contrast()` reports a
  contrast ratio (the regex grader missed this; failed by manual review).
- **O4 original** ignored the requested display name `Status: Current`
  (2/2), so the quoting rule was not exercised. The revised version quoted
  it correctly (2/2). This is a task-following difference that may be noise
  at this sample size; filter shapes were valid in all runs.
- Revised reference files were never read in any run. The pilot tasks did
  not need them, so reachability is shown by routing text and link checks,
  not by observed reads.

## Rubric disagreements

- The skill-audit rubric's Biggs test would cut the r-lib-cli snapshot
  example as inferable. Pilot evidence kept it: the original skill's
  guidance produced wrong fixes that a fresh model repeated. The executed
  snapshot is verifier-facing detail.
- The rubric favours compressing shiny-bslib, but the evidence justified
  adding 9 lines of theming essentials (S3).

## Dispositions for the other family items

| Skill | Disposition | Reason |
|---|---|---|
| r-lib-cran-extrachecks | Deferred to a follow-up pilot | Mandatory claims must first be verified against current CRAN policy (authoritative source), and it has no references to move material into; #411 already touched it |
| r-lib-mirai | Separate factual fix, then deferred pilot | The Shiny `ExtendedTask` example calls `task$invoke(input$n)` but the UI defines no `n` input (found by reading, not executed); fix under #298's process before restructuring |
| r-lib-cli-app | Deferred to a follow-up pilot | Not exercised beyond sibling routing (C2 routed correctly in both versions); needs its own invariant prompts (type mapping, NA vs NULL, executable shipping) |
| r-lib-testing | Deferred to a follow-up pilot | Needs version-conditioned testthat features checked per #308 first |
| r-lib-package-dev | Retained, with reason | 358 body lines; formatter policy changed in #411; separating preference from fact needs its own review |
| r-lib-lifecycle | Retained, with reason | 242 body lines, already under the 300-line target |
| shiny-bslib | Changed (this PR) | Theming consolidation and best-practices route |

## Limitations

- One model (`claude-sonnet-5`) and one host; 1–3 repetitions per case.
  Routing varied between runs (C4 rev, S2), so small differences are not
  significant.
- The Obsidian results rest on the skill's own rules; no Obsidian instance
  was available to confirm that the answers render.
- Loaded content for explicit invocations is not emitted by the CLI;
  input-token totals include the system prompt and every turn, so they are a
  coarse proxy.
- `claude plugin eval` was not used (no suites for these plugins, and it
  compares with/without plugin rather than two versions).
- The #303 size reporter was built from an unmerged branch for measurement
  only.

## Open questions

1. **Bases date subtraction.** The official help describes a millisecond
   difference, but the skill and upstream describe a Duration with `.days`.
   Someone with Obsidian should run `(now() - file.ctime).days` and
   `((now() - file.ctime) / 86400000).round(0)` in a base and record the
   app version. Tracked in [#428](https://github.com/nq-rdl/agent-extensions/issues/428);
   #304 remains open for this critical invariant.
2. **r:lib-cli routing.** The skill was never auto-selected for a "write a
   cli error helper" task (C1). Subsequently resolved in the
   [R/Shiny review](skill-review/r-shiny.md): revised routing passed 3/3.
