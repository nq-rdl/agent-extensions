|image1|

pixi-build-r\ `# <#pixi-build-r>`__
===================================

The ``pixi-build-r`` backend is designed for building R packages using
``R CMD INSTALL``. It automatically parses the ``DESCRIPTION`` file to
extract metadata and dependencies, and detects whether native code
compilation is needed.

.. admonition::

   Warning

   ``pixi-build`` is a preview feature, and will change until it is
   stabilized. This is why we require users to opt in to that feature by
   adding "pixi-build" to ``workspace.preview``.

   .. container:: language-toml highlight

      ::

         [workspace]
         preview = ["pixi-build"]

Overview\ `# <#overview>`__
---------------------------

This backend automatically generates conda packages from R projects by:

-  **DESCRIPTION parsing**: Reads package metadata, dependencies
   (``Imports``, ``Depends``, ``LinkingTo``), and license information
   from the standard R ``DESCRIPTION`` file
-  **Automatic compiler detection**: Detects native code by checking for
   a ``src/`` directory or ``LinkingTo`` fields, and adds C, C++, and
   Fortran compilers automatically
-  **Dependency mapping**: Converts R package names to conda-forge names
   (e.g., ``curl`` becomes ``r-curl``, ``R6`` becomes ``r-r6``)
-  **Cross-platform support**: Generates platform-appropriate build
   scripts for Linux, macOS, and Windows

Basic Usage\ `# <#basic-usage>`__
---------------------------------

To use the R backend in your ``pixi.toml``, add it to your package's
build configuration:

.. container:: language-toml highlight

   ::

      [workspace]
      channels = ["https://prefix.dev/conda-forge"]
      platforms = ["linux-64", "osx-arm64", "win-64"]
      preview = ["pixi-build"]

      [package]
      name = "r-mypackage"
      version = "1.0.0"

      [package.build]
      backend = { name = "pixi-build-r", version = "*" }
      channels = ["https://prefix.dev/conda-forge"]

Your R package should have a standard ``DESCRIPTION`` file in the
project root:

.. container:: language-text highlight

   ::

      Package: mypackage
      Version: 1.0.0
      Title: My R Package
      Description: A short description of the package.
      License: MIT
      Imports:
          dplyr (>= 1.0),
          ggplot2

Required Dependencies\ `# <#required-dependencies>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The backend automatically includes the following dependencies:

-  ``r-base`` - The R runtime (added to both host and run dependencies)

Dependencies listed in ``Imports``, ``Depends``, and ``LinkingTo``
fields of the ``DESCRIPTION`` file are automatically converted to conda
packages and added to the recipe.

You can add additional dependencies to your
`host-dependencies <https://pixi.sh/latest/build/dependency_types/>`__
if needed:

.. container:: language-toml highlight

   ::

      [package.host-dependencies]
      r-base = ">=4.1"

Configuration Options\ `# <#configuration-options>`__
-----------------------------------------------------

You can customize the R backend behavior using the
``[package.build.config]`` section in your ``pixi.toml``. The backend
supports the following configuration options:

``extra-args``\ `# <#extra-args>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: ``[]``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific args
   completely replace base args

Extra arguments to pass to ``R CMD INSTALL``.

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-args = ["--no-multiarch", "--no-test-load"]

For target-specific configuration, platform-specific args completely
replace the base:

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-args = ["--no-multiarch"]

      [package.build.target.win-64.config]
      extra-args = ["--no-multiarch", "--no-test-load"]
      # Result for win-64: ["--no-multiarch", "--no-test-load"]

``env``\ `# <#env>`__
~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Map<String, String>``
-  **Default**: ``{}``
-  **Target Merge Behavior**: ``Merge`` - Platform environment variables
   override base variables with same name, others are merged

Environment variables to set during the build process. These variables
are available during ``R CMD INSTALL``.

.. container:: language-toml highlight

   ::

      [package.build.config]
      env = { R_LIBS_USER = "$PREFIX/lib/R/library" }

For target-specific configuration, platform environment variables are
merged with base variables:

.. container:: language-toml highlight

   ::

      [package.build.config]
      env = { COMMON_VAR = "base" }

      [package.build.target.win-64.config]
      env = { COMMON_VAR = "windows", WIN_SPECIFIC = "value" }
      # Result for win-64: { COMMON_VAR = "windows", WIN_SPECIFIC = "value" }

