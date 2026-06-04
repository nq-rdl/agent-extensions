# MCP Integrations

Each MCP integration is a Go module under `mcp/`. Binaries are prebuilt for each supported platform and committed to the subject plugin that wires the server, at `plugins/<subject>/bin/mcp/` (the catalog currently ships no Go MCP servers).

Build locally:

```bash
cd mcp/<name>-go
go mod download       # first time only
make build            # current platform
make cross-compile DESTDIR=../../plugins/<subject>/bin/mcp
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
