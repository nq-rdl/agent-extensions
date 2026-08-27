House Style – Rule Sets and Tables
==================================

The long form behind ``SKILL.md``. Load the section you need; the skill's
checklist is the summary. Origin: the Proxmox Technical Writing Style Guide
(https://pve.proxmox.com/wiki/Technical_Writing_Style_Guide), itself adapted
from the Microsoft Writing Style Guide, re-based here on Australian English.

Locale
------

**Australian English (en-AU)** for everything the team authors. If a project
already spells consistently in another locale, keep that locale – a copyedit
never flips spelling.

High-drift words – the ones a model defaults to en-US on:

.. list-table::
   :header-rows: 1

   * - Pattern
     - en-AU
     - Not
   * - ``-ise`` / ``-isation``
     - organise, optimise, serialisation, initialise
     - organize, optimize
   * - ``-our``
     - colour, behaviour, favour, honour
     - color, behavior
   * - ``-re``
     - centre, metre, litre
     - center, meter
   * - ``-logue``
     - catalogue, dialogue, analogue
     - catalog, dialog (keep ``dialog`` only for a UI *dialog box*)
   * - ``-yse``
     - analyse, paralyse
     - analyze
   * - noun / verb pairs
     - licence (noun) / license (verb); practice (noun) / practise (verb)
     - license for both
   * - doubled ``l``
     - cancelled, modelling, labelled, enrolment (single ``l``), fulfil
     - canceled, modeling, labeled
   * - other
     - grey, programme (an agenda) but program (software), disc (optical) but disk (magnetic), artefact
     - gray, artifact

Dashes, en-AU style (Australian Government Style Manual):

- **Spaced en dash** ( – ) to set off a parenthetical or an abrupt turn:
  "The information – numbers, configuration, and text – lives in a container."
- **Unspaced en dash** for ranges and spans: 10–20 ms, 2024–2026, pages 3–7.
- No em dashes (—). No double hyphens.
- Hyphen only inside words: read-only, command-line tool.

Dates in prose: 27 August 2026. In machine-readable places: ISO 8601
(``2026-08-27``).

Person and mood
---------------

.. list-table::
   :header-rows: 1

   * - Content
     - Use
     - Example
   * - Description – introducing a feature, telling the reader what happens
     - Third-person indicative
     - "A technician inserts the memory card into the card slot."
   * - Instruction – telling the reader what to do
     - Second-person imperative, present tense
     - "Insert the memory card into the card slot."
   * - Recommendation
     - "We recommend …" – the one permitted first-person plural
     - "We recommend a dedicated network for storage traffic."

Rules that follow:

- Never first-person singular ("I", "me") in documentation.
- Avoid "we" when the subject is the product or the project:
  "Proxmox VE supports two virtualisation technologies", not "We implemented
  two virtualisation technologies".
- Never "one" as a pronoun – it reads as archaic and over-formal.
- No modal verbs in instructions. "Click **Save**", not "You should click
  Save". *Should*, *could*, *might* hedge an instruction into a suggestion.
- "You" is fine in descriptions and makes simpler sentences; prefer the
  imperative form where it exists: "To create a container, …" over
  "You can create a container by …".

Purpose before action
---------------------

Put the important information first. State the purpose, then the action, so
the reader can skip the instruction when the purpose does not apply.

.. list-table::
   :header-rows: 1

   * - Not
     - Write
   * - To enable quick and easy integration with third-party tools, Proxmox VE offers a RESTful API.
     - Proxmox VE offers a RESTful API to enable quick and easy integration with third-party tools.
   * - Click Delete if you want to delete the entire document.
     - To delete the entire document, click **Delete**.
   * - Click File > New > Document to start a new document.
     - To start a new document, click **File > New > Document**.

Sentence length: aim for an average of 15–20 words. Vary length and openings.
A sentence that lists three or more items usually works better as a list.

Procedures
----------

A procedure is a numbered sequence of steps for one task.

- **Heading** in gerund style, same style throughout the document: "Closing
  the program".
- **Intro sentence** adds context without repeating the heading: "To do this
  with something, follow these steps:".
- **Each step** is one meaningful action that answers "what do I do next?" –
  imperative verb, parallel structure across steps.
- **Single-step procedure** – a bullet, never ``1.``::

     Closing the program

     * To close the program, choose Exit on the File menu.

- **Sub-steps** take lowercase letters; sub-sub-steps take lowercase Roman
  numerals::

     1. First, do foo, as follows:
        a. Do the first part of foo.
        b. Do the second part of foo.
           i.  Do the first sub-part of foo part two.
           ii. Do the second sub-part of foo part two.
     2. Next, do bar.

- **Enter inside the step.** If the reader must press Enter after a step,
  say so in that step::

     Not:   1. Click the search box, then type custom function.
            2. Press Enter.
     Write: 1. Click the search box, then type custom function and press Enter.

- Sequence words take a comma: "First, …", "Then, …", "After that, …".

Lists
-----

- Three or more items in a row inside running text → pull them out as a list.
- Bullet list when the items are options with no required order; numbered
  list when the reader performs or reads them in order.
- One style per list – either every item is a full sentence ending in a full
  stop, or every item is a fragment with no end punctuation. Capitalise the
  first word either way.
- Term-and-definition items: **bold the term**, plain text for the definition.
- Link-and-description items: the link first, the description indented on the
  line beneath.

Headings
--------

Title case for H1 and H2; sentence case for H3 and below.

Title-case rules:

- Always capitalise the first and last word: *A Home to Go Back To*.
- Do not capitalise *a*, *an*, *the* unless first: *Proxmox on the Issue*.
- Do not capitalise prepositions of four letters or fewer (on, to, in, up,
  down, of, for, with) unless first or last: *How to Install Proxmox VE*.
- Do not capitalise *and*, *but*, *or*, *nor*, *yet*, *so* unless first or
  last: *Monitoring and Operating a Cluster*.
- Capitalise everything else – nouns, verbs (including *is* and other forms
  of *be*), adverbs, adjectives, pronouns (*this*, *that*, *its*).
- Capitalise the second half of a hyphenated compound if it would be
  capitalised alone, or if it is the last word: *Hyper-Converged
  Infrastructure*.
- Keep UI labels and API terms in their own casing (``fdisk`` stays
  lowercase).

Sentence-case rules: capitalise the first word and proper nouns only;
capitalise the first word after a colon: *Network: Setup and configuration*.

Punctuation
-----------

If a sentence needs more than a comma or two, rewrite it.

Use a comma:

- Oxford (serial) comma in a list of three or more: "the dancers, John, and
  David" – without it, John and David *are* the dancers.
- Before a coordinating conjunction (*and, but, for, or, nor, so, yet*) that
  joins two independent clauses: "I went running, and I saw a duck." No comma
  when the second verb shares the subject: "I went running and saw a duck."
- After an introductory phrase or adverb: "With the app, you can call any
  phone." "Finally, the job runs."
- After a sequence word: "First, pour the milk."
- After a dependent clause that opens the sentence: "When the job finishes,
  the log rotates."
- Between two adjectives that modify the same noun: "the big, mean duck".

Do not use a comma:

- To join two independent clauses without a conjunction – use a semicolon:
  "Select **Options**; then select **Enable fast saves**."
- Between the verbs of a compound predicate: "The installer evaluates the
  system and then copies the files."

Slashes: a slash means a combination – *client/server*, *TCP/IP*; capitalise
the second word if the first is capitalised. Never a slash for "or": write
"product or service".

Hyphens – hyphenate two or more words that modify a noun as a unit when:

- confusion would result without it: *read-only memory*, *built-in drive*;
  *command-line tool* (adjective) but *the Linux command line* (noun);
- one word is a participle: *left-aligned text*, *well-defined schema*;
- the modifier is a number or single letter plus a noun: *two-sided arrow*,
  *5-point star*.

Hyphenate a compound noun whose first part is abbreviated: *e-book*,
*e-commerce*, *e-bike* – but *email*.

Words
-----

- **Contractions** – common ones are fine and read naturally: *it's*,
  *you're*, *that's*, *don't*. Never contract a noun with a verb: "Proxmox is
  the leading …", not "Proxmox's the leading …".
- **Abbreviations** – none out of laziness. Not *approx.* (write "about");
  avoid *etc.* – it is usually redundant after "such as". Avoid *e.g.* and
  *i.e.*: write "for example" and "that is", or *for instance*, *namely*,
  *such as*, *in particular*, *specifically*. If a template forces them, they
  are "e.g.," and "i.e.," with the comma.
- **Acronyms** – spell out on first use with the acronym in brackets:
  "Kernel Samepage Merging (KSM)". Do not introduce an acronym you use only
  once. Commonly known acronyms need no expansion: USB, HTML, URL, FAQ, API,
  CPU, RAM, SSH.
- **Jargon, slang, idioms** – use the familiar term: *symbol*, not *glyph*.
- **Gender** – singular *they/them/their*; if it reads awkwardly, drop the
  pronoun or switch to the imperative.
- **Data** is singular: "the data is stored".
- **A / an** by sound: *an MGC* (em-gee-see), *a URL* (you-are-el),
  *a historical*, *an hour*, *a European*.

Terminology
-----------

Stick to one term per concept. On first use, add the alternatives readers
search for, in brackets: "A USB flash drive (USB stick) is the recommended
installation medium." Keep an *Instead of → Use* table in the project's docs;
start from this shape and extend it as choices are settled:

.. list-table::
   :header-rows: 1

   * - Instead of
     - Use
   * - mainboard, main board
     - motherboard
   * - USB stick, usb drive, flash drive, thumb drive
     - USB flash drive
   * - Web UI, WebUI, webinterface
     - web interface, web UI, or GUI
   * - life cycle
     - lifecycle
   * - e-mail
     - email
   * - HOWTO
     - how-to (guide)
   * - the Web
     - the web

**The brand is not the product.** A company name alone does not identify a
version or a thing to install: "Proxmox 3.4" names nothing – write "Proxmox
VE 3.4" or "Proxmox Backup Server 3.1". Same shape everywhere: "Red Hat 9"
→ "Red Hat Enterprise Linux 9"; "Posit" → "Posit Workbench" or "Posit
Connect". In public or formal text, use the full product name.

Vendor casing – always the vendor's own:

.. list-table::
   :header-rows: 1

   * - Not
     - Write
   * - ProxMox, proxmox
     - Proxmox VE, Proxmox Server Solutions GmbH
   * - centos, CENTOS
     - CentOS
   * - VMWARE, Vmware
     - VMware
   * - openvz
     - OpenVZ
   * - ceph
     - Ceph (Ceph Filesystem, Ceph Object Storage, Ceph Block Devices)
   * - MacOS, OSX
     - macOS
   * - Github, gitlab
     - GitHub, GitLab
   * - Postgres SQL, postgresql
     - PostgreSQL
   * - NodeJS, node.js
     - Node.js
   * - Javascript, Typescript
     - JavaScript, TypeScript
   * - kubernetes, K8S
     - Kubernetes (K8s only after first use)
   * - html, json, yaml (in prose)
     - HTML, JSON, YAML

Examples
--------

An example must be clear, **correct**, and **tested**. Better no example than
a wrong one. Show the command and its expected output; pin the version the
example was tested against.

Canonical sources
-----------------

Read these when a question is not settled here and being wrong would mislead:

- Australian Government Style Manual – spelling, punctuation, dashes, dates:
  https://www.stylemanual.gov.au/
- Microsoft Writing Style Guide – the Proxmox guide's own primary source, for
  everything grammar and formatting:
  https://learn.microsoft.com/en-us/style-guide/welcome/
- Microsoft A–Z word list – casing and hyphenation of technical terms (the
  *command-line* entry is the one the Proxmox guide cites):
  https://learn.microsoft.com/en-us/style-guide/a-z-word-list-term-collections/c/command-line
- Australian Government Style Manual – dashes and spelling pages:
  https://www.stylemanual.gov.au/grammar-punctuation-and-conventions/punctuation/dashes
  https://www.stylemanual.gov.au/grammar-punctuation-and-conventions/spelling
- Google developer documentation style guide – procedures:
  https://developers.google.com/style/procedures
- Origin: Proxmox Technical Writing Style Guide (a wiki page in flux; take the
  decisions, not the prose):
  https://pve.proxmox.com/wiki/Technical_Writing_Style_Guide
