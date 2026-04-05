"""Run both pymupdf4llm and Docling on a directory of PDFs, storing outputs side-by-side."""

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
        help="Base output dir (default: <input_dir>/extracted)",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-extract even if outputs already exist"
    ),
    strategy: str = typer.Option(
        "lines",
        "--strategy",
        "-s",
        help="pymupdf4llm table strategy: lines_strict, lines, text",
    ),
    skip_docling: bool = typer.Option(
        False,
        "--skip-docling",
        help="Run only pymupdf4llm (useful for quick first pass)",
    ),
) -> None:
    """Extract all PDFs with both pymupdf4llm and Docling, storing outputs in separate subdirs.

    Output layout:
      <output_dir>/pymupdf/<stem>.md
      <output_dir>/docling/<stem>.md

    Run check-quality afterwards to compare results and generate a quality report.
    """
    base = output_dir or input_dir / "extracted"
    pymupdf_dir = base / "pymupdf"
    docling_dir = base / "docling"
    pymupdf_dir.mkdir(parents=True, exist_ok=True)
    docling_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        rprint(f"[yellow]No PDFs found in {input_dir}[/yellow]")
        raise typer.Exit(1)

    rprint(f"Found [bold]{len(pdfs)}[/bold] PDFs in {input_dir}")
    rprint(f"Output: [dim]{base}[/dim]  (pymupdf/ + docling/ subdirs)")
    console.print()

    # --- Phase 1: pymupdf4llm (fast) ---
    rprint("[bold cyan]Phase 1:[/bold cyan] pymupdf4llm extraction")
    pymupdf_results: list[dict] = []
    pymupdf_skipped = 0

    with Progress(console=console) as progress:
        task = progress.add_task("pymupdf4llm...", total=len(pdfs))
        for pdf_path in pdfs:
            dest = pymupdf_dir / f"{pdf_path.stem}.md"
            if dest.exists() and not force:
                pymupdf_skipped += 1
                progress.advance(task)
                continue
            try:
                chunks = pymupdf4llm.to_markdown(
                    str(pdf_path), page_chunks=True, table_strategy=strategy
                )
                md_text = "\n\n".join(c["text"] for c in chunks)
                dest.write_text(md_text, encoding="utf-8")
                pymupdf_results.append(
                    {
                        "file": pdf_path.name,
                        "words": len(md_text.split()),
                        "tables": sum(len(c.get("tables", [])) for c in chunks),
                        "status": "[green]OK[/green]",
                    }
                )
            except Exception as e:
                pymupdf_results.append(
                    {
                        "file": pdf_path.name,
                        "words": 0,
                        "tables": 0,
                        "status": f"[red]ERROR: {e}[/red]",
                    }
                )
            progress.advance(task)

    _print_summary("pymupdf4llm", pymupdf_results, pymupdf_skipped, len(pdfs))

    if skip_docling:
        rprint("[yellow]Skipping Docling (--skip-docling flag set)[/yellow]")
        return

    # --- Phase 2: Docling (slower, AI-powered) ---
    console.print()
    rprint("[bold cyan]Phase 2:[/bold cyan] Docling extraction (TableFormer)")
    rprint("[dim]First run downloads ML models (~1-2 GB) to ~/.cache/docling/[/dim]")

    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        rprint(
            "[red]Docling not installed.[/red] Run: cd ~/.claude/skills/pdf && pixi install"
        )
        raise typer.Exit(1)

    docling_results: list[dict] = []
    docling_skipped = 0

    with console.status("Loading Docling models..."):
        converter = DocumentConverter()

    with Progress(console=console) as progress:
        task = progress.add_task("Docling...", total=len(pdfs))
        for pdf_path in pdfs:
            dest = docling_dir / f"{pdf_path.stem}.md"
            if dest.exists() and not force:
                docling_skipped += 1
                progress.advance(task)
                continue
            try:
                result = converter.convert(str(pdf_path))
                md_text = result.document.export_to_markdown()
                dest.write_text(md_text, encoding="utf-8")
                docling_results.append(
                    {
                        "file": pdf_path.name,
                        "words": len(md_text.split()),
                        "tables": len(list(result.document.tables)),
                        "status": "[green]OK[/green]",
                    }
                )
            except Exception as e:
                docling_results.append(
                    {
                        "file": pdf_path.name,
                        "words": 0,
                        "tables": 0,
                        "status": f"[red]ERROR: {e}[/red]",
                    }
                )
            progress.advance(task)

    _print_summary("Docling", docling_results, docling_skipped, len(pdfs))

    console.print()
    rprint("[bold green]Dual extraction complete.[/bold green]")
    rprint(f"  pymupdf output: [dim]{pymupdf_dir}[/dim]")
    rprint(f"  docling output: [dim]{docling_dir}[/dim]")
    rprint(f"  Next step: [bold]pixi run check-quality {base}[/bold]")


def _print_summary(name: str, results: list[dict], skipped: int, total: int) -> None:
    if not results:
        rprint(f"  {name}: all {skipped} already extracted (use --force to re-run)")
        return

    tbl = Table(title=f"{name} Results")
    tbl.add_column("File", style="cyan", max_width=40)
    tbl.add_column("Words", justify="right")
    tbl.add_column("Tables", justify="right")
    tbl.add_column("Status")
    for r in results:
        tbl.add_row(r["file"], f"{r['words']:,}", str(r["tables"]), r["status"])
    console.print(tbl)

    ok = sum(1 for r in results if "OK" in r["status"])
    err = sum(1 for r in results if "ERROR" in r["status"])
    rprint(f"  {ok} extracted, {skipped} skipped, {err} errors (of {total} total)")


if __name__ == "__main__":
    app()
