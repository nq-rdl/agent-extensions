# MCP Integrations

Each MCP integration is a Go module under `mcp/`. Binaries are prebuilt for each supported platform and committed to `plugins/dev-tools/bin/mcp/`.

Build locally:

```bash
cd mcp/pi-rpc-go      # or mcp/gemini-cli-go
go mod download       # first time only
make build            # current platform
make cross-compile DESTDIR=../../plugins/dev-tools/bin/mcp
```

Layout:

```text
mcp/
  <name>-go/
    go.mod
    go.sum
    Makefile
    cmd/<name>/main.go
    internal/
```
