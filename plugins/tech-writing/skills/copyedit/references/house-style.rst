House style – tables and examples
=================================

The long form behind ``SKILL.md``: only what the checklist does not carry.
Origin: the Proxmox Technical Writing Style Guide, itself adapted from the
Microsoft Writing Style Guide, re-based here on Australian English (the
Australian Government Style Manual is the locale authority).

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
   * - ``-ise`` and ``-isation``
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
   * - noun and verb pairs
     - licence (noun) but license (verb); practice (noun) but practise (verb)
     - license for both
   * - doubled ``l``
     - cancelled, modelling, labelled, enrolment (single ``l``), fulfil
     - canceled, modeling, labeled
   * - other
     - grey, artefact, program (every sense – Macquarie gives no *programme*), disc (optical) but disk (magnetic)
     - gray, artifact, programme

Dashes – a house decision informed by the Style Manual, which recommends en
dashes and notes spaced en dashes read better with screen readers:

- **Spaced en dash** ( – ) sets off a parenthetical or an abrupt turn: "The
  information – numbers, configuration, and text – lives in a container."
- **Unspaced en dash** for a span: 10–20 ms, 2024–2026, pages 3–7. **Never
  mix** *from* or *between* with an en dash: "from 10 to 20 ms", "between
  2024 and 2026". In running prose the Manual prefers the phrase over the
  dash; the dash is fine in tables and technical content.
- No em dashes (—); no double hyphens. Hyphens only inside words.

Dates: in prose, "27 August 2026" (day month year, no comma, no ordinal).
Numeric dates that people read, such as table cells: ``27/8/2026``. ISO 8601
(``2026-08-27``) only in data, logs, and filenames – the Manual lists it under
"not this" for human-facing text.

Headings
--------

Sentence case for every heading level: capitalise the first word, proper
nouns, and the first word after a colon.

- Running a hyper-converged infrastructure with Proxmox VE
- Network: Setup and configuration
- Closing the program

UI labels and command names keep their own casing (``fdisk`` stays
lowercase). This is a deliberate deviation from the Proxmox origin, which
title-cases H1 and H2; both the Style Manual and Microsoft prescribe sentence
case, and it removes a rule set nobody applies consistently.

Procedures
----------

Single-step procedure – a bullet, never ``1.``::

   Closing the program

   * To close the program, choose Exit on the File menu.

Sub-steps take lowercase letters; sub-sub-steps take lowercase Roman
numerals::

   1. First, do foo, as follows:
      a. Do the first part of foo.
      b. Do the second part of foo.
         i.  Do the first sub-part of foo part two.
         ii. Do the second sub-part of foo part two.
   2. Next, do bar.

Enter inside the step::

   Not:   1. Click the search box, then type custom function.
          2. Press Enter.
   Write: 1. Click the search box, then type custom function and press Enter.

Sequence words take a comma: "First, …", "Then, …", "After that, …".

Front-loading, both directions
------------------------------

.. list-table::
   :header-rows: 1

   * - Kind
     - Not
     - Write
   * - Instruction – purpose first
     - Click Delete if you want to delete the entire document.
     - To delete the entire document, click **Delete**.
   * - Instruction – purpose first
     - Click File > New > Document to start a new document.
     - To start a new document, click **File > New > Document**.
   * - Description – subject first
     - To enable quick and easy integration with third-party tools, Proxmox VE offers a RESTful API.
     - Proxmox VE offers a RESTful API to enable quick and easy integration with third-party tools.

Person and mood – the bad forms
-------------------------------

.. list-table::
   :header-rows: 1

   * - Not
     - Write
     - Why
   * - We implemented two virtualisation technologies.
     - Proxmox VE supports two virtualisation technologies.
     - the product, not "we", is the subject of a description
   * - You should click Save.
     - Click **Save**.
     - a modal turns an instruction into a suggestion
   * - One must restart the service.
     - Restart the service.
     - "one" reads as archaic and over-formal
   * - You can create a container by running …
     - To create a container, run …
     - imperative form where one exists

Abbreviations
-------------

Alternatives to *e.g.* and *i.e.* beyond "for example" and "that is": *for
instance*, *namely*, *such as*, *in particular*, *specifically*. Avoid
*etc.* after "such as" – it is redundant: "fruit such as apples, oranges, and
bananas".

Terminology
-----------

Starter *Instead of → Use* table – copy into the project's docs and extend it
as choices are settled:

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

Canonical sources
-----------------

The URLs are kept in ``SKILL.md`` (the link checker covers ``*.md`` only).
Read the Style Manual for en-AU spelling, punctuation, dashes, and dates, and
the Microsoft Writing Style Guide for everything else; where the house
decisions conflict with either, the house decisions win.
