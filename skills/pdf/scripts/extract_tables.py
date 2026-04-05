"""Extract tables from a PDF using pdfplumber → CSV files."""

from pathlib import Path

import pandas as pd
import pdfplumber
import typer
from rich import print as rprint
from rich.console import Console

console = Console()

app = typer.Typer(add_completion=False)


@app.command()
def main(
    pdf_path: Path = typer.Argument(..., help="Path to a PDF file"),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory (default: same as input PDF)"
    ),
    pages: str | None = typer.Option(
        None, "--pages", "-p", help="Comma-separated 1-indexed pages, e.g. '1,2,6'"
    ),
    vertical: str = typer.Option(
        "lines", "--vertical", help="Vertical strategy: lines, text, explicit"
    ),
    horizontal: str = typer.Option(
        "lines", "--horizontal", help="Horizontal strategy: lines, text, explicit"
    ),
    snap_tolerance: int = typer.Option(
        3, "--snap-tolerance", help="Snap tolerance in points"
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d", help="Save annotated debug images"
    ),
) -> None:
    """Extract tables from a PDF to CSV files using pdfplumber."""
    if not pdf_path.exists():
        rprint(f"[red]File not found:[/red] {pdf_path}")
        raise typer.Exit(1)

    dest_dir = output_dir or pdf_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    table_settings = {
        "vertical_strategy": vertical,
        "horizontal_strategy": horizontal,
        "snap_tolerance": snap_tolerance,
    }

    page_set = {int(p.strip()) for p in pages.split(",")} if pages else None
    table_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_num = page.page_number  # 1-indexed
            if page_set and page_num not in page_set:
                continue

            tables = page.extract_tables(table_settings)

            if debug:
                img = page.to_image(resolution=150)
                img.debug_tablefinder(table_settings)
                debug_path = dest_dir / f"{pdf_path.stem}_p{page_num}_debug.png"
                img.save(debug_path)
                rprint(f"  [dim]Debug image → {debug_path}[/dim]")

            for j, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue
                df = pd.DataFrame(table[1:], columns=table[0])  # type: ignore[invalid-argument-type]
                csv_path = dest_dir / f"{pdf_path.stem}_p{page_num}_t{j + 1}.csv"
                df.to_csv(csv_path, index=False)
                table_count += 1
                rprint(
                    f"  [green]Table[/green] p{page_num} t{j + 1}: {df.shape[0]} rows × {df.shape[1]} cols → {csv_path.name}"
                )

    if table_count == 0:
        rprint(f"[yellow]No tables found in {pdf_path.name}[/yellow]")
    else:
        rprint(
            f"\n[green]{table_count} table(s)[/green] extracted from {pdf_path.name}"
        )


if __name__ == "__main__":
    app()
