|image1|

pixi-build-python\ `# <#pixi-build-python>`__
=============================================

The ``pixi-build-python`` backend is designed for building Python
projects using standard Python packaging tools. It provides seamless
integration with Pixi's package management workflow while supporting
both `PEP 517 <https://peps.python.org/pep-0517/>`__ and `PEP
518 <https://peps.python.org/pep-0518/>`__ compliant projects.

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

This backend automatically generates conda packages from Python projects
by:

-  **PEP 517/518 compliance**: Works with modern Python packaging
   standards including ``pyproject.toml``
-  **PyPI-to-conda mapping** (opt-in): Maps ``project.dependencies`` and
   ``build-system.requires`` from ``pyproject.toml`` to conda packages
   (see `ignore-pypi-mapping <#ignore-pypi-mapping>`__)
-  **Automatic compiler detection**: Detects build tools like
   ``maturin`` or ``setuptools-rust`` and automatically adds required
   compilers
-  **Cross-platform support**: Works consistently across Linux, macOS,
   and Windows
-  **Flexible installation**: Automatically selects between ``pip`` and
   ``uv`` for package installation

Basic Usage\ `# <#basic-usage>`__
---------------------------------

To use the Python backend in your ``pixi.toml``, add it to your
package's build configuration:

.. container:: language-toml highlight

   ::

      [package]
      name = "python_package"
      version = "0.1.0"

      [package.build]
      backend = { name = "pixi-build-python", version = "*" }
      channels = ["https://prefix.dev/conda-forge"]

Required Dependencies\ `# <#required-dependencies>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The backend automatically includes the following build tools:

-  ``python`` - The Python interpreter
-  ``pip`` - Python package installer (or ``uv`` if specified)

You can add these to your
`host-dependencies <https://pixi.sh/latest/build/dependency_types/>`__
if you need specific versions:

.. container:: language-toml highlight

   ::

      [package.build-dependencies]
      python = "3.11"

The backend will be automatically selected by the automatic PyPI
dependency mapping feature if you have ``pyproject.toml`` in your source
directory. Otherwise, you need to explicitly add it to your package
definition in the ``[host-dependencies]``:

.. container:: language-toml highlight

   ::

      [package.host-dependencies]
      hatchling = "*"

Configuration Options\ `# <#configuration-options>`__
-----------------------------------------------------

You can customize the Python backend behavior using the
``[package.build.config]`` section in your ``pixi.toml``. The backend
supports the following configuration options:

``noarch``\ `# <#noarch>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Boolean``
-  **Default**: ``true`` (unless `compilers <#compilers>`__ are
   specified)
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific noarch
   setting takes precedence over base

Controls whether to build a platform-independent (noarch) package or a
platform-specific package. The backend tries to derive whether the
package can be built as ``noarch`` based on the presence of
`compilers <#compilers>`__. If compilers are specified, the backend
assume that native extensions are build as part of the build process.
Most of the time these are platform-specific, so the package will be
built as a platform-specific package. If no compilers are specified, the
default value for ``noarch`` is ``true``, meaning the package will be
built as a noarch python package.

.. container:: language-toml highlight

   ::

      [package.build.config]
      noarch = false  # Build platform-specific package

For target-specific configuration, platform-specific noarch setting
overrides the base:

.. container:: language-toml highlight

   ::

      [package.build.config]
      noarch = true

      [package.build.target.win-64.config]
      noarch = false  # Windows needs platform build
      # Result for win-64: false

``env``\ `# <#env>`__
~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Map<String, String>``
-  **Default**: ``{}``
-  **Target Merge Behavior**: ``Merge`` - Platform environment variables
   override base variables with same name, others are merged

Environment variables to set during the build process. These variables
are available during package installation.

.. container:: language-toml highlight

   ::

      [package.build.config]
      env = { SETUPTOOLS_SCM_PRETEND_VERSION = "1.0.0" }

For target-specific configuration, platform environment variables are
merged with base variables:

.. container:: language-toml highlight

   ::

      [package.build.config]
      env = { PYTHONPATH = "/base/path", COMMON_VAR = "base" }

      [package.build.target.win-64.config]
      env = { COMMON_VAR = "windows", WIN_SPECIFIC = "value" }
      # Result for win-64: { PYTHONPATH = "/base/path", COMMON_VAR = "windows", WIN_SPECIFIC = "value" }

``debug-dir``\ `# <#debug-dir>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The backend always writes JSON-RPC request/response logs and the
generated intermediate recipe to the ``debug`` subdirectory inside the
work directory (for example ``<work_directory>/debug``). The deprecated
``debug-dir`` configuration option is ignored; if present, a warning is
emitted to highlight that the setting no longer has any effect.

``extra-input-globs``\ `# <#extra-input-globs>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: ``[]``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific globs
   completely replace base globs

