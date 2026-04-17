---
name: r-expert
license: MIT
description: >-
  R language expert skill. Use when writing, reviewing, or debugging R code,
  or when the user asks for R best practices, idiomatic R, or guidance on the
  R ecosystem. Covers base R, tidyverse style, vectorization, pipe usage,
  error handling, and performance patterns. Complements r-lib (package dev)
  and shiny (web apps) — this skill focuses on the language itself.
compatibility: >-
  Requires R runtime
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# R Expert — Idiomatic R Language Guide

## Style Foundations

Follow the [tidyverse style guide](https://style.tidyverse.org/) as the default.
Use [styler](https://styler.r-lib.org/) to auto-format and
[lintr](https://lintr.r-lib.org/) to lint.

### Naming

- **snake_case** for variables and functions: `fit_model`, `raw_data`
- Reserve dots for S3 methods only: `print.my_class`
- Nouns for data objects, verbs for functions
- No single-letter names outside tight loops or math formulas

### Assignment & Operators

- Use `<-` for assignment, never `=` at the top level
- Use `TRUE`/`FALSE`, never `T`/`F` (they can be overwritten)
- Use `"` for strings; `'` only when the string contains double quotes
- Never use semicolons to combine statements

### Spacing & Indentation

- Two-space indent (no tabs)
- Spaces around infix operators (`<-`, `==`, `+`) except `::`, `$`, `[`, `^`
- Space after commas, never before
- 80-character line limit

### Pipes

- Prefer the native pipe `|>` over magrittr `%>%` (R 4.3+)
- Space before `|>`, then newline; indent continuation by two spaces
- One function per line in multi-step pipes
- Avoid pipes when manipulating multiple objects simultaneously

```r
result <-
  raw_data |>
  dplyr::filter(age > 18) |>
  dplyr::mutate(bmi = weight / height^2) |>
  dplyr::summarise(mean_bmi = mean(bmi, na.rm = TRUE))
```

### Functions

- Only use `return()` for early returns; rely on implicit return for the final expression
- Name arguments explicitly when overriding defaults; omit for obvious data arguments
- Never use partial argument matching

```r
compute_mean <- function(x, trim = 0, na.rm = FALSE) {
  if (!is.numeric(x)) {
    stop("`x` must be numeric", call. = FALSE)
  }
  mean(x, trim = trim, na.rm = na.rm)
}
```

---

## Vectorization

R is designed around vectorized operations. Always prefer them over explicit loops.

### Use vectorized base functions

```r
# Good — vectorized
result <- sqrt(x) + log(y)
is_positive <- x > 0

# Bad — unnecessary loop
result <- numeric(length(x))
for (i in seq_along(x)) {
  result[i] <- sqrt(x[i]) + log(y[i])
}
```

### Use `vapply()` for type-safe iteration (base R)

```r
# vapply is type-safe — it errors if the return type is wrong
file_sizes <- vapply(paths, file.size, numeric(1))
```

### Use `purrr::map_*()` in tidyverse code

```r
# Type-safe mapping
file_sizes <- purrr::map_dbl(paths, file.size)
model_summaries <- purrr::map(datasets, \(d) lm(y ~ x, data = d))
```

### Never grow objects in loops

```r
# Bad — grows vector on each iteration (quadratic time)
result <- c()
for (i in seq_len(n)) {
  result <- c(result, compute(i))
}

# Good — pre-allocate
result <- numeric(n)
for (i in seq_len(n)) {
  result[i] <- compute(i)
}
```

---

## Error Handling

### Use `stop()`, `warning()`, `message()` appropriately

```r
validate_input <- function(x) {
  if (!is.data.frame(x)) {
    stop("`x` must be a data frame, not ", class(x)[[1]], call. = FALSE)
  }
  if (nrow(x) == 0) {
    warning("Input data frame has zero rows", call. = FALSE)
  }
}
```

### Use `tryCatch()` for recoverable errors

```r
safe_read <- function(path) {
  tryCatch(
    readr::read_csv(path, show_col_types = FALSE),
    error = function(e) {
      warning("Failed to read ", path, ": ", conditionMessage(e), call. = FALSE)
      NULL
    }
  )
}
```

### Use cli for user-facing messages

```r
cli::cli_abort(c(
  "Column {.val {col}} not found in data.",
  "i" = "Available columns: {.val {names(data)}}"
))
```

---

## Data Manipulation Patterns

### dplyr for tabular data

```r
summary_stats <-
  data |>
  dplyr::group_by(category) |>
  dplyr::summarise(
    n = dplyr::n(),
    mean_val = mean(value, na.rm = TRUE),
    sd_val = sd(value, na.rm = TRUE),
    .groups = "drop"
  )
```

### tidyr for reshaping

```r
long_data <- tidyr::pivot_longer(wide_data, cols = -id, names_to = "measure", values_to = "value")
wide_data <- tidyr::pivot_wider(long_data, names_from = measure, values_from = value)
```

### Joins

```r
# Explicit join type and key
combined <- dplyr::left_join(orders, customers, by = "customer_id")

# Multiple keys
combined <- dplyr::inner_join(x, y, by = c("id", "date"))
```

---

## Namespace & Dependency Management

- **Always qualify** non-base functions: `dplyr::filter()`, `rlang::.data`
- Never use `library()` inside functions or packages — qualify instead
- In scripts, load packages at the top with `library()`
- Avoid `attach()` entirely — it creates naming conflicts

---

## Performance

- Profile with `bench::mark()` or `microbenchmark::microbenchmark()`
- Use `data.table` for large datasets (millions of rows)
- Use `vroom` or `arrow` for fast file I/O
- Parallelize with `future` + `furrr` for embarrassingly parallel tasks
- Avoid `apply()` family on data frames when a vectorized alternative exists

---

## Testing

- Use `testthat` (3rd edition) for unit tests
- Test expectations, not implementation details
- Use `withr::local_*()` for temporary state (files, options, env vars)
- See the `r-lib-testing` skill for full testing guidance

---

## References

- [Tidyverse Style Guide](https://style.tidyverse.org/)
- [Google R Style Guide](https://google.github.io/styleguide/Rguide.html)
- [Advanced R (Hadley Wickham)](https://adv-r.hadley.nz/)
- [R for Data Science (2e)](https://r4ds.hadley.nz/)
- [Efficient R Programming](https://csgillespie.github.io/efficientR/)
- `references/style-quick-ref.rst` — condensed style rules for quick lookup
