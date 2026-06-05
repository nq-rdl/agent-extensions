|image1|

uv
==

This guide helps you transition from uv to Pixi. It compares commands
and concepts between the two tools, and explains what Pixi adds on top:
the full conda ecosystem for managing non-Python dependencies, system
libraries, and multi-language projects.

Why Pixi?\ `# <#why-pixi>`__
----------------------------

uv is a fast Python package manager, but it's limited to the PyPI
ecosystem. Pixi builds on conda, which brings several fundamental
advantages:

-  **System dependencies included.** Need CUDA, OpenSSL, compilers, or C
   libraries? Conda packages bundle them. With uv, you have to install
   these yourself via ``apt``, ``brew``, Docker, or manual setup.
-  **Multi-language support.** A single Pixi workspace can manage
   Python, R, C/C++, Rust, Node.js, and more, while uv only handles
   Python.
-  **Binary-first distribution.** Conda packages are pre-compiled, so
   you rarely need a build toolchain on your machine. No waiting for
   source builds or debugging missing C headers.
-  **Complete environment modeling.** Conda environments contain
   everything (interpreters, libraries, headers, compilers, CLI tools),
   all managed by the solver. With uv, your Python environment depends
   on whatever your system happens to provide.
-  **True cross-platform lockfiles.** Pixi solves for all target
   platforms in a single lockfile, even platforms you're not currently
   running on.
-  **Built-in task runner.** Define and run tasks directly in your
   manifest, no need for ``Makefile``, ``just``, or shell scripts.

.. admonition::

   You can still use PyPI packages

   Pixi fully supports PyPI packages alongside conda packages, powered
   by uv under the hood. Use ``pixi add --pypi <package>`` to add PyPI
   dependencies, or define them in ``[project.dependencies]`` when using
   ``pyproject.toml``. See `Conda & PyPI <../../concepts/conda_pypi/>`__
   for how the two ecosystems work together.

Quick look at the differences\ `# <#quick-look-at-the-differences>`__
---------------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 28 48

   * - Task
     - uv
     - Pixi
   * - Creating a project
     - ``uv init myproject``
     - ``pixi init myproject``
   * - Adding a dependency
     - ``uv add numpy``
     - ``pixi add numpy`` (conda) or ``pixi add --pypi numpy`` (PyPI)
   * - Removing a dependency
     - ``uv remove numpy``
     - ``pixi remove numpy`` (conda) or ``pixi remove --pypi numpy``
       (PyPI)
   * - Installing/syncing
     - ``uv sync``
     - ``pixi install``
   * - Running a command
     - ``uv run python main.py``
     - ``pixi run python main.py``
   * - Running a standalone script
     - ``uv run script.py`` (PEP 723)
     - ``pixi exec`` via
       `shebang <../../advanced/shebang/>`__
   * - Running a task
     - *(no built-in task runner)*
     - ``pixi run my_task``
   * - Locking dependencies
     - ``uv lock``
     - ``pixi lock`` (also runs automatically on ``pixi add`` /
       ``pixi install``)
   * - Installing Python
     - ``uv python install 3.12``
     - ``pixi add python=3.12`` (managed as a regular dependency)
   * - Ephemeral tool execution
     - ``uvx ruff check``
     - ``pixi exec ruff check``
   * - Global tool install
     - ``uv tool install ruff``
     - ``pixi global install ruff``
   * - Building a package
     - ``uv build``
     - Supported via
       `pixi-build backends <../../build/getting_started/>`__
   * - Publishing a package
     - ``uv publish``
     - Upload to a
       `prefix.dev channel <../../deployment/prefix/>`__
   * - Exporting a lockfile
     - ``uv export``
     - ``pixi workspace export conda-environment``
   * - Virtual environments
     - ``.venv/`` (automatic)
     - ``.pixi/envs/`` (automatic, supports multiple environments)
   * - Cache management
     - ``uv cache clean``
     - ``pixi clean cache``
   * - Updating dependencies
     - ``uv lock --upgrade``
     - ``pixi update``
   * - GitHub Actions
     - ``astral-sh/setup-uv``
     - ``prefix-dev/setup-pixi``

Project configuration\ `# <#project-configuration>`__
-----------------------------------------------------

