# R Style Quick Reference

Condensed from the [Tidyverse Style Guide](https://style.tidyverse.org/) and
[Google R Style Guide](https://google.github.io/styleguide/Rguide.html).

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Variables | snake_case | `raw_data`, `fit_model` |
| Functions | snake_case (verbs) | `compute_mean()`, `validate_input()` |
| S3 methods | generic.class | `print.my_model` |
| Constants | SCREAMING_SNAKE | `MAX_RETRIES` |
| Files | snake_case.R | `data_processing.R` |

## Assignment

```r
x <- 10       # Good
x = 10        # Bad (top-level)
10 -> x       # Bad (right-assign)
```

## Spacing

```r
# Spaces around most operators
x <- y + z
x == y
x != y

# No spaces around high-precedence operators
pkg::fun()
df$col
x[1]
x^2
-1

# Commas: space after, not before
fun(x, y, z)

# Parentheses: space before/after for control flow
if (condition) { ... }
for (i in seq_len(n)) { ... }

# No space inside function calls
mean(x)
```

## Pipes

```r
# Native pipe (R 4.3+)
result <-
  data |>
  dplyr::filter(x > 0) |>
  dplyr::mutate(y = log(x))

# One function per line, two-space indent
# Space before |>, newline after
```

## Functions

```r
# Implicit return for final expression
square <- function(x) {
  x^2
}

# Explicit return() only for early exits
safe_divide <- function(x, y) {
  if (y == 0) {
    return(NA_real_)
  }
  x / y
}
```

## Braces

```r
# Opening { at end of line
# Closing } at start of line
# else on same line as }
if (condition) {
  do_this()
} else {
  do_that()
}
```

## Strings & Booleans

```r
name <- "hello"     # Double quotes default
msg <- 'she said "hi"'  # Single when needed
flag <- TRUE         # Never T/F
```

## Namespace

```r
# Always qualify in packages and functions
dplyr::filter(data, x > 0)
rlang::.data$col

# Only use library() at script top level
library(dplyr)
library(ggplot2)
```
