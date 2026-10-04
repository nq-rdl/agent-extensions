# Security scanning

Canonical skills under `skills/` are scanned with
[NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector), and every finding
is classified against the
[OWASP Agentic Skills Top 10](https://owasp.org/projects/agentic-skills-top-10)
(AST01–AST10) ([issue #259](https://github.com/nq-rdl/agent-extensions/issues/259)).

OWASP does not publish a scanner of its own. Its
[scanner integration guide](https://owasp.github.io/www-project-agentic-skills-top-10/skill-scanner-integration)
recommends SkillSpector and asks that scanner findings be mapped to the AST
taxonomy in reports and CI output. That mapping is what this repo adds.

## Where it runs

| Where | What | Gating |
|---|---|---|
| `skillspector.yml` on every PR | Static scan (`--no-llm`) of each skill, merged SARIF uploaded to code scanning (category `skillspector`), findings per OWASP risk in the job summary | Informational |
| lefthook `pre-push` (`skillspector` job) | Terminal report for all skills; skipped without Docker | Informational |

All scan logic lives in `tools/skillspector/`:

| File | Role |
|---|---|
| `scan.sh` | Builds the pinned SkillSpector image and scans each skill directory |
| `merge-sarif.sh` | Merges per-skill SARIF into one run and adds the OWASP tags |
| `owasp-ast10.json` | SkillSpector rule ID → OWASP risk mapping |
| `owasp-summary.sh` | Renders the per-risk Markdown table for the job summary |

Every result is uploaded at SARIF level `note`, so the code-scanning check
that GitHub creates for the upload never fails a PR. `scan.sh` documents why.

## Reading the results

Each result carries `properties["owasp-ast10"]` (for example `AST03`) and a
`owasp-ast10/<id>` tag. Each rule carries the same tag and a `helpUri` to the
OWASP risk page. In the Security tab, filter code-scanning alerts with
`tool:skillspector tag:owasp-ast10/AST03`.

The merged run also keeps each skill's SARIF `invocations` (tagged
`properties.skill`). They record whether the scan succeeded, the inspection
completeness, and warnings for files SkillSpector inspected only partially,
for example when a reference is missing or a parse limit was hit. Below the
risk table, the job summary states how many skills were fully inspected and
lists the incomplete ones in a collapsible table. A zero count only covers
what was inspected. The run keeps SkillSpector's `columnKind`
(`unicodeCodePoints`), so finding columns stay correct after emoji and other
non-BMP characters.

Run the same scan locally (Docker and `jq` required):

```bash
SKILLSPECTOR_FORMAT=sarif SKILLSPECTOR_OUTPUT=skillspector.sarif tools/skillspector/scan.sh
tools/skillspector/owasp-summary.sh skillspector.sarif
```

## Mapping

A rule resolves by exact ID in `rules` first, then by its family prefix (the
ID without trailing digits) in `families`. Every entry records a one-line
rationale. A rule ID that matches neither is tagged `owasp-ast10/unmapped` and
counted in its own summary row. Extend the mapping when that row appears.

SkillSpector's own `AST1`–`AST10` rules belong to its Python-AST analyzer and
are unrelated to OWASP's AST01–AST10. OWASP IDs are always two-digit and
namespaced `owasp-ast10/`. SkillSpector's `AST10` (insecure deserialization)
maps to OWASP AST04.

| OWASP risk | SkillSpector rule families |
|---|---|
| AST01 Malicious Skills | `P` prompt injection and hidden instructions, `E` exfiltration, `MP`, `RA`, `TT`, `YR`, `AS`, `AR`, plus `AST8`, `AST9`, `BH2` |
| AST02 Supply Chain Compromise | `SC` |
| AST03 Over-Privileged Skills | `PE`, `EA`, `TM`, `AST1`–`AST7`, `OH`, `LP2`/`LP4`, `BH1`/`BH3`/`BH4` |
| AST04 Insecure Metadata | `TR`, `TP`, `DS`, `LP1`/`LP3`, `AST10`, `TT6` |
| AST06 Weak Isolation | `SSRF`, `TM4` |
| AST07 Update Drift | `RP` MCP rug-pull: unpinned references and manifest changes |
| AST08 Poor Scanning | `AE` artifact evasion, and artifacts the scanner could not completely inspect |

## Risks without a static rule

AST05, AST09, and AST10 have no SkillSpector rule in static mode. The summary
table marks them "no SkillSpector rule". The repository addresses them, and
supplements the partial rule coverage of AST06–AST08, through process:

| OWASP risk | How this repo addresses it |
|---|---|
| AST05 Untrusted External Instructions | Links in skills are checked by lychee on PRs and by weekly [link monitoring](link-monitoring.md). Link checks show availability, not content integrity. |
| AST06 Weak Isolation | Sandboxing and permissions belong to the host agent (Claude Code or Codex), not the skill. The `SSRF` and `TM4` rules only flag code patterns that weaken isolation. |
| AST07 Update Drift | Plugin trees are generated copies of `skills/`, and the drift checks (`sync-plugins.sh --check`, `generate_manifests.py --check`) keep them identical. Releases go through a reviewed PR that stamps `VERSION`. |
| AST08 Poor Scanning | SkillSpector checks both the code and the natural-language layer of a skill, and `asctl repo-check` validates skill structure. The optional LLM stage is not used (`--no-llm`), so intent coverage is reduced. |
| AST09 No Governance | `registry/bundles/` is the inventory of what ships, `check_exposure.py` enforces it, changes need PR review and a changie fragment, and alerts collect in the Security tab. |
| AST10 Cross-Platform Reuse | One canonical `skills/` tree generates both the Claude Code and Codex packages; see [Codex](codex.md). |

## Upgrading SkillSpector

`scan.sh` pins a SkillSpector commit (`SKILLSPECTOR_REF`). When you bump it,
check its changelog for new rule families and add them to `owasp-ast10.json`.
Run `pixi run python3 -m unittest tests.test_skillspector_owasp` and one local
scan, then confirm that the summary has no unmapped row.
