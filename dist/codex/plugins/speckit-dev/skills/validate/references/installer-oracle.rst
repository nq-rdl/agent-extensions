spec-kit installer oracle
=========================

Use this only with the user's explicit approval to fetch and run the upstream
installer. It confirms what the pinned ``specify`` CLI does with an extension,
without touching the user's project. The requirements are in ``SKILL.md``; this
file gives commands and a fixture set.

Status: **not run** by this repository. On 2026-09-29 the session's permission
policy refused to execute the fetched installer, so every label in ``SKILL.md``
is source-derived. Record your own run (tag, commands, exit codes, cleanup)
before relying on it.

Isolated run
------------

Needs ``uv`` and a Python >= 3.11 interpreter (``uv`` must not download one:
``UV_PYTHON_DOWNLOADS=never``). Replace ``$PY`` with that interpreter::

    T="$(mktemp -d)"
    mkdir -p "$T"/{home,cfg,cache,data,uvcache,uvtools,proj}
    cp -R ./my-ext "$T/ext"                      # a copy, never the original
    iso() {
      env -i PATH=/usr/bin:/bin HOME="$T/home" \
        XDG_CONFIG_HOME="$T/cfg" XDG_CACHE_HOME="$T/cache" XDG_DATA_HOME="$T/data" \
        UV_CACHE_DIR="$T/uvcache" UV_TOOL_DIR="$T/uvtools" UV_NO_CONFIG=1 \
        UV_PYTHON_DOWNLOADS=never GIT_TERMINAL_PROMPT=0 NO_COLOR=1 "$@"
    }
    SPECIFY="$(command -v uv) tool run --python $PY \
      --from git+https://github.com/github/spec-kit@v1.0.12 specify"
    iso $SPECIFY version
    (cd "$T/proj" && iso $SPECIFY init --here --force --integration claude \
       --script sh --ignore-agent-tools --non-interactive)
    (cd "$T/proj" && iso $SPECIFY extension add --dev "$T/ext"); echo "exit=$?"
    rm -rf "$T"; test ! -e "$T" && echo "cleaned up"

``env -i`` drops tokens such as ``GITHUB_TOKEN`` and ``GH_TOKEN``. Record the
exit code and the first error or warning line. Use a fresh copy of ``proj`` per
extension, so one install cannot affect the next.

Fixtures
--------

Each fixture is the minimal valid manifest (``schema_version: "1.0"``, strings
for ``id``/``name``/``version``/``description``, ``speckit_version: ">=0.12.0"``,
one command ``speckit.<id>.greet`` with ``commands/greet.md`` carrying a
``description``) with one change. "Predicted" is read from the v1.0.12 source,
not observed.

=====================  ==========================================  ==========================
Fixture                Change                                      Predicted (v1.0.12)
=====================  ==========================================  ==========================
valid                  none                                        installs
effect-typo            ``effect: readonly``                        rejects
short-command          command ``speckit.greet``                   warns, renamed, installs
hook-unknown           hook ``before_build``                       installs; never fires
hook-converge          hook ``before_converge``                    installs
loose-version          ``version: "1.0"``                          installs
missing-file           no ``commands/greet.md``                    installs; command skipped
no-description         command file without frontmatter            installs
wrong-namespace        command ``speckit.other.greet``             rejects
unquoted-version       ``version: 1.0``                            rejects
core-id                ``id: plan``                                rejects
priority-zero          hook ``priority: 0``                        rejects
schema-float           ``schema_version: 1.0``                     rejects
future-speckit         ``speckit_version: ">=99.0.0"``             rejects
alias-traversal        ``aliases: ["../evil"]``                    rejects
=====================  ==========================================  ==========================

If an observed result differs from the prediction, the observation wins: update
``SKILL.md`` and ``validation-rules.rst`` and record the tag.
