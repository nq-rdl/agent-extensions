---
name: tdd
license: CC-BY-4.0
description: >-
  Test-driven development concepts, cycle, and anti-patterns. Load when
  writing or reviewing tests, adding mocks, implementing new behaviour, or
  when an agent needs TDD guidance. Not for orchestrating TDD phases — use
  tdd-team-workflow for that.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# TDD Skill

Test-driven development knowledge for any agent writing or reviewing code. Covers the red→green→refactor cycle, test quality rules, and the five anti-patterns that break real test coverage.

---

## The Cycle

```
RED → GREEN → REFACTOR → repeat
```

### 1. RED — Write a failing test
- Write one test that describes the next piece of behaviour
- Run the test — it must **fail** (not error, not skip — fail)
- The failure message should clearly describe what's missing

### 2. GREEN — Make it pass
- Write the **minimum** code to make the test pass
- No extra features, no generalisation, no cleanup
- Run all tests — they must all pass

### 3. REFACTOR — Clean up
- Improve structure, naming, duplication
- Do NOT change behaviour — all tests must still pass
- Run tests after every refactoring step

---

## The Five Rules

1. Never write production code without a failing test
2. Write only enough of a test to fail — one assertion at a time
3. Write only enough code to pass — resist the urge to generalise
4. Refactor only while green — never change behaviour during cleanup
5. Run tests after every change — the cycle is a loop, not a batch

---

## Test Quality

Good tests are **FIRST**:
- **Fast** — milliseconds, not seconds
- **Isolated** — no shared state between tests
- **Repeatable** — same result every time
- **Self-validating** — pass or fail, no manual inspection
- **Timely** — written before or alongside the code

**Structure (AAA):**
```
Arrange — set up preconditions
Act     — call the function under test
Assert  — verify the result
```

**What to test:**
- Happy path, edge cases, error cases
- One logical assertion per test

---

## When TDD Is Optional

- Configuration-only changes (no logic)
- Documentation changes
- Trivial fixes with existing comprehensive test coverage
- Spike/prototype code (add tests before merging)

Even when TDD is optional, ensure test coverage exists before declaring done.

---

## Anti-Patterns

See `references/testing-anti-patterns.rst` for the full catalogue with gate functions.

**The five violations to watch for:**
1. Testing mock behavior instead of real behavior
2. Test-only methods added to production classes
3. Mocking without understanding dependencies
4. Incomplete mocks (partial data structures)
5. Tests as an afterthought (written after implementation)

**Core principle:** Test what the code does, not what the mocks do.

---

## Reference Files

- `references/testing-anti-patterns.rst` — Full anti-pattern catalogue with gate functions and fixes
