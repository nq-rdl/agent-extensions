"""Cross-sheet completion dashboard for scoping review extraction CSVs."""

import re
from pathlib import Path

import pyarrow.csv as pcsv
import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(add_completion=False)


def _is_placeholder(col: str) -> bool:
    return bool(re.fullmatch(r"Column_\d+", col))


def _is_empty(val) -> bool:
    if val is None:
        return True
    return str(val).strip() in ("", "None")


def _read_csv(path: Path):
    parse_opts = pcsv.ParseOptions(delimiter="|")
    convert_opts = pcsv.ConvertOptions(strings_can_be_null=False)
    return pcsv.read_csv(path, parse_options=parse_opts, convert_options=convert_opts)


def _completeness(tbl) -> tuple[int, int]:
    """Return (complete_rows, total_rows). A row is complete if no non-placeholder field is empty."""
    rows = tbl.to_pydict()
    check_cols = [c for c in tbl.column_names if not _is_placeholder(c)]
    n = tbl.num_rows
    complete = 0
    for i in range(n):
        if all(not _is_empty(rows[c][i]) for c in check_cols):
            complete += 1
    return complete, n


@app.command()
def main(
    dir_path: Path = typer.Argument(
        ..., help="Directory containing extraction CSV files"
    ),
    pattern: str = typer.Option(
        "*_E.*.csv", "--pattern", "-p", help="Glob pattern to match CSV files"
    ),
    key: str = typer.Option("SID", "--key", "-k", help="Row identifier column"),
    all_rows: bool = typer.Option(
        False, "--all/--no-all", help="Include fully complete sheets in output"
    ),
    by_study: bool = typer.Option(
        False, "--by-study/--no-by-study", help="Show per-SID breakdown across sheets"
    ),
) -> None:
    """Display a completion dashboard across all extraction CSV sheets."""
    if not dir_path.is_dir():
        console.print(f"[red]Not a directory:[/red] {dir_path}")
        raise typer.Exit(1)

    csv_files = sorted(dir_path.glob(pattern))
    if not csv_files:
        console.print(f"[yellow]No files matching '{pattern}' in {dir_path}[/yellow]")
        raise typer.Exit(0)

    # ── Per-sheet summary ────────────────────────────────────────────────────
    summary_table = Table(
        title="[bold]Extraction sheet completion[/bold]", show_lines=False
    )
    summary_table.add_column("Sheet", style="bold")
    summary_table.add_column("Complete", justify="right", style="green")
    summary_table.add_column("Total", justify="right")
    summary_table.add_column("Missing", justify="right", style="red")
    summary_table.add_column("Progress")

    sheet_data: dict[str, dict] = {}

    for csv_path in csv_files:
        try:
            tbl = _read_csv(csv_path)
        except Exception as e:
            console.print(f"[red]Error reading {csv_path.name}:[/red] {e}")
            continue

        complete, total = _completeness(tbl)
        missing = total - complete
        sheet_data[csv_path.name] = {"tbl": tbl, "complete": complete, "total": total}

        if not all_rows and missing == 0:
            continue

        pct = complete / total if total else 0
        bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
        summary_table.add_row(
            csv_path.stem,
            str(complete),
            str(total),
            str(missing),
            f"[green]{bar}[/green] {pct:.0%}",
        )

    console.print(summary_table)

    if not by_study:
        return

    # ── Per-SID cross-sheet breakdown ────────────────────────────────────────
    # Collect all SIDs and per-sheet status
    all_sids: set[str] = set()
    sid_status: dict[str, dict[str, str]] = {}  # sid → sheet_name → Y/P/N

    for sheet_name, data in sheet_data.items():
        tbl = data["tbl"]
        if key not in tbl.column_names:
            continue
        rows = tbl.to_pydict()
        check_cols = [
            c for c in tbl.column_names if not _is_placeholder(c) and c != key
        ]
        n = tbl.num_rows
        for i in range(n):
            sid = str(rows[key][i]).strip()
            if not sid or sid == "None":
                continue
            all_sids.add(sid)
            missing_fields = [c for c in check_cols if _is_empty(rows[c][i])]
            if not missing_fields:
                status = "[green]Y[/green]"
            elif len(missing_fields) == len(check_cols):
                status = "[red]N[/red]"
            else:
                status = "[yellow]P[/yellow]"
            sid_status.setdefault(sid, {})[sheet_name] = status

    if not all_sids:
        return

    # Sort SIDs numerically
    def sid_sort_key(s: str):
        m = re.search(r"\d+", s)
        return int(m.group()) if m else 0

    sorted_sids = sorted(all_sids, key=sid_sort_key)
    sheet_names = list(sheet_data.keys())

    study_table = Table(
        title="[bold]Per-study completion (Y=complete, P=partial, N=none)[/bold]",
        show_lines=False,
    )
    study_table.add_column(key, style="bold cyan")
    for sn in sheet_names:
        study_table.add_column(sn[:18], justify="center")

    for sid in sorted_sids:
        row = [sid] + [
            sid_status.get(sid, {}).get(sn, "[dim]—[/dim]") for sn in sheet_names
        ]
        study_table.add_row(*row)

    console.print(study_table)


if __name__ == "__main__":
    app()
