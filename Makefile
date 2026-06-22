# agent-extensions — developer entrypoints.
#
# The catalog build/validation steps are bash + python scripts (see CLAUDE.md);
# this Makefile only exposes the one-command dependency bootstrap so it is the
# same invocation for a human contributor and for Claude Code on the web.

.DEFAULT_GOAL := help

.PHONY: help
help: ## List available targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install-deps
install-deps: ## Install dev deps (lefthook, changie, gopls, python/jq). On Claude Code web also pre-seeds plugins + Docker.
	@bash .claude/scripts/install-deps.sh
# Human devs: `make install-deps` provisions the local dev toolchain.
# Claude Code on the web: set the environment's Setup-script field to
#   CLAUDE_CODE_REMOTE=true make install-deps
# so the declared plugins are pre-seeded into the snapshot BEFORE Claude
# enumerates skills — the only way their /<plugin>:<skill> commands appear on the
# first session. The committed SessionStart hook (install-deps.sh --session) then
# self-heals the install on later/resumed sessions.
