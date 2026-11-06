"""L2: a source label cannot close the HTML comment of a claim line in the paste-ready release body.

render writes each claim as "- text <!-- C1: <source labels> -->". A source path, ref, slug or item that holds
a double hyphen, an angle bracket or a control character could end the comment and show a link to the
researcher. check refuses those characters, naming the field and the rule and never the value. Normal
labels render unchanged. Synthetic data only: the link target is example.org.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_data_request_release import RELEASE, REPO, SLUG, record, run
except ModuleNotFoundError:
    from tests.test_data_request_release import RELEASE, REPO, SLUG, record, run

HOSTILE = "src/a.py --> [click](https://example.org/x) <!--"
RULE = "must not contain --, < or > or control characters"


def with_source(**fields):
    doc = record()
    doc["claims"][0]["sources"] = [{"kind": "file", "path": "src/pipelines/falls.py", "ref": "v1.0.0", **fields}]
    return doc


@unittest.skipUnless(shutil.which("jq"), "release.sh needs jq")
class SourceLabels(unittest.TestCase):
    def check(self, doc):
        return run(RELEASE, ["check", "--stdin"], REPO, stdin=json.dumps(doc))

    def render(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "release.json"
            f.write_text(json.dumps(doc))
            return run(RELEASE, ["render", str(f)], tmp)

    def test_the_repro_is_refused_by_check_and_render(self):
        doc = with_source(path=HOSTILE)
        c = self.check(doc)
        self.assertEqual(c.returncode, 4, c.stdout + c.stderr)
        self.assertIn(f"C1: source path {RULE}", c.stdout)
        r = self.render(doc)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        for out in (c.stdout + c.stderr, r.stdout + r.stderr):
            self.assertNotIn("example.org", out)
            self.assertNotIn("click", out)

    def test_each_field_and_each_character_is_refused(self):
        for field in ("path", "ref"):
            for bad in ("a--b", "a<b", "a>b", "a\nb", "a\tb", "a\x00b", "a\x7fb"):
                with self.subTest(field=field, bad=repr(bad)):
                    c = self.check(with_source(**{field: bad}))
                    self.assertEqual(c.returncode, 4, c.stdout + c.stderr)
                    self.assertIn(f"C1: source {field} {RULE}", c.stdout)

    def test_slug_and_item_of_a_review_source_are_refused(self):
        for field in ("slug", "item"):
            doc = record()
            doc["claims"][0]["sources"][0][field] = "x-->y"
            with self.subTest(field=field):
                c = self.check(doc)
                self.assertEqual(c.returncode, 4, c.stdout + c.stderr)
                self.assertIn(f"C1: source {field} {RULE}", c.stdout)

    def test_a_scope_item_that_is_not_a_string_is_refused(self):
        doc = record()
        doc["claims"][0]["sources"] = [{"kind": "scope", "slug": SLUG, "item": {"x": 1}, "revision": 2}]
        c = self.check(doc)
        self.assertEqual(c.returncode, 4, c.stdout + c.stderr)
        self.assertIn("C1: source item must be a string", c.stdout)

    def test_a_pending_claim_is_checked_too(self):
        doc = with_source(ref="v1--x")
        doc["claims"][0].update(decision="pending", final=None, decided_by=None, decided_at=None)
        doc["status"] = "draft"
        c = self.check(doc)
        self.assertEqual(c.returncode, 4, c.stdout + c.stderr)
        self.assertIn(f"C1: source ref {RULE}", c.stdout)

    def test_normal_labels_render_unchanged(self):
        r = self.render(record())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<!-- C1: review sql__v1__falls A1 r2; file src/pipelines/falls.py@v1.0.0 -->", r.stdout)
        doc = with_source(path="src/pipelines/v2.1-a_b/falls.py", ref="release-1.0.0")
        r = self.render(doc)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<!-- C1: file src/pipelines/v2.1-a_b/falls.py@release-1.0.0 -->", r.stdout)


if __name__ == "__main__":
    unittest.main()
