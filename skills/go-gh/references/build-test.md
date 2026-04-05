# Build and Test Go with GitHub Actions

> Source: <https://docs.github.com/en/actions/tutorials/build-and-test-code/go>

## Starter Workflow

Navigate to **Actions → New workflow → search "go"** to use the official
starter template, or create `.github/workflows/go.yml` manually.

## Specifying a Go Version

### Single Version

```yaml
name: Go CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Setup Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.25.x'
      - name: Display Go version
        run: go version
```

### Version Matrix

Test across multiple Go versions:

```yaml
name: Go CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        go-version: ['1.23', '1.24', '1.25.x']
    steps:
      - uses: actions/checkout@v5
      - name: Setup Go ${{ matrix.go-version }}
        uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}
      - name: Display Go version
        run: go version
```

## Installing Dependencies

```yaml
steps:
  - uses: actions/checkout@v5
  - uses: actions/setup-go@v5
    with:
      go-version-file: go.mod
  - name: Install dependencies
    run: go mod download
```

For specific additional dependencies:

```yaml
- name: Install extra dependencies
  run: |
    go get example.com/octo-examplemodule
    go get example.com/octo-examplemodule@v1.3.4
```

### Caching Dependencies

`actions/setup-go` v5+ handles caching automatically. For monorepos or
multi-module layouts:

```yaml
- uses: actions/setup-go@v5
  with:
    go-version-file: go.mod
    cache-dependency-path: subdir/go.sum
```

## Building

```yaml
- name: Build
  run: go build -v ./...
```

## Testing

### Basic Tests

```yaml
- name: Test
  run: go test -v ./...
```

### With Race Detection and Coverage

```yaml
- name: Test
  run: go test -v -race -coverprofile=coverage.out ./...
```

### JSON Test Output

```yaml
- name: Test with JSON output
  run: go test -json ./... > TestResults-${{ matrix.go-version }}.json
```

## Uploading Test Artifacts

Save test results for later analysis or cross-job consumption:

```yaml
name: Upload Go test results
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        go-version: ['1.23', '1.24', '1.25.x']
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}
      - name: Install dependencies
        run: go mod download
      - name: Build
        run: go build -v ./...
      - name: Test
        run: go test -json ./... > TestResults-${{ matrix.go-version }}.json
      - name: Upload test results
        uses: actions/upload-artifact@v4
        with:
          name: Go-results-${{ matrix.go-version }}
          path: TestResults-${{ matrix.go-version }}.json
```

## Complete Production Workflow

A full CI workflow combining all patterns:

```yaml
name: Go CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        go-version: ['1.24', '1.25']
    steps:
      - uses: actions/checkout@v5

      - name: Setup Go ${{ matrix.go-version }}
        uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}

      - name: Install dependencies
        run: go mod download

      - name: Build
        run: go build -v ./...

      - name: Test
        run: go test -v -race -coverprofile=coverage.out ./...

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-${{ matrix.go-version }}
          path: coverage.out

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.go-version }}
          path: TestResults-*.json
```
