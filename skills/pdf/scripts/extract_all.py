"""Batch-extract all PDFs in data/included/ → data/extracted/ as markdown."""

from pathlib import Path

import pymupdf4llm
import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()

app = typer.Typer(add_completion=False)


@app.command()
def main(
    input_dir: Path = typer.Argument(..., help="Directory containing PDF files"),
    output_dir: Path = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory (default: <input_dir>/extracted)",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-extract even if output already exists"
    ),
    strategy: str = typer.Option(
        "lines", "--strategy", "-s", help="Table strategy: lines_strict, lines, text"
    ),
) -> None:
    """Extract all PDFs in a directory to markdown."""
    out = output_dir or input_dir / "extracted"
    out.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        rprint(f"[yellow]No PDFs found in {input_dir}[/yellow]")
        raise typer.Exit(1)

    results: list[dict] = []
    skipped = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Extracting PDFs...", total=len(pdfs))

        for pdf_path in pdfs:
            dest = out / f"{pdf_path.stem}.md"

            if dest.exists() and not force:
                skipped += 1
                progress.advance(task)
                continue

            try:
                chunks = pymupdf4llm.to_markdown(
                    str(pdf_path),
                    page_chunks=True,
                    table_strategy=strategy,
                )
                md_text = "\n\n".join(chunk["text"] for chunk in chunks)
                dest.write_text(md_text, encoding="utf-8")

                results.append(
                    {
                        "file": pdf_path.name,
                        "pages": len(chunks),
                        "words": sum(len(c["text"].split()) for c in chunks),
                        "tables": sum(len(c.get("tables", [])) for c in chunks),
                        "status": "[green]OK[/green]",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "file": pdf_path.name,
                        "pages": 0,
                        "words": 0,
                        "tables": 0,
                        "status": f"[red]ERROR: {e}[/red]",
                    }
                )

            progress.advance(task)

    # Summary table
    summary = Table(title="Extraction Summary")
    summary.add_column("File", style="cyan", max_width=40)
    summary.add_column("Pages", justify="right")
    summary.add_column("Words", justify="right")
    summary.add_column("Tables", justify="right")
    summary.add_column("Status")

    for r in results:
        summary.add_row(
            r["file"], str(r["pages"]), f"{r['words']:,}", str(r["tables"]), r["status"]
        )

    console.print()
    console.print(summary)

    ok_count = sum(1 for r in results if "OK" in r["status"])
    err_count = sum(1 for r in results if "ERROR" in r["status"])

    console.print()
    rprint(
        f"[bold]Total:[/bold] {len(pdfs)} PDFs — {ok_count} extracted, {skipped} skipped, {err_count} errors"
    )


if __name__ == "__main__":
    app()
