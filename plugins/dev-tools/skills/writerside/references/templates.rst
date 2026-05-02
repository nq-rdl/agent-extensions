Writerside Documentation Templates
==================================

Two standard templates for Writerside documentation: a **How-to Guide**
for technical documentation and procedures, and a **Standard Operating
Procedure** (SOP) for formal governance documents.

--------------

When to Use Which Template
--------------------------

+-----------------------+-----------------------+---------------------+
| Template              | Use When              | Examples            |
+=======================+=======================+=====================+
| **How-to Guide**      | Documenting how to do | Deployment guide,   |
|                       | something — setup,    | API integration     |
|                       | deployment,           | guide,              |
|                       | configuration, usage  | troubleshooting     |
|                       |                       | guide               |
+-----------------------+-----------------------+---------------------+
| **SOP**               | Formal procedure      | Security incident   |
|                       | requiring governance  | response, data      |
|                       | approval, compliance  | handling            |
|                       | tracking, role        | procedures, access  |
|                       | definitions           | control policies    |
+-----------------------+-----------------------+---------------------+

--------------

How-to Guide Template
---------------------

.. code:: xml

   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE topic SYSTEM "https://resources.jetbrains.com/writerside/1.0/xhtml-entities.dtd">
   <topic title="${TITLE}" id="${slug}"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:noNamespaceSchemaLocation="https://resources.jetbrains.com/writerside/1.0/topic.v2.xsd">

Guide slug: The guide slug is a single sentence that describes the
purpose of the guide, this will show in the highlight section on the
guides overview page.

   **Template Instructions:** The Guide template is to be used for
   documentation that does not fit within the formality of the “Standard
   Operating Procedure” template. Use this for how-to guides, technical
   documentation, deployment guides, operational procedures, and
   user-facing instructions. For formal governance procedures, use the
   SOP template instead.

Abstract
~~~~~~~~

[2-3 sentence summary of what this guide covers and who it’s for. Keep
it brief and actionable.]

Chapters
~~~~~~~~

Try and break your structure down into ``chapters``.

**Semantic XML:**

.. code:: xml

   <chapter title="Example chapter" id="example-chapter-id">
       <p>Some text.</p>
       <chapter title="Subchapter" id="subchapter">
           <p>Some more text.</p>
       </chapter>
   </chapter>

**Markdown equivalent:**

.. code:: markdown

   ## Example Chapter
   Some text.
   ### Subchapter
   Some more text.

To present both options in Writerside using tabs:

.. code:: xml

   <tabs>
       <tab id="chapter-semantic" title="Semantic XML">
           <code-block lang="xml">
               <![CDATA[
               <chapter title="Example chapter" id="example-chapter-id">
                   <p>Some text.</p>
                   <chapter title="Subchapter" id="subchapter">
                       <p>Some more text.</p>
                   </chapter>
               </chapter>
               ]]>
           </code-block>
       </tab>
       <tab id="chapter-markdown" title="Markdown">
           <code-block lang="markdown">
           ## Example Chapter
           Some text.
           ### Subchapter
           </code-block>
       </tab>
   </tabs>

Introduction
~~~~~~~~~~~~

   The Introduction is always your first chapter. Explain what the
   reader will learn, why it matters, and any important context.

[Your introduction content here]

[Your Chapter Title Here]
~~~~~~~~~~~~~~~~~~~~~~~~~

   From here, structure your guide however makes sense for your content.
   Common patterns include: - Prerequisites → Setup → Usage →
   Troubleshooting - Overview → Configuration → Verification - Problem →
   Solution → Implementation

[Your content here]

--------------

Template Features and Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using Procedures
^^^^^^^^^^^^^^^^

When documenting step-by-step instructions, use ``<procedure>`` and
``<step>`` tags:

.. code:: xml

   <procedure title="Example: Deploying a Service">
       <step>
           Clone the repository and navigate to the project directory.
       </step>
       <step>
           Copy the configuration template and update the environment variables.
       </step>
       <step>
           Run the deployment command: <code>podman-compose up -d</code>
       </step>
   </procedure>

Adding Code Blocks
^^^^^^^^^^^^^^^^^^

For code examples, use triple backticks with the language specified:

.. code:: markdown

   ```bash
   # Example bash command
   git clone https://github.com/example/repo.git
   cd repo
   ```

.. code:: markdown

   ```python
   # Example Python code
   def example_function():
       return "Hello!"
   ```

XML and HTML Code
^^^^^^^^^^^^^^^^^

If you need to provide a sample of XML or HTML code, wrap the contents
of the code block with a `CDATA <https://en.wikipedia.org/wiki/CDATA>`__
section. This prevents Writerside from processing the tags.

.. code:: xml

   <code-block lang="xml">
       <![CDATA[
           <some-tag>text in tag</some-tag>
       ]]>
   </code-block>

See the full `Writerside code
documentation <https://www.jetbrains.com/help/writerside/code.html>`__
for advanced features like syntax highlighting, line numbers, and code
references.

Using TLDR Blocks
^^^^^^^^^^^^^^^^^

For quick reference information, add a TLDR block near the top of your
guide:

.. code:: xml

   <tldr>
       <p>Quick command: <code>podman-compose up -d</code></p>
       <p>Config location: <path>/etc/app/config.yaml</path></p>
       <p>Default port: 8080</p>
   </tldr>

See the full `Writerside TLDR
documentation <https://www.jetbrains.com/help/writerside/tl-dr-blocks.html>`__
for more examples.