uv uses ``pyproject.toml`` for project configuration and ``uv.toml`` for
tool-level settings. Pixi supports both ``pixi.toml`` (its native
format) and ``pyproject.toml`` for project configuration, and uses a
separate `configuration file <../../reference/pixi_configuration/>`__
for tool-level settings.

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      uv (pyproject.toml)
      Pixi (pixi.toml)
      Pixi (pyproject.toml)

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [project]
               name = "myproject"
               version = "0.1.0"
               requires-python = ">=3.12"
               dependencies = [
                   "numpy>=1.26",
                   "pandas>=2.0",
               ]

               [dependency-groups]
               dev = ["pytest>=8.0"]

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [workspace]
               name = "myproject"
               channels = ["conda-forge"]
               platforms = ["linux-64", "osx-arm64", "win-64"]

               [dependencies]
               python = ">=3.12"
               numpy = ">=1.26"
               pandas = ">=2.0"

               [feature.test.dependencies]
               pytest = ">=8.0"

               [environments]
               test = ["test"]

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [project]
               name = "myproject"
               version = "0.1.0"
               requires-python = ">=3.12"
               dependencies = [
                   "numpy>=1.26",
                   "pandas>=2.0",
               ]

               [dependency-groups]
               test = ["pytest>=8.0"]

               [tool.pixi.workspace]
               channels = ["conda-forge"]
               platforms = ["linux-64", "osx-arm64", "win-64"]

               [tool.pixi.environments]
               test = { features = ["test"], solve-group = "default" }

With ``pyproject.toml``, Pixi reads ``[project.dependencies]`` as PyPI
dependencies and ``[tool.pixi.dependencies]`` as conda dependencies. See
the `pyproject.toml guide <../../python/pyproject_toml/>`__ for details.

Concepts mapping\ `# <#concepts-mapping>`__
-------------------------------------------

Python version management\ `# <#python-version-management>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv manages Python installations separately with ``uv python install``.
In Pixi, Python is just another package:

.. container:: language-shell highlight

   ::

      pixi add python=3.12    # add Python as a conda dependency

Python gets version-locked in your lockfile alongside everything else,
so there's no separate ``.python-version`` file to manage.

Virtual environments\ `# <#virtual-environments>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv creates a single ``.venv/`` directory per project. Pixi creates
environments under ``.pixi/envs/``, and supports **multiple named
environments** that exist simultaneously in one workspace:

.. container:: language-toml highlight

   pixi.toml
   ::

      [environments]
      default = []
      test = ["test"]
      docs = ["docs"]
      cuda = ["cuda"]

Each environment can have completely different (even conflicting)
dependencies, and Pixi keeps them all installed side by side. For
example, you can have one environment with ``numpy 1.x`` and another
with ``numpy 2.x``, both ready to use without reinstalling anything.

uv can resolve conflicting dependency groups separately in the lockfile
via ``tool.uv.conflicts``, but it still uses a single ``.venv/`` that
you swap between with ``uv sync --group <name>``. Pixi environments are
independent directories, so switching is instant.

See `Multi Environment <../../workspace/multi_environment/>`__.

Dependency groups and extras\ `# <#dependency-groups-and-extras>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv uses `PEP 735 dependency
groups <https://peps.python.org/pep-0735/>`__ and optional dependencies
(extras) to organize dependencies. Pixi uses **features**, composable
sets of dependencies that map to environments:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - uv
     - Pixi
   * - ``[dependency-groups]``
     - ``[feature.<name>.dependencies]``
   * - ``[project.optional-dependencies]``
     - ``[feature.<name>.dependencies]`` mapped to environments
   * - ``uv sync --group dev``
     - ``pixi install -e dev``
   * - ``uv sync --all-groups``
     - ``pixi install --all``

Features are more flexible than dependency groups: they can include
conda dependencies, platform-specific packages, system requirements, and
activation scripts.

Workspaces\ `# <#workspaces>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both tools support multi-package workspaces. uv defines workspace
members with a glob pattern in ``pyproject.toml``:

.. container:: language-toml highlight

   uv pyproject.toml
   ::

      [tool.uv.workspace]
      members = ["packages/*"]

Pixi takes a different approach: you reference local packages as path
dependencies directly in the workspace manifest. Any subdirectory with
its own ``pixi.toml`` (containing a ``[package]`` section) can be pulled
in this way:

.. container:: language-toml highlight

   pixi.toml
   ::

      [workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "win-64"]

      [dependencies]
      my_lib = { path = "packages/my_lib" }

Both tools share a single lockfile across the workspace. See `Building
Multiple Packages <../../build/workspace/>`__.

Standalone scripts\ `# <#standalone-scripts>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv supports `PEP 723 inline script
metadata <https://peps.python.org/pep-0723/>`__ for standalone scripts
that declare their own dependencies:

