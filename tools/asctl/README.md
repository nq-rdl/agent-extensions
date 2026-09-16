# asctl

Repository CLI for validating canonical skills and generating discovery metadata.
Build from the repository root with Go (version requirements are in `go.mod`):

```bash
CGO_ENABLED=0 go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/
/tmp/asctl validate skills/lychee
/tmp/asctl repo-check
/tmp/asctl repo-check --size-report
/tmp/asctl repo-check --size-report skills/lychee/SKILL.md
```

`validate` checks SKILL.md frontmatter and body size. `repo-check` also checks
directory structure and discovery-prompt generation. With no paths it validates
all skills under `--skills-root` (default `skills`); paths select affected skills.
Both commands fail on bodies above the repository limit of **500 lines**.
Existing CI and local `repo-check` calls exercise the limit automatically.

The body begins after the closing frontmatter fence. All blank lines count,
including leading and trailing blanks. LF and CRLF each end one line; a final
newline does not create an extra line. A nonempty final line without a newline
counts, and an empty body has zero lines. Missing or malformed frontmatter keeps
its existing parse failure.

`--size-report` adds a table sorted by descending body lines, with skill path as
the tie-breaker. It shows:

- Body lines, using the same count as validation.
- Approximate tokens: raw UTF-8 body bytes divided by four, displayed to two
  decimal places. This includes whitespace and original line endings; it is an
  estimate, not a tokenizer result or observed model usage.
- Visible regular files recursively under `references/`, excluding hidden files,
  hidden directories, and symlinks. Missing `references/` means zero files.

Unreadable/unparseable bodies sort last. Unavailable metrics show `n/a` with a
reason. Reporting does not change validation rules, suppress existing failures,
or turn a failed metric into a new validation failure.

The 500-body-line limit is house policy, distinct from the
[Agent Skills recommendation](https://agentskills.io/specification#progressive-disclosure)
for a main file under 500 lines and an instruction body below roughly 5,000
tokens. The **300-body-line review target** is editorial, without a requirement
to create reference files solely to hit it. See
[CONTRIBUTING.md](../../CONTRIBUTING.md#skill-content-conventions) for disclosure
and description targets. Behavioral pilots must establish correctness and actual
loading costs separately; static size does not prove improvement.

Run the CLI tests and checks:

```bash
go -C tools/asctl test ./...
go -C tools/asctl vet ./...
```
