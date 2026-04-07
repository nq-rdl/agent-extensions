.PHONY: build test lint generate serve clean cross-compile

BIN     := bin/pi-server
PKG     := ./cmd/pi-server/
PORT    ?= 4097
DESTDIR ?= bin

PLATFORMS := linux/amd64 darwin/arm64 darwin/amd64

build:
	CGO_ENABLED=0 go build -o $(BIN) $(PKG)

cross-compile:
	@for platform in $(PLATFORMS); do \
	  os=$${platform%%/*}; arch=$${platform##*/}; \
	  echo "Building pi-server-$$os-$$arch"; \
	  CGO_ENABLED=0 GOOS=$$os GOARCH=$$arch \
	    go build -o $(DESTDIR)/pi-server-$$os-$$arch $(PKG); \
	done

test:
	go test ./...

lint:
	go vet ./...

generate:
	buf generate

serve: build
	PI_SERVER_PORT=$(PORT) ./$(BIN)

clean:
	rm -rf bin/
