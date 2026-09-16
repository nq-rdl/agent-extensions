Platform notes (macOS vs Linux)
===============================

The scripts detect the platform with ``uname -s`` (``Darwin`` / ``Linux``; WSL via
``/proc/version``) and avoid the usual portability traps:

* **Fetcher** – ``curl`` first, ``wget`` fallback. ``wget`` is absent on stock macOS and
  on many minimal Linux hosts/devcontainers; ``curl`` is present on both. Nothing else
  (python/requests, httpie, node) is used or allowed by the guard hook.
* **bash 3.2** (macOS default) – no associative arrays, ``mapfile``, or ``${var,,}``.
* **stat** – GNU ``stat -c %a`` vs BSD ``stat -f %Lp`` (file-mode check on the token file);
  GNU ``stat -c %Y`` vs BSD ``stat -f %m`` for the tree-cache age (``rh_file_mtime``). BSD
  ``date -r`` takes an epoch, not a path, so it is not used; GNU is probed first because GNU
  ``stat -f`` means *file-system* status and would succeed with the wrong answer.
* **wget auth** – the Bearer header is handed to wget through a 0600 ``--config`` wgetrc
  translated from the curl ``-K`` config, never as a ``--header=`` argument (which would show
  in ``ps`` / ``/proc/<pid>/cmdline``).
* **pipefail** – ``rh-fetch.sh`` sets it and renders the docs route into a file before
  ``emit``, so a failed ``raw.githubusercontent.com`` fetch exits 2 instead of printing only the
  provenance header with exit 0.
* **read -p** – not used in the commands users paste (``/redhat:setup``): zsh, the macOS
  default shell, treats ``read -p`` as "read from a coprocess" and would store an empty
  token. The prompts use ``printf`` + ``IFS= read -rs``, which behave the same in bash and zsh.
* **mktemp** – always called with an explicit ``XXXXXX`` template (BSD requires it).
* **base64** – avoided entirely: GitHub content is fetched raw
  (``raw.githubusercontent.com``) rather than decoded from the contents API.
* **Keychain** – macOS ``security find-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -w``;
  Linux ``secret-tool lookup service redhat key RH_OFFLINE_TOKEN`` (needs a running Secret
  Service – typically absent on headless hosts, where the 0600 file or Bitwarden applies).
* **Runtime cache** – ``$XDG_RUNTIME_DIR`` (Linux, tmpfs, per-user) falling back to
  ``$TMPDIR`` (macOS per-user) then ``/tmp``. Because ``/tmp/rh-token-<uid>`` is predictable
  on a shared host, ``rh_cache_dir`` refuses a symlink or a directory it does not own, forces
  mode 700, and ``rh-token.sh`` writes ``curl.cfg`` via mktemp + rename (never truncating a
  pre-existing file in place).
* **wget errors** – ``--content-on-error`` keeps 4xx/5xx bodies (so ``invalid_grant`` is
  still readable), the status is taken from wget's own stderr, and a connect/DNS failure
  prints wget's message and returns non-zero instead of an empty status.
* **sed -i** – not used (BSD needs ``-i ''``).
* **xtrace** – ``rh-lib.sh`` turns ``set -x``/``-v`` off as its first statement, so a caller's
  ``bash -x`` or an exported ``SHELLOPTS=xtrace`` cannot trace the token into stderr.