Additional glob patterns to include as input files for the build
process. These patterns are added to the default input globs that
include Python source files, configuration files (``setup.py``,
``pyproject.toml``, etc.), and other build-related files.

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-input-globs = [
          "data/**/*",
          "templates/*.html",
          "*.md"
      ]

For target-specific configuration, platform-specific globs completely
replace the base:

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-input-globs = ["*.py"]

      [package.build.target.win-64.config]
      extra-input-globs = ["*.py", "*.dll", "*.pyd", "windows-resources/**/*"]
      # Result for win-64: ["*.py", "*.dll", "*.pyd", "windows-resources/**/*"]

``compilers``\ `# <#compilers>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: ``[]`` (no compilers)
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific
   compilers completely replace base compilers

List of compilers to use for the build. Most pure Python packages don't
need compilers, but this is useful for packages with C extensions or
other compiled components. The backend automatically generates
appropriate compiler dependencies using conda-forge's compiler
infrastructure.

.. container:: language-toml highlight

   ::

      [package.build.config]
      compilers = ["c", "cxx"]

For target-specific configuration, platform compilers completely replace
the base configuration:

.. container:: language-toml highlight

   ::

      [package.build.config]
      compilers = []

      [package.build.target.win-64.config]
      compilers = ["c", "cxx"]
      # Result for win-64: ["c", "cxx"] (only on Windows)

.. admonition::

   Pure Python vs. Extension Packages

   The Python backend defaults to no compilers (``[]``) since most
   Python packages are pure Python and don't need compilation. This is
   different from other backends like CMake which default to
   ``["cxx"]``. Only specify compilers if your package has C extensions
   or other compiled components:

   .. container:: language-toml highlight

      ::

         # Pure Python package (default behavior)
         [package.build.config]
         # No compilers needed - defaults to []

         # Python package with C extensions
         [package.build.config]
         compilers = ["c", "cxx"]

.. admonition::

   Automatic Compiler Detection

   The backend automatically detects compilers required by certain build
   tools in your ``build-system.requires``. For example:

   -  ``maturin`` → "rust"
   -  ``setuptools-rust`` → "rust"

   These detected compilers are merged with any explicitly configured
   compilers. You only need to manually specify compilers if your
   package uses build tools that aren't auto-detected.

.. admonition::

   Comprehensive Compiler Documentation

   For detailed information about available compilers, platform-specific
   behavior, and how conda-forge compilers work, see the `Compilers
   Documentation <../../key_concepts/compilers/>`__.

``abi3``\ `# <#abi3>`__
~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Boolean``
-  **Default**: ``false``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific setting
   takes precedence over base

Controls whether the package uses the `Python Stable ABI
(abi3) <https://docs.python.org/3/c-api/stable.html>`__. When set to
``true``, a ``python_abi`` dependency is added to the host requirements
with version bounds derived from ``requires-python`` in your
``pyproject.toml``.

The ``python_abi`` package has ``run_exports`` that automatically
propagate the ABI constraint to the run environment, so only a host
dependency is needed.

.. container:: language-toml highlight

   ::

      [package.build.config]
      abi3 = true
      compilers = ["c"]

The version bounds are computed from the lower bound of
``requires-python``:

-  ``requires-python = ">=3.9"`` → ``python_abi >=3.9,<3.10.0a0``
-  ``requires-python = ">=3.11,<4"`` → ``python_abi >=3.11,<3.12.0a0``
-  If ``requires-python`` is not specified, defaults to
   ``python_abi >=3.8,<3.9.0a0``

.. admonition::

   Incompatible with noarch

   Setting ``abi3 = true`` with ``noarch = true`` will produce an error,
   since the stable ABI is only meaningful for packages with compiled
   extensions.

``extra-args``\ `# <#extra-args>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Array<String>``
-  **Default**: ``[]``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific globs
   completely replace base globs

Extra arguments to pass to ``pip``. A use-case could be `pip``'s
``--config-settings``
parameter <https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-C>`__.

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-args = ["-Cbuilddir=mybuilddir"]

For target-specific configuration, platform-specific globs completely
replace the base:

.. container:: language-toml highlight

   ::

      [package.build.config]
      extra-args = ["-Cbuilddir=mybuilddir"]

      [package.build.target.win-64.config]
      extra-args = ["-Cbuilddir=foo"]
      # Result for win-64: ["-Cbuilddir=foo"]

``ignore-pyproject-manifest``\ `# <#ignore-pyproject-manifest>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Boolean``
-  **Default**: ``false``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific setting
   takes precedence over base

