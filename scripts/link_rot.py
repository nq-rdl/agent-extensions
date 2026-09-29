#!/usr/bin/env python3
"""Weekly link-rot monitoring for canonical catalog content (issue #301).

Two subcommands, run by ``.github/workflows/link-rot-check.yml`` through pixi:

``scan``
    Enumerate the canonical inputs (and the report-only assets), verify the
    single effective lychee configuration, run lychee, re-check every
    non-healthy URL in a confirmation pass, probe DNS for connection failures,
    and classify each URL as healthy / broken / unknown / excluded. Writes
    ``observations.json`` (machine-readable) and ``scan-report.md`` (human).
    Exits 1 on an operational failure (tool/config failure, malformed JSON,
    incomplete scan, unexpected zero inputs) after writing what it has.

``track``
    Read ``observations.json`` and reconcile the single ``link-rot`` tracker
    issue: open/update/close/reopen it, apply per-URL suppressions, and keep its
    durable state in a hidden JSON block in the issue body. Refuses to act
    (exit 1, no writes) when the scan was not complete. ``--dry-run`` snapshots
    the tracker through read-only API calls into an in-memory mock and prints
    the planned writes; ``--issues-fixture`` runs entirely offline.

Classification policy (see ``classify``):

* fresh success in any pass, with no 404/410 seen -> healthy (may resolve)
* 404/410 in the main *and* confirmation pass -> broken
* connection failure in both passes and NXDOMAIN on every one of
  ``DNS_LOOKUPS`` lookups, with the control host resolving -> broken
* timeout, refusal/reset, resolver failure, 403/429/5xx, other status codes,
  missing fragments, rejected redirects, inconsistent passes -> unknown
* matched a lychee.toml exclusion -> excluded (a reviewed policy decision)

Only canonical inputs drive the tracker; report-only assets (hooks/*.sh and
skill shell/YAML/JSON/Python files) use lychee's plaintext extraction, which
also finds templated URLs (``$VERSION``), so their results are reported only.

Standard library only (plus the pixi environment's Python); no network access
is needed by the unit tests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# --------------------------------------------------------------------------
# Policy constants. Changing any of these is a reviewed change (tests pin them).
# --------------------------------------------------------------------------

#: lychee version the workflow installs; the config schema is version-specific.
LYCHEE_VERSION = "0.24.2"
#: The single effective configuration (repository policy). Never merged with
#: another --config: lychee 0.24 merges repeated --config files, so the scan
#: passes exactly one and records its digest.
CONFIG_PATH = "lychee.toml"
#: Documented command-line overrides applied on top of CONFIG_PATH.
LYCHEE_OVERRIDES = (
    "--cache=false",          # fresh requests; no .lycheecache is read or written
    "--no-progress",
    "--mode", "plain",
    "--format", "json",
    "--verbose",              # JSON then includes success_map/excluded_map
    "--scheme", "https",      # network scan only; local file:// references
    "--scheme", "http",       # are asctl repo-check's job (#300)
)

CANONICAL_PATTERNS = (
    "skills/**/*.md",
    "skills/**/*.rst",
    "agents/**/*.md",
    "docs/**/*.md",
    "README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
)
REPORT_ONLY_PATTERNS = (
    "hooks/*.sh",
    "skills/**/*.sh",
    "skills/**/*.yaml",
    "skills/**/*.yml",
    "skills/**/*.json",
    "skills/**/*.py",
)
#: A pattern that matches nothing here means the enumeration is wrong
#: ("unexpected zero inputs"). agents/ is optional: the catalog has none today.
REQUIRED_PATTERNS = (
    "skills/**/*.md",
    "skills/**/*.rst",
    "docs/**/*.md",
    "README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
)
#: Generated copies are never scanned for network rot.
EXCLUDED_PREFIXES = ("plugins/", "dist/")

EXTRACTION_LIMITS = (
    "Markdown and reStructuredText use lychee's native extractors; the "
    "extractor reports line/column spans, which are shown as-is (none are invented).",
    "Shell, YAML, JSON and Python assets use lychee's plaintext extraction: "
    "URLs assembled at runtime are missed and templated URLs ($VERSION, $1) are "
    "requested literally, so these results are report-only.",
    "Only http(s) URLs are checked; local file references belong to asctl repo-check.",
)

#: HTTP statuses that can confirm rot. Everything else is unknown.
BROKEN_STATUSES = frozenset({404, 410})
#: Passes (main + confirmation) that must agree before a URL is broken.
CONFIRMATION_PASSES = 2
#: Default wait before the confirmation pass (seconds).
CONFIRM_DELAY_SECONDS = 30
#: NXDOMAIN must be returned by every lookup, spaced DNS_INTERVAL apart.
DNS_LOOKUPS = 3
DNS_INTERVAL_SECONDS = 2.0
#: Must resolve before and after the probes, else the resolver is suspect.
DNS_CONTROL_HOST = "github.com"
#: Fresh healthy observations needed to resolve a tracked finding.
RECOVERY_OBSERVATIONS = 1
#: Resolved findings are kept this long for recurrence history.
RESOLVED_RETENTION_DAYS = 90

OBSERVATIONS_SCHEMA = "link-rot-observations/v1"
STATE_VERSION = 1
LABEL = "link-rot"
LABEL_COLOR = "d93f0b"
LABEL_DESCRIPTION = "Weekly link-rot tracker (link-rot-check.yml, #301)"
TRACKER_TITLE = "Link rot: weekly external link tracker"
TRACKER_MARKER = "<!-- link-rot-tracker -->"
STATE_RE = re.compile(r"<!-- link-rot-state:v(\d+)\n(.*?)\n-->", re.S)
EVENT_RE = re.compile(r"<!-- link-rot-event:([0-9a-f]+) -->")
COMMAND_RE = re.compile(r"^/link-rot[ \t]+(suppress|unsuppress)[ \t]+(\S+)(?:[ \t]+(.*))?$", re.M)
#: Only these comment authors may suppress (GitHub author_association).
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
MAX_BODY_CHARS = 65000  # GitHub's issue body limit is 65536

HEALTHY, BROKEN, UNKNOWN, EXCLUDED, REMOVED = "healthy", "broken", "unknown", "excluded", "removed"


class OperationalError(Exception):
    """The scan or tracker state cannot be trusted; nothing may be closed or reopened."""


# --------------------------------------------------------------------------
# URL identity
# --------------------------------------------------------------------------

_PCT = re.compile(r"%[0-9a-fA-F]{2}")


def normalize_url(raw: str) -> str:
    """Stable per-URL identity used for state, suppression and dedupe.

    Lower-cases scheme and host, drops userinfo (never persisted) and default
    ports, strips a trailing dot from the host, gives an empty path ``/``,
    upper-cases percent-escapes, and drops an empty ``?``/``#``. Path case,
    query and fragment are otherwise kept: fragments are checked by the policy,
    so ``page#a`` and ``page#b`` are different findings.
    """
    text = raw.strip()
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        return text
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.hostname:
        return text
    host = parts.hostname.lower().rstrip(".")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None and (scheme, port) not in (("http", 80), ("https", 443)):
        netloc += f":{port}"
    upper = lambda m: m.group(0).upper()  # noqa: E731
    path = _PCT.sub(upper, parts.path) or "/"
    query = _PCT.sub(upper, parts.query)
    return urlunsplit((scheme, netloc, path, query, parts.fragment))


# --------------------------------------------------------------------------
# Input enumeration
# --------------------------------------------------------------------------

def _match(path: str, pattern: str) -> bool:
    """Glob match where ``**/`` spans zero or more directories and ``*`` does not cross ``/``."""
    regex = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            regex += "(?:[^/]+/)*"
            i += 3
        elif pattern[i] == "*":
            regex += "[^/]*"
            i += 1
        else:
            regex += re.escape(pattern[i])
            i += 1
    return re.fullmatch(regex, path) is not None


def select_inputs(paths: list[str]) -> dict:
    """Split tracked paths into canonical and report-only inputs.

    Returns ``{"canonical": [...], "report_only": [...], "errors": [...]}``;
    an error means the enumeration is not trustworthy.
    """
    canonical, report_only, errors = [], [], []
    seen_patterns = set()
    for path in sorted(set(paths)):
        if path.startswith(EXCLUDED_PREFIXES):
            continue
        hits = [p for p in CANONICAL_PATTERNS if _match(path, p)]
        if hits:
            canonical.append(path)
            seen_patterns.update(hits)
        elif any(_match(path, p) for p in REPORT_ONLY_PATTERNS):
            report_only.append(path)
    for pattern in REQUIRED_PATTERNS:
        if pattern not in seen_patterns:
            errors.append(f"unexpected zero inputs for required pattern {pattern!r}")
    return {"canonical": canonical, "report_only": report_only, "errors": errors}


def tracked_files(root: Path) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise OperationalError(f"git ls-files failed: {exc}") from exc
    return [p for p in out.decode().split("\0") if p]


# --------------------------------------------------------------------------
# lychee report parsing and classification
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Raw:
    """One lychee result for one URL occurrence."""
    kind: str            # ok | excluded | http | timeout | network | fragment | other
    code: int | None = None
    detail: str = ""
    duplicate: bool = False  # lychee's in-run dedupe copy ("... (cached)")

    @property
    def broken_candidate(self) -> bool:
        return self.kind == "http" and self.code in BROKEN_STATUSES

    def label(self) -> str:
        if self.kind == "http":
            return f"http-{self.code}"
        return self.kind


def classify_entry(map_name: str, entry: dict) -> Raw:
    status = entry.get("status") or {}
    text = str(status.get("text", ""))
    details = str(status.get("details", ""))
    code = status.get("code")
    duplicate = text.endswith("(cached)")
    if map_name == "success_map":
        return Raw("ok", code, text, duplicate)
    if map_name == "excluded_map":
        return Raw("excluded", None, details or text, duplicate)
    if map_name == "timeout_map":
        return Raw("timeout", code, details or text, duplicate)
    lowered = f"{text} {details}".lower()
    if "fragment" in lowered:
        return Raw("fragment", code, details or text, duplicate)
    if isinstance(code, int):
        return Raw("http", code, text, duplicate)
    if "timed out" in lowered or "timeout" in lowered:
        return Raw("timeout", None, details or text, duplicate)
    if "network error" in lowered or "connection" in lowered or "dns" in lowered:
        return Raw("network", None, details or text, duplicate)
    return Raw("other", None, details or text, duplicate)


RESULT_MAPS = ("success_map", "error_map", "timeout_map", "excluded_map")


def parse_report(report: object, label: str) -> dict:
    """Group a lychee JSON report by normalized URL.

    Returns ``{url: {"raw": str, "results": [Raw], "sources": [{path, line?, column?}]}}``
    and raises OperationalError when the report is malformed or incomplete.
    """
    if not isinstance(report, dict):
        raise OperationalError(f"{label}: lychee report is not a JSON object")
    missing = [k for k in ("total", *RESULT_MAPS) if k not in report]
    if missing:
        raise OperationalError(f"{label}: lychee report lacks {', '.join(missing)} "
                               "(was it produced with --format json --verbose?)")
    grouped: dict[str, dict] = {}
    count = 0
    for map_name in RESULT_MAPS:
        entries_by_source = report[map_name]
        if not isinstance(entries_by_source, dict):
            raise OperationalError(f"{label}: {map_name} is not an object")
        for source, entries in entries_by_source.items():
            if not isinstance(entries, list):
                raise OperationalError(f"{label}: {map_name}[{source!r}] is not a list")
            for entry in entries:
                count += 1
                if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
                    raise OperationalError(f"{label}: malformed entry in {map_name}[{source!r}]")
                raw_url = entry["url"]
                if urlsplit(raw_url).scheme.lower() not in ("http", "https"):
                    continue  # scheme-filtered local references
                url = normalize_url(raw_url)
                item = grouped.setdefault(url, {"raw": raw_url, "results": [], "sources": []})
                item["results"].append(classify_entry(map_name, entry))
                src = {"path": source}
                span = entry.get("span")
                if isinstance(span, dict) and isinstance(span.get("line"), int):
                    src["line"] = span["line"]
                    if isinstance(span.get("column"), int):
                        src["column"] = span["column"]
                if src not in item["sources"]:
                    item["sources"].append(src)
    if count != report["total"]:
        raise OperationalError(f"{label}: incomplete lychee report: {count} results for "
                               f"total={report['total']}")
    return grouped


def reduce_pass(results: list[Raw]) -> Raw:
    """Collapse one pass's occurrences of a URL into one result.

    In-run dedupe copies only count when no original is present. A success
    beside a failure (lychee reports a missing fragment next to the page's 200)
    yields the failure; disagreeing failures yield ``other``.
    """
    originals = [r for r in results if not r.duplicate] or list(results)
    failures = [r for r in originals if r.kind not in ("ok", "excluded")]
    if not failures:
        if any(r.kind == "excluded" for r in originals):
            return next(r for r in originals if r.kind == "excluded")
        return originals[0]
    kinds = {(r.kind, r.code) for r in failures}
    if len(kinds) == 1:
        return failures[0]
    return Raw("other", None, "inconsistent results: " + ", ".join(sorted(r.label() for r in failures)))


def classify(passes: list[Raw], dns: str | None = None) -> tuple[str, str]:
    """Final state and reason for one URL from its per-pass results.

    ``dns`` is ``nxdomain``, ``resolves`` or ``resolver-error`` (or None when
    not probed). Only agreement across CONFIRMATION_PASSES can prove rot; only
    a fresh success can prove health; everything else is unknown.
    """
    if not passes:
        return UNKNOWN, "not-observed"
    first, last = passes[0], passes[-1]
    if first.kind == "excluded":
        return EXCLUDED, "excluded by lychee.toml"
    if first.kind == "ok":
        return HEALTHY, "ok"
    if len(passes) >= CONFIRMATION_PASSES:
        if all(p.broken_candidate for p in passes):
            return BROKEN, last.label()
        if all(p.kind == "network" for p in passes) and dns == "nxdomain":
            return BROKEN, "nxdomain"
    if last.kind == "ok":
        if any(p.broken_candidate for p in passes):
            return UNKNOWN, "inconsistent: " + " then ".join(p.label() for p in passes)
        return HEALTHY, "ok-on-retry"
    if len(passes) < CONFIRMATION_PASSES and first.broken_candidate:
        return UNKNOWN, f"unconfirmed {first.label()}"
    if last.kind == "network":
        return UNKNOWN, {"resolves": "connection-failure", "resolver-error": "resolver-failure",
                         "nxdomain": "unconfirmed-nxdomain"}.get(dns or "", "connection-failure")
    if last.kind == "fragment":
        return UNKNOWN, "fragment-not-found"
    return UNKNOWN, last.label() if last.kind != "other" else (last.detail or "other")[:120]


def dns_probe(host: str, *, lookups: int = DNS_LOOKUPS, interval: float = DNS_INTERVAL_SECONDS,
              control: str = DNS_CONTROL_HOST, resolver=socket.getaddrinfo,
              sleep=time.sleep) -> str:
    """Return ``nxdomain`` only when every lookup says the name does not exist.

    ``EAI_NONAME`` is the resolver's "no such name" answer; ``EAI_AGAIN`` (and
    anything else) is a resolver failure. The control host must resolve before
    and after, which separates an absent name from a broken resolver.
    """
    def lookup(name):
        try:
            resolver(name, None)
            return "resolves"
        except socket.gaierror as exc:
            return "nxdomain" if exc.errno == socket.EAI_NONAME else "resolver-error"
        except OSError:
            return "resolver-error"

    if lookup(control) != "resolves":
        return "resolver-error"
    answers = []
    for i in range(lookups):
        if i:
            sleep(interval)
        answers.append(lookup(host))
        if answers[-1] != "nxdomain":
            break
    if lookup(control) != "resolves":
        return "resolver-error"
    if len(answers) == lookups and all(a == "nxdomain" for a in answers):
        return "nxdomain"
    return "resolves" if "resolves" in answers else "resolver-error"


def build_observations(main: dict, confirm: dict | None, dns: dict[str, str],
                       inputs: dict) -> list[dict]:
    """Combine the main and confirmation passes into per-URL observations."""
    canonical_inputs = set(inputs["canonical"])
    out = []
    for url in sorted(main):
        item = main[url]
        passes = [reduce_pass(item["results"])]
        if passes[0].kind not in ("ok", "excluded"):
            if confirm is None or url not in confirm:
                raise OperationalError(f"confirmation pass did not observe {url}")
            passes.append(reduce_pass(confirm[url]["results"]))
        host = (urlsplit(url).hostname or "").lower()
        state, reason = classify(passes, dns.get(host))
        out.append({
            "url": url,
            "state": state,
            "reason": reason,
            "canonical": any(s["path"] in canonical_inputs for s in item["sources"]),
            "sources": item["sources"],
            "passes": [p.label() for p in passes],
        })
    return out


# --------------------------------------------------------------------------
# Scan
# --------------------------------------------------------------------------

def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def verify_config(root: Path) -> dict:
    path = root / CONFIG_PATH
    try:
        data = path.read_bytes()
        config = tomllib.loads(data.decode())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise OperationalError(f"cannot read {CONFIG_PATH}: {exc}") from exc
    if config.get("cache") is not False:
        raise OperationalError(f"{CONFIG_PATH} must set cache = false (fresh verification)")
    return {"path": CONFIG_PATH, "sha256": hashlib.sha256(data).hexdigest(),
            "overrides": list(LYCHEE_OVERRIDES)}


def _run(cmd: list[str], cwd: Path, timeout: int = 3600) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OperationalError(f"{cmd[0]} failed to run: {exc}") from exc


def lychee_version(lychee: str, root: Path) -> str:
    result = _run([lychee, "--version"], root, timeout=60)
    match = re.search(r"(\d+\.\d+\.\d+)", result.stdout)
    if result.returncode != 0 or not match:
        raise OperationalError(f"cannot determine lychee version: {result.stderr.strip()}")
    return match.group(1)


def run_lychee_pass(lychee: str, root: Path, inputs_file: Path, output: Path,
                    label: str) -> dict:
    cmd = [lychee, "--config", CONFIG_PATH, *LYCHEE_OVERRIDES,
           "--output", str(output), "--files-from", str(inputs_file)]
    result = _run(cmd, root)
    # 0: all links fine; 2: some links failed. Anything else is a tool/config failure.
    if result.returncode not in (0, 2):
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise OperationalError(f"{label}: lychee exited {result.returncode}: {tail}")
    try:
        return json.loads(output.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise OperationalError(f"{label}: malformed lychee JSON: {exc}") from exc


def verify_lychee_inputs(lychee: str, root: Path, inputs_file: Path, expected: list[str]) -> None:
    """lychee must see exactly the enumerated inputs (no silent skips)."""
    result = _run([lychee, "--config", CONFIG_PATH, "--cache=false", "--dump-inputs",
                   "--files-from", str(inputs_file)], root, timeout=300)
    if result.returncode != 0:
        raise OperationalError(f"lychee --dump-inputs exited {result.returncode}: "
                               f"{result.stderr.strip()[-500:]}")
    seen = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    missing = sorted(set(expected) - seen)
    if missing:
        raise OperationalError(f"lychee did not accept {len(missing)} enumerated inputs, "
                               f"e.g. {missing[:3]}")


def scan(root: Path, out_dir: Path, *, lychee: str = "lychee", confirm_delay: float = CONFIRM_DELAY_SECONDS,
         fixture: Path | None = None, now: str | None = None, prober=dns_probe,
         sleep=time.sleep, expected_version: str = LYCHEE_VERSION) -> dict:
    """Run (or replay from ``fixture``) a complete scan; always returns a document."""
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    doc: dict = {
        "schema": OBSERVATIONS_SCHEMA, "scan_ok": False, "errors": [],
        "observed_at": now or _now(), "lychee_version": None, "config": None,
        "inputs": {"canonical": [], "report_only": []},
        "extraction_limits": list(EXTRACTION_LIMITS),
        "thresholds": {
            "broken_statuses": sorted(BROKEN_STATUSES),
            "confirmation_passes": CONFIRMATION_PASSES,
            "confirm_delay_seconds": confirm_delay,
            "dns_lookups": DNS_LOOKUPS, "dns_interval_seconds": DNS_INTERVAL_SECONDS,
            "dns_control_host": DNS_CONTROL_HOST,
            "recovery_observations": RECOVERY_OBSERVATIONS,
        },
        "cache": "disabled (--cache=false); '(cached)' results are lychee's in-run dedupe "
                 "of a request made in this run",
        "summary": {}, "urls": [],
    }
    try:
        if fixture is not None:
            inputs = json.loads((fixture / "inputs.json").read_text())
            selection = select_inputs(inputs["canonical"] + inputs["report_only"])
            doc["lychee_version"] = "fixture"
            doc["config"] = {"path": str(fixture), "sha256": None, "overrides": list(LYCHEE_OVERRIDES)}
        else:
            doc["config"] = verify_config(root)
            doc["lychee_version"] = lychee_version(lychee, root)
            if doc["lychee_version"] != expected_version:
                raise OperationalError(f"lychee {doc['lychee_version']} found; this policy is "
                                       f"verified against {expected_version}")
            selection = select_inputs(tracked_files(root))
        doc["inputs"] = {"canonical": selection["canonical"], "report_only": selection["report_only"]}
        if selection["errors"]:
            raise OperationalError("; ".join(selection["errors"]))
        all_inputs = selection["canonical"] + selection["report_only"]

        if fixture is not None:
            main_report = json.loads((fixture / "main.json").read_text())
        else:
            inputs_file = out_dir / "inputs.txt"
            inputs_file.write_text("".join(f"{p}\n" for p in all_inputs))
            verify_lychee_inputs(lychee, root, inputs_file, all_inputs)
            main_report = run_lychee_pass(lychee, root, inputs_file, out_dir / "lychee-main.json", "main pass")
        main = parse_report(main_report, "main pass")
        for item in main.values():
            unknown_sources = [s["path"] for s in item["sources"] if s["path"] not in all_inputs]
            if unknown_sources:
                raise OperationalError(f"lychee reported a source outside the enumerated inputs: "
                                       f"{unknown_sources[0]}")

        retry = [u for u, item in main.items() if reduce_pass(item["results"]).kind not in ("ok", "excluded")]
        confirm = {}
        if retry:
            if fixture is not None:
                confirm_report = json.loads((fixture / "confirm.json").read_text())
            else:
                sleep(confirm_delay)
                confirm_file = out_dir / "confirm-inputs.md"
                confirm_file.write_text("".join(f"<{main[u]['raw']}>\n" for u in retry))
                list_file = out_dir / "confirm-inputs.txt"
                list_file.write_text(f"{confirm_file}\n")
                confirm_report = run_lychee_pass(lychee, root, list_file,
                                                 out_dir / "lychee-confirm.json", "confirmation pass")
            confirm = parse_report(confirm_report, "confirmation pass")

        dns: dict[str, str] = {}
        if fixture is not None and (fixture / "dns.json").exists():
            dns = json.loads((fixture / "dns.json").read_text())
        else:
            for url in retry:
                both = [reduce_pass(main[url]["results"])]
                if url in confirm:
                    both.append(reduce_pass(confirm[url]["results"]))
                host = (urlsplit(url).hostname or "").lower()
                if host and host not in dns and all(p.kind == "network" for p in both) \
                        and len(both) >= CONFIRMATION_PASSES:
                    dns[host] = prober(host)
        doc["dns"] = dns
        doc["urls"] = build_observations(main, confirm, dns, selection)
        doc["scan_ok"] = True
    except (OperationalError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        doc["errors"].append(str(exc) if isinstance(exc, OperationalError) else f"{type(exc).__name__}: {exc}")
    doc["summary"] = summarize(doc["urls"])
    return doc


def summarize(urls: list[dict]) -> dict:
    summary: dict = {}
    for scope in ("canonical", "report_only"):
        counts = {s: 0 for s in (HEALTHY, BROKEN, UNKNOWN, EXCLUDED)}
        for obs in urls:
            if obs["canonical"] == (scope == "canonical"):
                counts[obs["state"]] += 1
        summary[scope] = counts
    return summary


# --------------------------------------------------------------------------
# Tracker state and lifecycle
# --------------------------------------------------------------------------

def empty_state() -> dict:
    return {"version": STATE_VERSION, "findings": {}, "suppressions": {},
            "acknowledged_closed_at": None, "last_comment_id": 0, "last_scan": None}


def parse_state(body: str | None) -> dict:
    match = STATE_RE.search(body or "")
    if not match:
        raise OperationalError("tracker body has no link-rot-state block")
    if int(match.group(1)) != STATE_VERSION:
        raise OperationalError(f"unsupported link-rot-state version {match.group(1)}")
    try:
        state = json.loads(match.group(2))
    except json.JSONDecodeError as exc:
        raise OperationalError(f"malformed link-rot-state JSON: {exc}") from exc
    if not isinstance(state, dict) or not isinstance(state.get("findings"), dict) \
            or not isinstance(state.get("suppressions"), dict):
        raise OperationalError("link-rot-state lacks findings/suppressions")
    base = empty_state()
    base.update(state)
    return base


def dump_state(state: dict) -> str:
    # '<' and '>' only occur inside JSON strings, so escaping them keeps the
    # HTML comment intact whatever URLs or reasons contain.
    text = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e")


def state_digest(state: dict | None) -> str:
    if state is None:
        return "none"
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:16]


def clean_text(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text.replace("`", "'")).strip()
    return text[:limit]


@dataclass
class Plan:
    state: dict
    actions: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _reportable(state: dict) -> set[str]:
    return {u for u, f in state["findings"].items()
            if f["status"] == "active" and u not in state["suppressions"]}


def _days_between(a: str, b: str) -> float:
    parse = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return (parse(b) - parse(a)).total_seconds() / 86400


def apply_commands(state: dict, comments: list[dict], notes: list[str]) -> None:
    """Process ``/link-rot suppress|unsuppress`` comments once each, in id order."""
    for comment in sorted(comments, key=lambda c: c["id"]):
        # Only command comments advance the cursor, so ordinary discussion
        # (and this workflow's own comments) never changes the stored state.
        if comment["id"] <= state["last_comment_id"] or not COMMAND_RE.search(comment.get("body") or ""):
            continue
        state["last_comment_id"] = comment["id"]
        author = (comment.get("user") or {}).get("login", "?")
        if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
            notes.append(f"ignored command from @{author} ({comment.get('author_association')})")
            continue
        for verb, target, reason in COMMAND_RE.findall(comment.get("body") or ""):
            if verb == "unsuppress":
                if target == "all":
                    state["suppressions"].clear()
                else:
                    state["suppressions"].pop(normalize_url(target), None)
                continue
            reason = clean_text(reason or "")
            if not reason:
                notes.append(f"ignored suppress of {target} by @{author}: a reason is required")
                continue
            state["suppressions"][normalize_url(target)] = {
                "reason": reason, "by": author, "at": comment.get("created_at"), "source": "comment"}


def plan_tracker(obs_doc: dict, tracker: dict | None, comments: list[dict], now: str,
                 run_url: str | None = None) -> Plan:
    """Pure lifecycle: previous tracker state + observations -> new state + actions.

    ``tracker`` is None or ``{number, state, body, user, closed_by, closed_at}``.
    """
    if not obs_doc.get("scan_ok"):
        raise OperationalError("scan incomplete; tracker left untouched: "
                               + "; ".join(obs_doc.get("errors") or ["unknown error"]))
    prev = parse_state(tracker["body"]) if tracker else None
    state = json.loads(json.dumps(prev)) if prev else empty_state()
    plan = Plan(state)
    prev_reportable = _reportable(prev) if prev else set()
    observed = {o["url"]: o for o in obs_doc["urls"] if o["canonical"]}
    scanned_at = obs_doc["observed_at"]

    if tracker:
        apply_commands(state, comments, plan.notes)
        bot = (tracker.get("user") or {}).get("login")
        closer = (tracker.get("closed_by") or {}).get("login")
        if tracker["state"] == "closed" and closer != bot \
                and tracker.get("closed_at") != state["acknowledged_closed_at"]:
            # Human closure dismisses exactly the findings reported at that time.
            for url in sorted(_reportable(state)):
                state["suppressions"][url] = {
                    "reason": f"tracker #{tracker['number']} closed by @{closer or 'unknown'}",
                    "by": closer or "unknown", "at": tracker.get("closed_at"), "source": "closure"}
            state["acknowledged_closed_at"] = tracker.get("closed_at")
            plan.notes.append(f"tracker closed by @{closer}: active findings suppressed")

    findings = state["findings"]
    resolved_now = []
    for url, finding in findings.items():
        if finding["status"] != "active":
            continue
        obs = observed.get(url)
        if obs is None:
            outcome = REMOVED
        else:
            finding["last_observed"] = scanned_at
            finding["last_observed_state"] = obs["state"]
            finding["last_reason"] = obs["reason"]
            finding["sources"] = obs["sources"][:10]
            outcome = obs["state"]
        # Consecutive fresh successes; anything else restarts the count.
        finding["healthy_streak"] = finding.get("healthy_streak", 0) + 1 if outcome == HEALTHY else 0
        if outcome == BROKEN:
            finding["last_confirmed_broken"] = scanned_at
        if outcome in (REMOVED, EXCLUDED) or \
                (outcome == HEALTHY and finding["healthy_streak"] >= RECOVERY_OBSERVATIONS):
            finding.update(status="resolved", resolved_at=scanned_at,
                           resolution={HEALTHY: "healthy", REMOVED: "removed from canonical inputs",
                                       EXCLUDED: "excluded by lychee.toml"}[outcome])
            if outcome == REMOVED:
                finding["last_observed_state"] = REMOVED
            resolved_now.append(url)
        # UNKNOWN keeps the finding active: it cannot prove recovery.

    for url, obs in observed.items():
        if obs["state"] != BROKEN:
            continue
        finding = findings.get(url)
        if finding and finding["status"] == "active":
            continue
        record = {"status": "active", "first_seen": scanned_at, "last_confirmed_broken": scanned_at,
                  "last_observed": scanned_at, "last_observed_state": BROKEN,
                  "last_reason": obs["reason"], "sources": obs["sources"][:10],
                  "recurrences": 0, "healthy_streak": 0}
        if finding:  # resolved earlier: this is a recurrence
            record["first_seen"] = finding.get("first_seen", scanned_at)
            record["recurrences"] = finding.get("recurrences", 0) + 1
            record["previously_resolved_at"] = finding.get("resolved_at")
        findings[url] = record

    # Suppression reset: a confirmed recovery or removal ends a suppression, so a
    # later recurrence is reported again.
    for url in list(state["suppressions"]):
        obs = observed.get(url)
        if url in resolved_now or (obs and obs["state"] == HEALTHY) or \
                (obs is None and url in findings):
            state["suppressions"].pop(url)

    for url in [u for u, f in findings.items() if f["status"] == "resolved"
                and _days_between(f.get("resolved_at", scanned_at), scanned_at) > RESOLVED_RETENTION_DAYS]:
        del findings[url]

    state["last_scan"] = {"observed_at": scanned_at, "run_url": run_url,
                          "summary": obs_doc.get("summary", {})}
    reportable = _reportable(state)
    new = sorted(reportable - prev_reportable)
    digest = state_digest(prev)
    body = render_body(state, obs_doc)

    if not tracker:
        if reportable:
            plan.actions.append({"op": "ensure_label"})
            plan.actions.append({"op": "create", "title": TRACKER_TITLE, "body": body, "urls": new})
        return plan

    # Transitions and comments first, state last: if a run dies part-way, the
    # stored state is still the previous one, so the rerun plans the same events
    # and the comment keys (derived from that state) suppress duplicates.
    number = tracker["number"]
    if tracker["state"] == "open":
        if not reportable:
            plan.actions.append(_comment(number, "close", resolved_now, digest,
                                         close_comment(state, resolved_now, prev_reportable)))
            plan.actions.append({"op": "close", "number": number})
        elif new:
            plan.actions.append(_comment(number, "findings", new, digest, findings_comment(state, new, False)))
    elif new:
        plan.actions.append({"op": "reopen", "number": number})
        plan.actions.append(_comment(number, "findings", new, digest, findings_comment(state, new, True)))
    if body != tracker["body"]:
        plan.actions.append({"op": "edit_body", "number": number, "body": body})
    return plan


def _comment(number: int, event: str, urls: list[str], digest: str, text: str) -> dict:
    key = hashlib.sha256(json.dumps([event, sorted(urls), digest]).encode()).hexdigest()[:16]
    return {"op": "comment", "number": number, "key": key,
            "body": f"<!-- link-rot-event:{key} -->\n{text}"}


def _code(url: str) -> str:
    return f"`{url.replace('`', '%60')}`"


def _sources(sources: list[dict], limit: int = 3) -> str:
    parts = []
    for s in sources[:limit]:
        loc = s["path"] + (f":{s['line']}" if "line" in s else "")
        parts.append(f"`{loc}`")
    if len(sources) > limit:
        parts.append(f"(+{len(sources) - limit} more)")
    return ", ".join(parts) or "—"


def findings_comment(state: dict, urls: list[str], reopening: bool) -> str:
    head = ("Reopening: the weekly scan confirmed broken link(s) that are not suppressed."
            if reopening else "The weekly scan confirmed new broken link(s).")
    lines = [head, ""]
    for url in urls:
        f = state["findings"][url]
        extra = ""
        if f.get("recurrences"):
            extra = f" — recurred (previously resolved {f.get('previously_resolved_at')})"
        lines.append(f"- {_code(url)} — {f['last_reason']} — {_sources(f['sources'])}{extra}")
    if state["suppressions"]:
        lines += ["", f"{len(state['suppressions'])} suppressed URL(s) stay suppressed."]
    return "\n".join(lines)


def close_comment(state: dict, resolved: list[str], prev_reportable: set[str]) -> str:
    lines = ["Every tracked finding is resolved or suppressed after a complete scan; closing.", ""]
    for url in sorted(resolved):
        lines.append(f"- {_code(url)} — {state['findings'][url]['resolution']}")
    newly_suppressed = sorted(prev_reportable & set(state["suppressions"]))
    for url in newly_suppressed:
        lines.append(f"- {_code(url)} — suppressed: {state['suppressions'][url]['reason']}")
    return "\n".join(lines)


def render_body(state: dict, obs_doc: dict) -> str:
    findings = state["findings"]
    active = sorted(u for u, f in findings.items() if f["status"] == "active" and u not in state["suppressions"])
    suppressed = sorted(state["suppressions"])
    resolved = sorted((u for u, f in findings.items() if f["status"] == "resolved"),
                      key=lambda u: findings[u].get("resolved_at", ""), reverse=True)
    summary = obs_doc.get("summary", {}).get("canonical", {})
    last = state.get("last_scan") or {}
    run = f" ([run]({last['run_url']}))" if last.get("run_url") else ""

    def table(header, rows):
        if not rows:
            return ["_None._"]
        return [header, "|" + "---|" * (header.count("|") - 1), *rows]

    out = [
        TRACKER_MARKER,
        ("Maintained by the **Link rot check** workflow (`.github/workflows/link-rot-check.yml`, "
         "#301). It tracks only confirmed rot in canonical content: HTTP 404/410 in two passes, or "
         "NXDOMAIN on every DNS lookup. Timeouts, refusals, 403/429, 5xx and other ambiguous "
         "results are *unknown*: they appear in the run report and never open, close or resolve "
         "anything here."),
        "",
        f"Last complete scan: {last.get('observed_at', '—')}{run} — canonical URLs: "
        + ", ".join(f"{k} {v}" for k, v in summary.items()),
        "",
        f"### Active findings ({len(active)})",
        *table("| URL | Last observation | Sources | First seen | Last confirmed broken |", [
            f"| {_code(u)} | {findings[u]['last_observed_state']} ({findings[u]['last_reason']}) | "
            f"{_sources(findings[u]['sources'])} | {findings[u]['first_seen']} | "
            f"{findings[u]['last_confirmed_broken']} |" for u in active]),
        "",
        f"### Suppressed ({len(suppressed)})",
        *table("| URL | Reason | By | Since | Last observation |", [
            f"| {_code(u)} | {state['suppressions'][u]['reason']} | @{state['suppressions'][u]['by']} | "
            f"{state['suppressions'][u].get('at') or '—'} | "
            f"{findings.get(u, {}).get('last_observed_state', '—')} |" for u in suppressed]),
        "",
        f"### Resolved in the last {RESOLVED_RETENTION_DAYS} days ({len(resolved)})",
        *table("| URL | Resolution | Resolved | Recurrences |", [
            f"| {_code(u)} | {findings[u]['resolution']} | {findings[u]['resolved_at']} | "
            f"{findings[u].get('recurrences', 0)} |" for u in resolved]),
        "",
        "### Commands",
        "Maintainers (owner/member/collaborator) can comment:",
        "",
        ("- `/link-rot suppress <url> <reason>` — stop reporting one URL; the reason is required. "
         "A suppression ends when the URL is confirmed healthy or removed."),
        "- `/link-rot unsuppress <url>` or `/link-rot unsuppress all`",
        "",
        ("Closing this issue by hand suppresses every finding listed as active at that moment. "
         "A new broken URL reopens it; suppressed ones stay suppressed. Do not edit the state "
         "block below."),
        "",
        f"<!-- link-rot-state:v{STATE_VERSION}\n{dump_state(state)}\n-->",
    ]
    body = "\n".join(out)
    if len(body) > MAX_BODY_CHARS:
        body = "\n".join([*out[:4], "", "_Report truncated: see the workflow run report._", "", out[-1]])
    if len(body) > MAX_BODY_CHARS:
        raise OperationalError("tracker state exceeds the GitHub issue body limit")
    return body


# --------------------------------------------------------------------------
# Issue stores
# --------------------------------------------------------------------------

class MockIssues:
    """In-memory issue store (fixtures, tests, dry-run). Records every write."""

    def __init__(self, data: dict, actor: str = "github-actions[bot]"):
        self.data = data
        self.data.setdefault("issues", [])
        self.data.setdefault("labels", [])
        self.actor = actor
        self.writes: list[dict] = []

    def _issue(self, number):
        return next(i for i in self.data["issues"] if i["number"] == number)

    def trackers(self) -> list[dict]:
        return sorted((i for i in self.data["issues"]
                       if LABEL in i.get("labels", []) and TRACKER_MARKER in (i.get("body") or "")),
                      key=lambda i: i["number"])

    def comments(self, number: int) -> list[dict]:
        return list(self._issue(number).get("comments", []))

    def ensure_label(self):
        if LABEL not in self.data["labels"]:
            self.data["labels"].append(LABEL)
            self.writes.append({"op": "create_label", "name": LABEL})

    def create(self, title: str, body: str) -> dict:
        number = max([i["number"] for i in self.data["issues"]] + [0]) + 1
        issue = {"number": number, "title": title, "body": body, "state": "open",
                 "labels": [LABEL], "user": {"login": self.actor}, "closed_by": None,
                 "closed_at": None, "comments": []}
        self.data["issues"].append(issue)
        self.writes.append({"op": "create", "number": number, "title": title})
        return issue

    def edit_body(self, number: int, body: str):
        self._issue(number)["body"] = body
        self.writes.append({"op": "edit_body", "number": number})

    def set_state(self, number: int, state: str, now: str):
        issue = self._issue(number)
        issue["state"] = state
        issue["closed_by"] = {"login": self.actor} if state == "closed" else None
        issue["closed_at"] = now if state == "closed" else None
        self.writes.append({"op": "close" if state == "closed" else "reopen", "number": number})

    def comment(self, number: int, body: str):
        issue = self._issue(number)
        next_id = max([c["id"] for i in self.data["issues"] for c in i.get("comments", [])] + [0]) + 1
        issue.setdefault("comments", []).append({
            "id": next_id, "body": body, "user": {"login": self.actor},
            "author_association": "NONE", "created_at": None})
        self.writes.append({"op": "comment", "number": number})


class GitHubIssues:
    """REST access through ``gh api`` (GH_TOKEN / GH_REPO from the environment)."""

    def __init__(self, repo: str):
        self.repo = repo

    def _api(self, method: str, path: str, payload: dict | None = None, paginate: bool = False):
        cmd = ["gh", "api", "-X", method, f"repos/{self.repo}/{path}"]
        if paginate:
            cmd += ["--paginate", "--slurp"]
        if payload is not None:
            cmd += ["--input", "-"]
        try:
            result = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                                    capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            raise OperationalError(f"gh api {method} {path}: {exc}") from exc
        if result.returncode != 0:
            raise OperationalError(f"gh api {method} {path} failed: {result.stderr.strip()[-300:]}")
        data = json.loads(result.stdout or "null")
        if paginate:
            data = [item for page in data for item in page]
        return data

    def trackers(self) -> list[dict]:
        issues = self._api("GET", f"issues?state=all&labels={LABEL}&per_page=100", paginate=True)
        found = []
        for i in sorted(issues, key=lambda i: i["number"]):
            if i.get("pull_request") is None and TRACKER_MARKER in (i.get("body") or ""):
                full = self._api("GET", f"issues/{i['number']}")  # list omits closed_by
                found.append({"number": full["number"], "title": full["title"], "body": full["body"] or "",
                              "state": full["state"], "labels": [l["name"] for l in full["labels"]],
                              "user": {"login": full["user"]["login"]},
                              "closed_by": {"login": full["closed_by"]["login"]} if full.get("closed_by") else None,
                              "closed_at": full.get("closed_at")})
        return found

    def comments(self, number: int) -> list[dict]:
        return [{"id": c["id"], "body": c.get("body") or "", "user": {"login": c["user"]["login"]},
                 "author_association": c.get("author_association"), "created_at": c.get("created_at")}
                for c in self._api("GET", f"issues/{number}/comments?per_page=100", paginate=True)]

    def ensure_label(self):
        labels = self._api("GET", "labels?per_page=100", paginate=True)
        if not any(l["name"] == LABEL for l in labels):
            self._api("POST", "labels", {"name": LABEL, "color": LABEL_COLOR,
                                         "description": LABEL_DESCRIPTION})

    def create(self, title: str, body: str) -> dict:
        issue = self._api("POST", "issues", {"title": title, "body": body, "labels": [LABEL]})
        return {"number": issue["number"]}

    def edit_body(self, number: int, body: str):
        self._api("PATCH", f"issues/{number}", {"body": body})

    def set_state(self, number: int, state: str, now: str):
        payload = {"state": state}
        if state == "closed":
            payload["state_reason"] = "completed"
        self._api("PATCH", f"issues/{number}", payload)

    def comment(self, number: int, body: str):
        self._api("POST", f"issues/{number}/comments", {"body": body})


def snapshot(store: GitHubIssues) -> MockIssues:
    """Read-only copy of the live tracker(s) for a dry run."""
    issues = store.trackers()
    for issue in issues:
        issue["comments"] = store.comments(issue["number"])
    return MockIssues({"issues": issues, "labels": [LABEL]})


def track(obs_doc: dict, store, now: str, run_url: str | None = None) -> tuple[Plan, list[dict]]:
    """Plan against the store's current tracker and apply the plan. Returns (plan, applied)."""
    if obs_doc.get("schema") != OBSERVATIONS_SCHEMA:
        raise OperationalError(f"unexpected observations schema {obs_doc.get('schema')!r}")
    trackers = store.trackers()
    tracker = trackers[0] if trackers else None
    comments = store.comments(tracker["number"]) if tracker else []
    plan = plan_tracker(obs_doc, tracker, comments, now, run_url)
    applied = []
    for dup in trackers[1:]:  # keep one tracker: the lowest-numbered one
        if dup["state"] == "open":
            plan.actions.append(_comment(dup["number"], "duplicate", [str(tracker["number"])], "",
                                         f"Duplicate of #{tracker['number']}, the canonical link-rot "
                                         "tracker. Closed by the link-rot check."))
            plan.actions.append({"op": "close", "number": dup["number"]})
    posted = {n: {m for c in store.comments(n) for m in EVENT_RE.findall(c["body"])}
              for n in {a["number"] for a in plan.actions if a["op"] == "comment"}}
    for action in plan.actions:
        op = action["op"]
        if op == "ensure_label":
            store.ensure_label()
        elif op == "create":
            action["number"] = store.create(action["title"], action["body"])["number"]
        elif op == "edit_body":
            store.edit_body(action["number"], action["body"])
        elif op == "comment":
            if action["key"] in posted[action["number"]]:
                continue  # already posted (e.g. an earlier run failed after commenting)
            store.comment(action["number"], action["body"])
        elif op in ("close", "reopen"):
            store.set_state(action["number"], "closed" if op == "close" else "open", now)
        applied.append({k: v for k, v in action.items() if k != "body"})
    return plan, applied


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------

