#!/usr/bin/env python3
"""Summarise an agent-skills sync into a concise PR body.

The previous workflow embedded ``git diff --stat HEAD~1`` directly in the PR
body, producing a ~60k-line dump that can blow past GitHub's 65,536-char body
limit. This turns the raw ``git diff --name-status`` output into a short summary
of which skills were added / removed / modified, plus an explicit
"reconciliation required" section when bundles reference removed skills.

CLI:
    git diff --name-status BASE..HEAD | python3 scripts/sync_pr_body.py <tag> [REPO_ROOT]

Passing REPO_ROOT enables the "map these to publish" section, which flags synced
skills that no bundle references yet (so they are copied but not installable).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SKILLS_REPO = "nq-rdl/agent-skills"


def mapped_skill_sources(repo):
    """Return the set of upstream skill sources referenced by any bundle.

    A skill only becomes an installable plugin facet once a bundle in
    ``registry/bundles/`` references it (flat ``<name>`` or ``{source, leaf}``).
    The sync workflow only *copies* ``skills/`` — it never maps. So a freshly
    synced skill is invisible to users until a maintainer adds it to a bundle.
    This lets the PR body flag exactly which new skills still need that step.

    Returns ``None`` (not an empty set) when the registry or PyYAML is
    unavailable: "unknown", so the caller skips the unmapped section rather than
    falsely flagging every skill as unmapped. A genuinely empty set (registry
    present but referencing no skills) is a real "nothing mapped" answer.
    """
    repo = Path(repo)
    bundles_dir = repo / "registry" / "bundles"
    if not bundles_dir.is_dir():
        return None
    try:
        import yaml
    except ImportError:
        return None
    sources: set = set()
    for bf in sorted(list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))):
        try:
            data = yaml.safe_load(bf.read_text()) or {}
        except yaml.YAMLError:
            continue
        for member in data.get("skills") or []:
            if isinstance(member, str):
                sources.add(member)
            elif isinstance(member, dict) and isinstance(member.get("source"), str):
                sources.add(member["source"])
    return sources


def classify_skill_changes(name_status_lines) -> dict:
    """Bucket top-level skills/<name>/ dirs into added / removed / modified.

    Paths outside skills/ (e.g. plugins/ mirrors) are ignored: the plugin trees
    are derivative, so the skill name is the unit a reviewer cares about.
    """
    statuses: dict = {}
    for line in name_status_lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t") if "\t" in line else line.split(None, 1)
        if len(parts) < 2:
            continue
        status = parts[0]
        # Renames/copies are emitted as "R100\told\tnew" — count the old path as
        # removed and the new path as added, not the rename char against one path.
        if status[0] in ("R", "C") and len(parts) >= 3:
            path_statuses = [(parts[1], "D"), (parts[2], "A")]
        else:
            path_statuses = [(parts[1], status[0])]
        for path, char in path_statuses:
            segs = path.split("/")
            if len(segs) < 2 or segs[0] != "skills":
                continue
            statuses.setdefault(segs[1], set()).add(char)

    added, removed, modified = [], [], []
    for name, st in statuses.items():
        if st == {"A"}:
            added.append(name)
        elif st == {"D"}:
            removed.append(name)
        else:
            modified.append(name)
    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "modified": sorted(modified),
    }


def _bullets(names, limit=50) -> str:
    if not names:
        return "_none_"
    out = "\n".join(f"- `{n}`" for n in names[:limit])
    if len(names) > limit:
        out += f"\n- _…and {len(names) - limit} more_"
    return out


def render_pr_body(tag, changes, drift_messages=None, mapped_sources=None, max_chars=60000) -> str:
    added = changes.get("added", [])
    removed = changes.get("removed", [])
    modified = changes.get("modified", [])
    link = f"https://github.com/{SKILLS_REPO}/releases/tag/{tag}"

    parts = [
        f"Automated sync of skill directories from [{SKILLS_REPO}@{tag}]({link}).",
        "",
        "> This workflow **only copies** `skills/` from upstream. A new skill is "
        "not installable until a maintainer maps it into a subject bundle in "
        "`registry/bundles/` — see "
        "[`CONTRIBUTING.md`](../blob/main/CONTRIBUTING.md#packaging-a-new-skill-into-a-plugin).",
        "",
        f"**Summary:** {len(added)} added · {len(removed)} removed · "
        f"{len(modified)} modified",
        "",
        "### Added",
        _bullets(added),
        "",
        "### Removed",
        _bullets(removed),
        "",
        "### Modified",
        _bullets(modified),
    ]
    # Surface skills added by THIS sync that no bundle references yet: copied but
    # not installable until mapped. Scope is the sync delta (the `added` set) on
    # purpose — flagging every long-unmapped skill on every sync PR would be
    # noise; this PR is responsible for what it introduced.
    if mapped_sources is not None:
        unmapped = sorted(s for s in added if s not in mapped_sources)
        if unmapped:
            parts += [
                "",
                "### 📦 Action required — map these to publish",
                "Copied from upstream but referenced by **no** bundle, so they are "
                "**not yet installable**. Add each to a subject bundle "
                "(`registry/bundles/<subject>.yaml`) as a flat `<name>` or "
                "`{source, leaf}` mapping, then run `scripts/sync-plugins.sh`:",
                *[f"- `{n}`" for n in unmapped],
            ]
    if drift_messages:
        parts += [
            "",
            "### ⚠️ Reconciliation required",
            "Bundles still reference skills or agents that no longer exist "
            "upstream. `validate-bundles` will fail until the registry is "
            "reconciled — edit the bundle YAML in `registry/bundles/`, then run "
            "`python3 scripts/generate_manifests.py .` to regenerate the manifests):",
            *[f"- {m}" for m in drift_messages],
        ]

    body = "\n".join(parts)
    if len(body) > max_chars:
        body = (
            body[: max_chars - 80].rstrip()
            + "\n\n_…summary truncated to fit GitHub's PR body limit._"
        )
    return body


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tag = argv[0] if argv else "unknown"
    repo = argv[1] if len(argv) > 1 else None
    changes = classify_skill_changes(sys.stdin.read().splitlines())
    # Drift messages (bundles referencing removed skills) are passed in via the
    # SYNC_DRIFT env var so the workflow can surface them in the PR body.
    drift = [m for m in os.environ.get("SYNC_DRIFT", "").splitlines() if m.strip()]
    mapped = mapped_skill_sources(repo) if repo else None
    print(render_pr_body(tag, changes, drift_messages=drift, mapped_sources=mapped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
