"""A stand-in for query-builder's describe_script, for SQLREVIEW_DESCRIBE_CMD.

It follows the call contract of the helper: the SQL on stdin; exit 0 and the manifest JSON on stdout; exit 4 and a
reason on stderr for a script the reader refuses; exit 3 when it knows nothing about the script. It answers from the
shipped conformance fixtures, matching the whole script text, so it returns what the real reader is specified to.
"""
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sql = sys.stdin.buffer.read().decode("utf-8")
for path in sorted(here.glob("*.sql")):
    if path.read_bytes().decode("utf-8") != sql:
        continue
    refusal = path.with_suffix(".refusal.json")
    if refusal.exists():
        sys.stderr.write(json.loads(refusal.read_text())["error"] + " (conformance fixture)\n")
        sys.exit(4)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    manifest["library_version"] = "0.0.0-standin"
    sys.stdout.write(json.dumps(manifest))
    sys.exit(0)
sys.exit(3)
