.PHONY: build test lint clean

BIN := bin/jules
PKG := ./cmd/jules/

build:
	CGO_ENABLED=0 go build -o $(BIN) $(PKG)

test:
	go test ./...

lint:
	go vet ./...

clean:
	rm -rf bin/
