"""Round-trip tests for the bitwarden skill's shell owner, skills/bitwarden/scripts/bw-env.sh.

A fake ``bw`` on PATH stands in for the Bitwarden CLI; no real vault, account or
credential is used. The stub mirrors the observable behaviour of @bitwarden/cli
2026.9.0 that the functions depend on: ``create item`` and ``edit item`` read the
base64 request from an argument or stdin and print the full item JSON (notes
included) to stdout, ``get notes`` prints the notes, and a missing item fails with
``Not found.`` on stderr.

Every value in the fixture .env is a fake marker string. The tests assert that
``bwc``/``bwu``/``bwe``/``bwunload`` load the values with dotenv semantics and never
echo any of them to stdout or stderr (the output a model reads back).
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "skills" / "bitwarden" / "scripts" / "bw-env.sh"
PACKAGED = REPO / "plugins" / "bitwarden" / "skills" / "secrets" / "scripts" / "bw-env.sh"

FAKE_BW = r'''#!/usr/bin/env python3
"""Fake Bitwarden CLI for tests. State lives in $BW_STUB_DIR/items.json."""
import base64, json, os, sys, uuid

state = os.path.join(os.environ["BW_STUB_DIR"], "items.json")
items = json.load(open(state)) if os.path.exists(state) else []
args = [a for a in sys.argv[1:]]
if "--session" in args:
    i = args.index("--session"); del args[i:i + 2]
args = [a for a in args if a not in ("--raw", "--pretty", "--nointeraction")]

def save():
    json.dump(items, open(state, "w"))

def find(key):
    hits = [it for it in items if it["id"] == key] or [it for it in items if it["name"] == key]
    if not hits:
        sys.stderr.write("Not found.\n"); sys.exit(1)
    if len(hits) > 1:
        sys.stderr.write("More than one result was found.\n"); sys.exit(1)
    return hits[0]

def request(rest):
    raw = rest[0] if rest else sys.stdin.read()
    return json.loads(base64.b64decode(raw.strip()))

cmd = args[:2]
if args[:1] == ["unlock"]:
    print("FAKE-SESSION-KEY")
elif args[:1] == ["encode"]:
    sys.stdout.write(base64.b64encode(sys.stdin.read().encode()).decode())
elif cmd == ["get", "template"]:
    print(json.dumps({"type": 1, "name": "Item name", "notes": "Some notes about this item.",
                      "secureNote": None, "fields": [], "login": None}))
elif cmd == ["create", "item"]:
    item = request(args[2:]); item["id"] = str(uuid.uuid4()); items.append(item); save()
    print(json.dumps(item))
elif cmd == ["edit", "item"]:
    old = find(args[2]); new = request(args[3:]); new["id"] = old["id"]
    items[items.index(old)] = new; save(); print(json.dumps(new))
elif cmd == ["get", "item"]:
    print(json.dumps(find(args[2])))
elif cmd == ["get", "notes"]:
    print(find(args[2]).get("notes") or "")
elif cmd == ["list", "items"]:
    term = args[args.index("--search") + 1] if "--search" in args else ""
    print(json.dumps([it for it in items if term.lower() in it["name"].lower()]))
elif cmd == ["delete", "item"]:
    items.remove(find(args[2])); save()
else:
    sys.stderr.write("fake bw: unsupported %r\n" % (args,)); sys.exit(2)
'''

# Fake values only. Each marker is unique so a leak is unambiguous.
DOTENV = textwrap.dedent(
    """\
    # comment line stays harmless
    export ALREADY_EXPORTED=FAKE-EXP-1111

    PLAIN=FAKE-PLAIN-2222
    DOUBLE="FAKE-DOUBLE 3333"
    SINGLE='FAKE-SINGLE $NOT_EXPANDED 4444'
    UNQUOTED_SPACE=FAKE-SPACE 5555
    DOLLAR=FAKE-DOLLAR$HOME-6666
    EMPTY=
    APOS=FAKE-it's-8888
    INLINE=FAKE-INLINE-9999 # trailing comment
    """
)

EXPECTED = {
    "ALREADY_EXPORTED": "FAKE-EXP-1111",
    "PLAIN": "FAKE-PLAIN-2222",
    "DOUBLE": "FAKE-DOUBLE 3333",
    "SINGLE": "FAKE-SINGLE $NOT_EXPANDED 4444",
    "UNQUOTED_SPACE": "FAKE-SPACE 5555",
    "DOLLAR": "FAKE-DOLLAR$HOME-6666",
    "EMPTY": "",
    "APOS": "FAKE-it's-8888",
    "INLINE": "FAKE-INLINE-9999",
}
MARKERS = ["1111", "2222", "3333", "4444", "5555", "6666", "8888", "9999"]


class BwEnvRoundTrip(unittest.TestCase):
    script = CANONICAL

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        (bindir / "bw").write_text(FAKE_BW)
        (bindir / "bw").chmod(0o755)
        (self.tmp / "state").mkdir()
        (self.tmp / "work").mkdir()
        (self.tmp / "work" / ".env").write_text(DOTENV)
        self.env = {
            "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.tmp),
            "BW_STUB_DIR": str(self.tmp / "state"),
        }

    def sh(self, body):
        """Run bash with bw-env.sh sourced; returns the CompletedProcess."""
        prog = f'set -u\nsource "{self.script}"\n{body}\n'
        return subprocess.run(["bash", "-c", prog], capture_output=True, text=True,
                              env=self.env, cwd=self.tmp / "work", timeout=60)

    def stored_notes(self):
        items = json.loads((self.tmp / "state" / "items.json").read_text())
        return {it["name"]: it["notes"] for it in items}

    def assert_no_secret(self, proc):
        out = proc.stdout + proc.stderr
        for marker in MARKERS:
            self.assertNotIn(marker, out, f"secret value marker {marker} was printed:\n{out}")

    def dump_loaded(self):
        names = " ".join(EXPECTED)
        return f'for v in {names}; do printf "%s=%s\\0" "$v" "${{!v-<unset>}}" >> "$HOME/loaded"; done'

    def read_loaded(self):
        raw = (self.tmp / "loaded").read_text()
        return dict(pair.split("=", 1) for pair in raw.split("\0") if pair)

    def test_script_present_in_both_trees(self):
        self.assertTrue(CANONICAL.is_file())
        self.assertEqual(CANONICAL.read_bytes(), PACKAGED.read_bytes(),
                         "plugin copy is stale: run pixi run bash scripts/sync-plugins.sh bitwarden")

    def test_bwc_then_bwe_loads_dotenv_values(self):
        proc = self.sh('bwc fake-app-dev && bwe fake-app-dev && ' + self.dump_loaded())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_loaded(), EXPECTED)

    def test_bwc_and_bwe_do_not_print_secret_values(self):
        proc = self.sh("bwc fake-app-dev && bwe fake-app-dev")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_no_secret(proc)

    def test_stored_note_is_export_lines(self):
        proc = self.sh("bwc fake-app-dev")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for line in self.stored_notes()["fake-app-dev"].splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                self.assertRegex(line, r"^export [A-Za-z_][A-Za-z0-9_]*=")

    def test_bwu_updates_without_printing(self):
        (self.tmp / "work" / "new.env").write_text("PLAIN=FAKE-NEWVALUE-7777\n")
        proc = self.sh("bwc fake-app-dev && bwu fake-app-dev new.env && bwe fake-app-dev && "
                       'printf "%s" "$PLAIN" > "$HOME/plain"')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("7777", proc.stdout + proc.stderr)
        self.assert_no_secret(proc)
        self.assertEqual((self.tmp / "plain").read_text(), "FAKE-NEWVALUE-7777")

    def test_bwunload_unsets_loaded_names(self):
        proc = self.sh("bwc fake-app-dev && bwe fake-app-dev && bwunload fake-app-dev && "
                       + self.dump_loaded())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(set(self.read_loaded().values()), {"<unset>"})

    def test_bwe_missing_item_fails_cleanly(self):
        proc = self.sh("bwe no-such-item")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no-such-item", proc.stderr)

    def test_bwe_refuses_note_with_non_assignment_lines(self):
        payload = {"type": 2, "name": "hostile", "notes": "export OK=1\ntouch \"$HOME/pwned\"\n",
                   "secureNote": {"type": 0}, "id": str(uuid.uuid4())}
        (self.tmp / "state" / "items.json").write_text(json.dumps([payload]))
        proc = self.sh("bwe hostile")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.tmp / "pwned").exists(), "bwe evaluated a non-assignment line")


class PackagedBwEnvRoundTrip(BwEnvRoundTrip):
    """Same checks against the copy an installed plugin ships."""

    script = PACKAGED


if __name__ == "__main__":
    unittest.main()
