actions/setup-go — Advanced Usage
=================================

   Source:
   https://github.com/actions/setup-go/blob/main/docs/advanced-usage.md
   (condensed; checked against the v7.0.0 tag on 2026-09-29. Upstream
   examples still show ``@v6``; inputs are unchanged in v7.)

Version Specification
---------------------

Exact Versions
~~~~~~~~~~~~~~

For reproducible builds, specify ``major.minor.patch``:

.. code:: yaml

   go-version: '1.25.5'

Major.Minor Versions
~~~~~~~~~~~~~~~~~~~~

Specify ``1.25`` to get the latest patch. A single patch per minor is
pre-installed on runners, making setup faster.

.. code:: yaml

   go-version: '1.25'

Pre-release Versions
~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   go-version: '1.25.0-rc.2'

Version Aliases
~~~~~~~~~~~~~~~

.. code:: yaml

   go-version: 'stable'      # latest stable from go-versions manifest
   go-version: 'oldstable'   # previous minor's latest patch

SemVer Ranges
~~~~~~~~~~~~~

.. code:: yaml

   go-version: '^1.25.1'
   go-version: '>=1.24.0-rc.1'

Reading from Version Files
--------------------------

The ``go-version-file`` input supports:

- ``go.mod`` — reads ``toolchain`` directive first, falls back to ``go``
  directive
- ``go.work``
- ``.go-version``
- ``.tool-versions`` (asdf format, requires SemVer-compliant version)

.. code:: yaml

   - uses: actions/setup-go@v7
     with:
       go-version-file: 'go.mod'

Matrix Testing
--------------

.. code:: yaml

   strategy:
     matrix:
       go: ['1.24', '1.25']
       os: [ubuntu-latest, macos-latest]
     exclude:
       - os: macos-latest
         go: '1.24'

   steps:
     - uses: actions/checkout@v7
     - uses: actions/setup-go@v7
       with:
         go-version: ${{ matrix.go }}

Check Latest Version
--------------------

Force a check that the cached version is current:

.. code:: yaml

   - uses: actions/setup-go@v7
     with:
       go-version: '1.25'
       check-latest: true

Supports major and major.minor selectors. Has a performance cost — adds
a network call. Ignored when using custom download URLs.

Caching Strategies
------------------

Default Behavior
~~~~~~~~~~~~~~~~

Caching is enabled by default (since v4) and covers the module cache
(``GOMODCACHE``) and build cache (``GOCACHE``). From v6 the key hashes the
root ``go.mod``; set ``cache-dependency-path`` to key on ``go.sum`` files or
modules outside the root. If caching fails, the action logs a warning and
continues.

Monorepos
~~~~~~~~~

.. code:: yaml

   - uses: actions/setup-go@v7
     with:
       go-version-file: go.mod
       cache-dependency-path: subdir/go.sum

Multi-module Repositories
~~~~~~~~~~~~~~~~~~~~~~~~~

Glob patterns and multi-line values:

.. code:: yaml

   cache-dependency-path: |
     subdir/go.sum
     tools/go.sum

Or wildcards:

.. code:: yaml

   cache-dependency-path: '**/go.sum'

Multi-target Builds
~~~~~~~~~~~~~~~~~~~

Include build environment files to vary cache by target:

.. code:: yaml

   cache-dependency-path: |
     go.sum
     env.txt  # Contains GOOS/GOARCH

Source-change Invalidation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Include source files to bust cache on code changes:

.. code:: yaml

   cache-dependency-path: |
     go.sum
     **/*.go

..

   **Warning:** Frequent source-file patterns create new caches on every
   commit, increasing storage usage.

Restore-only Caches
~~~~~~~~~~~~~~~~~~~

Read from cache without writing back. The restore key must equal the key of
the job that saved the cache; a made-up key restores nothing. To reuse the
caches setup-go saves, rebuild its key
(``setup-go-<os>-<arch>-<ImageOS>-go-<version>-<hash of go.mod>``) as in the
upstream example; this sketch assumes another job saves with the same key:

.. code:: yaml

   - uses: actions/setup-go@v7
     id: setup-go
     with:
       go-version: '1.25.5'
       cache: false

   - uses: actions/cache/restore@v6
     with:
       path: |
         ~/go/pkg/mod
         ~/.cache/go-build
       key: go-${{ runner.os }}-${{ steps.setup-go.outputs.go-version }}-${{ hashFiles('**/go.mod') }}

Parallel Builds
~~~~~~~~~~~~~~~

Avoid race conditions by either using distinct cache keys per parallel
job or creating the cache in one job and restoring in others.

Outputs
-------

``go-version``
~~~~~~~~~~~~~~

The exact version installed (useful when specifying ranges):

.. code:: yaml

   - uses: actions/setup-go@v7
     id: setup
     with:
       go-version: '^1.24'
   - run: echo "Installed Go ${{ steps.setup.outputs.go-version }}"

``cache-hit``
~~~~~~~~~~~~~

Boolean — ``true`` when the primary cache key matched exactly:

.. code:: yaml

   - uses: actions/setup-go@v7
     id: setup
     with:
       cache: true
   - run: echo "Cache hit: ${{ steps.setup.outputs.cache-hit }}"

Custom Download URLs
--------------------

Basic Usage
~~~~~~~~~~~

.. code:: yaml

   - uses: actions/setup-go@v7
     with:
       go-version: '1.25.0'
       go-download-base-url: 'https://aka.ms/golang/release/latest'

Via Environment Variable
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   env:
     GO_DOWNLOAD_BASE_URL: 'https://aka.ms/golang/release/latest'

The ``go-download-base-url`` input takes precedence over the env var.

Limitations with Custom URLs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Version ranges (``^1.25``, ``~1.24``) not supported unless the server
  provides ``/?mode=json&include=all``
- Aliases (``stable``, ``oldstable``) not supported
- Only exact versions: ``1.25``, ``1.25.0``, or ``1.25.0-1`` (revision
  numbers)
- ``check-latest`` is ignored

Authenticated Downloads
~~~~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   - uses: actions/setup-go@v7
     with:
       go-version: '1.25.0'
       go-download-base-url: 'https://private-mirror.example.com/golang'
       token: ${{ secrets.MIRROR_TOKEN }}

Token is passed as an ``Authorization`` header.

GHES (GitHub Enterprise Server)
-------------------------------

- setup-go reads the version manifest from ``actions/go-versions`` on
  github.com with unauthenticated requests (60 per hour per IP; GHES runners
  often share one IP). It then falls back to the raw manifest and to go.dev.
  If all fail, pass a github.com personal access token as ``token``.
- **No access to github.com:** every requested Go version must already be in
  the runner's tool cache. See `Setting up the tool cache on self-hosted
  runners without internet access
  <https://docs.github.com/en/enterprise-server@3.2/admin/github-actions/managing-access-to-actions-from-githubcom/setting-up-the-tool-cache-on-self-hosted-runners-without-internet-access>`__.
  A reachable internal mirror with ``go-download-base-url`` is the other
  option (exact versions only, see above).
