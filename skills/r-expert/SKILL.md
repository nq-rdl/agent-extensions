---
name: r-expert
license: CC-BY-4.0
description: >-
  R language expert skill. Use when writing, reviewing, or debugging R code,
  or when the user asks for R best practices, idiomatic R, or guidance on the
  R ecosystem. Covers base R, tidyverse style, vectorization, pipe usage,
  error handling, and performance patterns. Complements r-lib (package dev)
  and shiny (web apps) — this skill focuses on the language itself.
compatibility: >-
  Requires R runtime
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# R Expert — Idiomatic R Language Guide

This skill captures the non-inferable delta: R-version-pinned high-drift items,
this project's toolchain preferences, and where to delegate. Generic tidyverse
style (naming, spacing, assignment, basic pipes, vectorization, pre-allocation)
is assumed — follow the [tidyverse style guide](https://style.tidyverse.org/);
do not restate it here.

## High-drift items (verify against your R version)

- Native pipe `|>` over magrittr `%>%` — base R, no import. Available since
  **R 4.1**, but the `_` named-argument placeholder (`x |> f(y = _)`) needs
  **R 4.2+** (R 4.3+ to use `_` with extraction, e.g. `_$col`). Without `_`,
  the piped value can only fill the first argument.
- Lambda shorthand `\(x)` — backslash function syntax, **R 4.1+**
  (e.g. `purrr::map_dbl(x, \(d) d^2)`).
- `testthat` **3rd edition** semantics (`expect_snapshot()`, parallel tests,
  stricter `expect_*`) — opt in via `DESCRIPTION`'s `Config/testthat/edition: 3`.
  See `r-lib-testing`.

## Project toolchain preferences

- User-facing messages/errors via `cli::cli_abort()` / `cli::cli_inform()` /
  `cli::cli_warn()` (not bare `stop()` / `warning()` / `message()`). cli markup
  (`{.val}`, `{.code}`, pluralization) gives consistent, styled output.
- Format with `styler`; lint with `lintr`.
- Performance / IO stack: `bench` (benchmarking), `data.table` / `arrow` /
  `vroom` (large data + fast IO), `future` + `furrr` (embarrassingly parallel).

## Delegation

- Package development → `r-lib-package-dev`, with deep dives in `r-lib-testing`
  (testthat), `r-lib-cli` (user-facing messages), and `r-lib-lifecycle`
  (deprecation / versioning).
- Shiny apps → `shiny-bslib` (layouts, components) and `shiny-bslib-theming`
  (theming, dark mode, brand.yml).
- Style-guide details (naming, spacing, pipes, vectorization): the tidyverse
  style guide — do not restate here.

## References

- [Tidyverse Style Guide](https://style.tidyverse.org/) — canonical style reference
- [Advanced R (Hadley Wickham)](https://adv-r.hadley.nz/)
- [R for Data Science (2e)](https://r4ds.hadley.nz/)
