Writerside Documentation Quality
================================

Reference for Writerside’s built-in quality inspections, how to
configure them, and how to integrate quality checks into your workflow.

--------------

Overview
--------

Writerside provides documentation quality checks at three levels:

1. **IDE editor** — Real-time inspections highlight problems as you type
2. **Local preview** — The Preview tool window lists all problems found
   in rendered topics
3. **Docker build** — The builder analyzes every topic and reports
   problems to console output

All three levels run the same inspection engine, so issues caught in the
IDE will also be caught during builds.

--------------

Inspection Categories
---------------------

+-------------------+-----------------------------+-------------------+
| Category          | What It Checks              | Examples          |
+===================+=============================+===================+
| **Markup          | XML/Markdown                | Unclosed tags,    |
| validity**        | well-formedness, valid tag  | unknown elements, |
|                   | usage                       | invalid nesting   |
+-------------------+-----------------------------+-------------------+
| **References**    | Internal links, anchors,    | Broken            |
|                   | includes                    | ``<a href>``,     |
|                   |                             | missing           |
|                   |                             | ``element-id`` in |
|                   |                             | ``<include>``     |
+-------------------+-----------------------------+-------------------+
| **IDs**           | Uniqueness and validity of  | Duplicate ``id``  |
|                   | element identifiers         | attributes,       |
|                   |                             | invalid ID        |
|                   |                             | characters        |
+-------------------+-----------------------------+-------------------+
| **Images**        | Image file references and   | Missing ``src``   |
|                   | accessibility               | files, missing    |
|                   |                             | ``alt`` text      |
+-------------------+-----------------------------+-------------------+
| **Structure**     | Topic and chapter           | Empty chapters,   |
|                   | organization                | orphaned topics   |
|                   |                             | not in tree       |
+-------------------+-----------------------------+-------------------+
| **Variables**     | Variable definitions and    | Undefined         |
|                   | usage                       | variables, unused |
|                   |                             | variable          |
|                   |                             | definitions       |
+-------------------+-----------------------------+-------------------+

--------------

Running Quality Checks
----------------------

In the IDE
~~~~~~~~~~

Inspections run automatically in the editor. Problems appear as: - **Red
underlines** — Errors that will break the build - **Yellow underlines**
— Warnings about potential issues - **Weak warnings** — Style
suggestions

Use **Ctrl+Q** (Quick Documentation) on any element to see its valid
attributes and usage.

Use **Alt+Insert** to generate valid markup for tables, images, and
links.

In Local Preview
~~~~~~~~~~~~~~~~

Open the Preview tool window to see a list of all problems found across
rendered topics. This catches issues that only appear in the built
output (e.g., broken cross-topic links).

In Docker Builds
~~~~~~~~~~~~~~~~

The Docker builder reports problems to console output as
``Test failed: <ID>: …`` (errors) and ``Inspection failed: <ID> …``
(warnings), and writes them to ``report.json`` in the output directory.
The container exits non-zero (255) on errors and 0 on warnings only.
Do not grep the log for ``ERROR``: inspection errors do not use that
word, while normal startup logs print ``SEVERE`` plugin messages.
``WRS_BUILDER`` is defined in `docker-deployment.rst <docker-deployment.rst>`__
→ Builder image and version:

.. code:: bash

   set -o pipefail   # keep docker's exit code through tee
   docker run --rm \
     -v .:/opt/sources \
     -e SOURCE_DIR=/opt/sources \
     -e MODULE_INSTANCE=Writerside/hi \
     -e OUTPUT_DIR=/opt/sources/output \
     -e RUNNER=other \
     "$WRS_BUILDER" 2>&1 | tee build.log \
     || { echo "Documentation build has errors"; exit 1; }

   # Alternatively, read the error count from the report
   jq -e '.testsErrorsCount == 0' output/report.json

--------------

Suppressing Inspections
-----------------------

Per-Build Suppression
~~~~~~~~~~~~~~~~~~~~~

In ``buildprofiles.xml``, use the ``<ignore-problems>`` element to
suppress specific problem IDs:

.. code:: xml

   <variables>
       <ignore-problems>
           duplicate-id,missing-alt-text
       </ignore-problems>
   </variables>

Provide a comma-separated list of problem IDs to suppress.

When to Suppress
~~~~~~~~~~~~~~~~

- **Acceptable:** Suppressing warnings for known limitations or
  intentional patterns
- **Not recommended:** Suppressing errors — these indicate real build
  problems
- **Review regularly:** Suppressed warnings can mask legitimate issues
  over time

--------------

Quality Workflow
----------------

Recommended Process
~~~~~~~~~~~~~~~~~~~

1. **Author with inspections active** (Writerside plugin in a JetBrains
   IDE) — Fix errors and warnings as
   you write
2. **Preview locally** — Check the rendered output and review the
   problems list
3. **Commit and build** — Docker build catches any remaining issues
4. **CI gate** — Fail the pipeline if the build reports errors

Pre-Commit Checklist
~~~~~~~~~~~~~~~~~~~~

Before committing documentation changes:

- ☐ No red underlines in the IDE editor
- ☐ Local preview renders correctly
- ☐ All internal links resolve (check Preview problems list)
- ☐ Images referenced in topics exist in the project
- ☐ No duplicate IDs across topics

--------------

CI/CD Integration
-----------------

GitHub Actions Example
~~~~~~~~~~~~~~~~~~~~~~

Use JetBrains' documented workflow, shown in
`docker-deployment.rst <docker-deployment.rst>`__ → GitHub Actions: the
``build`` job runs ``JetBrains/writerside-github-action@v4`` with the
builder tag in ``DOCKER_VERSION`` (see Builder image and version) and
uploads the website archive plus ``report.json``; the ``test`` job runs
``JetBrains/writerside-checker-action@v1``, which fails when
``report.json`` contains errors.

--------------

Common Issues and Fixes
-----------------------

+-----------------------------+-----------------------+-----------------------------------------------+
| Problem                     | Cause                 | Fix                                           |
+=============================+=======================+===============================================+
| “Unknown element”           | Using a tag not in    | Check                                         |
|                             | the Writerside schema | `markup-reference.rst <markup-reference.rst>`__ |
|                             |                       | for valid tags                                |
+-----------------------------+-----------------------+-----------------------------------------------+
| “Duplicate ID”              | Two elements share    | Rename one of the duplicate IDs               |
|                             | the same ``id`` value |                                               |
+-----------------------------+-----------------------+-----------------------------------------------+
| “Unresolved reference”      | ``<a href>`` or       | Verify the target topic/element exists        |
|                             | ``<include>`` points  |                                               |
|                             | to missing target     |                                               |
+-----------------------------+-----------------------+-----------------------------------------------+
| “Empty chapter”             | ``<chapter>`` with no | Add content or remove the empty chapter       |
|                             | content inside        |                                               |
+-----------------------------+-----------------------+-----------------------------------------------+
| “Missing alt text”          | ``<img>`` without     | Add descriptive ``alt`` text to all images    |
|                             | ``alt`` attribute     |                                               |
+-----------------------------+-----------------------+-----------------------------------------------+
