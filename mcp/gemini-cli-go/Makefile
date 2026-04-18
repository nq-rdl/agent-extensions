BINARY     := gemini-cli-mcp
MODULE_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
DESTDIR    ?= $(MODULE_DIR)/bin
VERSION    := $(shell git -C $(MODULE_DIR) describe --tags --always --dirty 2>/dev/null || echo dev)
LDFLAGS    := -X main.version=$(VERSION)
GOFLAGS    := -trimpath -ldflags="$(LDFLAGS)"

TARGETS := \
	linux/amd64 \
	linux/arm64 \
	darwin/amd64 \
	darwin/arm64

.PHONY: build cross-compile test lint clean tidy

build:
	CGO_ENABLED=0 go build $(GOFLAGS) -o $(DESTDIR)/$(BINARY) ./cmd/$(BINARY)

cross-compile:
	@mkdir -p $(DESTDIR)
	$(foreach target,$(TARGETS), \
		$(eval GOOS=$(word 1,$(subst /, ,$(target)))) \
		$(eval GOARCH=$(word 2,$(subst /, ,$(target)))) \
		CGO_ENABLED=0 GOOS=$(GOOS) GOARCH=$(GOARCH) go build $(GOFLAGS) \
			-o $(DESTDIR)/$(BINARY)-$(GOOS)-$(GOARCH) \
			./cmd/$(BINARY);)

test:
	go test -race ./...

lint:
	go vet ./...

tidy:
	go mod tidy

clean:
	rm -f $(DESTDIR)/$(BINARY) $(DESTDIR)/$(BINARY)-*
