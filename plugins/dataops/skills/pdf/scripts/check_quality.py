"""Compare pymupdf4llm and Docling outputs; produce a table-quality report.

Scoring heuristics (higher = better table quality):
  +10  per table detected
  +2   per data row in a table
  -20  per table with Col1/Col2/Col3 placeholder headers
  -5   per <br> broken value inside a table
  -15  per table that is likely a chart misread (all numeric cells, <=2 unique cols)
"""

import csv
import re
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(add_completion=False)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


@app.command()
def main(
    base_dir: Path = typer.Argument(
        ...,
        help="Base output dir produced by extract-dual (contains pymupdf/ and docling/ subdirs)",
    ),
    output_csv: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Save report as CSV (default: <base_dir>/quality_report.csv)",
    ),
    show_all: bool = typer.Option(
        False, "--all", "-a", help="Show all papers, not just flagged ones"
    ),
) -> None:
    """Compare pymupdf4llm vs Docling outputs and flag papers needing manual review."""
    pymupdf_dir = base_dir / "pymupdf"
    docling_dir = base_dir / "docling"

    if not pymupdf_dir.is_dir() or not docling_dir.is_dir():
        rprint(f"[red]Expected pymupdf/ and docling/ subdirs inside:[/red] {base_dir}")
        rprint("Run [bold]extract-dual[/bold] first to generate both outputs.")
        raise typer.Exit(1)

    # Match papers that have BOTH versions
    pymupdf_stems = {p.stem for p in pymupdf_dir.glob("*.md")}
    docling_stems = {p.stem for p in docling_dir.glob("*.md")}
    both = sorted(pymupdf_stems & docling_stems)
    only_pymupdf = sorted(pymupdf_stems - docling_stems)
    only_docling = sorted(docling_stems - pymupdf_stems)

    if only_pymupdf:
        rprint(
            f"[yellow]Missing Docling output for {len(only_pymupdf)} papers:[/yellow] {', '.join(only_pymupdf)}"
        )
    if only_docling:
        rprint(
            f"[yellow]Missing pymupdf output for {len(only_docling)} papers:[/yellow] {', '.join(only_docling)}"
        )

    rows: list[dict] = []
    for stem in both:
        pm_md = (pymupdf_dir / f"{stem}.md").read_text(encoding="utf-8")
        dc_md = (docling_dir / f"{stem}.md").read_text(encoding="utf-8")

        pm = score_tables(pm_md)
        dc = score_tables(dc_md)

        winner = _pick_winner(pm, dc)
        needs_review = _needs_manual_review(pm, dc)

        rows.append(
            {
                "paper": stem,
                "pm_tables": pm["table_count"],
                "pm_rows": pm["total_rows"],
                "pm_placeholders": pm["col_placeholders"],
                "pm_broken": pm["broken_values"],
                "pm_score": pm["score"],
                "dc_tables": dc["table_count"],
                "dc_rows": dc["total_rows"],
                "dc_placeholders": dc["col_placeholders"],
                "dc_broken": dc["broken_values"],
                "dc_score": dc["score"],
                "winner": winner,
                "needs_review": needs_review,
                "notes": _generate_notes(pm, dc),
            }
        )

    # Console output
    _print_console_report(rows, show_all)

    # CSV output
    csv_path = output_csv or base_dir / "quality_report.csv"
    _write_csv(rows, csv_path)
    console.print()
    rprint(f"[bold]Report saved:[/bold] [dim]{csv_path}[/dim]")

    flagged = [r for r in rows if r["needs_review"]]
    if flagged:
        rprint(
            f"\n[bold yellow]{len(flagged)} papers flagged for manual review:[/bold yellow]"
        )
        for r in flagged:
            rprint(f"  [yellow]{r['paper']}[/yellow]: {r['notes']}")


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def score_tables(md_text: str) -> dict:
    """Score table quality in a markdown document using structural heuristics."""
    table_blocks = _extract_table_blocks(md_text)

    if not table_blocks:
        return {
            "table_count": 0,
            "total_rows": 0,
            "col_placeholders": 0,
            "broken_values": 0,
            "chart_misreads": 0,
            "score": 0,
        }

    total_rows = 0
    col_placeholder_count = 0
    broken_value_count = 0
    chart_misread_count = 0

    for block in table_blocks:
        # Data rows = non-separator rows
        data_rows = [
            line for line in block if not re.match(r"^\s*\|[-:\s|]+\|\s*$", line)
        ]
        total_rows += max(0, len(data_rows) - 1)  # subtract header row

        # Col1/Col2 placeholder headers
        if block and re.search(r"\|\s*Col\d+\s*\|", block[0]):
            col_placeholder_count += 1

        full_block = "\n".join(block)

        # Broken values across lines
        broken_value_count += full_block.count("<br>")

        # Chart misread: table with many rows but all cells are short numbers/dashes
        # (charts rendered as grids of pixels/values)
        if _looks_like_chart_misread(data_rows):
            chart_misread_count += 1

    score = (
        len(table_blocks) * 10
        + total_rows * 2
        - col_placeholder_count * 20
        - broken_value_count * 5
        - chart_misread_count * 15
    )

    return {
        "table_count": len(table_blocks),
        "total_rows": total_rows,
        "col_placeholders": col_placeholder_count,
        "broken_values": broken_value_count,
        "chart_misreads": chart_misread_count,
        "score": max(0, score),
    }


