# Implementation Plan: #204 SpecKit-side extension recommendation

**Type**: documentation / recommendation (no code).

## Approach

1. Compare `superpowers-bridge` (`superb`) vs `cc-spex` extensions vs the constitution-clause
   baseline against the two friction points (constitution drift, session continuity).
2. Recommend a layered approach consistent with #203 (cc-spex not adopted) and #205 (routing).
3. Deliver a `docs/playbooks/` playbook with target-repo setup steps that `speckit-lifecycle`
   (#124) references.

## Deliverable

- `docs/playbooks/speckit-superpowers-extension.md`.
- No `skills/`/`registry/` changes.

## Edge cases & preconditions

Operational preconditions for the `superb` opt-in layer (verified against
`RbBtSn0w/spec-kit-extensions` `catalog.json` + `superpowers-bridge/extension.yml`):

- **Spec Kit `>=0.12.0` required** — `superb` v1.8.0 declares this minimum; `specify
  extension add superb` fails on older CLIs. Target repos must check `specify --version`
  and upgrade first.
- **Catalog install policy** — the catalog must be registered with `--install-allowed`
  or `extension add` is blocked. Orgs that disallow external catalogs use the release-pin
  fallback (`specify extension add superpowers-bridge --from <release-zip>`).
- **Baseline must stand alone** — the #205 constitution clause + CLAUDE.md routing block
  is the zero-dependency floor for repos that cannot or will not install `superb`; the
  recommendation degrades gracefully to convention-only enforcement.

These are captured here (ephemeral branch record); the durable decision — including these
preconditions — is distilled into an ADR when this branch merges into the epic (#207).

## References

- `RbBtSn0w/spec-kit-extensions` (superpowers-bridge / `superb`); #203; #205; #124.
