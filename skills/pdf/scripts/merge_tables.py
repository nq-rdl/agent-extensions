"""Merge docling + pymupdf extractions for unmerged papers.

Takes docling as the base (better table structure), then:
  1. Collapses consecutive duplicate separator rows (|---|---| repeated back-to-back)
  2. Flags tables with Col1/Col2 placeholder headers (need agent fix)
  3. Flags possible missing row-group labels (pymupdf has ≥30% more table rows than docling)
  4. Writes merged file with <!-- EXTRACTION: merged ... --> header comment

Returns {"status": "DONE"|"NEEDS_AGENT"|"ERROR", "stem": ..., "issues": [...]}

Usage:
    pixi run merge-tables /path/to/project
    pixi run merge-tables /path/to/project --stem wang_y_2024
    pixi run merge-tables /path/to/project --stem wang_y_2024 --dry-run
    pixi run merge-tables /path/to/project --json
"""

import json
import re
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(add_completion=False)
err = Console(stderr=True)

# Separator row: |---|---| or |:--|:--| or |:---:|---| etc.
SEP_ROW_RE = re.compile(r"^\s*\|[-:\s|]+\|\s*$")

# Col1/Col2/Col3 placeholder header inside a table cell
COL_PLACEHOLDER_RE = re.compile(r"\|\s*Col\d+\s*\|")


def merge_paper(stem: str, project: Path, dry_run: bool = False) -> dict:
    """Merge docling + pymupdf extractions for one stem.

    Returns dict with keys:
        status  — "DONE", "NEEDS_AGENT", or "ERROR"
        stem    — paper stem
        issues  — list of issue strings (empty = clean merge)
        output  — path to written merged file (absent if ERROR or dry_run)
        collapsed_separators  — count of duplicate separator rows removed
    """
    base_dir = project / "data" / "included" / "extracted"
    docling_path = base_dir / "docling" / f"{stem}.md"
    pymupdf_path = base_dir / "pymupdf" / f"{stem}.md"
    out_path = base_dir / f"{stem}.md"

    if not docling_path.exists():
        return {"status": "ERROR", "stem": stem, "issues": ["no docling file found"]}

    docling_text = docling_path.read_text(encoding="utf-8")
    pymupdf_text = (
        pymupdf_path.read_text(encoding="utf-8") if pymupdf_path.exists() else ""
    )

    issues: list[str] = []
    needs_agent = False

    # Step 1: Collapse consecutive duplicate separator rows
    merged_text, n_collapsed = _collapse_duplicate_separators(docling_text)
    collapsed_note = f"{n_collapsed} row(s)" if n_collapsed else "none"

    # Step 2: Detect Col1/Col2 placeholder headers
    placeholders = len(COL_PLACEHOLDER_RE.findall(merged_text))
    if placeholders > 0:
        issues.append(
            f"Col1/Col2 placeholders in {placeholders} location(s) — needs agent"
        )
        needs_agent = True

    # Step 3: Detect possible missing row-group labels
    flagged_tables = _detect_missing_row_groups(merged_text, pymupdf_text)
    label_note = f"{flagged_tables} table(s)" if flagged_tables else "none"
    if flagged_tables:
        issues.append(
            f"{flagged_tables} table(s) may be missing row-group labels — needs agent"
        )
        needs_agent = True

    status = "NEEDS_AGENT" if needs_agent else "DONE"

    # Build header comment matching the format used in existing merged files
    issues_str = (
        "; ".join(issues) if issues else "Clean merge — no structural issues found."
    )
    header = (
        f"<!-- EXTRACTION: merged (docling base + structural fixes)\n"
        f"     Duplicate headers collapsed: {collapsed_note}\n"
        f"     Row-group labels restored from pymupdf: {label_note}\n"
        f"     Manual review needed: {'yes — run extraction-qa-check agent' if needs_agent else 'none'}\n"
        f"     Notes: {issues_str} -->"
    )

    out_content = header + "\n\n" + merged_text

    if not dry_run:
        out_path.write_text(out_content, encoding="utf-8")

    return {
        "status": status,
        "stem": stem,
        "issues": issues,
        "output": str(out_path),
        "collapsed_separators": n_collapsed,
    }


