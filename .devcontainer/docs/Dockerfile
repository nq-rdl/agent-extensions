# Docs preview container for the Zensical documentation site.
#
# The repo's `docs` pixi environment solves only for `linux-64` — Zensical has
# no macOS or aarch64 conda build (see pixi.lock: only conda-forge/linux-64).
# The platform is therefore pinned to linux/amd64 so the `docs` env resolves; on
# an Apple Silicon host this runs under Docker's amd64 emulation, which is fine
# for a preview server. The pin is enforced in three layers so it can't be
# silently dropped: this FROM flag (build-time, honored regardless of how the
# Dev Containers CLI invokes docker build), `build.options` (the documented
# devcontainer.json way to pass docker-build flags), and `runArgs` (docker run).
#
# This is intentionally lightweight: no iptables firewall (unlike the
# marketplace sandbox in ../Dockerfile) — a docs preview box needs open
# outbound to fetch conda/PyPI packages, not the locked-down sandbox.
FROM --platform=linux/amd64 node:20-slim

ARG TZ=America/Los_Angeles
ENV TZ="$TZ"

# Minimal tooling: git for the workspace, curl + ca-certificates for the pixi
# installer and HTTPS package fetches. node:20-slim ships neither curl nor CA
# certs by default.
RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set `DEVCONTAINER` to help with orientation, matching the sandbox container.
ENV DEVCONTAINER=true

# Let the default `node` user own the global npm prefix (for the claude-code
# install below) and its Claude config dir (target of a persisted volume).
RUN mkdir -p /usr/local/share/npm-global /home/node/.claude \
  && chown -R node:node /usr/local/share/npm-global /home/node/.claude

USER node
# Docker's USER does not set HOME; set it so the pixi installer and npm land in
# /home/node (not /root) during the build.
ENV HOME=/home/node
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=/usr/local/share/npm-global/bin:$PATH

# Claude Code, so docs can be authored with Claude inside this container.
ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# pixi provides the `docs` environment (Zensical). Same official installer the
# marketplace sandbox uses.
RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH=/home/node/.pixi/bin:$PATH
