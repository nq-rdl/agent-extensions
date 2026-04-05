"""Shared test fixtures for docx skill."""

import sys
from pathlib import Path

# Allow tests to import from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
