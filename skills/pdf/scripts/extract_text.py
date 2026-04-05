"""Extract text from a single PDF using PyMuPDF4LLM → markdown."""

from pathlib import Path

import pymupdf4llm
import typer
from rich import print as rprint
from rich.console import Console

console = Console()

app = typer.Typer(add_completion=False)


@app.command()
def main(
    pdf_path: Path = typer.Argument(..., help="Path to a PDF file"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: <pdf_stem>.md next to input)",
    ),
    pages: str | None = typer.Option(
        None, "--pages", "-p", help="Comma-separated 0-indexed pages, e.g. '0,1,5'"
    ),
    strategy: str = typer.Option(
        "lines", "--strategy", "-s", help="Table strategy: lines_strict, lines, text"
    ),
) -> None:
    """Extract text from a single PDF to markdown using PyMuPDF4LLM."""
    if not pdf_path.exists():
        rprint(f"[red]File not found:[/red] {pdf_path}")
        raise typer.Exit(1)

    dest = output or pdf_path.with_suffix(".md")
    dest.parent.mkdir(parents=True, exist_ok=True)

    page_list = [int(p.strip()) for p in pages.split(",")] if pages else None

    with console.status(f"Extracting [bold]{pdf_path.name}[/bold]..."):
        chunks = pymupdf4llm.to_markdown(
            str(pdf_path),
            page_chunks=True,
            pages=page_list,
            table_strategy=strategy,
        )

    md_text = "\n\n".join(chunk["text"] for chunk in chunks)
    dest.write_text(md_text, encoding="utf-8")

    page_count = len(chunks)
    word_count = sum(len(chunk["text"].split()) for chunk in chunks)
    table_count = sum(len(chunk.get("tables", [])) for chunk in chunks)

    rprint(f"[green]Extracted:[/green] {pdf_path.name}")
    rprint(f"  Pages:  {page_count}")
    rprint(f"  Words:  {word_count:,}")
    rprint(f"  Tables: {table_count}")
    rprint(f"  Output: [dim]{dest}[/dim]")


if __name__ == "__main__":
    app()