Controls whether to ignore the ``pyproject.toml`` manifest file and rely
solely on the project model for package metadata. When set to ``true``,
the backend will not extract metadata (name, version, description,
license, URLs) from ``pyproject.toml`` and will use only the information
provided in the Pixi project model.

.. container:: language-toml highlight

   ::

      [package.build.config]
      ignore-pyproject-manifest = true  # Ignore pyproject.toml metadata

This option is useful when you want complete control over package
metadata through the Pixi project configuration, or when the
``pyproject.toml`` contains metadata that conflicts with your conda
package requirements.

For target-specific configuration, platform-specific setting overrides
the base:

.. container:: language-toml highlight

   ::

      [package.build.config]
      ignore-pyproject-manifest = false

      [package.build.target.win-64.config]
      ignore-pyproject-manifest = true  # Ignore pyproject.toml on Windows only
      # Result for win-64: true

.. admonition::

   Metadata Extraction from pyproject.toml

   By default (when ``ignore-pyproject-manifest`` is ``false``), the
   backend automatically extracts package metadata from your
   ``pyproject.toml`` file, including:

   -  **name**: Package name from ``project.name``
   -  **version**: Package version from ``project.version``
   -  **description/summary**: From ``project.description``
   -  **license**: From ``project.license`` (supports text, file, or
      SPDX formats)
   -  **homepage**: From ``project.urls.Homepage``
   -  **repository**: From ``project.urls.Repository``,
      ``project.urls.Source``, or ``project.urls."Source Code"``
   -  **documentation**: From ``project.urls.Documentation`` or
      ``project.urls.Docs``

   This metadata is automatically included in the generated conda
   recipe. The ``pyproject.toml`` file itself is also added to the input
   globs for incremental build detection.

``ignore-pypi-mapping``\ `# <#ignore-pypi-mapping>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Type**: ``Boolean``
-  **Default**: ``true``
-  **Target Merge Behavior**: ``Overwrite`` - Platform-specific setting
   takes precedence over base

Controls whether to ignore the automatic PyPI-to-conda dependency
mapping feature. When set to ``true`` (the default), dependencies from
``pyproject.toml`` will not be automatically mapped to conda packages.
Set to ``false`` to enable automatic mapping.

.. container:: language-toml highlight

   ::

      [package.build.config]
      ignore-pypi-mapping = false  # Enable automatic PyPI-to-conda mapping

.. admonition::

   Default Behavior

   This option currently defaults to ``true`` (mapping disabled) to
   avoid breaking existing setups. In a future release, the default will
   change to ``false`` (mapping enabled). If you want to opt-in to
   automatic dependency mapping now, explicitly set
   ``ignore-pypi-mapping = false``.

For target-specific configuration, platform-specific setting overrides
the base:

.. container:: language-toml highlight

   ::

      [package.build.config]
      ignore-pypi-mapping = false

      [package.build.target.win-64.config]
      ignore-pypi-mapping = true  # Disable mapping on Windows only
      # Result for win-64: true

Automatic PyPI Dependency Mapping\ `# <#automatic-pypi-dependency-mapping>`__
-----------------------------------------------------------------------------

The Python backend can automatically map PyPI dependencies from your
``pyproject.toml`` to their corresponding conda packages. This means you
don't need to manually duplicate your dependencies in both
``pyproject.toml`` and ``pixi.toml``.

.. admonition::

   Opt-in Feature

   This feature is currently disabled by default. To enable automatic
   PyPI-to-conda dependency mapping, set ``ignore-pypi-mapping = false``
   in your build configuration:

   .. container:: language-toml highlight

      ::

         [package.build.config]
         ignore-pypi-mapping = false

How It Works\ `# <#how-it-works>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The backend reads dependencies from two sources in your
``pyproject.toml``:

#. **``project.dependencies``** → Added to conda **run** dependencies
#. **``build-system.requires``** → Added to conda **host** dependencies

For each PyPI package, the backend queries a mapping service to find the
corresponding conda-forge package name. The mapping is cached locally
for 24 hours to improve performance.

Example\ `# <#example>`__
~~~~~~~~~~~~~~~~~~~~~~~~~

Given this ``pyproject.toml``:

.. container:: language-toml highlight

   ::

      [project]
      name = "my-package"
      version = "1.0.0"
      dependencies = [
          "requests>=2.28",
          "pydantic>=2.0,<3.0",
      ]

      [build-system]
      requires = ["hatchling"]
      build-backend = "hatchling.build"

