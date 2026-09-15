FROM node:20-bookworm-slim

# Keep the native runtime pinned to the compatibility version tested in CI.
ARG CODEX_VERSION=0.154.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates git jq diffutils python3 \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force

RUN mkdir -p /workspace /home/node/.cache \
    && chown node:node /workspace /home/node/.cache
USER node
WORKDIR /workspace
CMD ["sleep", "infinity"]
