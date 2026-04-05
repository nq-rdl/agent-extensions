# actions/setup-go — Advanced Usage

> Source: <https://github.com/actions/setup-go/blob/main/docs/advanced-usage.md>

## Version Specification

### Exact Versions

For reproducible builds, specify `major.minor.patch`:

```yaml
go-version: '1.25.5'
```

### Major.Minor Versions

Specify `1.25` to get the latest patch. A single patch per minor is
pre-installed on runners, making setup faster.

```yaml
go-version: '1.25'
```

### Pre-release Versions

```yaml
go-version: '1.25.0-rc.2'
```

### Version Aliases

```yaml
go-version: 'stable'      # latest stable from go-versions manifest
go-version: 'oldstable'   # previous minor's latest patch
```

### SemVer Ranges

```yaml
go-version: '^1.25.1'
go-version: '>=1.24.0-rc.1'
```

## Reading from Version Files

The `go-version-file` input supports:

- `go.mod` — reads `toolchain` directive first, falls back to `go` directive
- `go.work`
- `.go-version`
- `.tool-versions` (asdf format, requires SemVer-compliant version)

```yaml
- uses: actions/setup-go@v5
  with:
    go-version-file: 'go.mod'
```

## Matrix Testing

```yaml
strategy:
  matrix:
    go: ['1.24', '1.25']
    os: [ubuntu-latest, macos-latest]
  exclude:
    - os: macos-latest
      go: '1.24'

steps:
  - uses: actions/checkout@v5
  - uses: actions/setup-go@v5
    with:
      go-version: ${{ matrix.go }}
```

## Check Latest Version

Force a check that the cached version is current:

```yaml
- uses: actions/setup-go@v5
  with:
    go-version: '1.25'
    check-latest: true
```

Supports major and major.minor selectors. Has a performance cost — adds a
network call. Ignored when using custom download URLs.

## Caching Strategies

### Default Behavior

`actions/setup-go` v5+ automatically caches `~/go/pkg/mod` and
`~/.cache/go-build` using `go.sum` as the cache key.

### Monorepos

```yaml
- uses: actions/setup-go@v5
  with:
    go-version-file: go.mod
    cache-dependency-path: subdir/go.sum
```

### Multi-module Repositories

Glob patterns and multi-line values:

```yaml
cache-dependency-path: |
  subdir/go.sum
  tools/go.sum
```

Or wildcards:

```yaml
cache-dependency-path: '**/go.sum'
```

### Multi-target Builds

Include build environment files to vary cache by target:

```yaml
cache-dependency-path: |
  go.sum
  env.txt  # Contains GOOS/GOARCH
```

### Source-change Invalidation

Include source files to bust cache on code changes:

```yaml
cache-dependency-path: |
  go.sum
  **/*.go
```

> **Warning:** Frequent source-file patterns create new caches on every commit,
> increasing storage usage.

### Restore-only Caches

Read from cache without writing back:

```yaml
- uses: actions/setup-go@v5
  with:
    go-version: '1.25.5'
    cache: false

- uses: actions/cache/restore@v5
  with:
    path: |
      ~/go/pkg/mod
      ~/.cache/go-build
    key: go-${{ runner.os }}-${{ hashFiles('**/go.sum') }}
```

### Parallel Builds

Avoid race conditions by either using distinct cache keys per parallel job or
creating the cache in one job and restoring in others.

## Outputs

### `go-version`

The exact version installed (useful when specifying ranges):

```yaml
- uses: actions/setup-go@v5
  id: setup
  with:
    go-version: '^1.24'
- run: echo "Installed Go ${{ steps.setup.outputs.go-version }}"
```

### `cache-hit`

Boolean — `true` when the primary cache key matched exactly:

```yaml
- uses: actions/setup-go@v5
  id: setup
  with:
    cache: true
- run: echo "Cache hit: ${{ steps.setup.outputs.cache-hit }}"
```

## Custom Download URLs

### Basic Usage

```yaml
- uses: actions/setup-go@v5
  with:
    go-version: '1.25.0'
    go-download-base-url: 'https://aka.ms/golang/release/latest'
```

### Via Environment Variable

```yaml
env:
  GO_DOWNLOAD_BASE_URL: 'https://aka.ms/golang/release/latest'
```

The `go-download-base-url` input takes precedence over the env var.

### Limitations with Custom URLs

- Version ranges (`^1.25`, `~1.24`) not supported unless the server provides
  `/?mode=json&include=all`
- Aliases (`stable`, `oldstable`) not supported
- Only exact versions: `1.25`, `1.25.0`, or `1.25.0-1` (revision numbers)
- `check-latest` is ignored

### Authenticated Downloads

```yaml
- uses: actions/setup-go@v5
  with:
    go-version: '1.25.0'
    go-download-base-url: 'https://private-mirror.example.com/golang'
    token: ${{ secrets.MIRROR_TOKEN }}
```

Token is passed as an `Authorization` header.

## GHES (GitHub Enterprise Server)

- Use custom download URLs or pre-cached versions to reduce external API calls
- For environments without github.com access, configure a private mirror via
  `go-download-base-url` with the appropriate auth token
