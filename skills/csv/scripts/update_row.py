"""Update fields in a pipe-delimited CSV row identified by a key match."""

import shutil
from pathlib import Path
from typing import Annotated

import pyarrow as pa
import pyarrow.csv as pcsv
import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(add_completion=False)


def _read_pipe_csv(path: Path) -> pa.Table:
    parse_opts = pcsv.ParseOptions(delimiter="|")
    convert_opts = pcsv.ConvertOptions(strings_can_be_null=False)
    return pcsv.read_csv(path, parse_options=parse_opts, convert_options=convert_opts)


def _write_pipe_csv(table: pa.Table, path: Path) -> None:
    write_opts = pcsv.WriteOptions(delimiter="|")
    pcsv.write_csv(table, path, write_options=write_opts)


def _parse_set(assignments: list[str]) -> dict[str, str]:
    """Parse 'Field=Value' strings into a dict."""
    result = {}
    for assignment in assignments:
        if "=" not in assignment:
            raise typer.BadParameter(
                f"Invalid --set value '{assignment}': expected 'Field=Value'"
            )
        field, _, value = assignment.partition("=")
        result[field.strip()] = value.strip()
    return result


@app.command()
def main(
    csv_path: Path = typer.Argument(..., help="Path to the pipe-delimited CSV file"),
    key: str = typer.Option(
        ..., "--key", "-k", help="Column name to match on (e.g. SID)"
    ),
    match: str = typer.Option(
        ..., "--match", "-m", help="Value to match in the key column (e.g. S34)"
    ),
    set_values: Annotated[
        list[str],
        typer.Option(
            "--set", "-s", help="'Field=Value' assignments (repeat for multiple)"
        ),
    ] = [],
    dry_run: bool = typer.Option(
        False, "--dry-run/--no-dry-run", help="Show what would change without writing"
    ),
    backup: bool = typer.Option(
        False, "--backup/--no-backup", help="Create a .bak copy before writing"
    ),
) -> None:
    """Update fields in a CSV row identified by a key column match."""
    if not csv_path.exists():
        console.print(f"[red]File not found:[/red] {csv_path}")
        raise typer.Exit(1)

    if not set_values:
        console.print("[red]No --set assignments provided.[/red]")
        raise typer.Exit(1)

    updates = _parse_set(set_values)
    tbl = _read_pipe_csv(csv_path)
    all_cols = tbl.column_names

    if key not in all_cols:
        console.print(f"[red]Key column '{key}' not found.[/red] Available: {all_cols}")
        raise typer.Exit(1)

    for field in updates:
        if field not in all_cols:
            console.print(
                f"[red]Field '{field}' not found in CSV.[/red] Available: {all_cols}"
            )
            raise typer.Exit(1)

    # Find matching row index
    key_col = tbl.column(key).to_pylist()
    matches = [i for i, v in enumerate(key_col) if str(v) == str(match)]

    if not matches:
        console.print(f"[red]No row found where {key} = '{match}'[/red]")
        raise typer.Exit(1)
    if len(matches) > 1:
        console.print(
            f"[red]Multiple rows ({len(matches)}) match {key} = '{match}'[/red] — cannot update ambiguously"
        )
        raise typer.Exit(1)

    row_idx = matches[0]
    rows = tbl.to_pydict()

    # Show diff
    diff_table = Table(
        title=f"[bold]Update preview:[/bold] {key}={match}", show_lines=True
    )
    diff_table.add_column("Field", style="bold")
    diff_table.add_column("Before", style="red")
    diff_table.add_column("After", style="green")

    for field, new_val in updates.items():
        old_val = rows[field][row_idx]
        diff_table.add_row(field, str(old_val) if old_val is not None else "", new_val)

    console.print(diff_table)

    if dry_run:
        console.print("[yellow]Dry run — no changes written.[/yellow]")
        raise typer.Exit(0)

    # Apply updates
    for field, new_val in updates.items():
        col_data = rows[field][:]
        col_data[row_idx] = new_val
        col_idx = all_cols.index(field)
        tbl = tbl.set_column(col_idx, field, pa.array(col_data, type=pa.string()))

    if backup:
        bak = csv_path.with_suffix(csv_path.suffix + ".bak")
        shutil.copy2(csv_path, bak)
        console.print(f"[dim]Backup written to {bak}[/dim]")

    _write_pipe_csv(tbl, csv_path)
    console.print(
        f"[green]Updated {len(updates)} field(s) in {csv_path.name} ({key}={match})[/green]"
    )


if __name__ == "__main__":
    app()