def _extract_table_blocks(md_text: str) -> list[list[str]]:
    """Split markdown into contiguous blocks of table lines."""
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in md_text.split("\n"):
        if "|" in line and line.strip().startswith("|"):
            current.append(line)
        else:
            if len(current) >= 2:  # need at least header + separator
                blocks.append(current)
            current = []

    if len(current) >= 2:
        blocks.append(current)

    return blocks


def _looks_like_chart_misread(data_rows: list[str]) -> bool:
    """Detect tables that are likely charts rendered as grids (many rows, only short numeric cells)."""
    if len(data_rows) < 10:
        return False

    cell_values: list[str] = []
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        cell_values.extend(cells)

    if not cell_values:
        return False

    # If >90% of cells are very short (<=4 chars) and mostly numeric/dash, likely a chart
    short_numeric = sum(
        1 for v in cell_values if len(v) <= 4 and re.match(r"^[-\d.]+$", v or "-")
    )
    return (short_numeric / len(cell_values)) > 0.9


# --------------------------------------------------------------------------- #
# Comparison helpers
# --------------------------------------------------------------------------- #


def _pick_winner(pm: dict, dc: dict) -> str:
    if pm["score"] > dc["score"]:
        return "pymupdf"
    elif dc["score"] > pm["score"]:
        return "docling"
    elif pm["table_count"] == 0 and dc["table_count"] == 0:
        return "tie (no tables)"
    else:
        return "tie"


def _needs_manual_review(pm: dict, dc: dict) -> bool:
    """Flag cases where automated scoring is unreliable or both outputs are poor."""
    # Both have zero tables but paper likely has tables (heuristic: high word count suggests prose-only)
    if pm["table_count"] == 0 and dc["table_count"] == 0:
        return False  # Can't tell without reading — defer to agent

    # Significant disagreement in table counts
    if pm["table_count"] > 0 and dc["table_count"] > 0:
        ratio = max(pm["table_count"], dc["table_count"]) / min(
            pm["table_count"], dc["table_count"]
        )
        if ratio >= 3:
            return True

    # Either has many placeholders or broken values
    if pm["col_placeholders"] > 0 or dc["col_placeholders"] > 0:
        return True
    if pm["broken_values"] > 2 or dc["broken_values"] > 2:
        return True
    if pm["chart_misreads"] > 0 or dc["chart_misreads"] > 0:
        return True

    return False


def _generate_notes(pm: dict, dc: dict) -> str:
    notes = []
    if pm["col_placeholders"] > 0:
        notes.append(f"pymupdf: {pm['col_placeholders']} Col1/Col2 headers")
    if dc["col_placeholders"] > 0:
        notes.append(f"docling: {dc['col_placeholders']} Col1/Col2 headers")
    if pm["broken_values"] > 0:
        notes.append(f"pymupdf: {pm['broken_values']} <br> breaks")
    if dc["broken_values"] > 0:
        notes.append(f"docling: {dc['broken_values']} <br> breaks")
    if pm["chart_misreads"] > 0:
        notes.append(f"pymupdf: {pm['chart_misreads']} chart-as-table")
    if dc["chart_misreads"] > 0:
        notes.append(f"docling: {dc['chart_misreads']} chart-as-table")
    count_delta = abs(pm["table_count"] - dc["table_count"])
    if count_delta >= 3:
        notes.append(
            f"table count mismatch: pymupdf={pm['table_count']} vs docling={dc['table_count']}"
        )
    return "; ".join(notes) if notes else "OK"


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def _print_console_report(rows: list[dict], show_all: bool) -> None:
    display = (
        rows
        if show_all
        else [r for r in rows if r["needs_review"] or r["winner"] != "tie"]
    )

    tbl = Table(title="Table Quality Report", show_lines=False)
    tbl.add_column("Paper", style="cyan", max_width=30)
    tbl.add_column("PM tbls", justify="right")
    tbl.add_column("PM score", justify="right")
    tbl.add_column("DC tbls", justify="right")
    tbl.add_column("DC score", justify="right")
    tbl.add_column("Winner", justify="center")
    tbl.add_column("Review?", justify="center")
    tbl.add_column("Notes", max_width=40)

    for r in display:
        winner_str = (
            "[green]docling[/green]"
            if r["winner"] == "docling"
            else "[blue]pymupdf[/blue]"
            if r["winner"] == "pymupdf"
            else "[dim]tie[/dim]"
        )
        review_str = "[yellow]YES[/yellow]" if r["needs_review"] else "[dim]no[/dim]"
        tbl.add_row(
            r["paper"],
            str(r["pm_tables"]),
            str(r["pm_score"]),
            str(r["dc_tables"]),
            str(r["dc_score"]),
            winner_str,
            review_str,
            r["notes"],
        )

    console.print(tbl)

    total = len(rows)
    flagged = sum(1 for r in rows if r["needs_review"])
    docling_wins = sum(1 for r in rows if r["winner"] == "docling")
    pymupdf_wins = sum(1 for r in rows if r["winner"] == "pymupdf")
    console.print()
    rprint(
        f"[bold]Summary:[/bold] {total} papers — "
        f"docling better: {docling_wins}, pymupdf better: {pymupdf_wins}, "
        f"flagged for review: [yellow]{flagged}[/yellow]"
    )


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "paper",
        "pm_tables",
        "pm_rows",
        "pm_placeholders",
        "pm_broken",
        "pm_score",
        "dc_tables",
        "dc_rows",
        "dc_placeholders",
        "dc_broken",
        "dc_score",
        "winner",
        "needs_review",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    app()
