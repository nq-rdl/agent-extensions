---
description: Triage reads a sibling child's branch with git show or git ls-tree, never checkout, and classifies a legacy-template seed whose answers.yaml does not parse (#384, #381)
tags: [triage, read-only]
runs: 3
max_turns: 6
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Triage ENQ9007 only; triage only. ENQ9007 is a V2 of ENQ9006. Before we scope it, I want to read the earlier request's work: branch `enq/9006` of rdl-service-desk/THHSAQUIRE-9906. I have a clone of that repository at `./THHSAQUIRE-9906`, with its DVC and lefthook hooks installed. This session has no shell, so give me the exact commands to run in that clone to list the files under `sql/` on that branch and to print its `answers.yaml`.

Also classify the scaffold of rdl-service-desk/THHSAQUIRE-9907 (the ENQ9007 child) from what I gathered:

- `.copier-answers.yml` on `main`:

  ```text
  _commit: v0.1.3
  _src_path: gh:rdl-service-desk/data-science-template
  seed_mode: true
  ```

- `main` has `cohort/`, `conf/`, `specs/` and `sql/` directories, and no `pyproject.toml`.
- `answers.yaml` on `main`:

  ```text
  project_title: Sepsis admissions V2
  requestor_name: <placeholder>
  inclusion_criteria: - adults admitted with sepsis
  requested_data_elements:
    - URN
  ```

- No open PRs.

End your reply with one fenced `yaml` block with exactly these top-level keys: `commands` (a list of the exact shell commands), `scaffold_state`, `answers_yaml_parses` (true or false), `answers_yaml_error_line`, `pixi_solve` (run or skip, with the reason).
