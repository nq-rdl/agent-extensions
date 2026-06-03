"""Shared registry helpers for the pipeline scripts.

The single canonical parser for a bundle skill member lives here so the
validators (``check_bundle_refs.py``, ``check_grouping.py``) agree on the
contract. The bash-embedded heredocs in ``sync-plugins.sh`` and
``validate-plugins.sh`` inline an equivalent of ``normalize_member`` (the
heredoc boundary makes importing awkward); keep them in step with this file.
"""
from __future__ import annotations


def normalize_member(member) -> tuple[str, str]:
    """Return ``(source, leaf)`` for a bundle skill member.

    A member is either:

      * a flat string ``"sops"`` — ``source == leaf == "sops"`` (legacy shape,
        and still how single-facet plugins are written); or
      * an explicit mapping ``{"source": "go-gh", "leaf": "gh"}`` — packages the
        flat upstream skill ``skills/go-gh/`` under leaf ``gh`` so Claude Code
        invokes ``<pluginName>:gh`` (Option-2 grouping, owned in this repo).

    Raises ``ValueError`` on any other shape so callers/validators surface a
    malformed member instead of silently mis-syncing.
    """
    if isinstance(member, str):
        return member, member
    if isinstance(member, dict):
        source, leaf = member.get("source"), member.get("leaf")
        if isinstance(source, str) and source and isinstance(leaf, str) and leaf:
            return source, leaf
    raise ValueError(
        f"malformed skill member {member!r}: expected a string or a "
        "{source, leaf} mapping with non-empty string values"
    )
