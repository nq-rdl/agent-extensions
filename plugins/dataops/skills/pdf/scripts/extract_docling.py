"""Extract text and tables from a PDF using Docling (IBM TableFormer model)."""

from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console

console = Console()

app = typer.Typer(add_completion=False)


@app.command()
def main(
    pdf_path: Path = typer.Argument(
        ..., help="Path to a PDF file or directory (batch mode)"
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for single file, or output dir for batch",
    ),
    batch: bool = typer.Option(
        False,
        "--batch",
        "-b",
        help="Treat pdf_path as a directory and extract all PDFs",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-extract even if output already exists"
    ),
) -> None:
    """Extract text and tables from a PDF using Docling's AI-powered TableFormer model.

    First run will download Docling's ML models (~1-2 GB) to ~/.cache/docling/.
    Subsequent runs are fast (models are cached).
    """

    if batch:
        _run_batch(pdf_path, output, force)
    else:
        _run_single(pdf_path, output)


def _run_single(pdf_path: Path, output: Path | None) -> None:
    from docling.document_converter import DocumentConverter

    if not pdf_path.exists():
        rprint(f"[red]File not found:[/red] {pdf_path}")
        raise typer.Exit(1)

    dest = output or pdf_path.parent / f"{pdf_path.stem}_docling.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    with console.status(
        f"Extracting [bold]{pdf_path.name}[/bold] with Docling (TableFormer)..."
    ):
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        md_text = result.document.export_to_markdown()

    dest.write_text(md_text, encoding="utf-8")

    table_count = len(list(result.document.tables))
    word_count = len(md_text.split())

    rprint(f"[green]Extracted:[/green] {pdf_path.name}")
    rprint(f"  Words:  {word_count:,}")
    rprint(f"  Tables: {table_count}")
    rprint(f"  Output: [dim]{dest}[/dim]")


def _run_batch(input_dir: Path, output_dir: Path | None, force: bool) -> None:
    from docling.document_converter import DocumentConverter
    from rich.progress import Progress
    from rich.table import Table as RichTable

    if not input_dir.is_dir():
        rprint(f"[red]Not a directory:[/red] {input_dir}")
        raise typer.Exit(1)

    out = output_dir or input_dir / "extracted" / "docling"
    out.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        rprint(f"[yellow]No PDFs found in {input_dir}[/yellow]")
        raise typer.Exit(1)

    # Initialise converter once — model loading happens here
    with console.status("Loading Docling models (first run downloads ~1-2 GB)..."):
        converter = DocumentConverter()

    results: list[dict] = []
    skipped = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Extracting with Docling...", total=len(pdfs))

        for pdf_path in pdfs:
            dest = out / f"{pdf_path.stem}.md"

            if dest.exists() and not force:
                skipped += 1
                progress.advance(task)
                continue

            try:
                result = converter.convert(str(pdf_path))
                md_text = result.document.export_to_markdown()
                dest.write_text(md_text, encoding="utf-8")

                table_count = len(list(result.document.tables))
                results.append(
                    {
                        "file": pdf_path.name,
                        "words": len(md_text.split()),
                        "tables": table_count,
                        "status": "[green]OK[/green]",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "file": pdf_path.name,
                        "words": 0,
                        "tables": 0,
                        "status": f"[red]ERROR: {e}[/red]",
                    }
                )

            progress.advance(task)

    summary = RichTable(title="Docling Extraction Summary")
    summary.add_column("File", style="cyan", max_width=40)
    summary.add_column("Words", justify="right")
    summary.add_column("Tables", justify="right")
    summary.add_column("Status")

    for r in results:
        summary.add_row(r["file"], f"{r['words']:,}", str(r["tables"]), r["status"])

    console.print()
    console.print(summary)

    ok = sum(1 for r in results if "OK" in r["status"])
    err = sum(1 for r in results if "ERROR" in r["status"])
    console.print()
    rprint(
        f"[bold]Total:[/bold] {len(pdfs)} PDFs — {ok} extracted, {skipped} skipped, {err} errors"
    )
    rprint(f"[bold]Output:[/bold] [dim]{out}[/dim]")


if __name__ == "__main__":
    app()
