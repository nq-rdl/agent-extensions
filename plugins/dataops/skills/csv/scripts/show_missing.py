"""Scan a pipe-delimited CSV for rows with empty/null fields."""

from pathlib import Path

import pyarrow.csv as pcsv
import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(add_completion=False)


def _is_placeholder(col: str) -> bool:
    """Return True for auto-generated Column_N placeholder headers."""
    import re

    return bool(re.fullmatch(r"Column_\d+", col))


def _is_empty(val) -> bool:
    """Return True if a cell value is empty or null."""
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s == "None"


@app.command()
def main(
    csv_path: Path = typer.Argument(..., help="Path to the pipe-delimited CSV file"),
    key: str = typer.Option(
        "SID", "--key", "-k", help="Column name used as row identifier"
    ),
    columns: str | None = typer.Option(
        None,
        "--columns",
        "-c",
        help="Comma-separated list of columns to check (default: all non-placeholder)",
    ),
    only_missing: bool = typer.Option(
        False,
        "--only-missing/--no-only-missing",
        help="Only show rows that have at least one missing field",
    ),
    count: bool = typer.Option(
        False, "--count/--no-count", help="Show summary counts only, no per-row table"
    ),
) -> None:
    """Scan a CSV for rows with missing (empty or null) field values."""
    if not csv_path.exists():
        console.print(f"[red]File not found:[/red] {csv_path}")
        raise typer.Exit(1)

    read_opts = pcsv.ReadOptions()
    parse_opts = pcsv.ParseOptions(delimiter="|")
    convert_opts = pcsv.ConvertOptions(strings_can_be_null=False)
    tbl = pcsv.read_csv(
        csv_path,
        read_options=read_opts,
        parse_options=parse_opts,
        convert_options=convert_opts,
    )

    all_cols = tbl.column_names
    check_cols = (
        [c.strip() for c in columns.split(",")]
        if columns
        else [c for c in all_cols if not _is_placeholder(c)]
    )

    # Resolve key column
    if key not in all_cols:
        console.print(f"[red]Key column '{key}' not found.[/red] Available: {all_cols}")
        raise typer.Exit(1)

    rows = tbl.to_pydict()
    n_rows = tbl.num_rows

    # Build per-row missing info
    results = []
    for i in range(n_rows):
        row_key = rows[key][i]
        missing = [c for c in check_cols if _is_empty(rows.get(c, [None] * n_rows)[i])]
        results.append((row_key, missing))

    complete = sum(1 for _, m in results if not m)
    incomplete = n_rows - complete

    if count:
        console.print(
            f"[bold]{complete}[/bold] of [bold]{n_rows}[/bold] rows complete | [bold red]{incomplete}[/bold red] rows with missing data"
        )
        raise typer.Exit(0)

    # Rich table
    table = Table(
        title=f"[bold]{csv_path.name}[/bold] — missing field scan", show_lines=False
    )
    table.add_column(key, style="bold cyan", no_wrap=True)
    for col in check_cols:
        table.add_column(col, justify="center")

    shown = 0
    for row_key, missing in results:
        if only_missing and not missing:
            continue
        cells = []
        for col in check_cols:
            cells.append("[red]✗[/red]" if col in missing else "[green]✓[/green]")
        table.add_row(str(row_key), *cells)
        shown += 1

    if shown:
        console.print(table)
    else:
        console.print("[green]All rows are complete.[/green]")

    console.print(
        f"\n[bold]{complete}[/bold] of [bold]{n_rows}[/bold] rows complete | [bold red]{incomplete}[/bold red] rows with missing data"
    )


if __name__ == "__main__":
    app()