def _collapse_duplicate_separators(text: str) -> tuple[str, int]:
    """Remove back-to-back duplicate separator rows from markdown tables.

    A duplicate separator looks like:
        | Header |
        |--------|
        |--------|   <- this one is removed
        | data   |
    """
    lines = text.split("\n")
    result: list[str] = []
    n_removed = 0
    prev_is_sep = False

    for line in lines:
        is_sep = bool(SEP_ROW_RE.match(line))
        if is_sep and prev_is_sep:
            n_removed += 1  # skip duplicate
        else:
            result.append(line)
        prev_is_sep = is_sep

    return "\n".join(result), n_removed


def _count_table_rows(text: str) -> int:
    """Count total non-separator table rows across all tables."""
    count = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and "|" in stripped[1:]:
            if not SEP_ROW_RE.match(line):
                count += 1
    return count


def _detect_missing_row_groups(docling_text: str, pymupdf_text: str) -> int:
    """Flag if pymupdf has ≥30% more table rows than docling.

    A large discrepancy suggests docling merged some row-group label rows
    into adjacent cells (collapsing them), while pymupdf preserved them.
    Returns 1 if flagged (coarse heuristic), 0 otherwise.
    """
    if not pymupdf_text:
        return 0
    dc_rows = _count_table_rows(docling_text)
    pm_rows = _count_table_rows(pymupdf_text)
    if dc_rows > 0 and pm_rows > dc_rows * 1.3:
        return 1
    return 0


def find_unmerged_stems(project: Path) -> list[str]:
    """Find stems that have a docling file but no merged output file."""
    base_dir = project / "data" / "included" / "extracted"
    merged_stems = {p.stem for p in base_dir.glob("*.md")}
    docling_stems = {p.stem for p in (base_dir / "docling").glob("*.md")}
    return sorted(docling_stems - merged_stems)


@app.command()
def main(
    project: Path = typer.Argument(..., help="Project root directory"),
    stem: str = typer.Option(None, "--stem", help="Process only this stem"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be written without writing"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output results JSON to stdout"
    ),
) -> None:
    """Merge docling + pymupdf extractions for unmerged papers."""
    if stem:
        stems = [stem]
    else:
        stems = find_unmerged_stems(project)
        err.print(f"[blue]Auto-detected {len(stems)} unmerged stems[/blue]")

    if not stems:
        err.print(
            "[yellow]No unmerged stems found — all papers already have merged files.[/yellow]"
        )
        raise typer.Exit(0)

    if dry_run:
        err.print("[yellow]DRY RUN — no files will be written[/yellow]")

    results: list[dict] = []
    needs_agent_list: list[str] = []

    for s in stems:
        result = merge_paper(s, project, dry_run=dry_run)
        results.append(result)
        color = {"DONE": "green", "NEEDS_AGENT": "yellow", "ERROR": "red"}.get(
            result["status"], "white"
        )
        issues_str = ", ".join(result.get("issues", [])) or "clean"
        collapsed = result.get("collapsed_separators", 0)
        collapsed_note = f" [{collapsed} sep collapsed]" if collapsed else ""
        err.print(f"  [{color}]{result['status']}[/] {s}{collapsed_note}: {issues_str}")
        if result["status"] == "NEEDS_AGENT":
            needs_agent_list.append(s)

    # Summary
    done = sum(1 for r in results if r["status"] == "DONE")
    agent = sum(1 for r in results if r["status"] == "NEEDS_AGENT")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    err.print(f"\n[bold]Done:[/bold] {done} clean  {agent} need agent  {errors} errors")

    if needs_agent_list:
        err.print(
            f"\n[yellow]Run extraction-qa-check on:[/yellow] {', '.join(needs_agent_list)}"
        )

    if output_json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    app()