.. container:: language-python highlight

   uv script
   ::

      # /// script
      # requires-python = ">=3.12"
      # dependencies = ["requests"]
      # ///
      import requests
      print(requests.get("https://example.com").status_code)

Pixi has a similar capability via `shebang
scripts <../../advanced/shebang/>`__ using ``pixi exec``, which creates
a temporary environment with the specified dependencies:

.. container:: language-python highlight

   pixi shebang script
   ::

      #!/usr/bin/env -S pixi exec --spec requests --spec python=3.12 -- python
      import requests
      print(requests.get("https://example.com").status_code)

This works on Linux and macOS. A more complete scripting feature is
under discussion in
`#3751 <https://github.com/prefix-dev/pixi/issues/3751>`__.

Tasks\ `# <#tasks>`__
~~~~~~~~~~~~~~~~~~~~~

uv has no built-in task runner. Pixi does:

.. container:: language-toml highlight

   pixi.toml
   ::

      [tasks]
      start = "python main.py"
      test = "pytest"
      lint = "ruff check ."
      check = { depends-on = ["lint", "test"] }  # task dependencies
      fmt = { cmd = "ruff format .", env = { RUFF_LINE_LENGTH = "120" } }

.. container:: language-shell highlight

   ::

      pixi run check   # runs lint then test
      pixi run start

Tasks support inter-task dependencies, environment variables, working
directory configuration, and cross-platform commands. See
`Tasks <../../workspace/advanced_tasks/>`__.

Ephemeral tool execution (``uvx`` vs ``pixi exec``)\ `# <#ephemeral-tool-execution-uvx-vs-pixi-exec>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``uvx`` (short for ``uv tool run``) runs a tool in a temporary
environment without installing it permanently. ``pixi exec`` does the
same thing:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - uv
     - Pixi
   * - ``uvx ruff check``
     - ``pixi exec ruff check``
   * - ``uvx --from 'ruff>=0.5' ruff check``
     - ``pixi exec --spec 'ruff>=0.5' ruff check``
   * - ``uvx --with numpy ruff check``
     - ``pixi exec --with numpy ruff check``

Global tools (``uv tool`` vs ``pixi global``)\ `# <#global-tools-uv-tool-vs-pixi-global>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both tools install CLI tools globally in isolated environments:

========================== ==============================
uv                         Pixi
========================== ==============================
``uv tool install ruff``   ``pixi global install ruff``
``uv tool list``           ``pixi global list``
``uv tool uninstall ruff`` ``pixi global uninstall ruff``
========================== ==============================

Because Pixi global tools come from the conda ecosystem, you can install
non-Python tools too:

.. container:: language-shell highlight

   ::

      pixi global install git bat ripgrep starship

See `Global Tools <../../global_tools/introduction/>`__.

Package indexes and channels\ `# <#package-indexes-and-channels>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv uses PyPI as its default package index, with support for custom
indexes via ``[[tool.uv.index]]``.

Pixi uses **conda channels**, repositories of pre-compiled packages. The
default is `conda-forge <https://conda-forge.org/>`__, the largest
community-maintained channel:

.. container:: language-toml highlight

   pixi.toml
   ::

      [workspace]
      channels = ["conda-forge"]
      # Add additional channels:
      # channels = ["conda-forge", "pytorch", "https://my-company.com/channel"]

For private packages, you can host your own channel on
`prefix.dev <https://prefix.dev/>`__, S3, or JFrog Artifactory. See
`Authentication <../../deployment/authentication/>`__.

Resolution cutoffs (``exclude-newer``)\ `# <#resolution-cutoffs-exclude-newer>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you use uv's ``exclude-newer`` setting to ignore packages uploaded
after a given date, the Pixi equivalent is
`[workspace].exclude-newer <../../reference/pixi_manifest/#exclude-newer-optional>`__:

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      pixi.toml
      pyproject.toml

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [workspace]
               exclude-newer = "2025-01-01"

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [tool.pixi.workspace]
               exclude-newer = "2025-01-01"

Pixi applies this cutoff across both conda and PyPI resolution.

