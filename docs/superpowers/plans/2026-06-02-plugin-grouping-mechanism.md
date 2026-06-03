# Plugin Grouping — Mechanism, Manifest Generation & Meta-Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the *unblocked* parts of the subject-grouping migration (`docs/specs/2026-06-02-plugin-grouping-design.md`): the Phase-2 packaging mechanism (grouped sync + validators, backward-compatible), D-3 manifest generation, and the D-1 `rdl` meta-plugin — so that the actual subject migration (Phase 3) becomes a registry-only change once `agent-skills#118` lands upstream.

**Architecture:** The registry (`registry/bundles/*.yaml` + a new `registry/marketplace.yaml` + a `VERSION` file) becomes the single source of truth. `sync-plugins.sh` learns to copy path-qualified grouped members (`skills/<group>/<leaf>/` → `plugins/<group>/skills/<leaf>/`, dropping the prefix) while flat members stay byte-identical (no-diff). A new `generate_manifests.py` emits `plugin.json` + `marketplace.json` from the registry (killing #100 rot), with a `--check` mode wired into CI. New grouping validators enforce the cross-repo contract (`name:`==leaf, group==`pluginName`, no dup leaf, unique `pluginName`).

**Tech Stack:** Bash + Python 3 (stdlib + PyYAML), `unittest`, GitHub Actions, `changie`, `jq`. No new runtime deps.

**Scope guardrails (from the spec):**
- **Claude Code only.** No Codex / `.codex-plugin` / multi-host emit (spec §6).
- **Do NOT edit `skills/`** — it is vendored from `agent-skills` and clobbered on sync. No real grouped *skill* can exist here until `#118` merges + releases; grouped behavior is proven with **test fixtures**, not by restructuring vendored content.
- **No subject migration of skills yet** (Phase 3, gated on `#118`). The 8 existing bundles (`swe`, `infra`, `informatics`, `dev-tools`, `meta`, `hooks`, `rust`, `lucid`) stay as-is; only the *machinery* changes, backward-compatibly.

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `scripts/sync-plugins.sh` | Copy canonical skills/agents into plugin trees; now grouped-member aware | Modify |
| `scripts/check_bundle_refs.py` | Resolve registry refs (now incl. `<group>/<leaf>`) | Modify (+ tests) |
| `scripts/check_grouping.py` | **NEW** — enforce grouping contract (name==leaf, group==pluginName, dup-leaf, unique pluginName, flat-not-descended) | Create |
| `scripts/generate_manifests.py` | **NEW** — generate `plugin.json` + `marketplace.json` from registry; `--check` mode | Create |
| `scripts/check_consistency.py` | Three-way check; teach it about the generated `rdl` meta-plugin | Modify |
| `registry/marketplace.yaml` | **NEW** — top-level marketplace metadata, external passthrough entries, plugin defaults, order, meta-plugin config | Create |
| `registry/bundles/*.yaml` | Add `keywords:` (source of truth for marketplace keywords) | Modify ×8 |
| `VERSION` | **NEW** — single version source (`0.8.0`) | Create |
| `.github/workflows/validate.yml` | Add `check_grouping` + `generate_manifests --check` steps | Modify |
| `.github/workflows/release.yml` | Replace per-manifest jq version-bump with `VERSION` write + regenerate | Modify |
| `plugins/rdl/.claude-plugin/plugin.json` | **NEW (generated)** — meta-plugin (pending D-1 field confirmation) | Generate |
| `tests/test_*.py` | New tests for sync grouping, check_grouping, generate_manifests | Create/Modify |
| `AGENTS.md` | Update mechanics map (grouped members, generated manifests) — light touch | Modify |
| `CHANGELOG`/`.changes/unreleased/*` | Changie fragments | Create |

---

## Part A — Phase-2 mechanism: grouped-member support (backward-compatible)

### Task A1: `sync-plugins.sh` copies grouped members, dropping the group prefix

**Files:**
- Modify: `scripts/sync-plugins.sh` (the inline Python `sync_skill` + keep-set logic, ~lines 78–146)
- Test: `tests/test_sync_plugins.py`

**Contract:** a bundle member is either flat `"<leaf>"` (e.g. `go-gh`) or grouped `"<group>/<leaf>"` (e.g. `go/gh`). The plugin tree is **always keyed by leaf** — `plugins/<plugin>/skills/<leaf>/`. So `go/gh` → `plugins/<plugin>/skills/gh/` (prefix dropped); `go-gh` → `plugins/<plugin>/skills/go-gh/` (unchanged → no-diff).

- [ ] **Step 1: Write failing tests** in `tests/test_sync_plugins.py` (extend existing). Add a `TestGroupedMembers` case:

```python
class TestGroupedMembers(unittest.TestCase):
    def test_grouped_member_drops_group_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "registry" / "bundles" / "obsidian.yaml",
                  "id: obsidian\nskills:\n  - obsidian/bases\n"
                  "targets:\n  claude:\n    enabled: true\n    pluginName: obsidian\n")
            write(repo / "skills" / "obsidian" / "bases" / "SKILL.md", "---\nname: bases\n---\n")
            run_sync(repo)
            self.assertTrue((repo / "plugins" / "obsidian" / "skills" / "bases" / "SKILL.md").is_file(),
                            "grouped member must land at plugins/obsidian/skills/bases/ (prefix dropped)")
            self.assertFalse((repo / "plugins" / "obsidian" / "skills" / "obsidian").exists(),
                             "group prefix must NOT appear in the plugin tree")

    def test_flat_member_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "registry" / "bundles" / "swe.yaml",
                  "id: swe\nskills:\n  - go-gh\n"
                  "targets:\n  claude:\n    enabled: true\n    pluginName: swe\n")
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            run_sync(repo)
            self.assertTrue((repo / "plugins" / "swe" / "skills" / "go-gh" / "SKILL.md").is_file())
```

- [ ] **Step 2: Run, verify red.** `python3 -m unittest tests.test_sync_plugins -v` → grouped test FAILS (lands at `skills/obsidian/bases`, not `skills/bases`).
- [ ] **Step 3: Implement.** In the inline Python, key skill dst by leaf and key the prune keep-set by leaf:

```python
def _leaf(member: str) -> str:
    return member.rsplit("/", 1)[-1]

def sync_skill(plugin: str, member: str, bundle_file: Path) -> None:
    src = repo / "skills" / member            # pathlib resolves "go/gh"
    dst = repo / "plugins" / plugin / "skills" / _leaf(member)
    if not src.is_dir():
        warn(bundle_file, f"Skill '{member}' has no source skills/{member}/ — skipped. ...")
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    print(f"  ✓ skill {member}")
```

And the keep-set (replace `present_skills` usage feeding `prune_entries`):

```python
present_skills = [s for s in skills if (repo / "skills" / s).is_dir()]
present_skill_leaves = {_leaf(s) for s in present_skills}
prune_entries(repo / "plugins" / plugin / "skills", present_skill_leaves)
```

(Agents are unaffected — agents have no upstream grouping; leave `sync_agent` as-is.)

- [ ] **Step 4: Run, verify green.** `python3 -m unittest tests.test_sync_plugins -v` → all pass (incl. the original prune test).
- [ ] **Step 5: No-diff guard on the real repo.** `bash scripts/sync-plugins.sh && git status --porcelain plugins/` → **empty** (flat bundles re-sync byte-identical).
- [ ] **Step 6: Commit.** `feat(sync): support grouped <group>/<leaf> skill members (prefix-drop)`

### Task A2: `check_bundle_refs.py` resolves grouped members (lock with a test)

**Files:** Modify (likely test-only): `scripts/check_bundle_refs.py`; Test: `tests/test_check_bundle_refs.py`

- [ ] **Step 1: Write a test** asserting a grouped ref `obsidian/bases` resolves when `skills/obsidian/bases/` exists and is flagged when missing. `(repo/"skills"/"obsidian/bases").is_dir()` already works via pathlib, so this likely passes without code change — the test **locks** that behavior. If the error suffix needs grouped-aware wording, adjust `main()`'s suffix line.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_check_bundle_refs -v`. Green (or fix suffix, then green).
- [ ] **Step 3: Commit** (fold into A3 if no code change).

### Task A3: New grouping validators (`check_grouping.py`)

**Files:** Create `scripts/check_grouping.py`; Create `tests/test_check_grouping.py`; Modify `.github/workflows/validate.yml`

Rules enforced (spec §3 · CONTRIBUTING §6), per **enabled** Claude bundle:
1. **Unique `pluginName`** across all bundles.
2. For each **grouped** member `g/l`: `g == pluginName`; group folder `skills/g/` has **no** direct `SKILL.md` (flat-not-descended); `skills/g/l/SKILL.md` frontmatter `name == l`.
3. For each **flat** member `m`: `skills/m/SKILL.md` frontmatter `name == m`.
4. **No duplicate leaf** within a bundle (grouped leaf `l`, or flat `m`).

- [ ] **Step 1: Write `tests/test_check_grouping.py`** (mirror `test_check_consistency.py` structure) covering: clean grouped repo → `[]`; `name:`≠leaf → issue; group≠pluginName → issue; duplicate leaf → issue; duplicate pluginName across two bundles → issue; group folder with stray `SKILL.md` → issue; clean flat legacy bundle → `[]` (regression guard so legacy `swe`/`go-gh` keeps passing).

```python
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_grouping  # noqa: E402

def repo_with(tmp, bundles, skills):
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    for stem, body in bundles.items():
        (repo / "registry" / "bundles" / f"{stem}.yaml").write_text(body)
    for path, name in skills.items():   # path rel to skills/, frontmatter name
        f = repo / "skills" / path / "SKILL.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"---\nname: {name}\n---\n")
    return repo

ENABLED = "targets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"

class TestGrouping(unittest.TestCase):
    def test_clean_grouped(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(t,
                {"obsidian": "id: obsidian\nskills:\n  - obsidian/bases\n" + ENABLED.format(p="obsidian")},
                {"obsidian/bases": "bases"})
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_name_must_equal_leaf(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(t,
                {"obsidian": "id: obsidian\nskills:\n  - obsidian/bases\n" + ENABLED.format(p="obsidian")},
                {"obsidian/bases": "WRONG"})
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("name" in i and "bases" in i for i in issues), issues)

    def test_group_must_equal_pluginname(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(t,
                {"obsidian": "id: obsidian\nskills:\n  - go/gh\n" + ENABLED.format(p="obsidian")},
                {"go/gh": "gh"})
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("group" in i.lower() for i in issues), issues)

    def test_duplicate_leaf(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(t,
                {"x": "id: x\nskills:\n  - x/gh\n  - other/gh\n" + ENABLED.format(p="x")},
                {"x/gh": "gh", "other/gh": "gh"})
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("duplicate" in i.lower() and "gh" in i for i in issues), issues)

    def test_duplicate_pluginname(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(t,
                {"a": "id: a\nskills:\n  - a/one\n" + ENABLED.format(p="dup"),
                 "b": "id: b\nskills:\n  - b/two\n" + ENABLED.format(p="dup")},
                {"a/one": "one", "b/two": "two"})
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("pluginName" in i and "dup" in i for i in issues), issues)

    def test_flat_legacy_bundle_ok(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(t,
                {"swe": "id: swe\nskills:\n  - go-gh\n" + ENABLED.format(p="swe")},
                {"go-gh": "go-gh"})
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])
```

- [ ] **Step 2: Run, verify red** (module doesn't exist). `python3 -m unittest tests.test_check_grouping -v` → ImportError/fail.
- [ ] **Step 3: Implement `scripts/check_grouping.py`:**

```python
#!/usr/bin/env python3
"""Enforce the cross-repo skill-grouping contract (spec §3 / CONTRIBUTING §6).

For each enabled Claude bundle:
  * pluginName is unique across bundles.
  * grouped member 'g/l': g == pluginName; skills/g/ has no direct SKILL.md;
    skills/g/l/SKILL.md frontmatter name == l.
  * flat member 'm': skills/m/SKILL.md frontmatter name == m.
  * no duplicate leaf within a bundle.
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml

def _frontmatter_name(skill_md: Path) -> str | None:
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return None
    try:
        return (yaml.safe_load(parts[1]) or {}).get("name")
    except yaml.YAMLError:
        return None

def find_grouping_issues(repo) -> list[str]:
    repo = Path(repo)
    issues: list[str] = []
    seen_plugin: dict[str, str] = {}
    bd = repo / "registry" / "bundles"
    for bf in sorted(list(bd.glob("*.yaml")) + list(bd.glob("*.yml"))):
        data = yaml.safe_load(bf.open()) or {}
        claude = (data.get("targets") or {}).get("claude") or {}
        if not claude.get("enabled"):
            continue
        plugin = claude.get("pluginName") or data.get("id") or bf.stem
        if plugin in seen_plugin:
            issues.append(f"pluginName '{plugin}' used by both '{seen_plugin[plugin]}' and '{bf.stem}'")
        else:
            seen_plugin[plugin] = bf.stem
        leaves: set[str] = set()
        for member in data.get("skills") or []:
            if "/" in member:
                group, leaf = member.split("/", 1)
                if group != plugin:
                    issues.append(f"{bf.stem}: member '{member}' group '{group}' != pluginName '{plugin}'")
                if (repo / "skills" / group / "SKILL.md").is_file():
                    issues.append(f"{bf.stem}: group folder skills/{group}/ has a direct SKILL.md (flat skill descended into)")
                nm = _frontmatter_name(repo / "skills" / group / leaf / "SKILL.md")
                if nm is not None and nm != leaf:
                    issues.append(f"{bf.stem}: skills/{member}/ frontmatter name '{nm}' != leaf '{leaf}'")
            else:
                leaf = member
                nm = _frontmatter_name(repo / "skills" / member / "SKILL.md")
                if nm is not None and nm != member:
                    issues.append(f"{bf.stem}: skills/{member}/ frontmatter name '{nm}' != '{member}'")
            if leaf in leaves:
                issues.append(f"{bf.stem}: duplicate leaf '{leaf}'")
            leaves.add(leaf)
    return issues

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = Path(argv[0]) if argv else Path(".")
    issues = find_grouping_issues(repo)
    for msg in issues:
        print(f"::error::{msg}", file=sys.stderr)
    if issues:
        print(f"{len(issues)} grouping contract violation(s)", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run, verify green.** `python3 -m unittest tests.test_check_grouping -v`. Then `python3 scripts/check_grouping.py .` on the real repo → exit 0 (legacy flat bundles pass; frontmatter `name` matches flat folder names — verify `go-gh` etc.).
- [ ] **Step 5: Wire into CI.** Add to `validate.yml` `validate-bundles` job after the bundle-refs step:

```yaml
      - name: Check skill grouping contract
        run: python3 scripts/check_grouping.py .
```

- [ ] **Step 6: Commit.** `feat(validate): enforce skill-grouping contract (name==leaf, group==pluginName, unique pluginName, no dup leaf)`

---

## Part B — D-3 manifest generation

### Task B1: Introduce the generation inputs (`registry/marketplace.yaml`, `VERSION`, bundle `keywords:`)

**Files:** Create `registry/marketplace.yaml`, `VERSION`; Modify `registry/bundles/*.yaml` (×8)

- [ ] **Step 1: Create `VERSION`** with `0.8.0` + trailing newline.
- [ ] **Step 2: Create `registry/marketplace.yaml`:**

```yaml
# Top-level marketplace metadata + entries not backed by a local bundle.
# plugin.json + marketplace.json are GENERATED from this + registry/bundles/* by
# scripts/generate_manifests.py. Do not hand-edit the generated manifests.
name: rdl
owner:
  name: nq-rdl
  email: r.schnetler@uq.edu.au
description: Agent extensions — curated skill bundles for Claude Code
pluginRoot: ./plugins
# Constant fields stamped into every generated plugins/<p>/.claude-plugin/plugin.json
pluginDefaults:
  author:
    name: nq-rdl
  repository: https://github.com/nq-rdl/agent-extensions
  license: MIT
# Marketplace display order for LOCAL plugins; any enabled bundle missing here is
# appended alphabetically (with a warning). External entries follow, in list order.
order: [swe, infra, informatics, rust, dev-tools, meta, hooks, lucid]
# External marketplace entries (non-local source) — passthrough, preserved verbatim.
external:
  - name: worktrunk
    source: {source: github, repo: max-sixty/worktrunk}
    description: Developer tools — Git worktree CLI for parallel AI agent workflows, config guidance, and automatic Claude session tracking
    keywords: [git, worktree, agents, workflow]
# D-1 meta-plugin (see Part C). Emitted only when 'enabled: true'.
meta:
  name: rdl
  enabled: false   # flipped on in Part C once the dependency field is confirmed
  description: Installs the full RDL agent-extensions set (every subject plugin).
```

- [ ] **Step 3: Add `keywords:` to each bundle YAML** matching current committed marketplace values (so generation reproduces them):

| bundle | keywords |
|---|---|
| swe | `[go, ci-cd, security, changelog]` |
| infra | `[ansible, git-hooks, starrocks]` |
| informatics | `[r, shiny, quarto, cran, tidyverse]` |
| rust | `[rust, explain, ownership, borrow-checker]` |
| dev-tools | `[agents, claude-code, jules, lychee, writerside]` |
| meta | `[skills, review, quality]` |
| hooks | `[hooks, skills, evaluation]` |
| lucid | `[lucid, lucidchart, lucidspark, diagrams, mcp]` |

- [ ] **Step 4: Commit.** `chore(registry): add marketplace.yaml, VERSION, and per-bundle keywords as the manifest-generation source of truth`

### Task B2: `generate_manifests.py` (generate + `--check`)

**Files:** Create `scripts/generate_manifests.py`; Create `tests/test_generate_manifests.py`

- [ ] **Step 1: Write `tests/test_generate_manifests.py`** asserting:
  - `generate(repo)["marketplace"]` has `name/owner/metadata{description,version,pluginRoot}` and `plugins[]` in `order` then external; each local entry `{name, source: "./plugins/<n>", description, version, keywords}`.
  - `generate(repo)["plugins"]["swe"]` == `{name, version, description, author, repository, license}` (key order matters for no-diff).
  - external `worktrunk` entry preserved with object source + stamped version.
  - version comes from `VERSION`.
  - `check(repo)` returns `[]` when on-disk == generated and a drift string when a description is hand-edited.
- [ ] **Step 2: Run, verify red.**
- [ ] **Step 3: Implement `scripts/generate_manifests.py`** — importable `generate(repo) -> dict`, `write(repo)`, `check(repo) -> list[str]`, CLI `[REPO] [--check]`. Key details:
  - Read `VERSION` (strip), `registry/marketplace.yaml`, all enabled bundles.
  - Local plugin order = `order` list ∩ enabled, then any enabled not listed (sorted, `::warning::`).
  - Marketplace entry (local): `{"name": p, "source": f"./plugins/{p}", "description": desc, "version": VER, "keywords": kw}`.
  - External entries appended verbatim with `"version": VER` injected.
  - `plugin.json` dict built with explicit key order `name, version, description, author, repository, license`.
  - JSON output: `json.dumps(obj, indent=2, ensure_ascii=False) + "\n"` (match existing formatting; verify against current `swe` plugin.json byte-for-byte).
  - `write()` writes `.claude-plugin/marketplace.json` and each `plugins/<p>/.claude-plugin/plugin.json`.
  - `check()` compares generated strings to on-disk; report each mismatch as `"<path> is stale — run scripts/generate_manifests.py"`.
- [ ] **Step 4: Run, verify green.**
- [ ] **Step 5: Generate against the real repo & review the diff.** `python3 scripts/generate_manifests.py .` then `git diff .claude-plugin/marketplace.json plugins/*/.claude-plugin/plugin.json`. Expected diff = **only #100 rot corrections**: `lucid` version `0.6.0`→`0.8.0`; `lucid` plugin.json/marketplace descriptions unified to the bundle description. Confirm nothing else moved. If an unexpected field/order drift appears, fix the generator (not the manifest) and regenerate.
- [ ] **Step 6: Commit.** `feat(manifests): generate plugin.json + marketplace.json from the registry (#100)` — include the regenerated manifests.

### Task B3: Wire `--check` into CI; keep `check_consistency.py`

**Files:** Modify `.github/workflows/validate.yml`

- [ ] **Step 1:** Add to `validate-bundles`:

```yaml
      - name: Check generated manifests are in sync
        run: python3 scripts/generate_manifests.py . --check
```

- [ ] **Step 2:** Run the full suite locally: `bash scripts/validate-plugins.sh && python3 scripts/check_bundle_refs.py . && python3 scripts/check_grouping.py . && python3 scripts/generate_manifests.py . --check && python3 scripts/check_consistency.py . && python3 -m unittest discover -s tests -p 'test_*.py'` → all green.
- [ ] **Step 3: Commit.** `ci: assert registry↔generated-manifests stay in sync`

### Task B4: Migrate `release.yml` to regenerate instead of jq-bumping

**Files:** Modify `.github/workflows/release.yml` (the "Bump versions in all manifests" step, ~lines 67–96)

- [ ] **Step 1:** Replace the marketplace + `plugins/*/.claude-plugin/plugin.json` jq bump block with:

```yaml
      - name: Stamp version and regenerate manifests
        env:
          VERSION: ${{ steps.version.outputs.version }}
        run: |
          echo "$VERSION" > VERSION
          python3 -m pip install --user pyyaml
          python3 scripts/generate_manifests.py .
```

Keep the `pyproject.toml` TOML-sed step untouched (guarded by `[ -f pyproject.toml ]`). Keep `changie batch`/`merge` and the commit step (now also commits `VERSION`).

- [ ] **Step 2: Simulate locally (cannot run Actions).** `echo 9.9.9 > VERSION && python3 scripts/generate_manifests.py . && grep -r '9.9.9' .claude-plugin plugins/*/.claude-plugin | wc -l` → every manifest shows `9.9.9`. Then `git checkout VERSION .claude-plugin plugins && python3 scripts/generate_manifests.py .` to restore `0.8.0` and confirm clean.
- [ ] **Step 3: Commit.** `ci(release): version via VERSION file + manifest regeneration (single source)`

---

## Part C — D-1 `rdl` meta-plugin

> **Dependency field CONFIRMED** (claude-code-guide, sourced from code.claude.com/docs `plugin-dependencies` + `plugins-reference`): the field is **`dependencies`** — a top-level array in `.claude-plugin/plugin.json`. Same-marketplace deps are **bare name strings** (`"swe"`); all our subjects are in marketplace `rdl`, so no `allowCrossMarketplaceDependenciesOn` opt-in is needed. Transitive install is live; `claude plugin uninstall rdl --prune` (alias `autoremove`) cleans up. Plugin name = **`rdl`** (spec's `rdl@rdl`).

### Task C1: generate the `rdl` meta-plugin

**Files:** Modify `scripts/generate_manifests.py`, `scripts/check_consistency.py`, `registry/marketplace.yaml`; generated `plugins/rdl/.claude-plugin/plugin.json`

- [ ] Flip `meta.enabled: true` in `registry/marketplace.yaml`.
- [ ] Extend the generator: when `meta.enabled`, emit `plugins/rdl/.claude-plugin/plugin.json` =
  `{name: "rdl", version, description, dependencies: [<all enabled local plugin names, in `order`>], author, repository, license}`
  and append an `rdl` marketplace entry `{name: "rdl", source: "./plugins/rdl", description, version, keywords: [meta, install, rdl]}`. The `dependencies` list is **generated** from the enabled bundles, so it auto-tracks subjects as they migrate. (Bare-string deps — same marketplace.)
- [ ] Teach `check_consistency.py` to treat the meta plugin name (from `marketplace.yaml` `meta.name`) as a legitimate plugin with **no content bundle** — whitelist it so `plugins/rdl/` + its marketplace entry are not flagged as orphans.
- [ ] Tests: generator emits the meta plugin with `dependencies` == enabled-plugin list; `dependencies` excludes `rdl` itself and external `worktrunk`; `check_consistency` clean with the meta plugin present.
- [ ] Validate `plugins/rdl/` with `validate-plugins.sh` (manifest-only plugin — no skills/agents; confirm the validator tolerates a content-less plugin — it should, since the `agents/` and `hooks/` checks are guarded by directory existence).
- [ ] Document the one-command install in `AGENTS.md`: `claude plugin install rdl@rdl` (+ `uninstall rdl --prune`). Note the v2.1.110+/v2.1.121+ floors for dependency resolution / prune.
- [ ] **Commit.** `feat(meta): add generated rdl meta-plugin — one-command install of every subject (D-1)`

---

## Part D — Docs & changelog (light touch; full AGENTS.md slim-down deferred per D-4)

### Task D1: Update `AGENTS.md` mechanics map

**Files:** Modify `AGENTS.md`

- [ ] In "How skills and agents flow into plugins": note members may be flat `<leaf>` or grouped `<group>/<leaf>`, and sync drops the `<group>/` prefix → plugin tree stays one level.
- [ ] In "Build, test, lint": add `python3 scripts/generate_manifests.py .` (refresh manifests) and `--check`, plus `python3 scripts/check_grouping.py .`. State `plugin.json`/`marketplace.json` are **generated — do not hand-edit** (point to `registry/marketplace.yaml` + bundle `keywords`).
- [ ] In "Registry Bundles": document `keywords:` and the `<group>/<leaf>` member form.
- [ ] Keep it a *map*, not policy (policy stays in `CONTRIBUTING.md`). Do **not** attempt the full slim-down (deferred until subjects actually migrate).
- [ ] **Commit.** `docs(agents): document grouped members + generated manifests`

### Task D2: Changie fragments

**Files:** Create `.changes/unreleased/*.yaml`

- [ ] `changie new` (or write fragments) for:
  - **Added** — grouped `<group>/<leaf>` skill-member packaging support (backward-compatible; flat bundles unchanged).
  - **Added** — `plugin.json` + `marketplace.json` generated from the registry; grouping-contract validators in CI.
  - **Added** *(path α only)* — `rdl` meta-plugin for one-command install. *(or **Changed** — install via project settings, path β.)*
  - **Fixed** — reconcile `lucid` manifest drift (version + description) via generation (#100).
- [ ] **Commit.** `chore(changelog): fragments for grouping mechanism + manifest generation`

---

## Self-review checklist (run before final handoff)

1. **Spec coverage:** §3 mechanism → A1–A3; D-3 generation → B1–B4; D-1 meta → C1/C2; D-4 docs → D1; D-2 git grouping → *deferred (skill subjects gated on #118)*; §5 placement → *deferred*; §6 Codex → *not introduced (assert: `grep -ri codex .claude-plugin registry scripts` only matches pre-existing files)*.
2. **No-diff invariants:** `sync-plugins.sh` leaves `plugins/` clean on the current flat registry; generated manifests differ from pre-gen **only** by documented lucid rot fixes.
3. **Backward compat:** every existing test still green; legacy flat bundles pass `check_grouping`.
4. **No vendored edits:** `git status skills/` clean throughout (no grouped skill fabricated in `skills/`).
5. **CI parity:** everything CI runs (`validate.yml` jobs) passes locally before commit.
