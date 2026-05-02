"""Compare extraction quality of pymupdf4llm, pdfplumber, and pdfminer on a single PDF."""

from pathlib import Path

import pdfplumber
import pymupdf4llm
import typer
from pdfminer.high_level import extract_text as pdfminer_extract
from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(add_completion=False)

PREVIEW_CHARS = 500


def _extract_pymupdf4llm(pdf_path: str) -> str:
    return pymupdf4llm.to_markdown(pdf_path)


def _extract_pdfplumber(pdf_path: str) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
    return "\n\n".join(texts)


def _extract_pdfminer(pdf_path: str) -> str:
    return pdfminer_extract(pdf_path)


EXTRACTORS = {
    "pymupdf4llm": _extract_pymupdf4llm,
    "pdfplumber": _extract_pdfplumber,
    "pdfminer": _extract_pdfminer,
}


@app.command()
def main(
    pdf_path: Path = typer.Argument(..., help="Path to a PDF file"),
    preview: int = typer.Option(
        PREVIEW_CHARS, "--preview", "-n", help="Number of characters to preview"
    ),
) -> None:
    """Compare extraction quality across pymupdf4llm, pdfplumber, and pdfminer."""
    if not pdf_path.exists():
        rprint(f"[red]File not found:[/red] {pdf_path}")
        raise typer.Exit(1)

    results: dict[str, str] = {}

    for name, func in EXTRACTORS.items():
        with console.status(f"Running [bold]{name}[/bold]..."):
            try:
                results[name] = func(str(pdf_path))
            except Exception as e:
                results[name] = f"ERROR: {e}"

    # Summary table
    summary = Table(title=f"Extractor Comparison: {pdf_path.name}")
    summary.add_column("Extractor", style="cyan")
    summary.add_column("Words", justify="right")
    summary.add_column("Chars", justify="right")
    summary.add_column("Lines", justify="right")

    for name, text in results.items():
        if text.startswith("ERROR"):
            summary.add_row(name, "-", "-", "-")
        else:
            words = len(text.split())
            chars = len(text)
            lines = text.count("\n") + 1
            summary.add_row(name, f"{words:,}", f"{chars:,}", f"{lines:,}")

    console.print()
    console.print(summary)

    # Text previews
    for name, text in results.items():
        console.print()
        console.rule(f"[bold]{name}[/bold] — first {preview} chars")
        if text.startswith("ERROR"):
            rprint(f"[red]{text}[/red]")
        else:
            console.print(text[:preview])
            if len(text) > preview:
                rprint(f"[dim]... ({len(text) - preview:,} more chars)[/dim]")


if __name__ == "__main__":
    app()
