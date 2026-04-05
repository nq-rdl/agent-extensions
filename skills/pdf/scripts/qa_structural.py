"""Structural QA checks on merged markdown files.

Complements check_quality.py (which scores raw docling/pymupdf outputs) by
checking the final merged file for content-level issues that indicate extraction
failures or merge artifacts:

  - Section completeness: Abstract, Methods, Results, Discussion, References present?
  - Numeric truncation: scientific notation broken across lines (2.42E-<br>20 patterns)
  - Author line detection: is there a recognisable author list near the top?
  - Table integrity: no Col1/Col2 placeholder headers, no excessive <br> cell breaks

Papers that FAIL are flagged for the extraction-qa-check agent.
Papers that WARN have minor issues worth noting but may not need agent review.

Usage:
    pixi run qa-structural /path/to/project
    pixi run qa-structural /path/to/project --stem wang_y_2024
    pixi run qa-structural /path/to/project --all      # show all, not just flagged
    pixi run qa-structural /path/to/project --json
"""

import json
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table as RichTable

app = typer.Typer(add_completion=False)
err = Console(stderr=True)

# Expected section heading patterns
SECTION_PATTERNS: dict[str, re.Pattern] = {
    "Abstract": re.compile(
        r"^#+\s*(Abstract|A\s*B\s*S\s*T\s*R\s*A\s*C\s*T)", re.IGNORECASE | re.MULTILINE
    ),
    "Methods": re.compile(
        r"^#+\s*(Method|Material|Study Design|Data Collection|Patient|Cohort|Experimental Setup)",
        re.IGNORECASE | re.MULTILINE,
    ),
    "Results": re.compile(
        r"^#+\s*(Result|Finding|Outcome|Performance|Experiment|Evaluation)",
        re.IGNORECASE | re.MULTILINE,
    ),
    "Discussion": re.compile(
        r"^#+\s*(Discussion|Conclusion|Limitation|Implication)",
        re.IGNORECASE | re.MULTILINE,
    ),
    "References": re.compile(
        r"^#+\s*(Reference|Bibliography)", re.IGNORECASE | re.MULTILINE
    ),
}

# Scientific notation broken across a line by a <br> tag
# Example: 2.42E-<br>20  or  1.3e<br>-6
NUMERIC_BREAK_RE = re.compile(r"\d[\d.]*[Ee]-?<br>-?\d+", re.IGNORECASE)

# Heuristic: an author-list line has ≥2 entries matching "Lastname, Initial" or just "Lastname X"
# Looks for ≥2 capital-letter clusters separated by commas or semicolons in first 30 lines
AUTHOR_CLUSTER_RE = re.compile(r"([A-Z][a-z]+[,;]\s+){2,}")

# Col1/Col2/Col3 placeholder inside a table cell
COL_PLACEHOLDER_RE = re.compile(r"\|\s*Col\d+\s*\|")

# Table content line (starts with |)
TABLE_LINE_RE = re.compile(r"^\s*\|")

# Separator row (|---|---| style) — exclude from <br> count
SEP_ROW_RE = re.compile(r"^\s*\|[-:\s|]+\|\s*$")

# Max <br> breaks in table cells before it's flagged as FAIL (not WARN)
BR_FAIL_THRESHOLD = 2


