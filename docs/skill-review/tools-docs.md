# Tools and docs skills review (#305–#309)

This record follows the pilot protocol in epic #312 for the tools and docs
family: `bitwarden`, `starrocks`, `rust-explain`, `quarto-authoring`,
`quarto-alt-text`, `writerside`, `obsidian-markdown`, `obsidian-cli`,
`obsidian-bases` (follow-ups only), `ansible`, `go-naming`, `go-secure`,
`charm-tui`, `sops`, `argo-cd`, `defuddle`, and `pixi`. The earlier
[progressive-disclosure pilots](../progressive-disclosure-pilots.md) (#304) set
the evidence standard; `obsidian-bases` keeps the structure that #423 gave it.

The tasks, invariants, prompts, and expected outcomes below were recorded
**before** any skill content edit, at source revision `4817a19`
(`epic/skill-review`, v0.36.2 plus #301, #303, and #304).

## Baseline sizes

Measured with `asctl repo-check --size-report` at `4817a19`. Approximate tokens
are body bytes / 4, not measured model usage.

| Skill | Body lines | Approx. body tokens | References |
|---|---|---|---|
| quarto-authoring | 311 | 1634 | 19 |
| go-secure | 297 | 2124 | 1 |
| ansible | 294 | 2380 | 1 |
| obsidian-bases | 261 | 2127 | 2 |
| starrocks | 251 | 2154 | 3 |
| bitwarden | 248 | 1919 | 3 |
| obsidian-markdown | 192 | 1268 | 3 |
| quarto-alt-text | 192 | 1679 | 0 |
| charm-tui | 164 | 1885 | 8 |
| argo-cd | 162 | 1159 | 0 |
| go-naming | 114 | 831 | 0 |
| obsidian-cli | 102 | 669 | 0 |
| rust-explain | 100 | 1261 | 4 |
| writerside | 98 | 1558 | 10 |
| sops | 87 | 1188 | 2 |
| pixi | 71 | 621 | 24 |
| defuddle | 37 | 184 | 0 |

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **bitwarden**: CRITICAL: three divergent implementations of the same shell
  functions (SKILL.md, `references/shell-functions.rst`, `scripts/bw-env.sh`);
  only the script adds the `export` prefix, so the SKILL.md `bwc` stores a note
  that `bwe` cannot export. MODERATE: Quick-start puts a token on the command
  line (`--arg secret "ghp_xxxx"`). MODERATE: Pattern 2 uses GNU-only
  `grep -oP`. Recommendation: route to the script, COMPRESS.
- **starrocks**: MODERATE: body repeats the references' SQL examples; decision
  tables are the non-inferable part. MODERATE: no minimum version while
  examples use version-gated features. Recommendation: COMPRESS, pin.
- **rust-explain**: KEEP. The audit's proposal to drop the reading-vocabulary
  reference is tested below rather than accepted.
- **quarto-authoring**: MODERATE: body duplicates the reference examples
  (figures, tables, callouts, citations, workflows); cell-option syntax and
  label prefixes are the non-inferable part. MINOR: description is a topic list.
- **quarto-alt-text**: MODERATE: written for one book project ("this project",
  `numeric-splines.qmd`, chapter prose); the only verification is a
  `#| label: fig-` grep that misses Markdown images and unlabelled cells.
- **writerside**: MODERATE: the builder tag is repeated about ten times in
  three references with no owner or provenance.
- **obsidian-markdown**: MODERATE: description triggers on generic
  "frontmatter" and "tags"; body restates generic Markdown/LaTeX/Mermaid.
- **ansible**: MODERATE: "Before writing any Ansible content, read
  `role-reference.rst`" loads role scaffolding for non-role work. MINOR:
  description is 690 characters.
- **go-naming / go-secure**: MINOR: descriptions over 400 characters; go-secure
  cites a CVE whose wording needs checking.
- **charm-tui, sops, argo-cd, defuddle, obsidian-cli**: MODERATE each:
  requirements and examples not checked against the actual tool.
- **pixi**: MODERATE: 24 converted upstream pages without provenance; decision
  deferred to #309 evidence.

## Invariants

"Where" names the file that owns the detail after the change.

### bitwarden (#305)

| ID | Invariant | Where |
|---|---|---|
| BW-1 | Personal Password Manager `bw`, not Secrets Manager `bws` | SKILL.md |
| BW-2 | One shell implementation, `scripts/bw-env.sh`; other files route to it | script |
| BW-3 | `bwc` then `bwe` round-trips a `.env` (comments, quoted and unquoted values, existing `export`) | script, tested |
| BW-4 | No function prints stored values, except `bwf` (for capture) and `bwdotenv` (explicit plaintext file) | script, tested |
| BW-5 | `BW_SESSION` stays in memory; prefer item IDs in scripts; `bw sync` for stale data; CI uses API key login | SKILL.md |
| BW-6 | `bwdotenv` writes plaintext: delete after use, never commit | script + SKILL.md |

### starrocks (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| SR-1 | Table-type, loading-method, and index decision tables | SKILL.md |
| SR-2 | Primary Key for mutable/CDC data, Duplicate Key for append-only | SKILL.md |
| SR-3 | Collect CBO statistics after bulk loads | SKILL.md |
| SR-4 | Each version-gated feature states its minimum version; no blanket 3.x claim | SKILL.md + compatibility |
| SR-5 | Repeated SQL examples are reachable in references | references |

### rust-explain (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| RE-1 | Verify-canonical guard and the compile trust boundary (`env!`/`include_str!`) | SKILL.md, tooling.rst |
| RE-2 | Silent-bug radar for numeric code | numeric-idioms.rst |
| RE-3 | Tested toolchain context is stated | tooling.rst |

### quarto (#305, #306, #307, #308)

| ID | Invariant | Where |
|---|---|---|
| QA-1 | Cell options use the language comment plus `|` (`#|`, `%%|`, `//|`) and dashes, not dots | quarto-authoring SKILL.md |
| QA-2 | Cross-reference label prefixes `fig-`, `tbl-`, `sec-`, `eq-` | quarto-authoring SKILL.md |
| QA-3 | Every task in the routing table reaches its reference | quarto-authoring SKILL.md |
| QT-1 | Alt text: chart type first, variables, key insight, complements `fig-cap` | quarto-alt-text SKILL.md |
| QT-2 | Figures are found without assuming labels or one project layout | quarto-alt-text SKILL.md |
| QT-3 | Verification inspects the rendered HTML `alt` attributes when Quarto is available, with a source-only fallback | quarto-alt-text SKILL.md |

### writerside (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| WR-1 | One owner for the builder image and tag, with provenance | docker-deployment.rst |
| WR-2 | Build examples run as written | docker-deployment.rst |
| WR-3 | `MODULE_INSTANCE` is `Module/instance`; group builds need `IS_GROUP` | docker-deployment.rst |

### obsidian (#305, #306, #308)

| ID | Invariant | Where |
|---|---|---|
| OM-1 | Routing needs an Obsidian or vault signal, or an explicit request; generic frontmatter or tags do not suffice | description |
| OM-2 | Naming Obsidian is enough; no special syntax needed to route | description |
| OM-3 | Wikilinks vs Markdown links, embeds, callouts, block IDs, comments, highlights | SKILL.md |
| OM-4 | Feature applicability (properties, CLI) is stated from the official help source | SKILL.md / compatibility |

### ansible, go (#306, #307)

| ID | Invariant | Where |
|---|---|---|
| AN-1 | FQCN, lean roles, `import_tasks` default, check-then-apply, `no_log` on secrets | SKILL.md |
| AN-2 | `role-reference.rst` is read for role work, not for every Ansible task | SKILL.md |
| GO-1 | go-naming and go-secure keep their current routing on the existing `go` suite prompts | descriptions |

### sops, charm-tui, argo-cd, defuddle (#308)

| ID | Invariant | Where |
|---|---|---|
| SO-1 | Every command example runs against the tested sops/age versions | SKILL.md, references |
| CT-1 | Quick start compiles against the tested Charm v2 modules; Go minimum matches their `go.mod` | SKILL.md |
| AC-1 | Examples use live repositories and documented fields | SKILL.md |
| DF-1 | Install and flags match the published CLI | SKILL.md |

### pixi (#309)

A decision record, not a content rewrite. Tasks: consumer environment
creation, existing-project maintenance, and one less common workflow. Criteria:
network availability, provenance, broken links, maintenance burden. No
unconditional deletion.

## Behavioural protocol

Same harness as #304: `claude -p` (Claude Code CLI) with `--plugin-dir` on a
temporary copy of the generated plugin tree. The **original** copy is
`plugins/<bundle>/` exported from `4817a19`; the **revised** copy is regenerated
from this branch. Runs use a scratch working directory outside the repository,
`--output-format stream-json --verbose`, `--permission-mode dontAsk`,
`--settings '{"disableAllHooks": true}'`, model `claude-sonnet-5`, and tools
limited to `Skill Read Glob Grep` unless a case says otherwise. The
marketplace is not installed. Observed per run: `Skill` calls, reference
`Read` calls, loaded characters, turns, cost, and a graded answer.

### Prompts and expected outcomes

| Case | Plugin | Kind | Prompt (abridged; full text in the results) | Expected |
|---|---|---|---|---|
| B1 | bitwarden | normal | Store the `.env` in this folder in Bitwarden and load it in new shells | routes to `secrets`; uses or points to `scripts/bw-env.sh`; no secret on the command line |
| B2 | bitwarden | negative | Use Bitwarden Secrets Manager `bws` machine accounts | does not present `bw` Password Manager commands as `bws` |
| O1 | obsidian | positive, no syntax | "Write an Obsidian note for today's stand-up with links to the Alpha and Beta project notes" | `obsidian:markdown`; wikilinks |
| O2 | obsidian | negative | "Add YAML frontmatter with title, tags and date to this README.md for our MkDocs site" | not `obsidian:markdown`; no wikilinks |
| O3 | obsidian | ambiguous | "In my vault, make the note link to its sources and hide the draft paragraph" | `obsidian:markdown`; `%%` comment |
| Q1 | quarto | normal | Write a `.qmd` with an R figure cell: label, caption, hidden code, cross-reference | `quarto:authoring`; `#|` options with dashes; `fig-` label; `@fig-` |
| Q2 | quarto | normal | Add alt text to the figures in the provided `analysis.qmd` (fixture with a labelled cell, an unlabelled cell and a Markdown image) | `quarto:alt-text`; all three figures handled |
| Q3 | quarto | negative | Convert this Markdown table to HTML | no quarto skill |
| A1 | ansible | normal, role | Scaffold a role that installs and configures chrony | `ansible`; reads `role-reference.rst` |
| A2 | ansible | normal, non-role | Fix this playbook task that uses `dnf` short name and add group_vars for NTP servers | `ansible`; no `role-reference.rst` read |
| G1 | go | routing | The four `evals/claude/go` prompts | naming/secure routed as at baseline |
| S1 | starrocks | gotcha | "Our StarRocks cluster is 3.3. Plan bulk export over Arrow Flight SQL" | states 3.5+ requirement |
| W1 | writerside | normal | GitHub Actions step to build the `hi` instance with Docker | pinned builder image from one owner; valid command |
| R1 | rust | explanation | Explain a closure/iterator ownership snippet, with and without `reading-vocabulary.rst` | equal or better correctness with the reference |
| P1–P3 | pixi | #309 | New Python env with a C library; update a lockfile in an existing project; build a pixi-pack bundle | correct commands; reference use observed |
