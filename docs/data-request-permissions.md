# Data-request approval and runtime permissions

An enquiry's approval is the permission to build, commit and push its in-scope
request code, including generated extract SQL and count-only probes. The engineer
does not need a second governance permission step. The analyst checks delivered
elements against the approval during review, before release
([#445 decision](https://github.com/nq-rdl/agent-extensions/issues/445#issuecomment-5890963065)).
Known restrictions still apply; unchecked approval is not a build blocker.

## Engineer-owned Claude Code configuration

Only the engineer may add permission rules to their settings. This catalog does
not install or edit those rules. A rule is a narrowly reviewed allowance for a
request repository, not a blanket allowlist for Git, SQL, Bash or all repositories.
Use Claude Code's [permission settings](https://code.claude.com/docs/en/permissions)
to review the actual rule syntax, precedence, settings scope and mode behaviour
for the installed version before applying anything.

Before starting an authorised build session, the engineer can review allowances
for committing generated request SQL/probes and pushing the agreed enquiry
branch. Keep the configuration local to the request repository, name the intended
Git commands and remote/branch, and review exactly which arguments the rules
match. Do not include warehouse execution, publishing releases, merging, writing
to service-desk, pushing to `main`, or bypassing hooks. Rules do not skip the
repository's PII scan, tests or other mandatory checks. Never allowlist patient
values to make a check pass.

Task authority and runtime permission are different. A commit allowance does not
authorise a triage-only session to write, nor does a probe allowance authorise a
warehouse run. Keep extract data and patient values out of commits and messages.

## If the runtime denies an action

Report the denied action and the actual reason, then stop that action. Do not
retry a denied action in another form, split or disguise the command, route it
through another agent, or disable a check. The agent must not change settings to
make the action pass. The engineer owns any separate host-configuration review;
this guidance does not promise that an allow rule overrides an auto-mode
classifier or another runtime control. No such override was tested here.
