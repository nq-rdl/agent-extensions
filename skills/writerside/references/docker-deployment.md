# Writerside Docker Deployment

Awareness-level reference for building Writerside documentation with Docker. This skill does **not** create deployments — it provides the context needed to understand and troubleshoot the Docker-based build process.

---

## Overview

Writerside provides a Docker image (`jetbrains/writerside-builder`) that contains the full documentation builder. This enables:
- Version-specific builds independent of local Writerside IDE installations
- CI/CD automation on GitHub Actions, GitLab CI, and TeamCity
- Reproducible builds across platforms

---

## Docker Image

Pull the builder image (version-tagged):

```bash
docker pull jetbrains/writerside-builder:2026.02.8644
```

Alternative registry (JetBrains):

```bash
docker pull registry.jetbrains.team/p/writerside/builder/writerside-builder:2026.02.8644
```

---

## Basic Build Command

```bash
docker run --rm \
  -v .:/opt/sources \
  -e SOURCE_DIR=/opt/sources \
  -e MODULE_INSTANCE=Writerside/hi \
  -e OUTPUT_DIR=/opt/sources/output \
  -e RUNNER=other \
  jetbrains/writerside-builder:2026.02.8644
```

This mounts the current directory, builds the `hi` instance from the `Writerside` module, and writes output to `./output/`.

---

## Environment Variables

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `SOURCE_DIR` | Yes | Directory containing documentation sources | `/opt/sources` |
| `MODULE_INSTANCE` | Yes | Module and instance ID (format: `Module/instance`) | `Writerside/hi` |
| `OUTPUT_DIR` | Yes | Where to write generated artifacts | `/opt/sources/output` |
| `RUNNER` | No | Execution environment — affects artifact format | `github`, `gitlab`, `teamcity`, `other` |
| `PDF` | No | PDF export configuration filename | `PDF.xml` |
| `IS_GROUP` | No | Set `true` for multi-instance group builds | `true` |
| `DISPLAY` | No | Virtual display for rendering (needed in Dockerfiles) | `:99` |

---

## Command-Line Options

When invoking the builder script directly (e.g., in a custom Dockerfile):

| Option | Short | Purpose |
|--------|-------|---------|
| `--source-dir` | `-i` | Documentation sources location |
| `--output-dir` | `-o` | Build artifact destination |
| `--product` | `-p` | Module/instance pair for single instance builds |
| `--group` | `-g` | Module/build-group pair for grouped builds |
| `--runner` | `-r` | Environment specification |
| `-pdf` | — | Trigger PDF generation using specified settings file |

---

## Output

Built artifacts appear in the output directory. The generated filename follows the pattern:

```
webHelp<INSTANCE_ID>-all.zip
```

Where `<INSTANCE_ID>` is the instance ID in uppercase. For example, instance `hi` produces `webHelpHI-all.zip`.

Adding the `-pdf` parameter generates PDF output alongside the HTML website.

---

## Multi-Instance Builds

To build multiple instances as a unified documentation website:

1. Set `IS_GROUP=true`
2. Set `MODULE_INSTANCE` to the build group ID (not an individual instance)

```bash
docker run --rm \
  -v .:/opt/sources \
  -e SOURCE_DIR=/opt/sources \
  -e MODULE_INSTANCE=Writerside/all-docs \
  -e OUTPUT_DIR=/opt/sources/output \
  -e IS_GROUP=true \
  -e RUNNER=other \
  jetbrains/writerside-builder:2026.02.8644
```

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: Build docs
  run: |
    docker run --rm \
      -v ${{ github.workspace }}:/opt/sources \
      -e SOURCE_DIR=/opt/sources \
      -e MODULE_INSTANCE=Writerside/hi \
      -e OUTPUT_DIR=/opt/sources/output \
      -e RUNNER=github \
      jetbrains/writerside-builder:2026.02.8644
```

### Environment File

Pass variables via `.env` file for cleaner scripts:

```bash
docker run --rm \
  -v .:/opt/sources \
  --env-file .env \
  jetbrains/writerside-builder:2026.02.8644
```

---

## Custom Dockerfile Pattern

For advanced setups combining the builder with a web server:

```dockerfile
FROM jetbrains/writerside-builder:2026.02.8644 AS builder

# Critical: DISPLAY and Xvfb must be in the SAME RUN directive as the builder
RUN export DISPLAY=:99 && \
    Xvfb :99 & \
    /opt/builder/bin/idea.sh helpbuilderinspect \
      -source-dir /opt/sources \
      -product Writerside/hi \
      -output-dir /opt/results

FROM httpd:2.4
COPY --from=builder /opt/results/ /usr/local/apache2/htdocs/
```

**Critical requirement:** Setting the `DISPLAY` variable and starting `Xvfb` must happen in the same `RUN` directive as the builder script execution. Splitting them into separate `RUN` directives causes display initialization failures.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Build fails with display error | `DISPLAY` and `Xvfb` in separate RUN directives | Combine into single RUN directive |
| Empty output directory | Wrong `MODULE_INSTANCE` format | Use `Module/instance` format (e.g., `Writerside/hi`) |
| Instance not found | Instance ID doesn't match project config | Check instance ID in Writerside project settings |
| Slow builds | Large image download on every CI run | Cache the Docker image in your CI pipeline |
