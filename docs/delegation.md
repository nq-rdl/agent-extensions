# Delegation through skills

Reusable tasks are skills. The catalog no longer installs named agents from an
`agents/` directory. Each migrated skill links to `references/subagent.rst`, which
contains its optional worker instructions.

## Direct or delegated execution

Use `SKILL.md` for ordinary execution. Read the delegation outline when splitting
the work would help or the user asks to “create a subagent to execute this.” The
main agent supplies the objective, input paths, permitted changes, and expected
result, then uses the host’s available subagent mechanism. The worker receives
resolved paths or the relevant instruction text. The parent checks its evidence
and reports the result. If isolation is required but unavailable, say so.

The outline is ordinary reference text. It does not register an agent type or
install a model setting, tool allowlist, sandbox, or skill preload. Preserve
read-only and other scope boundaries in the handoff and use host permission
controls where needed. Companion skills must be available and read explicitly.

Codex's `agents/openai.yaml` is optional skill UI/policy/dependency metadata,
not a custom subagent definition. Custom Codex TOML agents are separately
configured; this marketplace does not install them. See the official
[skill metadata](https://learn.chatgpt.com/docs/build-skills#optional-metadata),
[subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), and
[Claude migration guide](https://developers.openai.com/plugins/guides/submit-claude-plugin).

## Migrated names

Invoke the owning skill instead of passing the former name as an agent type.
Claude uses `/plugin:skill`; Codex uses `$plugin:skill` for bundles enabled in the
[Codex pilot](codex.md). These names do not imply every bundle is Codex-enabled.

| Former agent | Owning skill | Canonical delegation outline |
|---|---|---|
| `address-comments` | `gh:address-comments` | `skills/address-comments/references/subagent.rst` |
| `adr-generator` | `planning:record-decision` | `skills/adr-generator/references/subagent.rst` |
| `arch-linux-expert` | `arch-linux:maintain` | `skills/arch-linux-expert/references/subagent.rst` |
| `codex-rescue` | `codex:rescue` | `skills/codex-rescue/references/subagent.rst` |
| `context-architect` | `planning:sequence` | `skills/context-architect/references/subagent.rst` |
| `debug` | `debug:diagnose` | `skills/debug/references/subagent.rst` |
| `github-actions-expert` | `gh:actions` | `skills/github-actions-expert/references/subagent.rst` |
| `go-mcp-expert` | `go:build-mcp` | `skills/go-mcp-expert/references/subagent.rst` |
| `hlbpa` | `planning:architecture` | `skills/hlbpa/references/subagent.rst` |
| `janitor` | `debug:clean` | `skills/janitor/references/subagent.rst` |
| `marketplace-scout` | `claude-code:discover-plugins` | `skills/marketplace-scout/references/subagent.rst` |
| `mongodb-performance-advisor` | `mongodb:analyse` | `skills/mongodb-performance-advisor/references/subagent.rst` |
| `plan` | `planning:strategy` | `skills/plan/references/subagent.rst` |
| `platform-sre-kubernetes` | `kubernetes:operate` | `skills/platform-sre-kubernetes/references/subagent.rst` |
| `playwright-tester` | `playwright:test` | `skills/playwright-tester/references/subagent.rst` |
| `postgresql-dba` | `postgres:administer` | `skills/postgresql-dba/references/subagent.rst` |
| `prompt-builder` | `claude-code:engineer-prompts` | `skills/prompt-builder/references/subagent.rst` |
| `redhat-docs-fetcher` | `redhat:fetch-docs` | `skills/redhat-docs-fetch/references/subagent.rst` |
| `repo-architect` | `gh:configure-repo` | `skills/repo-architect/references/subagent.rst` |
| `research-technical-spike` | `planning:research` | `skills/research-technical-spike/references/subagent.rst` |
| `se-gitops-ci-specialist` | `argo-cd:debug-delivery` | `skills/se-gitops-ci-specialist/references/subagent.rst` |
| `se-technical-writer` | `tech-writing:author` | `skills/se-technical-writer/references/subagent.rst` |
| `skill-auditor` | `claude-code:skill-audit` | `skills/skill-audit/references/subagent.rst` |
| `terraform` | `terraform:provision` | `skills/terraform/references/subagent.rst` |
| `terraform-iac-reviewer` | `terraform:review` | `skills/terraform-iac-reviewer/references/subagent.rst` |
| `terratest-module-testing` | `terraform:test` | `skills/terratest-module-testing/references/subagent.rst` |
| `wg-code-sentinel` | `go:review-security` | `skills/wg-code-sentinel/references/subagent.rst` |

The former skill-auditor, Red Hat fetcher, and Codex rescue agents fold into
existing skills. Other agent procedures have task-focused skill entrypoints.
Existing guest bundle coverage is preserved, with home subjects noted in the
registry. The sync script removes retired generated `plugins/*/agents/` trees.

Technical-writing completion hooks still use Claude's native agent hook handler;
that hook type is independent of named agent definitions. `SubagentStop` examines
the completed worker's task and skips unrelated work. Codex hook support remains
separately gated and does not execute Claude agent hook handlers.