``extra-input-globs``\ `# <#extra-input-globs>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: ``[]``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific globs
   completely replace base globs

Additional glob patterns to include as input files for the build
process. These patterns are added to the default input globs that
include R source files, documentation, and build-related files.

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-input-globs = [
          "inst/**/*",
          "data/**/*",
          "vignettes/**/*"
      ]

``compilers``\ `# <#compilers>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: Auto-detected (see below)
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific
   compilers completely replace base compilers

List of compilers to use for the build. By default, the backend
auto-detects whether compilers are needed by checking for:

#. A ``src/`` directory in the package root
#. A ``LinkingTo`` field in the ``DESCRIPTION`` file

If either is found, compilers default to ``["c", "cxx", "fortran"]``.
Otherwise, no compilers are added.

.. container:: language-toml highlight

   ::

      [package.build.config]
      compilers = ["c", "cxx"]  # Override auto-detection

For target-specific configuration, platform compilers completely replace
the base configuration:

.. container:: language-toml highlight

   ::

      [package.build.config]
      compilers = ["c"]

      [package.build.target.win-64.config]
      compilers = ["c", "cxx", "fortran"]
      # Result for win-64: ["c", "cxx", "fortran"]

.. admonition::

   Auto-Detection Behavior

   Unlike the Python backend which defaults to no compilers, the R
   backend actively inspects your package structure. Packages with a
   ``src/`` directory or ``LinkingTo`` dependencies automatically get C,
   C++, and Fortran compilers. Pure R packages (no ``src/``, no
   ``LinkingTo``) get no compilers.

   You can override this by explicitly setting the ``compilers`` option:

   .. container:: language-toml highlight

      ::

         # Force no compilers even if src/ exists
         [package.build.config]
         compilers = []

         # Only use C compiler
         [package.build.config]
         compilers = ["c"]

.. admonition::

   Comprehensive Compiler Documentation

   For detailed information about available compilers, platform-specific
   behavior, and how conda-forge compilers work, see the `Compilers
   Documentation <../../key_concepts/compilers/>`__.

``channels``\ `# <#channels>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: ``["conda-forge"]``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific channels
   completely replace base channels

Channels to use for resolving R package dependencies.

.. container:: language-toml highlight

   ::

      [package.build.config]
      channels = ["conda-forge", "r"]

Dependency Handling\ `# <#dependency-handling>`__
-------------------------------------------------

Automatic Dependency Parsing\ `# <#automatic-dependency-parsing>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The backend reads dependencies from the ``DESCRIPTION`` file:

-  **``Imports``** and **``Depends``** fields are added to both host and
   run dependencies
-  **``LinkingTo``** fields are added to host dependencies only
   (compile-time headers)
-  R version constraints are converted to conda format (e.g.,
   ``(>= 1.5)`` becomes ``>=1.5``)
-  R package names are converted to conda names with the ``r-`` prefix
   (e.g., ``dplyr`` becomes ``r-dplyr``)

Built-in Packages\ `# <#built-in-packages>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Packages that are included with R (such as ``stats``, ``utils``,
``base``, ``methods``, ``Matrix``, ``MASS``, etc.) are automatically
filtered out and not added as separate dependencies.

Build Process\ `# <#build-process>`__
-------------------------------------

The R backend follows this build process:

#. **DESCRIPTION Parsing**: Reads package metadata and dependencies from
   the ``DESCRIPTION`` file
#. **Compiler Detection**: Auto-detects or uses configured compilers
   based on package structure
#. **Recipe Generation**: Creates a conda recipe with all dependencies
   converted to conda format
#. **Build Script**: Generates a platform-appropriate script that:

   -  Prints R version information for debugging
   -  Creates the R library directory
   -  Runs
      ``R CMD INSTALL --library=<library_dir> --no-lock <source_dir>``

#. **Package Creation**: Creates a platform-specific conda package

Limitations\ `# <#limitations>`__
---------------------------------

-  Requires a standard R ``DESCRIPTION`` file in the project root
-  The ``DESCRIPTION`` file must use the DCF (Debian Control File)
   format
-  ``Suggests`` and ``Enhances`` dependencies are not automatically
   included
-  License mapping from CRAN format to SPDX is best-effort

See Also\ `# <#see-also>`__
---------------------------

-  `Build Backends Overview <../>`__ - Overview of all available build
   backends
-  `Compilers <../../key_concepts/compilers/>`__ - How pixi-build
   integrates with conda-forge's compiler infrastructure
-  `CRAN <https://cran.r-project.org/>`__ - The Comprehensive R Archive
   Network

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/build/backends/pixi-build-r.md
