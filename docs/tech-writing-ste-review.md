# Technical-writing completion review

The `tech-writing` plugin runs a blocking review of documentation produced with
`/tech-writing:copyedit` or `tech-writing:author`. Its simplified STE profile
adds concrete checks for sentence length, instructions, conditions, terminology,
and meaning. It does not establish full ASD-STE100 compliance.

## Sources and design decisions

Reviewed [SimpleEnglish](https://github.com/AminBlg/SimpleEnglish) at commit
`6fa7943df766d73000b6ef8a184b012ac72b136e`, including its skill, rule catalog,
dictionary workflow, activation hook, file linter, reply hook, and tests.

| Upstream behaviour | Decision here |
|---|---|
| Loads writing rules at every session start | Scope review to current tasks using this writing plugin |
| Reports file findings after writes | Inspect the actual document before completion |
| Returns an advisory message for reply defects | Block completion with concrete findings and recheck corrections |
| Applies a five-sentence chat cap and formatting bans | Keep chat and blog output outside this documentation profile |
| Replaces normative modals and defaults to US spelling | Preserve requirement semantics and the project’s established locale |
| Extracts dictionary lists from a locally supplied standard | Keep the official dictionary separate; do not claim a subset proves compliance |

The implementation uses Claude’s native agent hook. It adds no Node.js or
Python runtime dependency. The small Stylepedia reminder uses the existing
Bash and jq pattern; the review gate does not depend on that reminder succeeding.

## Hook behaviour

`Stop` reviews the current task when it uses copyedit or author.
`SubagentStop` reads the completed worker’s own transcript and applies the same
task scope, including workers given the author delegation outline. It skips
unrelated work; no retired agent-name matcher is used.
The reviewer inspects the document files or conversation draft, then returns
`ok: false` with actionable findings, or `ok: true` when the applicable checks
pass. It does not accept an assertion that the check passed instead of reading
the deliverable. It rechecks corrections even when `stop_hook_active` is true.

The review is read-only and applies to prose created or changed for the task.
It preserves code, literals, labels, facts, uncertainty, and normative language.
An explicit user cancellation or an honest report of an external blocker can
end the task without asserting success.

Claude’s agent hooks are experimental model reviews. They incur model calls,
have a timeout, and are subject to Claude’s repeated-block limit. A disabled
hook, timeout, model error, or forced stop is not a successful review. See the
[Claude hook reference](https://code.claude.com/docs/en/hooks#agent-based-hooks).

## Full ASD-STE100 verification

[ASD’s overview](https://www.asd-ste100.org/about_STE.html) explains that the
standard combines writing rules with a controlled dictionary. Issue 9 is the
current issue checked for this work. Request an
[official copy](https://www.asd-ste100.org/STE_downloads.html) for full vocabulary
and rule verification. The simplified profile deliberately retains our locale
and normative-language exceptions; do not label it full compliance.

## Validation

Local pipeline tests cover hook packaging, advisory event routing, silent
handling of malformed inputs, and the different config requirements for command
and model hooks. A live Claude Code 2.1.271 integration test used a temporary
document containing `The service is ready; restart it.` The native completion
hook blocked the first attempt. Claude changed it to two sentences, and the
next hook review passed. Separate reviewer fixtures rejected a contraction and
semicolon while accepting normative `MUST` and `MAY` wording.

These checks demonstrate the blocking and correction path. They do not prove
complete grammar, dictionary, or standard compliance.
