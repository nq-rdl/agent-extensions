#!/usr/bin/env python3
"""Summarise an agent-skills sync into a concise PR body.

The previous workflow embedded ``git diff --stat HEAD~1`` directly in the PR
body, producing a ~60k-line dump that can blow past GitHub's 65,536-char body
limit. This turns the raw ``git diff --name-status`` output into a short summary
of which skills were added / removed / modified, plus an explicit
"reconciliation required" section when bundles reference removed skills.

CLI:
    git diff --name-status BASE..HEAD | python3 scripts/sync_pr_body.py <tag>
"""
from __future__ import annotations

import os
import sys

SKILLS_REPO = "nq-rdl/agent-skills"


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
        status, path = parts[0], parts[1]
        segs = path.split("/")
        if len(segs) < 2 or segs[0] != "skills":
            continue
        statuses.setdefault(segs[1], set()).add(status[0])

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


def render_pr_body(tag, changes, drift_messages=None, max_chars=60000) -> str:
    added = changes.get("added", [])
    removed = changes.get("removed", [])
    modified = changes.get("modified", [])
    link = f"https://github.com/{SKILLS_REPO}/releases/tag/{tag}"

    parts = [
        f"Automated sync of skill directories from [{SKILLS_REPO}@{tag}]({link}).",
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
    if drift_messages:
        parts += [
            "",
            "### ⚠️ Reconciliation required",
            "Upstream removed skills that bundles still reference. "
            "`validate-bundles` will fail until the registry is reconciled "
            "(retire/trim the bundle, refresh `marketplace.json`):",
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
    changes = classify_skill_changes(sys.stdin.read().splitlines())
    # Drift messages (bundles referencing removed skills) are passed in via the
    # SYNC_DRIFT env var so the workflow can surface them in the PR body.
    drift = [m for m in os.environ.get("SYNC_DRIFT", "").splitlines() if m.strip()]
    print(render_pr_body(tag, changes, drift_messages=drift))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