The backend automatically adds:

-  ``requests >=2.28`` and ``pydantic >=2.0,<3.0`` to run dependencies
-  ``hatchling`` to host dependencies

Precedence Rules\ `# <#precedence-rules>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dependencies specified in your ``pixi.toml`` take precedence over those
inferred from ``pyproject.toml``:

-  If you specify ``requests = ">=2.30"`` in
   ``[package.run-dependencies]``, it will override the
   ``requests>=2.28`` from ``pyproject.toml``
-  Dependencies not in ``pixi.toml`` are added from ``pyproject.toml``

This allows you to:

-  Use ``pyproject.toml`` as the single source of truth for most
   dependencies
-  Override specific packages in ``pixi.toml`` when you need different
   versions or conda-specific packages

Limitations\ `# <#limitations>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **Environment markers** (e.g.,
   ``requests>=2.28; python_version >= "3.8"``) are only partially
   supported. At the moment, only ``platform_system``, ``os_name``,
   ``platform_machine`` and ``sys_platforms`` are currently checked.
-  **URL-based dependencies** (e.g., ``package @ https://...``) are
   skipped
-  Packages without a conda-forge mapping are logged as warnings and
   skipped

Build Process\ `# <#build-process>`__
-------------------------------------

The Python backend follows this build process:

#. **Installer Detection**: Automatically chooses between ``uv`` and
   ``pip`` based on available dependencies
#. **Environment Setup**: Configures Python environment variables for
   the build
#. **Package Installation**: Executes the selected installer with the
   following options:

   -  ``--no-deps``: Don't install dependencies (handled by conda)
   -  ``--no-build-isolation``: Use the conda environment for building
   -  ``-vv``: Verbose output for debugging

#. **Package Creation**: Creates either a noarch or platform-specific
   conda package

Installer Selection\ `# <#installer-selection>`__
-------------------------------------------------

The backend automatically detects which Python installer to use:

-  **uv**: Used if ``uv`` is present in the build or host dependencies
-  **pip**: Used as the default fallback installer

To use ``uv`` for faster installations, add it to your dependencies:

.. container:: language-toml highlight

   ::

      [package.host-dependencies]
      uv = "*"

Editable Installations\ `# <#editable-installations>`__
=======================================================

Until profiles are implemented, editable installations are not easily
configurable. This is the current behaviour:

-  ``editable`` is ``true`` when installing the package (e.g. with
   ``pixi install``)
-  ``editable`` is ``false`` when building the package (e.g. with
   ``pixi build``)
-  Set environment variable ``BUILD_EDITABLE_PYTHON`` to ``true`` or
   ``false`` to enforce a certain behavior

Default Variants\ `# <#default-variants>`__
-------------------------------------------

On Windows platforms, the backend automatically sets the following
default variants:

-  ``c_compiler``: ``vs2022`` - Visual Studio 2022 C compiler
-  ``cxx_compiler``: ``vs2022`` - Visual Studio 2022 C++ compiler

These variants are used when you specify compilers in your
`[package.build.config.compilers] <#compilers>`__ configuration.
Note that setting these default variants does not automatically add
compilers to your build - you still need to explicitly configure which
compilers to use.

This default is set to align with conda-forge's switch to Visual Studio
2022 and because `mainstream support for Visual Studio 2019 ended in
2024 <https://learn.microsoft.com/en-us/lifecycle/products/visual-studio-2019>`__.
The ``vs2022`` compiler is more widely supported on modern GitHub
runners and build environments.

You can override these defaults by explicitly setting variants using
`[workspace.build-variants] <https://pixi.sh/latest/reference/pixi_manifest/#build-variants-optional>`__
in your ``pixi.toml``:

.. container:: language-toml highlight

   ::

      [workspace.build-variants]
      c_compiler = ["vs2019"]
      cxx_compiler = ["vs2019"]

.. _limitations_1:

Limitations\ `# <#limitations_1>`__
-----------------------------------

-  Requires a PEP 517/518 compliant Python project with
   ``pyproject.toml``
-  Limited support for complex build customization compared to direct
   recipe-based approaches
-  Limited ways to configure editable installations

See Also\ `# <#see-also>`__
---------------------------

-  `Building Python Packages <https://pixi.sh/latest/build/python/>`__ -
   Tutorial for building Python packages with Pixi
-  `Python Packaging User Guide <https://packaging.python.org/>`__ -
   Official Python packaging documentation
-  `PEP 517 <https://peps.python.org/pep-0517/>`__ - A build-system
   independent format for source trees

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/build/backends/pixi-build-python.md
