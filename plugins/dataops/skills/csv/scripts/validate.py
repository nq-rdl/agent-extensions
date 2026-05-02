"""Validate a pipe-delimited CSV against built-in schema rules."""

import re
from dataclasses import dataclass
from pathlib import Path

import pyarrow.csv as pcsv
import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(add_completion=False)

# ── Built-in allowed values ───────────────────────────────────────────────────
FUNDING_VALUES = {"Public", "Commercial", "Mixed", "Not Reported"}
COI_VALUES = {"None declared", "Yes", "Not Reported"}
BOOLEAN_COLS = {"D16", "D25", "D40", "D41", "D42", "D43", "D44", "D45", "D46", "D47"}
VALID_BOOL = {"0", "1", ""}


@dataclass
class ValidationError:
    row: int
    sid: str
    column: str
    value: str
    reason: str
    level: str = "error"  # "error" or "warning"


def _check_row(
    row_idx: int,
    sid: str,
    col: str,
    val: str,
) -> ValidationError | None:
    """Apply built-in rules to a single cell. Returns an error or None."""
    v = val.strip() if val else ""

    if col == "SID" and v and not re.fullmatch(r"S\d+", v):
        return ValidationError(row_idx, sid, col, v, "SID must match S\\d+ pattern")

    if col == "Funding" and v and v not in FUNDING_VALUES:
        return ValidationError(
            row_idx, sid, col, v, f"Must be one of: {', '.join(sorted(FUNDING_VALUES))}"
        )

    if col == "COI" and v and v not in COI_VALUES:
        return ValidationError(
            row_idx, sid, col, v, f"Must be one of: {', '.join(sorted(COI_VALUES))}"
        )

    if col == "Published Year" and v:
        if not re.fullmatch(r"\d{4}", v):
            return ValidationError(
                row_idx, sid, col, v, "Published Year must be a 4-digit integer"
            )

    # Boolean columns — match by column name suffix pattern or known set
    if col in BOOLEAN_COLS or re.fullmatch(r"D(16|25|4[0-7])", col):
        if v not in VALID_BOOL:
            return ValidationError(
                row_idx, sid, col, v, "Boolean column must be 0, 1, or empty"
            )

    return None


@app.command()
def main(
    csv_path: Path = typer.Argument(..., help="Path to the pipe-delimited CSV file"),
    strict: bool = typer.Option(
        False, "--strict/--no-strict", help="Treat warnings as errors"
    ),
    quiet: bool = typer.Option(
        False, "--quiet/--no-quiet", "-q", help="Only show error count, not details"
    ),
) -> None:
    """Validate a pipe-delimited CSV against built-in schema rules."""
    if not csv_path.exists():
        console.print(f"[red]File not found:[/red] {csv_path}")
        raise typer.Exit(1)

    parse_opts = pcsv.ParseOptions(delimiter="|")
    convert_opts = pcsv.ConvertOptions(strings_can_be_null=False)
    tbl = pcsv.read_csv(
        csv_path, parse_options=parse_opts, convert_options=convert_opts
    )

    rows = tbl.to_pydict()
    n_rows = tbl.num_rows
    all_cols = tbl.column_names

    # Resolve SID column for reporting (may not exist)
    sid_list = rows.get("SID", [""] * n_rows)

    errors: list[ValidationError] = []
    for i in range(n_rows):
        sid = (
            str(sid_list[i]) if sid_list[i] else f"row {i + 2}"
        )  # +2 for 1-index + header
        for col in all_cols:
            val = rows[col][i]
            val_str = str(val) if val is not None else ""
            err = _check_row(i + 2, sid, col, val_str)
            if err:
                errors.append(err)

    if not errors:
        console.print(f"[green]✓ No validation errors in {csv_path.name}[/green]")
        raise typer.Exit(0)

    if quiet:
        console.print(
            f"[red]{len(errors)} validation error(s) in {csv_path.name}[/red]"
        )
        raise typer.Exit(1)

    table = Table(
        title=f"[bold red]Validation errors: {csv_path.name}[/bold red]",
        show_lines=False,
    )
    table.add_column("Row", style="dim", justify="right")
    table.add_column("SID", style="bold cyan")
    table.add_column("Column", style="yellow")
    table.add_column("Value", style="red")
    table.add_column("Reason")

    for err in errors:
        level_color = "red" if err.level == "error" else "yellow"
        table.add_row(
            str(err.row),
            err.sid,
            err.column,
            repr(err.value),
            f"[{level_color}]{err.reason}[/{level_color}]",
        )

    console.print(table)
    console.print(
        f"\n[bold red]{len(errors)} error(s)[/bold red] found in {csv_path.name}"
    )
    raise typer.Exit(1 if strict or any(e.level == "error" for e in errors) else 0)


if __name__ == "__main__":
    app()