def check_structural(stem: str, project: Path) -> dict:
    """Run structural checks on the merged (or docling fallback) markdown for one stem.

    Returns:
        {
          "stem": str,
          "status": "PASS" | "WARN" | "FAIL" | "ERROR",
          "issues": list[str],        # non-empty if WARN or FAIL
          "md_path": str,             # path of the file checked
        }
    """
    base_dir = project / "data" / "included" / "extracted"

    # Priority: merged > docling fallback
    md_path = base_dir / f"{stem}.md"
    source = "merged"
    if not md_path.exists():
        md_path = base_dir / "docling" / f"{stem}.md"
        source = "docling"
    if not md_path.exists():
        return {
            "stem": stem,
            "status": "ERROR",
            "issues": ["no markdown file found"],
            "md_path": "",
        }

    text = md_path.read_text(encoding="utf-8")
    # Strip the <!-- EXTRACTION: ... --> header comment so it doesn't confuse section checks
    text_clean = re.sub(r"^<!--.*?-->", "", text, flags=re.DOTALL).strip()

    issues: list[str] = []

    # ── 1. Section completeness ──────────────────────────────────────────────
    for section_name, pattern in SECTION_PATTERNS.items():
        if not pattern.search(text_clean):
            issues.append(f"Missing section heading: {section_name}")

    # ── 2. Numeric truncation (scientific notation split by <br>) ────────────
    num_breaks = NUMERIC_BREAK_RE.findall(text_clean)
    if num_breaks:
        issues.append(
            f"Numeric truncation (<br> in scientific notation): "
            f"{len(num_breaks)} occurrence(s), e.g. {num_breaks[0]!r}"
        )

    # ── 3. Author line detection (first 30 lines of cleaned text) ───────────
    first_lines = "\n".join(text_clean.split("\n")[:30])
    if not AUTHOR_CLUSTER_RE.search(first_lines):
        issues.append("No recognisable author list detected in first 30 lines")

    # ── 4. Table integrity ───────────────────────────────────────────────────
    col_placeholders = len(COL_PLACEHOLDER_RE.findall(text_clean))
    if col_placeholders > 0:
        issues.append(
            f"Col1/Col2 placeholder headers: {col_placeholders} occurrence(s)"
        )

    br_in_table_rows = sum(
        1
        for line in text_clean.split("\n")
        if TABLE_LINE_RE.match(line) and not SEP_ROW_RE.match(line) and "<br>" in line
    )
    if br_in_table_rows > BR_FAIL_THRESHOLD:
        issues.append(f"Broken <br> values in table cells: {br_in_table_rows} row(s)")

    # ── Severity classification ──────────────────────────────────────────────
    # FAIL: structural table problems that will corrupt downstream extraction
    fail_conditions = (
        col_placeholders > 0 or num_breaks or br_in_table_rows > BR_FAIL_THRESHOLD
    )
    if fail_conditions:
        status = "FAIL"
    elif issues:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "stem": stem,
        "status": status,
        "issues": issues,
        "md_path": str(md_path),
        "source": source,
    }


def find_stems(project: Path) -> list[str]:
    """Return all stems that have a merged or docling markdown file."""
    base_dir = project / "data" / "included" / "extracted"
    stems: set[str] = set()
    for f in base_dir.glob("*.md"):
        stems.add(f.stem)
    for f in (base_dir / "docling").glob("*.md"):
        stems.add(f.stem)
    return sorted(stems)


@app.command()
def main(
    project: Path = typer.Argument(..., help="Project root directory"),
    stem: str = typer.Option(None, "--stem", help="Check only this stem"),
    show_all: bool = typer.Option(
        False, "--all", "-a", help="Show all, not just flagged"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output QA report JSON to stdout"
    ),
) -> None:
    """Structural QA checks on merged markdown files. Flags papers for agent review."""
    if stem:
        stems = [stem]
    else:
        stems = find_stems(project)

    if not stems:
        err.print("[yellow]No markdown files found.[/yellow]")
        raise typer.Exit(0)

    results: list[dict] = [check_structural(s, project) for s in stems]

    # Display table
    display = results if show_all else [r for r in results if r["status"] != "PASS"]
    if display:
        tbl = RichTable(title="Structural QA Report", show_lines=True)
        tbl.add_column("Stem", style="bold", max_width=30)
        tbl.add_column("Status", justify="center")
        tbl.add_column("Source", justify="center")
        tbl.add_column("Issues")
        for r in display:
            color = {
                "PASS": "green",
                "WARN": "yellow",
                "FAIL": "red",
                "ERROR": "red",
            }.get(r["status"], "white")
            tbl.add_row(
                r["stem"],
                f"[{color}]{r['status']}[/]",
                r.get("source", "—"),
                "\n".join(r["issues"]) or "—",
            )
        err.print(tbl)

    passes = sum(1 for r in results if r["status"] == "PASS")
    warns = sum(1 for r in results if r["status"] == "WARN")
    fails = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    err.print(
        f"\n[bold]PASS:[/bold] {passes}  [bold]WARN:[/bold] {warns}  [bold]FAIL:[/bold] {fails}"
    )

    fail_stems = [r["stem"] for r in results if r["status"] in ("FAIL", "ERROR")]
    if fail_stems:
        err.print(f"\n[red]Flagged for agent QA:[/red] {', '.join(fail_stems)}")
        err.print("  Run: claude --agent extraction-qa-check for each flagged paper")

    if output_json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    app()
