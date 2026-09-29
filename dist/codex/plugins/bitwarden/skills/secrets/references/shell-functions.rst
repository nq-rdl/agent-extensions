Bitwarden Shell Functions: Design Notes
=======================================

The implementation lives in one place, ``scripts/bw-env.sh``. This file
explains why it is built the way it is. Read it before changing the script or
when a user's hand-written version misbehaves. Do not copy function bodies
from here; there are none, on purpose. Earlier copies in ``SKILL.md`` and in
this file had drifted: one ``bwc`` stored lines without ``export``, so ``bwe``
loaded nothing into the environment of child processes.

The behaviour below is checked by ``tests/test_bitwarden_bw_env.py`` in the
source repository, which puts a fake ``bw`` on ``PATH``.

Storage format
--------------

A Secure Note (item type 2) whose notes are comment lines, blank lines, and
lines of the form ``export NAME='value'``.

- ``bwc``/``bwu`` normalise the ``.env`` file before storing it. An unquoted
  value such as ``PASSWORD=pa ss`` would otherwise ``eval`` as
  ``export PASSWORD=pa`` plus an export of a variable called ``ss``, and
  ``TOKEN=a$HOME`` would expand ``$HOME``.
- Quoted input values (``"..."`` or ``'...'``) lose their outer quotes and are
  stored single-quoted. Embedded single quotes become ``'\''``.
- A trailing ``# comment`` after an unquoted value (preceded by a space) is
  dropped, as Docker Compose does.
- There is no variable interpolation. Store the resolved value.
- A line that is not ``NAME=value`` stops the upload. The error names the line
  number only, so the value does not reach the terminal.

Loading
-------

``bwe`` runs ``eval`` on the note, so it validates first: every non-comment line
must be ``export NAME=`` followed by a single-quoted value, a double-quoted value
without ``$``, backquote or backslash, or a bare value without shell syntax.
Anything else is refused, so a note edited in the web vault cannot run
commands.

Output discipline
-----------------

- ``bw create item`` and ``bw edit item`` print the created or edited item as
  JSON, notes included (checked in the @bitwarden/cli 2026.9.0 source,
  ``CreateCommand.createCipher`` returns a ``CipherResponse``). The script
  captures that output and prints only the item ID.
- Status messages go to stderr, so ``val="$(bwf item field)"`` captures only
  the value.
- ``bwf`` is the only function that prints a secret to stdout; use it inside
  ``$(...)``.
- Never enable ``set -x`` while a session key or secret is on a command line.

Shell portability
-----------------

- The script is sourced into interactive bash or zsh. It uses ``${VAR:-}`` so
  it works under ``set -u`` / ``setopt nounset``.
- zsh does not word-split unquoted parameters, so ``bwunload`` splits the
  variable names through command substitution.
- The awk programs avoid GNU-only features; they were run with GNU awk and
  BusyBox awk. ``grep -P`` is avoided because BSD grep lacks it.

Session handling
----------------

``bwss`` unlocks only when ``BW_SESSION`` is empty and leaves it unset if
unlocking fails, so the next call prompts again instead of reusing an empty
session.

Named loaders
-------------

For one token under several variable names, see ``scripts/load-github.sh``.
It is a zsh autoload function file: put the directory on ``fpath`` and
``autoload -Uz load_github`` so nothing is loaded at shell start. Use the item
UUID, not the name, so a rename does not break it.