Adapting Tone for Your Audience
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**For external users:** - Use clear, friendly language - Avoid technical
jargon where possible - Focus on what users can accomplish - Example:
“Submit your data request through the web form”

**For internal technical staff:** - Use technical terminology freely -
Include command examples and configuration details - Focus on how to
implement and troubleshoot - Example: “Configure the HAProxy backend
pool to include the new service endpoints”

The structure remains the same — just adjust your language and depth of
technical detail.

   **Final Reminder:** Delete instructional sections when creating your
   guide. Keep only the sections relevant to your content.

--------------

Standard Operating Procedure Template
-------------------------------------

.. code:: xml

   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE topic SYSTEM "https://resources.jetbrains.com/writerside/1.0/xhtml-entities.dtd">
   <topic title="${TITLE}" id="${sop-slug}"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:noNamespaceSchemaLocation="https://resources.jetbrains.com/writerside/1.0/topic.v2.xsd">

SOP Slug: The SOP slug is a single sentence that describes the purpose
of the guide, this will show in the highlight section on the guides
overview page.

   **Instructions:** Replace the title with the name of your procedure.
   Complete all sections below, removing instructional text (shown in
   blockquotes) as you go. This template is for formal Standard
   Operating Procedures that require governance approval.

Overview
~~~~~~~~

   Provide a 2-3 sentence high-level summary of what this SOP covers and
   why it exists.

[Brief description of the SOP’s focus and context]

Purpose
~~~~~~~

   State clearly why this SOP exists. What problem does it solve? What
   compliance requirement does it meet? What risk does it mitigate?

[Purpose statement]

Scope
~~~~~

   Define what and who this SOP applies to. Be specific about which
   systems, processes, or activities are covered; which roles or teams
   must follow this SOP; and what is explicitly excluded.

This SOP applies to: - [Scope item 1] - [Scope item 2] - [Scope item 3]

This SOP does not cover: - [Exclusion 1] - [Exclusion 2]

Definitions
~~~~~~~~~~~

   Define key terms, acronyms, and concepts used in this SOP. Only
   include terms that need clarification.

- **[Term 1]:** Definition
- **[Term 2]:** Definition
- **[Term 3]:** Definition

Roles and Responsibilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

   Clearly define who does what. List each role and their specific
   responsibilities related to this SOP.

- **[Role 1]:** Responsibilities
- **[Role 2]:** Responsibilities
- **[Role 3]:** Responsibilities

Requirements
~~~~~~~~~~~~

   Document the mandatory requirements, standards, or compliance
   obligations that must be met.

   If you have multiple categories of requirements, use subsections:
   ``### Data-in-Transit Requirements``,
   ``### Data-at-Rest Requirements``, etc.

Mandatory Requirements
^^^^^^^^^^^^^^^^^^^^^^

   List the must-have requirements. Use “SHALL” or “MUST” language where
   appropriate.

- Requirement 1
- Requirement 2
- Requirement 3

Policy Framework
^^^^^^^^^^^^^^^^

   Reference the policies, standards, legislation, or regulations that
   govern these requirements.

All implementations must comply with: - [Policy/Standard 1] -
[Policy/Standard 2] - [Legislation/Regulation]

Process
~~~~~~~

   Document the procedure(s) that must be followed.

   If you have multiple processes, use subsections:
   ``### Normal Processing Procedure``,
   ``### Emergency Processing Procedure``, etc.

   **Important:** You MUST use Writerside’s ``<procedure>`` semantic
   markup for step-by-step procedures.

   **When to add explicit procedure titles:** 1. When you have multiple
   procedures in the SOP 2. When the procedure name isn’t obvious from
   the SOP title

Example procedure with steps:

.. code:: xml

   <procedure title="Example Processing Procedure" id="example-procedure">
       <p>Context about this procedure — when to use it, prerequisites, expected outcomes.</p>
       <step>
           First step description. Be specific and actionable.
       </step>
       <step>
           Second step description. Include timing requirements if applicable
           (e.g., "within 24 hours").
       </step>
       <step>
           Third step description. Reference other procedures or documents as needed.
       </step>
   </procedure>

Decision Points
^^^^^^^^^^^^^^^

   If your process has decision points or branching logic, document them
   here.

- **[Condition A]:** Action to take
- **[Condition B]:** Action to take
- **[Condition C]:** Escalation required

Escalation Procedures
^^^^^^^^^^^^^^^^^^^^^

   Define when and how to escalate issues that arise during the process.

- [Issue type] → [Escalation contact] ([timeframe])
- [Issue type] → [Escalation contact] ([timeframe])

References
~~~~~~~~~~

   List all related documents, policies, procedures, legislation,
   external resources, and links.

- [Policy document name and link]
- [Related SOP name and link]
- [Legislation or regulation and link]
- [External standard or guideline]

Appendices
~~~~~~~~~~

   Include supporting materials such as checklists, templates, decision
   matrices, contact lists, or detailed technical specifications. Use
   alphabetical appendices (A, B, C, etc.) for each distinct supporting
   document.

Appendix A: [Title]
^^^^^^^^^^^^^^^^^^^

[Appendix content]

**Example: Processing Checklist**

- ☐ Checklist item 1
- ☐ Checklist item 2
- ☐ Checklist item 3

Appendix B: [Title]
^^^^^^^^^^^^^^^^^^^

[Additional appendix content as needed]
