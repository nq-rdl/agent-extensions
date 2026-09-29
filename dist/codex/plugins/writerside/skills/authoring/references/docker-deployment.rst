Writerside Docker Deployment
============================

Awareness-level reference for building Writerside documentation with
Docker. This skill does **not** create deployments — it provides the
context needed to understand and troubleshoot the Docker-based build
process.

--------------

Overview
--------

Writerside provides a Docker image (``jetbrains/writerside-builder``)
that contains the full documentation builder. This enables: -
Version-specific builds independent of the Writerside plugin version in
your IDE - CI/CD automation on GitHub Actions, GitLab CI, and TeamCity -
Reproducible builds across platforms

JetBrains sunset the standalone Writerside IDE on 2025-03-20; Writerside
continues as a free plugin for JetBrains IDEs, and the Docker builder and
GitHub actions keep working
(https://blog.jetbrains.com/writerside/2025/03/sunsetting-writerside-ide/).

--------------

Builder image and version
-------------------------

This section is the single source for the builder image and tag; other
references point here.

- **Image:** ``jetbrains/writerside-builder`` on Docker Hub, mirrored as
  ``registry.jetbrains.team/p/writerside/builder/writerside-builder``
  (same image digest).
- **Tag = builder version.** Pin one tag so markup processing stays
  stable; bump it when you update the Writerside plugin so builds match
  your local preview.
- **Current tag:** ``2026.09.0357`` — latest as of 2026-09-29 per
  https://www.jetbrains.com/help/writerside/build-with-docker.html.
- **Verified:** the Basic Build Command and the Custom Dockerfile below
  were run with ``2026.02.8644``, which also confirmed the output
  archive name. The other examples were not run.
- **Platform and size:** ``linux/amd64`` only; about 2.4 GB compressed
  (about 8.4 GB unpacked).
- **Output ownership:** the container runs as root, so files in the
  output directory are owned by root on the host.

Define the image once and reuse it in the commands below:

.. code:: bash

   WRS_BUILDER=jetbrains/writerside-builder:2026.09.0357
   # Mirror: registry.jetbrains.team/p/writerside/builder/writerside-builder:2026.09.0357
   docker pull "$WRS_BUILDER"

--------------

Basic Build Command
-------------------

.. code:: bash

   docker run --rm \
     -v .:/opt/sources \
     -e SOURCE_DIR=/opt/sources \
     -e MODULE_INSTANCE=Writerside/hi \
     -e OUTPUT_DIR=/opt/sources/output \
     -e RUNNER=other \
     "$WRS_BUILDER"

This mounts the current directory, builds the ``hi`` instance from the
``Writerside`` module, and writes output to ``./output/``. The container
exits non-zero (255) when inspections report errors; warnings alone
exit 0.

--------------

Environment Variables
---------------------

+---------------------+-----------------+----------------------+-------------------------+
| Variable            | Required        | Purpose              | Example                 |
+=====================+=================+======================+=========================+
| ``SOURCE_DIR``      | Yes             | Directory containing | ``/opt/sources``        |
|                     |                 | documentation        |                         |
|                     |                 | sources              |                         |
+---------------------+-----------------+----------------------+-------------------------+
| ``MODULE_INSTANCE`` | Yes             | Module and instance  | ``Writerside/hi``       |
|                     |                 | ID (format:          |                         |
|                     |                 | ``Module/instance``) |                         |
+---------------------+-----------------+----------------------+-------------------------+
| ``OUTPUT_DIR``      | Yes             | Where to write       | ``/opt/sources/output`` |
|                     |                 | generated artifacts  |                         |
+---------------------+-----------------+----------------------+-------------------------+
| ``RUNNER``          | No              | Execution            | ``github``, ``gitlab``, |
|                     |                 | environment —        | ``teamcity``, ``other`` |
|                     |                 | affects artifact     | (default: ``teamcity``) |
|                     |                 | format               |                         |
+---------------------+-----------------+----------------------+-------------------------+
| ``PDF``             | No              | PDF export           | ``PDF.xml``             |
|                     |                 | configuration        |                         |
|                     |                 | filename; not with   |                         |
|                     |                 | ``IS_GROUP``         |                         |
+---------------------+-----------------+----------------------+-------------------------+
| ``IS_GROUP``        | No              | Set ``true`` for     | ``true``                |
|                     |                 | multi-instance group |                         |
|                     |                 | builds; not with     |                         |
|                     |                 | ``PDF``              |                         |
+---------------------+-----------------+----------------------+-------------------------+

The image already sets ``DISPLAY=:99`` and its default command starts
``Xvfb`` itself; you do not pass ``DISPLAY``. The builder refuses to run
when ``IS_GROUP=true`` and ``PDF`` are both set.

--------------

Command-Line Options
--------------------

When invoking the builder script directly (e.g., in a custom
Dockerfile):

+------------------+--------+------------------------------------------+
| Option           | Short  | Purpose                                  |
+==================+========+==========================================+
| ``--source-dir`` | ``-i`` | Documentation sources location           |
+------------------+--------+------------------------------------------+
| ``--output-dir`` | ``-o`` | Build artifact destination               |
+------------------+--------+------------------------------------------+
| ``--product``    | ``-p`` | Module/instance pair for single instance |
|                  |        | builds                                   |
+------------------+--------+------------------------------------------+
| ``--group``      | ``-g`` | Module/build-group pair for grouped      |
|                  |        | builds                                   |
+------------------+--------+------------------------------------------+
| ``--runner``     | ``-r`` | Environment specification                |
+------------------+--------+------------------------------------------+
| ``-pdf``         | —      | Trigger PDF generation using specified   |
|                  |        | settings file                            |
+------------------+--------+------------------------------------------+

``--source-dir``, ``--output-dir`` and one of ``--product`` or
``--group`` (never both) are required. ``--runner`` defaults to
``teamcity``. Single-dash long forms (``-source-dir``) are also accepted.

--------------

Output
------

Built artifacts appear in the output directory. The generated filename
follows the pattern:

::

   webHelp<INSTANCE_ID_UPPER>2-all.zip

Where ``<INSTANCE_ID_UPPER>`` is the instance ID in uppercase, followed
by a literal ``2``. For example, instance ``hi`` produces
``webHelpHI2-all.zip``. The output directory also contains
``report.json`` (inspection results, including ``testsErrorsCount``),
``report.html`` and ``algolia-indexes-HI.zip``. The archive is still
produced when inspections report errors.

Setting ``PDF`` (or the ``-pdf`` option) generates a PDF; without it the
builder produces the regular website. JetBrains' GitHub workflow uses a
separate job for the PDF build.

--------------

Multi-Instance Builds
---------------------

To build multiple instances as a unified documentation website:

1. Set ``IS_GROUP=true``
2. Set ``MODULE_INSTANCE`` to the build group ID (not an individual
   instance)

.. code:: bash

   docker run --rm \
     -v .:/opt/sources \
     -e SOURCE_DIR=/opt/sources \
     -e MODULE_INSTANCE=Writerside/all-docs \
     -e OUTPUT_DIR=/opt/sources/output \
     -e IS_GROUP=true \
     -e RUNNER=other \
     "$WRS_BUILDER"

--------------

CI/CD Integration
-----------------

GitHub Actions
~~~~~~~~~~~~~~

JetBrains' documented pattern
(https://www.jetbrains.com/help/writerside/deploy-docs-to-github-pages.html)
uses ``JetBrains/writerside-github-action@v4`` for the build and
``JetBrains/writerside-checker-action@v1`` to fail on errors in
``report.json``. The builder version goes in ``DOCKER_VERSION``, the tag
only (see Builder image and version above):

.. code:: yaml

   env:
     INSTANCE: 'Writerside/hi'
     DOCKER_VERSION: '<builder tag>'  # tag from "Builder image and version"
     # IS_GROUP: 'true'               # uncomment to build a build group

   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Define artifact name
           run: |
             ID_UPPER=$(echo "${INSTANCE#*/}" | tr '[:lower:]' '[:upper:]')
             echo "ARTIFACT=webHelp${ID_UPPER}2-all.zip" >> "$GITHUB_ENV"
         - name: Build docs using Writerside Docker builder
           uses: JetBrains/writerside-github-action@v4
           with:
             instance: ${{ env.INSTANCE }}
             docker-version: ${{ env.DOCKER_VERSION }}
         - uses: actions/upload-artifact@v4
           with:
             name: docs
             path: |
               artifacts/${{ env.ARTIFACT }}
               artifacts/report.json
     test:
       needs: build
       runs-on: ubuntu-latest
       steps:
         - uses: actions/download-artifact@v4
           with:
             name: docs
             path: artifacts
         - uses: JetBrains/writerside-checker-action@v1
           with:
             instance: ${{ env.INSTANCE }}

The action writes to ``artifacts/``, not ``output/``. JetBrains' full
workflow adds a GitHub Pages deploy job and optional Algolia and PDF jobs.

Environment File
~~~~~~~~~~~~~~~~

Pass variables via ``.env`` file for cleaner scripts:

.. code:: bash

   docker run --rm \
     -v .:/opt/sources \
     --env-file .env \
     "$WRS_BUILDER"

--------------

Custom Dockerfile Pattern
-------------------------

For advanced setups combining the builder with a web server. Pass the
builder image as a build argument:
``docker build --build-arg WRS_BUILDER="$WRS_BUILDER" -t help-website .``
(the build argument is required; BuildKit warns
``InvalidDefaultArgInFrom`` because ``WRS_BUILDER`` has no default).

.. code:: dockerfile

   ARG WRS_BUILDER
   FROM ${WRS_BUILDER} AS build
   ARG INSTANCE=Writerside/hi
   WORKDIR /opt/sources
   COPY Writerside ./Writerside

   # The image sets DISPLAY=:99. Xvfb must run in the SAME RUN instruction
   # as the builder, because background processes end with each RUN step.
   RUN Xvfb :99 & \
       /opt/builder/bin/idea.sh helpbuilderinspect \
         --source-dir /opt/sources \
         --product "$INSTANCE" \
         --runner other \
         --output-dir /opt/wrs-output

   # Archive name: webHelp<INSTANCE_ID_UPPER>2-all.zip
   RUN id=$(echo "${INSTANCE#*/}" | tr '[:lower:]' '[:upper:]') && \
       unzip -O UTF-8 "/opt/wrs-output/webHelp${id}2-all.zip" -d /opt/wrs-output/site

   FROM httpd:2.4
   COPY --from=build /opt/wrs-output/site/ /usr/local/apache2/htdocs/

**Critical requirement:** start ``Xvfb`` in the same ``RUN``
instruction as ``idea.sh``. The builder stage must also contain the
sources (``COPY``), and the website archive must be unzipped before it
is served.

--------------

Troubleshooting
---------------

+-------------------------+-------------------------+---------------------+
| Issue                   | Cause                   | Fix                 |
+=========================+=========================+=====================+
| Build fails with        | ``Xvfb`` started in a   | Start ``Xvfb`` in   |
| display error           | separate RUN            | the same RUN as     |
|                         | instruction             | ``idea.sh``         |
+-------------------------+-------------------------+---------------------+
| ``Project root not      | Sources not in the      | ``COPY`` the module |
| found``                 | builder stage or wrong  | into the image; set |
|                         | ``--source-dir``        | ``--source-dir``    |
+-------------------------+-------------------------+---------------------+
| Empty output directory  | Wrong                   | Use                 |
|                         | ``MODULE_INSTANCE``     | ``Module/instance`` |
|                         | format                  | format (e.g.,       |
|                         |                         | ``Writerside/hi``)  |
+-------------------------+-------------------------+---------------------+
| Instance not found      | Instance ID doesn’t     | Check instance ID   |
|                         | match project config    | in Writerside       |
|                         |                         | project settings    |
+-------------------------+-------------------------+---------------------+
| Slow builds             | Large image download on | Cache the Docker    |
|                         | every CI run            | image in your CI    |
|                         |                         | pipeline            |
+-------------------------+-------------------------+---------------------+
