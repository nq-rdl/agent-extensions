import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

// Assert against the canonical authoring source of truth. sync-plugins.sh copies
// these bodies verbatim into the plugin tree (only frontmatter `name:` is stripped
// for grouping, which validate-plugins.sh already guards).
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SKILLS_DIR = path.join(ROOT, "skills");

function readSkill(name) {
  return fs.readFileSync(path.join(SKILLS_DIR, `codex-${name}`, "SKILL.md"), "utf8");
}

function frontmatter(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---/);
  assert.ok(match, "SKILL.md must open with a YAML frontmatter block");
  return match[1];
}

// One skill per deprecated upstream slash command (1:1 command -> skill mapping).
// Value is the companion subcommand the body must forward to; `rescue` is the
// exception — it routes to the codex-rescue subagent instead.
const ACTION_SKILLS = {
  setup: "setup",
  review: "review",
  "adversarial-review": "adversarial-review",
  rescue: null,
  result: "result",
  status: "status",
  transfer: "transfer",
  cancel: "cancel"
};

for (const [name, sub] of Object.entries(ACTION_SKILLS)) {
  test(`codex-${name}: named, user-invocable, and forwards correctly`, () => {
    const src = readSkill(name);
    const fm = frontmatter(src);
    assert.match(fm, new RegExp(`^name:\\s*codex-${name}\\s*$`, "m"), "must declare its canonical name");
    assert.match(fm, /^user-invocable:\s*true\s*$/m, "must be user-invocable");

    if (name === "rescue") {
      // rescue delegates to the subagent (agent id unchanged across the fork).
      assert.match(src, /subagent_type:\s*"codex:codex-rescue"/, "rescue must route to the subagent");
    } else {
      assert.ok(
        src.includes(`codex-companion.mjs" ${sub} `),
        `codex-${name} must forward the ${sub} subcommand`
      );
      assert.ok(src.includes("$ARGUMENTS"), `codex-${name} must forward $ARGUMENTS`);
    }
  });
}

test("review and adversarial-review enforce a verbatim output contract", () => {
  for (const name of ["review", "adversarial-review"]) {
    const src = readSkill(name);
    assert.match(src, /verbatim, exactly as-is/i, `codex-${name} must return stdout verbatim`);
    assert.match(src, /Do not paraphrase/i, `codex-${name} must forbid paraphrasing`);
  }
});

test("result and status forbid summarizing the companion output", () => {
  for (const name of ["result", "status"]) {
    const src = readSkill(name);
    assert.match(src, /Do not summarize or condense/i, `codex-${name} must present output verbatim`);
  }
});

test("rescue documents the GPT-5.6 effort ladder and model aliases", () => {
  const src = readSkill("rescue");
  // ultra is Sol/Terra only; the effort ladder has no `minimal` rung.
  assert.match(src, /`low`, `medium`, `high`, `xhigh`, `max`, and `ultra`/);
  assert.doesNotMatch(src, /minimal/i);
  assert.match(src, /gpt-5\.6-sol/);
  assert.match(src, /gpt-5\.6-terra/);
  assert.match(src, /gpt-5\.6-luna/);
  assert.match(src, /gpt-5\.3-codex-spark/);
});