def render_report(doc: dict, plan: Plan | None = None, applied: list[dict] | None = None,
                  dry_run: bool = False) -> str:
    lines = ["# Link rot report", ""]
    if not doc.get("scan_ok"):
        lines += [("**Operational failure — the scan is incomplete. The tracker issue was not "
                   "changed.**"), ""] +[f"- {e}" for e in doc.get("errors", [])] + [""]
    lines += [f"Observed at {doc.get('observed_at')} with lychee {doc.get('lychee_version')}; "
              f"config `{(doc.get('config') or {}).get('path')}` "
              f"(sha256 `{((doc.get('config') or {}).get('sha256') or '—')[:12]}`), "
              f"cache: {doc.get('cache')}.", "",
              f"Inputs: {len(doc['inputs']['canonical'])} canonical, "
              f"{len(doc['inputs']['report_only'])} report-only.", ""]
    for scope, counts in doc.get("summary", {}).items():
        lines.append(f"- {scope}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    state = plan.state if plan else None
    for scope, title in ((True, "Canonical"), (False, "Report-only (never tracked)")):
        for wanted in (BROKEN, UNKNOWN):
            rows = [o for o in doc.get("urls", []) if o["canonical"] == scope and o["state"] == wanted]
            if not rows:
                continue
            lines += ["", f"## {title}: {wanted} ({len(rows)})", "",
                      "| URL | Reason | Passes | Sources | Last confirmed state |",
                      "|---|---|---|---|---|"]
            for o in rows:
                confirmed = "—"
                if state and o["url"] in state["findings"]:
                    f = state["findings"][o["url"]]
                    confirmed = (f"broken {f.get('last_confirmed_broken')}" if f["status"] == "active"
                                 else f"{f.get('resolution')} {f.get('resolved_at')}")
                lines.append(f"| {_code(o['url'])} | {o['reason']} | {' / '.join(o['passes'])} | "
                             f"{_sources(o['sources'])} | {confirmed} |")
    lines += ["", "## Extraction limits", ""] + [f"- {x}" for x in doc.get("extraction_limits", [])]
    if plan is not None:
        verb = "Planned (dry run, nothing written)" if dry_run else "Applied"
        lines += ["", f"## Tracker: {verb}", ""]
        lines += [f"- {a['op']}" + (f" #{a['number']}" if a.get("number") else "")
                  + (f" ({', '.join(a['urls'])})" if a.get("urls") else "") for a in applied or []] \
            or ["- no changes"]
        lines += [f"- note: {n}" for n in plan.notes]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _emit(text: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="run lychee and classify observations")
    s.add_argument("--root", type=Path, default=Path("."))
    s.add_argument("--out-dir", type=Path, required=True)
    s.add_argument("--lychee", default="lychee")
    s.add_argument("--confirm-delay", type=float, default=CONFIRM_DELAY_SECONDS)
    s.add_argument("--fixture", type=Path, help="replay inputs.json/main.json/confirm.json/dns.json")
    s.add_argument("--now", help="observation timestamp (tests)")
    t = sub.add_parser("track", help="reconcile the link-rot tracker issue")
    t.add_argument("--observations", type=Path, required=True)
    t.add_argument("--out-dir", type=Path)
    t.add_argument("--repo", default=os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY"))
    t.add_argument("--dry-run", action="store_true",
                   help="snapshot the tracker read-only and print planned writes")
    t.add_argument("--issues-fixture", type=Path, help="offline mock issue store (JSON)")
    t.add_argument("--save-fixture", action="store_true",
                   help="write the mock store back (repeat-run testing; not with --dry-run)")
    t.add_argument("--now")
    args = parser.parse_args(argv)

    if args.command == "scan":
        doc = scan(args.root.resolve(), args.out_dir, lychee=args.lychee,
                   confirm_delay=args.confirm_delay, fixture=args.fixture, now=args.now)
        (args.out_dir / "observations.json").write_text(json.dumps(doc, indent=1) + "\n")
        report = render_report(doc)
        (args.out_dir / "scan-report.md").write_text(report)
        _emit(report)
        if not doc["scan_ok"]:
            for err in doc["errors"]:
                print(f"::error::link-rot scan: {err}", file=sys.stderr)
            return 1
        return 0

    now = args.now or _now()
    try:
        doc = json.loads(args.observations.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error::cannot read observations: {exc}", file=sys.stderr)
        return 1
    fixture_data = None
    if args.issues_fixture:
        fixture_data = json.loads(args.issues_fixture.read_text())
        store = MockIssues(fixture_data)
    elif args.repo:
        live = GitHubIssues(args.repo)
        try:
            store = snapshot(live) if args.dry_run else live
        except OperationalError as exc:
            print(f"::error::{exc}", file=sys.stderr)
            return 1
    else:
        print("::error::--repo (or GH_REPO) or --issues-fixture is required", file=sys.stderr)
        return 1
    run_url = None
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    try:
        plan, applied = track(doc, store, now, run_url)
    except OperationalError as exc:
        _emit(render_report(doc) if doc.get("schema") == OBSERVATIONS_SCHEMA else "")
        print(f"::error::link-rot track: {exc}", file=sys.stderr)
        return 1
    report = render_report(doc, plan, applied, dry_run=args.dry_run)
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / ("tracker-plan.md" if args.dry_run else "tracker-report.md")).write_text(report)
    _emit(report)
    if fixture_data is not None and args.save_fixture and not args.dry_run:
        args.issues_fixture.write_text(json.dumps(fixture_data, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
