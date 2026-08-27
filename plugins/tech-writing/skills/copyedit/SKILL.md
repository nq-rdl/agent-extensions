---
license: CC-BY-4.0
description: >-
  Apply the house technical-writing style when writing or copyediting
  documentation, READMEs, changelogs, how-to guides, runbooks, and docs-site
  pages. Use when asked to copyedit, proofread, tidy, or "make this read
  better", when drafting user-facing docs, or when a reviewer asks which
  person, mood, punctuation, or spelling to use. Encodes the decisions the
  team has made (en-AU, spaced en dash, imperative instructions, purpose
  before action, no e.g./i.e.), not general grammar.
argument-hint: "Paste or point at the prose to copyedit, or say what you are about to write (for example 'README install section')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
  origin: https://pve.proxmox.com/wiki/Technical_Writing_Style_Guide
---

# Tech Writing – Copyedit to House Style

These are the *decisions* a fresh writer makes inconsistently, not a grammar
lesson. Your default grammar is fine; apply the rules below on top of it. They
derive from the Proxmox Technical Writing Style Guide (see `metadata.origin`),
adapted to this team's locale.

## Locale: en-AU, spaced en dash

- Spell in **Australian English**: organise, colour, behaviour, catalogue,
  analyse, *licence* (noun) / *license* (verb). Exception: if the project
  already has a consistent spelling, keep it – never flip a project's locale in
  a copyedit.
- Set off a parenthetical with a **spaced en dash** ( – ), not an em dash (—)
  and not a hyphen. Use an unspaced en dash for ranges (10–20 ms, 2024–2026).
- Full rules and the high-drift word list: `references/house-style.rst`
  → *Locale*.

## Person and mood follow the content type

| Content | Person and mood | Never |
|---|---|---|
| Description – what a thing is or does | Third-person indicative: "The scheduler retries failed jobs." | "one", "I" |
| Instruction – what the reader does | Second-person imperative, present tense: "Insert the card." | modal verbs (*should*, *could*, *might*), "I", "we" |
| Recommendation | "We recommend …" is the one permitted "we" | – |

Prefer "To create a container, run …" over "You can create a container by …".
Blog posts and personal write-ups may use first person; documentation does not.

## Purpose before action

State the purpose first so the reader can skip what does not apply:
"To delete the entire document, click **Delete**." Not "Click Delete if you
want to delete the entire document." Applies to sentences and to procedure
steps alike. Put the important information at the front of the sentence.

## Procedures

- Give a procedure a gerund heading ("Closing the program") and an intro
  sentence that adds context without repeating the heading.
- One meaningful action per step, imperative, parallel structure.
- **A single-step procedure is a bullet, not "1."**
- Sub-steps are `a.`, `b.`; sub-sub-steps are `i.`, `ii.`.
- **"Press Enter" belongs inside the step it completes**, never as its own step.
- Average 15–20 words a sentence; three or more items inline become a list.

## Lists

- Bullets for options in no required order; numbers when order matters.
- One style per list: **all** full sentences ending in a full stop, or **all**
  fragments with no end punctuation. Never mix.
- Term–definition items: bold the term, plain text for the definition.
- Link-plus-description items: link first, description indented beneath.

## Punctuation decisions

- Oxford comma in lists of three or more.
- Comma after a sequence word that opens a sentence: "First, …", "Then, …".
- Two independent clauses with no conjunction take a semicolon, not a comma.
  No comma inside a compound predicate ("evaluates the system and then copies
  the files").
- A slash means a combination (TCP/IP, client/server). **Never use a slash for
  "or"** – write "product or service".
- Hyphenate a compound modifier before a noun: *command-line tool* but
  *the command line*; *read-only*, *well-defined*, *5-point*. *e-book*,
  *e-commerce*, but *email*.

## Words

- Contractions are fine (*it's*, *don't*, *you're*); never contract a noun
  ("Proxmox's the leading …").
- No *approx.* (write "about"), no *etc.*, no *e.g.* or *i.e.* – write
  "for example" and "that is". If a house template forces one, it is
  "e.g.," and "i.e.," with the comma.
- Spell an acronym out on first use with the acronym in brackets – "Kernel
  Samepage Merging (KSM)" – then use the acronym. **Do not introduce an acronym
  you use only once.** Common ones (USB, HTML, URL, API) need no expansion.
- Singular *they*; *data* is singular; the familiar word wins ("symbol", not
  "glyph").

## Terminology

- One term per concept for the whole document. On first use, add the synonyms
  readers search for in brackets: "a USB flash drive (USB stick)".
- Keep an *Instead of → Use* terms table in the project's docs and extend it
  when you settle a choice.
- **The brand is not the product.** "Proxmox 3.4" names nothing – write
  "Proxmox VE 3.4". Use the vendor's casing (CentOS, VMware, macOS); starter
  table in `references/house-style.rst` → *Terminology*.

## Headings and examples

- Title case for H1 and H2, sentence case for H3 and below; capitalise the
  first word after a colon. Full title-case rules in the reference.
- An example must be correct and tested. No example beats a bad one.

## Copyedit pass

When invoked on a passage:

1. Name the content type (description, instruction, recommendation) and set
   person and mood accordingly.
2. Fix purpose-before-action, modal verbs, and first person.
3. Fix procedures and lists (single-step bullet, Enter inside the step,
   consistent list punctuation).
4. Fix words: abbreviations, acronyms, one term per concept, en-AU spelling.
5. Fix punctuation: Oxford comma, semicolon, slash, hyphen, spaced en dash.
6. Report each change as *before → after* with the rule that drove it.

Do not change meaning, code, commands, file paths, UI labels, or quoted
program output. Leave a project's existing locale alone.

Worked example: "You should click Save to save the file, e.g. before exiting"
→ "To save the file before exiting, click **Save**." (purpose first, no modal,
no *e.g.*).

## Verify against the canonical sources

When a question is not settled here and being wrong would mislead, read the
source rather than guessing: the Australian Government Style Manual for en-AU
spelling and punctuation, and the Microsoft Writing Style Guide (the Proxmox
guide's own primary source) for everything else. URLs in
`references/house-style.rst` → *Canonical sources*.

## References

- `references/house-style.rst` – locale word list, title-case rules, comma
  decisions, hyphen and dash rules, procedure format, terminology tables, and
  the canonical source URLs