If you want to override the cutoff for a specific package, uv uses
`exclude-newer-package <https://docs.astral.sh/uv/reference/settings/#exclude-newer-package>`__:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [tool.uv]
      exclude-newer = "2025-01-01"
      exclude-newer-package = { tqdm = "2025-02-01" }

In Pixi, the equivalent depends on which ecosystem the package comes
from:

-  For a conda package, set it in
   `[exclude-newer] <../../reference/pixi_manifest/#exclude-newer-optional>`__.
-  For a PyPI package, set it in
   `[pypi-exclude-newer] <../../reference/pixi_manifest/#exclude-newer-optional>`__.

For example, a conda package can combine a channel pin with a
package-specific ``exclude-newer`` override:

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      pixi.toml
      pyproject.toml

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [workspace]
               exclude-newer = "2025-01-01"

               [dependencies]
               pytorch-cpu = { version = "*", channel = "pytorch" }

               [exclude-newer]
               pytorch-cpu = "2025-02-01"
               openssl = "2024-12-01"

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [tool.pixi.workspace]
               exclude-newer = "2025-01-01"

               [tool.pixi.dependencies]
               pytorch-cpu = { version = "*", channel = "pytorch" }

               [tool.pixi.exclude-newer]
               pytorch-cpu = "2025-02-01"
               openssl = "2024-12-01"

And a PyPI package uses the same pattern, but with PyPI-specific tables:

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      pixi.toml
      pyproject.toml

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [workspace]
               exclude-newer = "2025-01-01"

               [pypi-dependencies]
               torch = { version = "*", index = "https://download.pytorch.org/whl/cu124" }

               [pypi-exclude-newer]
               torch = "2025-02-01"
               tqdm = "2025-02-01"

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [tool.pixi.workspace]
               exclude-newer = "2025-01-01"

               [tool.pixi.pypi-dependencies]
               torch = { version = "*", index = "https://download.pytorch.org/whl/cu124" }

               [tool.pixi.pypi-exclude-newer]
               torch = "2025-02-01"
               tqdm = "2025-02-01"

Unlike uv, Pixi can also override ``exclude-newer`` on a per-channel
level:

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      pixi.toml
      pyproject.toml

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [workspace]
               exclude-newer = "7d"
               channels = [
                 { channel = "my-internal-channel", exclude-newer = "0d" },
                 "conda-forge",
               ]

      .. container:: tabbed-block

         .. container:: language-toml highlight

            ::

               [tool.pixi.workspace]
               exclude-newer = "7d"
               channels = [
                 { channel = "my-internal-channel", exclude-newer = "0d" },
                 "conda-forge",
               ]

Lockfiles\ `# <#lockfiles>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both tools generate lockfiles for reproducibility.

+-------------------+----------------------+-----------------------+
| Aspect            | uv (``uv.lock``)     | Pixi (``pixi.lock``)  |
+===================+======================+=======================+
| Format            | TOML                 | YAML                  |
+-------------------+----------------------+-----------------------+
| Cross-platform    | Universal resolution | Solves per-platform,  |
|                   |                      | stored in one file    |
+-------------------+----------------------+-----------------------+
| Multi-environment | Single resolution    | Per-environment       |
|                   |                      | resolution            |
+-------------------+----------------------+-----------------------+
| Package types     | PyPI only            | Conda + PyPI          |
+-------------------+----------------------+-----------------------+
| Generate/update   | ``uv lock``          | ``pixi lock`` (also   |
|                   |                      | automatic on          |
|                   |                      | ``pixi add`` /        |
|                   |                      | ``pixi install``)     |
+-------------------+----------------------+-----------------------+

See `Lock File <../../workspace/lockfile/>`__.

Building and publishing\ `# <#building-and-publishing>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv builds Python packages with ``uv build`` (PEP 517 backends) and
publishes to PyPI with ``uv publish``.

Pixi builds packages via `pixi-build <../../build/getting_started/>`__,
which produces conda packages from Python, C++, Rust, ROS, and more. You
can publish them to a `prefix.dev channel <../../deployment/prefix/>`__
or any conda channel.

CI with GitHub Actions\ `# <#ci-with-github-actions>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv provides
`astral-sh/setup-uv <https://github.com/astral-sh/setup-uv>`__ for
GitHub Actions. Pixi has
`prefix-dev/setup-pixi <https://github.com/prefix-dev/setup-pixi>`__,
which installs Pixi, sets up caching, and runs ``pixi install`` in your
workflow:

