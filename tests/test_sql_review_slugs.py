"""Issue 353: readable path-derived slugs, legacy-slug compatibility and one-command migration.

Path-derived slugs keep `_` and `.` literal where that stays unambiguous, so
`sql/cohort_pipeline/aaa_screening_log.sql` reviews live under
`reviews/sql__cohort_pipeline__aaa_screening_log/`. Reviews created under the legacy
encoding (every `_` and `.` percent-escaped) keep validating and working, and
`move PATH PATH` migrates one to the readable slug without forcing a re-analysis.
"""
import hashlib
import json
import re
import tempfile
import unittest
from urllib.parse import quote, unquote

from test_sql_review_scripts import Project, SQL_V1, SQL_V2, review_doc, scope_doc, run

PATH = "sql/cohort_pipeline/aaa_screening_log.sql"
READABLE = "sql__cohort_pipeline__aaa_screening_log"
LEGACY = "sql__cohort%5Fpipeline__aaa%5Fscreening%5Flog"

# Edge cases for the separator, the underscore rule and the dot rule. `x` and `x.sql` are
# listed together on purpose: stripping `.sql` before encoding already made them collide
# under the legacy encoding, and the readable encoding keeps that (documented) collision.
EDGE_PATHS = [
    "a__b", "_a", "a_", "a/b", "a_/b", "a/_b", "a___b", "a_b", "a_b_c", "_", "__",
    ".a", "a.b", "a..b", "a.", "..sql", "a%5Fb", "a%2Eb", "a/.b", "a.b/c_d.sql",
    "x.sql", "a b", "a~b", "a'b", "a!(b)*", "déjà/vu",
]
SQL_SUFFIX_COLLISION = ("x", "x.sql")


def stem(path):
    return path[:-4] if path.endswith(".sql") else path


def _escape(component):
    # Mirrors jq's @uri plus the extra escapes: only A-Za-z0-9 - _ . stay literal.
    return quote(component, safe="").replace("~", "%7E")


def legacy_slug(path):
    parts = stem(path).split("/")
    return "__".join("%00" if c == "" else _escape(c).replace("_", "%5F").replace(".", "%2E") for c in parts)


def readable_slug(path):
    def component(c):
        if c == "":
            return "%00"
        e = _escape(c)
        out = []
        for i, ch in enumerate(e):
            if ch == "_" and (i == 0 or i == len(e) - 1 or e[i - 1] == "_" or e[i + 1] == "_"):
                out.append("%5F")
            elif ch == "." and i == 0:
                out.append("%2E")
            else:
                out.append(ch)
        return "".join(out)
    return "__".join(component(c) for c in stem(path).split("/"))


def decode(slug):
    return "/".join("" if c == "%00" else unquote(c) for c in slug.split("__"))


