Platform notes (macOS vs Linux)
===============================

The scripts detect the platform with ``uname -s`` (``Darwin`` / ``Linux``; WSL via
``/proc/version``) and avoid the usual portability traps:

* **Fetcher** — ``curl`` first, ``wget`` fallback. ``wget`` is absent on stock macOS and
  on many minimal Linux hosts/devcontainers; ``curl`` is present on both. Nothing else
  (python/requests, httpie, node) is used or allowed by the guard hook.
* **bash 3.2** (macOS default) — no associative arrays, ``mapfile``, or ``${var,,}``.
* **stat** — GNU ``stat -c %a`` vs BSD ``stat -f %Lp`` (file-mode check on the token file);
  GNU ``stat -c %Y`` vs ``date -r`` for cache age.
* **mktemp** — always called with an explicit ``XXXXXX`` template (BSD requires it).
* **base64** — avoided entirely: GitHub content is fetched raw
  (``raw.githubusercontent.com``) rather than decoded from the contents API.
* **Keychain** — macOS ``security find-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -w``;
  Linux ``secret-tool lookup service redhat key RH_OFFLINE_TOKEN`` (needs a running Secret
  Service — typically absent on headless hosts, where the 0600 file or Bitwarden applies).
* **Runtime cache** — ``$XDG_RUNTIME_DIR`` (Linux, tmpfs, per-user) falling back to
  ``$TMPDIR`` (macOS per-user) then ``/tmp``; directory mode 700, files 600.
* **sed -i** — not used (BSD needs ``-i ''``).
