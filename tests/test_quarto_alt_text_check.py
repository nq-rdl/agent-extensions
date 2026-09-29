"""Tests for skills/quarto-alt-text/scripts/check-alt.sh.

The fixtures under tests/fixtures/quarto-alt-text/ are cut from real Quarto
1.10.18 HTML renders (Jupyter engine), so the checks run against the markup
Quarto actually produces rather than against source-level fig- labels:

- complete.html: labelled and unlabelled cells, a Markdown figure,
  computational subfigures, all with fig-alt.
- missing.html: a cell with only fig-cap, Markdown figures with and without an
  id, a subfigure without alt. Quarto omits the alt attribute; it does not fall
  back to the caption.
- multiline-leak.html: a multi-line ``#| fig-alt: |`` block under the Jupyter
  engine. The caption leaks into alt, the attribute text into the page, and the
  cross-reference is left unresolved (``?@fig-h``).
"""

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "quarto-alt-text"
SCRIPTS = [
    REPO / "skills" / "quarto-alt-text" / "scripts" / "check-alt.sh",
    REPO / "plugins" / "quarto" / "skills" / "alt-text" / "scripts" / "check-alt.sh",
]


class CheckAlt(unittest.TestCase):
    script = SCRIPTS[0]

    def run_check(self, *names):
        args = [str(FIXTURES / n) for n in names]
        return subprocess.run(["bash", str(self.script), *args], capture_output=True, text=True, timeout=60)

    def test_copies_match(self):
        self.assertEqual(SCRIPTS[0].read_bytes(), SCRIPTS[1].read_bytes(),
                         "plugin copy is stale: run pixi run bash scripts/sync-plugins.sh quarto")

    def test_complete_page_passes_and_counts_every_figure_image(self):
        proc = self.run_check("complete.html")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("6 figure images", proc.stdout)

    def test_missing_alt_is_reported_per_image(self):
        proc = self.run_check("missing.html")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        for src in ("fig-c-output-1.png", "img2.png", "sub2.png", "img.png"):
            self.assertIn(src, proc.stdout)
        # images that do have alt text are not reported
        self.assertNotIn("fig-a-output-1.png", proc.stdout)
        self.assertNotIn("sub1.png", proc.stdout)

    def test_multiline_fig_alt_leak_is_reported(self):
        proc = self.run_check("multiline-leak.html")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("fig-alt", proc.stdout)
        self.assertIn("?@fig-h", proc.stdout)

    def test_several_files_and_a_missing_file(self):
        proc = self.run_check("complete.html", "no-such.html")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no-such.html", proc.stderr)

    def test_no_arguments_prints_usage(self):
        proc = subprocess.run(["bash", str(self.script)], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stderr.lower())


class PackagedCheckAlt(CheckAlt):
    script = SCRIPTS[1]


if __name__ == "__main__":
    unittest.main()