class Encoding(unittest.TestCase):
    """The readable encoding, proven injective on the edge cases by round-tripping."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)

    def slug(self, path):
        r = run(["slug", path], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def check(self, slug, path):
        doc = scope_doc(slug, path)
        return run(["check", "--stdin"], self.p.root, stdin=json.dumps(doc))

    def test_new_reviews_get_readable_slugs(self):
        self.assertEqual(self.slug(PATH), READABLE)
        self.assertEqual(self.slug("reports/v1.2/monthly_counts.sql"), "reports__v1.2__monthly_counts")
        self.assertEqual(self.slug("reports/monthly.sql"), "reports__monthly")

    def test_slugs_are_distinct_safe_and_round_trip(self):
        slugs = {}
        for path in EDGE_PATHS:
            with self.subTest(path=path):
                s = self.slug(path)
                self.assertEqual(s, readable_slug(path))
                self.assertRegex(s, r"^[A-Za-z0-9_%.-]+$")
                self.assertNotIn(s, (".", ".."))
                self.assertFalse(s.startswith("."))
                for c in s.split("__"):
                    self.assertFalse(c.startswith("_") or c.endswith("_") or c.startswith("."), c)
                    self.assertNotIn(c, (".", ".."))
                self.assertEqual(decode(s), stem(path))
                slugs[path] = s
        self.assertEqual(len(set(slugs.values())), len(slugs), slugs)

    def test_legacy_slug_never_names_another_path(self):
        # Same decoder: a legacy slug decodes to its own path, so it cannot equal another's readable slug.
        for path in EDGE_PATHS:
            with self.subTest(path=path):
                self.assertEqual(decode(legacy_slug(path)), stem(path))
                for other in EDGE_PATHS:
                    if stem(other) != stem(path):
                        self.assertNotEqual(legacy_slug(path), readable_slug(other), other)

    def test_sql_suffix_collision_is_pre_existing(self):
        a, b = SQL_SUFFIX_COLLISION
        self.assertEqual(legacy_slug(a), legacy_slug(b))
        self.assertEqual(self.slug(a), self.slug(b))

    def test_slug_and_check_stay_in_lockstep(self):
        paths = [p for p in EDGE_PATHS if p not in SQL_SUFFIX_COLLISION] + ["x", PATH]
        slugs = {p: self.slug(p) for p in paths}
        for path in paths:
            with self.subTest(path=path):
                r = self.check(slugs[path], path)
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"))
                r = self.check(legacy_slug(path), path)
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"), "legacy slug must still bind")
                other = next(q for q in paths if q != path and slugs[q] != slugs[path])
                r = self.check(slugs[other], path)
                self.assertEqual(r.returncode, 4)
                self.assertIn("binding mismatch", r.stdout)


class LegacyEncodedReview(unittest.TestCase):
    """A review created under the legacy encoding keeps working, then migrates in one command."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql(PATH, SQL_V1)
        self.p.write_json(LEGACY, "scope.json", scope_doc(LEGACY, PATH))
        self.p.write_json(LEGACY, "review.json", review_doc(LEGACY, PATH))
        self.cmd("snapshot", LEGACY, PATH)
        self.cmd("render", LEGACY, "review")

    def cmd(self, *args, expected=0):
        r = run(list(args), self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r

    def rows(self, *flags):
        return {r["slug"]: r for r in json.loads(self.cmd("status", "--json", *flags).stdout)["reviews"]}

    def reviews(self):
        return self.p.root / ".sqlreview" / "reviews"

    def test_legacy_review_still_validates_and_works(self):
        self.assertEqual(self.cmd("check", str(self.reviews() / LEGACY / "review.json")).stdout.strip(), "ok")
        self.assertEqual(self.cmd("slug", PATH).stdout.strip(), LEGACY)
        self.assertEqual(self.rows()[LEGACY]["state"], "current")
        self.cmd("delta", LEGACY)
        # publish a second revision under the legacy slug, snapshot it, then detect a change.
        self.p.sql(PATH, SQL_V2)
        doc = review_doc(LEGACY, PATH, revision=2, sql_sha256=hashlib.sha256(SQL_V2.encode()).hexdigest())
        draft = self.p.write_json(LEGACY, "review.draft.json", doc)
        self.cmd("publish", LEGACY, "review", str(draft))
        self.cmd("snapshot", LEGACY, PATH)
        self.cmd("delta", LEGACY)
        self.p.sql(PATH, SQL_V1)
        self.cmd("delta", LEGACY, expected=10)
        self.assertFalse((self.reviews() / READABLE).exists())

    def test_readable_directory_wins_when_both_exist(self):
        self.p.review_dir(READABLE)
        self.assertEqual(self.cmd("slug", PATH).stdout.strip(), READABLE)

    def test_same_path_move_migrates_without_rebind(self):
        r = self.cmd("move", PATH, PATH)
        self.assertEqual(r.stdout.strip().split("\t"), ["moved", LEGACY, READABLE, PATH])
        self.assertFalse((self.reviews() / LEGACY).exists())
        d = self.reviews() / READABLE
        self.assertFalse((d / "rebind-required").exists(), "binding unchanged: no re-analysis forced")
        self.assertFalse((d / "review.md").exists(), "stale render removed")
        self.assertTrue((d / "source.sql").is_file())
        self.assertTrue((d / "history" / "1.sql").is_file())
        for name in ("review.json", "scope.json"):
            j = json.loads((d / name).read_text())
            self.assertEqual((j["slug"], j["sql_path"]), (READABLE, PATH))
            self.assertEqual(self.cmd("check", str(d / name)).stdout.strip(), "ok")
        self.assertEqual(self.rows()[READABLE]["state"], "current")
        self.assertEqual(self.cmd("slug", PATH).stdout.strip(), READABLE)
        self.cmd("render", READABLE, "review")

    def test_same_path_move_on_readable_slug_is_a_noop(self):
        self.cmd("move", PATH, PATH)
        self.cmd("render", READABLE, "review")
        r = self.cmd("move", PATH, PATH)
        self.assertIn("already", r.stdout + r.stderr)
        d = self.reviews() / READABLE
        self.assertFalse((d / "rebind-required").exists())
        self.assertTrue((d / "review.md").exists())
        self.assertEqual(self.rows()[READABLE]["state"], "current")

    def test_move_to_another_path_lands_on_readable_slug_and_requires_rebind(self):
        self.p.sql("sql/next_step/aaa_log.sql", SQL_V1)
        r = self.cmd("move", PATH, "sql/next_step/aaa_log.sql")
        self.assertEqual(r.stdout.strip().split("\t"), ["moved", LEGACY, "sql__next_step__aaa_log", "sql/next_step/aaa_log.sql"])
        self.assertTrue((self.reviews() / "sql__next_step__aaa_log" / "rebind-required").is_file())

    def test_verbose_status_flags_migratable_legacy_slugs(self):
        command = f"sqlreview.sh move '{PATH}' '{PATH}'"
        self.p.sql("reports/monthly.sql", SQL_V1)
        self.p.write_json("reports__monthly", "review.json", review_doc())
        text = self.cmd("status", "--verbose").stdout
        legacy_row = next(l for l in text.splitlines() if l.startswith(LEGACY + "\t"))
        self.assertTrue(legacy_row.endswith(f"\tmigrate={command}"), legacy_row)
        readable_row = next(l for l in text.splitlines() if l.startswith("reports__monthly\t"))
        self.assertNotIn("migrate=", readable_row)
        self.assertNotIn("migrate=", self.cmd("status").stdout)
        rows = self.rows("--verbose")
        self.assertEqual(rows[LEGACY]["migrate"], command)
        self.assertIsNone(rows["reports__monthly"]["migrate"])
        self.assertNotIn("migrate", self.rows()[LEGACY])


class SingleDefinition(unittest.TestCase):
    """sr_slug and check's path_slug come from one jq module, so they cannot drift."""

    def test_both_consumers_include_the_slug_module(self):
        from test_sql_review_scripts import SCRIPT
        scripts = SCRIPT.parent
        module = (scripts / "sqlreview-slug.jq").read_text()
        self.assertRegex(module, r"(?m)^def path_slug:")
        self.assertRegex(module, r"(?m)^def legacy_path_slug:")
        self.assertIn('include "sqlreview-slug";', (scripts / "sqlreview-check.jq").read_text())
        for name in ("sqlreview-check.jq", "sqlreview-lib.sh"):
            self.assertNotIn('gsub("_"; "%5F")', (scripts / name).read_text(), name)
        self.assertTrue(re.search(r'include "sqlreview-slug"', (scripts / "sqlreview-lib.sh").read_text()))


if __name__ == "__main__":
    unittest.main()
