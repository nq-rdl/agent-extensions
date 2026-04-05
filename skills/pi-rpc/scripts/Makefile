.PHONY: build test lint generate serve clean

BIN     := bin/pi-server
PKG     := ./cmd/pi-server/
PORT    ?= 4097

build:
	CGO_ENABLED=0 go build -o $(BIN) $(PKG)

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
