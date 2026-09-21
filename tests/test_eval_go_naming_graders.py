"""Fixture tests for the regex graders of evals/claude/go/naming-rewrite.

`claude plugin eval` applies each grader's `pattern` as a JavaScript regex to the
agent's final message, so every fixture is graded twice: by Python's `re` and, when
`node` is on PATH, by the JavaScript engine itself, and the two must agree. No model
call is made. Every grader is scoped to the rewritten file — the last fenced go block
that opens with `package account` — so prose, quoted before-code, and Go comments or
literals inside the file must not affect it.
"""

import json
import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path

import yaml

GRADERS = Path(__file__).resolve().parent.parent / "evals/claude/go/naming-rewrite/graders"

GOOD_FILE = """package account

type HTTPClient struct {
	baseURL string
	ownerID string
}

func NewHTTPClient(baseURL string, ownerID string) *HTTPClient {
	return &HTTPClient{baseURL: baseURL, ownerID: ownerID}
}

func (c *HTTPClient) OwnerID() string {
	return c.ownerID
}

func (c *HTTPClient) BaseURL() string {
	return c.baseURL
}
"""

ORIGINAL_FILE = """package account

type AccountHttpClient struct {
	base_url string
	ownerId  string
}

func NewAccountHttpClient(base_url string, ownerId string) *AccountHttpClient {
	return &AccountHttpClient{base_url: base_url, ownerId: ownerId}
}

func (this *AccountHttpClient) GetOwnerId() string {
	return this.ownerId
}

func (this *AccountHttpClient) GetBaseUrl() string {
	return this.base_url
}
"""


def block(code: str, fence: str = "```", info: str = "go") -> str:
    return f"{fence}{info}\n{code}{fence}\n"


NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""


def load() -> dict:
    sources = {}
    for path in sorted(GRADERS.glob("*.md")):
        meta = yaml.safe_load(path.read_text().split("\n---\n")[0].removeprefix("---\n"))
        if meta["type"] == "regex":
            sources[path.stem] = meta["pattern"]
    return sources


class GoNamingGraderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load()
        cls.patterns = {name: re.compile(src) for name, src in cls.sources.items()}

    def verdicts(self, reply: str) -> dict:
        python = {name: bool(p.search(reply)) for name, p in self.patterns.items()}
        if NODE:
            result = subprocess.run(
                [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": self.sources, "reply": reply}),
                capture_output=True, text=True, check=True, timeout=30,
            )
            self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return python

    def assert_all_pass(self, reply: str):
        failed = [n for n, ok in self.verdicts(reply).items() if not ok]
        self.assertEqual(failed, [])

    def assert_only_fails(self, reply: str, expected: set):
        failed = {n for n, ok in self.verdicts(reply).items() if not ok}
        self.assertEqual(failed, expected)

    def test_expected_grader_set(self):
        self.assertEqual(
            set(self.patterns),
            {"type-no-stutter", "constructor-no-stutter", "field-initialisms",
             "getter-initialism", "no-this-receiver", "identifier-casing"},
        )

    def test_graders_share_one_block_scoping_prefix(self):
        marker = "package\\s+account\\b"  # end of the selected block's package clause
        prefixes = {src[: src.index(marker) + len(marker)] for src in self.sources.values()}
        self.assertEqual(len(prefixes), 1)

    def test_correct_rewrite_passes(self):
        self.assert_all_pass("Here you go:\n\n" + block(GOOD_FILE))

    def test_shorter_type_name_and_value_receiver_pass(self):
        code = GOOD_FILE.replace("HTTPClient", "Client").replace("(c *Client)", "(c Client)")
        self.assert_all_pass(block(code))

    def test_leading_filename_comment_is_tolerated(self):
        self.assert_all_pass(block("// account.go\n" + GOOD_FILE))

    def test_prose_quoting_the_original_declarations_does_not_fail(self):
        reply = block(GOOD_FILE) + (
            "Changes:\n- `type AccountHttpClient struct` → `HTTPClient` (stutter)\n"
            "- `func NewAccountHttpClient` → `NewHTTPClient`\n"
            "- `base_url`/`ownerId` → `baseURL`/`ownerID`; `GetOwnerId()` → `OwnerID()`\n"
            "- receiver `func (this *AccountHttpClient)` → `c`\n"
        )
        self.assert_all_pass(reply)

    def test_before_and_after_blocks_grade_the_after_block(self):
        self.assert_all_pass("Before:\n" + block(ORIGINAL_FILE) + "After:\n" + block(GOOD_FILE))

    def test_trailing_snippet_block_does_not_hide_the_file(self):
        reply = block(GOOD_FILE) + "Callers now write:\n```go\nc := account.NewHTTPClient(u, id)\n```\n"
        self.assert_all_pass(reply)

    def test_tilde_fences_fence_attributes_and_crlf_are_accepted(self):
        self.assert_all_pass(block(GOOD_FILE, fence="~~~"))
        self.assert_all_pass(block(GOOD_FILE, info='go title="account.go"'))
        self.assert_all_pass(block(GOOD_FILE).replace("\n", "\r\n"))

    def test_longer_and_indented_fences_are_accepted(self):
        self.assert_all_pass(block(GOOD_FILE, fence="````"))
        indented = "".join("  " + line for line in block(GOOD_FILE).splitlines(keepends=True))
        self.assert_all_pass("1. The rewrite:\n\n" + indented)

    def test_grouped_field_and_parameter_declarations_pass(self):
        code = GOOD_FILE.replace("\tbaseURL string\n\townerID string\n", "\tbaseURL, ownerID string\n").replace(
            "(baseURL string, ownerID string)", "(baseURL, ownerID string)")
        self.assert_all_pass(block(code))

    def test_required_signatures_only_in_comments_do_not_count(self):
        code = GOOD_FILE.replace("OwnerID()", "GetOwnerID()").replace("BaseURL()", "GetBaseURL()") + (
            "// func (c *HTTPClient) OwnerID() string\n// func (c *HTTPClient) BaseURL() string\n")
        self.assert_only_fails(block(code), {"getter-initialism"})

    def test_old_names_quoted_in_comments_and_literals_do_not_fail(self):
        code = GOOD_FILE.replace(
            "type HTTPClient struct {",
            "// Renamed AccountHttpClient (was base_url / GetOwnerId, receiver this).\n"
            "/* func (this *AccountHttpClient) GetBaseUrl() */\n"
            "const legacy = \"AccountHttpClient.base_url\"\n"
            "const raw = `func NewAccountHttpClient(owner_id)`\n"
            "type HTTPClient struct {",
        )
        self.assert_all_pass(block(code))

    def test_backticks_in_a_comment_do_not_end_the_graded_block(self):
        code = GOOD_FILE + "\n// ```\nfunc (this *HTTPClient) Extra() {}\n"
        self.assert_only_fails(block(code), {"no-this-receiver"})

    def test_many_comments_with_a_late_violation_stay_fast(self):
        code = GOOD_FILE + "".join(f"// note {i} \"q\" `r`\n" for i in range(400)) + "var owner_id string\n"
        started = time.monotonic()
        self.assert_only_fails(block(code), {"identifier-casing"})
        self.assertLess(time.monotonic() - started, 5)

    def test_empty_or_codeless_reply_fails_everything(self):
        for reply in ("", "I renamed everything to be idiomatic.", block(ORIGINAL_FILE)[:20]):
            self.assertFalse(any(self.verdicts(reply).values()), reply)

    def test_unchanged_original_fails_everything(self):
        self.assertFalse(any(self.verdicts(block(ORIGINAL_FILE)).values()))

    def test_casing_fixed_but_stutter_kept(self):
        code = GOOD_FILE.replace("HTTPClient", "AccountHTTPClient")
        self.assert_only_fails(block(code), {"type-no-stutter", "constructor-no-stutter"})

    def test_title_cased_initialism_in_type_name(self):
        code = GOOD_FILE.replace("HTTPClient", "HttpClient")
        self.assert_only_fails(block(code), {"identifier-casing"})

    def test_underscore_and_title_case_left_in_parameters(self):
        code = GOOD_FILE.replace(
            "func NewHTTPClient(baseURL string, ownerID string)",
            "func NewHTTPClient(base_url string, ownerId string)",
        ).replace("{baseURL: baseURL, ownerID: ownerID}", "{baseURL: base_url, ownerID: ownerId}")
        self.assert_only_fails(block(code), {"identifier-casing"})

    def test_get_prefix_kept(self):
        code = GOOD_FILE.replace("OwnerID()", "GetOwnerID()")
        self.assert_only_fails(block(code), {"getter-initialism"})

    def test_base_url_get_prefix_kept(self):
        self.assert_only_fails(block(GOOD_FILE.replace("BaseURL()", "GetBaseURL()")), {"getter-initialism"})

    def test_long_receiver_kept(self):
        code = GOOD_FILE.replace("(c *HTTPClient)", "(client *HTTPClient)").replace("return c.", "return client.")
        self.assert_only_fails(block(code), {"no-this-receiver"})

    def test_two_character_receiver_passes(self):
        code = GOOD_FILE.replace("(c *HTTPClient)", "(hc *HTTPClient)").replace("return c.", "return hc.")
        self.assert_all_pass(block(code))

    def test_this_receiver_kept(self):
        code = GOOD_FILE.replace("(c *HTTPClient) OwnerID", "(this *HTTPClient) OwnerID").replace(
            "return c.ownerID", "return this.ownerID")
        self.assert_only_fails(block(code), {"no-this-receiver"})


if __name__ == "__main__":
    unittest.main()
