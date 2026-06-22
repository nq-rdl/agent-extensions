# RDL agent-extensions — convenience targets.
#
# Most build/validation here runs through the scripts/ pipeline and lefthook (see
# AGENTS.md / CLAUDE.md). This Makefile exists mainly to expose the Claude Code
# on the web provisioning entrypoint as a stable command for the environment's
# Setup-script field.

.PHONY: help cc-web-setup

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Claude Code on the web provisioning -------------------------------------
# Run this ONCE from the web environment's *Setup script* field (the bash that
# runs before Claude starts, whose filesystem is captured in the environment
# snapshot). Installing the declared plugins here — before the snapshot, before
# Claude enumerates skills — bakes their /<plugin>:<skill> commands into the
# image so they are available on the FIRST session. See .claude/hooks/cc-web-setup.sh.
cc-web-setup: ## Provision a Claude Code on the web VM (plugin pre-seed) — set the env Setup-script field to this
	@bash .claude/hooks/cc-web-setup.sh