.. container:: language-yaml highlight

   ::

      - uses: prefix-dev/setup-pixi@v0.8.8

See `GitHub Actions <../../integration/ci/github_actions/>`__ for more
details.

The ``uv pip`` interface\ `# <#the-uv-pip-interface>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

uv provides a ``uv pip`` compatibility layer (``uv pip install``,
``uv pip compile``, etc.).

Pixi has no pip compatibility layer, it manages all dependencies
declaratively through the manifest file. If you need pip for a specific
use case, you can install it as a dependency:

.. container:: language-shell highlight

   ::

      pixi add pip
      # not recommended, prefer pixi add --pypi
      pixi run pip install <some-package>

.. admonition::

   Prefer ``pixi add --pypi``

   Using ``pip`` inside a Pixi environment bypasses the solver and
   lockfile. Always prefer ``pixi add --pypi <package>`` to keep
   dependencies tracked and reproducible.

Why the conda ecosystem matters\ `# <#why-the-conda-ecosystem-matters>`__
-------------------------------------------------------------------------

If you're coming from uv, you might wonder why conda packages matter
when PyPI already has everything you need.

System dependencies are included\ `# <#system-dependencies-are-included>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With uv, installing ``scipy`` or ``pytorch`` often requires system-level
libraries (BLAS, LAPACK, CUDA) to already be on your machine. This leads
to platform-specific setup instructions, Docker containers just for
build deps, or cryptic build failures.

With Pixi, these system dependencies are conda packages, managed by the
solver like any other dependency:

.. container:: language-shell highlight

   ::

      # CUDA runtime, cuDNN, and all system libraries are resolved automatically
      pixi add pytorch-gpu

Reproducibility beyond Python\ `# <#reproducibility-beyond-python>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``uv.lock`` captures your Python dependencies precisely, but your
project also depends on the system's C compiler, CUDA version, OpenSSL
build, and more, none of which are tracked.

``pixi.lock`` captures **everything**: the Python interpreter, system
libraries, compilers, and CLI tools. When a colleague clones your
project and runs ``pixi install``, they get the exact same environment.
No "works on my machine" surprises.

No Docker needed for environment isolation\ `# <#no-docker-needed-for-environment-isolation>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A common pattern with uv is using Docker to get a reproducible
environment with the right system dependencies. Pixi environments
achieve the same isolation without containers: no root privileges
required, dramatically smaller than container images, instant creation,
and the same reproducibility guarantees via the lockfile.

Forward-compatible\ `# <#forward-compatible>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Conda packages compile against the oldest supported system baseline, so
they work on newer OS versions too. Your lockfile from today will still
install correctly on next year's OS release.

For a deeper dive into the differences between the conda and PyPI
ecosystems, see the `Conda !=
PyPI <https://conda.org/blog/conda-is-not-pypi>`__ blog post series.

Migrating a project\ `# <#migrating-a-project>`__
-------------------------------------------------

To migrate an existing uv project to Pixi, start by initializing Pixi in
your project directory:

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      pixi.toml
      pyproject.toml

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-shell highlight

            ::

               pixi init --format pixi

         This creates a ``pixi.toml`` alongside your ``pyproject.toml``.

      .. container:: tabbed-block

         .. container:: language-shell highlight

            ::

               pixi init --format pyproject

         This adds a ``[tool.pixi.workspace]`` section to your existing
         ``pyproject.toml``, keeping your PyPI dependencies in place.

#. **Where possible, use conda-forge packages instead of PyPI:**

   Conda packages bundle system libraries and pre-compiled binaries, so
   ``pixi add numpy`` gives you numpy with BLAS, LAPACK, and everything
   else included. Use ``pixi add --pypi <package>`` only for packages
   that aren't available on conda-forge. If a package you need is
   missing from conda-forge, consider `adding it
   yourself <https://github.com/pavelzw/skill-forge/blob/main/recipes/conda-forge/SKILL.md>`__.

#. **Set up tasks to replace your scripts:**

   .. container:: language-shell highlight

      ::

         pixi task add test "pytest"
         pixi task add lint "ruff check ."
         pixi task add serve "python -m http.server"

#. **Run your project:**

   .. container:: language-shell highlight

      ::

         pixi run test
         pixi run python main.py

Once everything works with ``pixi.lock``, you can remove ``uv.lock``.

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/switching_from/uv.md
