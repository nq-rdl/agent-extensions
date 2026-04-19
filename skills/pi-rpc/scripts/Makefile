.PHONY: build build-cli build-mcp test lint generate serve clean cross-compile

SERVER_BIN := bin/pi-server
CLI_BIN    := bin/pi-cli
MCP_BIN    := bin/pi-mcp
SERVER_PKG := ./cmd/pi-server/
CLI_PKG    := ./cmd/pi-cli/
MCP_PKG    := ./cmd/pi-mcp/
PORT       ?= 4097

DESTDIR ?= bin

LDFLAGS := -X main.version=$(shell git describe --tags --always --dirty 2>/dev/null || echo dev) \
           -X main.commit=$(shell git rev-parse --short HEAD 2>/dev/null || echo none)

TARGETS := \
	linux/amd64 \
	linux/arm64 \
	darwin/amd64 \
	darwin/arm64

build: build-server build-cli build-mcp

build-server:
	CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o $(SERVER_BIN) $(SERVER_PKG)

build-cli:
	CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o $(CLI_BIN) $(CLI_PKG)

build-mcp:
	CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o $(MCP_BIN) $(MCP_PKG)

# cross-compile builds the pi-server binary for all target platforms.
# Output: $(DESTDIR)/pi-server-<os>-<arch>
# Usage:  make cross-compile DESTDIR=/path/to/out
# Shell loop (not $(foreach)) so an individual build failure exits non-zero.
cross-compile:
	@mkdir -p $(DESTDIR)
	@for target in $(TARGETS); do \
		os=$${target%/*}; \
		arch=$${target#*/}; \
		echo "Building for $$os/$$arch..."; \
		CGO_ENABLED=0 GOOS=$$os GOARCH=$$arch go build \
			-trimpath -ldflags "$(LDFLAGS)" \
			-o $(DESTDIR)/pi-server-$$os-$$arch \
			$(SERVER_PKG) || exit 1; \
	done

test:
	go test -race ./...

lint:
	go vet ./...

generate:
	buf generate

serve: build-server
	PI_SERVER_PORT=$(PORT) ./$(SERVER_BIN)

clean:
	rm -rf bin/
