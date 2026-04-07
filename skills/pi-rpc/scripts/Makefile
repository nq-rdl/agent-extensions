.PHONY: build build-cli test lint generate serve clean

SERVER_BIN := bin/pi-server
CLI_BIN    := bin/pi-cli
SERVER_PKG := ./cmd/pi-server/
CLI_PKG    := ./cmd/pi-cli/
PORT       ?= 4097

LDFLAGS := -X main.version=$(shell git describe --tags --always --dirty 2>/dev/null || echo dev) \
           -X main.commit=$(shell git rev-parse --short HEAD 2>/dev/null || echo none)

build: build-server build-cli

build-server:
	CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o $(SERVER_BIN) $(SERVER_PKG)

build-cli:
	CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o $(CLI_BIN) $(CLI_PKG)

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
