FROM node:20-bookworm-slim

COPY --from=ghcr.io/prefix-dev/pixi:0.78.0 /usr/local/bin/pixi /usr/local/bin/pixi

# Keep the native runtime pinned to the compatibility version tested in CI.
ARG CODEX_VERSION=0.154.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates git jq diffutils \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force

# Bake the repository's locked Python environment into the image so tests can
# run offline against a read-only checkout. Keep its install prefix fixed.
COPY pyproject.toml pixi.lock /opt/codex-python/
RUN pixi install --locked --manifest-path /opt/codex-python/pyproject.toml \
    && chown -R node:node /opt/codex-python

RUN mkdir -p /workspace /home/node/.cache \
    && chown node:node /workspace /home/node/.cache
USER node
WORKDIR /workspace
CMD ["sleep", "infinity"]
