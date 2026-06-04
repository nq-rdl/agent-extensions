|image1|

Overview
========

To decouple the building of a conda package from Pixi we provide
something what are called build backends. These are essentially
executables following a specific protocol that is implemented for both
Pixi and the build backend. This also allows for decoupling of the build
backend from Pixi and it's manifest specification.

Available Backends\ `# <#available-backends>`__
-----------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Backend
     - Use Case
   * - `pixi-build-cmake <pixi-build-cmake/>`__
     - Projects using CMake
   * - `pixi-build-python <pixi-build-python/>`__
     - Building Python packages
   * - `pixi-build-rattler-build <pixi-build-rattler-build/>`__
     - Direct ``recipe.yaml`` builds with full control
   * - `pixi-build-ros <pixi-build-ros/>`__
     - ROS (Robot Operating System) packages
   * - `pixi-build-r <pixi-build-r/>`__
     - R packages using ``R CMD INSTALL``
   * - `pixi-build-rust <pixi-build-rust/>`__
     - Cargo-based Rust applications and libraries
   * - `pixi-build-mojo <pixi-build-mojo/>`__
     - Mojo applications and packages

All backends are available through the
`conda-forge <https://prefix.dev/channels/conda-forge>`__ conda channel
and work across multiple platforms (Linux, macOS, Windows). For the
latest backend versions, you can prepend the channel list with the
`prefix.dev/pixi-build-backends <https://prefix.dev/channels/pixi-build-backends>`__
conda channel.

Key Concepts\ `# <#key-concepts>`__
-----------------------------------

-  `Compilers <../key_concepts/compilers/>`__ - How pixi-build
   integrates with conda-forge's compiler infrastructure

Installation\ `# <#installation>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install a certain build backend by adding it to the ``package.build``
section of the manifest file.:

.. container:: language-toml highlight

   ::

      [package.build.backend]
      channels = ["https://prefix.dev/conda-forge"]
      name = "pixi-build-python"
      version = "0.*"

For custom backend channels, you can add the channel to the ``channels``
section of the manifest file:

.. container:: language-toml highlight

   ::

      [package.build]
      backend = { name = "pixi-build-python", version = "0.*" }
      channels = ["https://prefix.dev/conda-forge"]

Overriding the Build Backend\ `# <#overriding-the-build-backend>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes you want to override the build backend that is used by pixi.
Meaning overriding the backend that is specified in the
`[package.build] <../../reference/pixi_manifest/#build-table>`__. We
currently have two environment variables that allow for this:

#. ``PIXI_BUILD_BACKEND_OVERRIDE``: This environment variable allows for
   overriding of one or multiple backends. Use ``{name}={path}`` to
   specify a backend name mapped to a path and ``,`` to separate
   multiple backends. For example:
   ``pixi-build-cmake=/path/to/bin,pixi-build-python`` will:

   #. override the ``pixi-build-cmake`` backend with the executable
      located at ``/path/to/bin``
   #. and will use the ``pixi-build-python`` backend from the ``PATH``.

#. ``PIXI_BUILD_BACKEND_OVERRIDE_ALL``: If this environment variable is
   set to *some* value e.g ``1`` or ``true``, it will not install any
   backends in isolation and will assume that all backends are
   overridden and available in the ``PATH``. This is useful for
   development purposes. e.g
   ``PIXI_BUILD_BACKEND_OVERRIDE_ALL=1 pixi install``

Troubleshooting\ `# <#troubleshooting>`__
-----------------------------------------

Rebuilding Generated Recipes\ `# <#rebuilding-generated-recipes>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you build a package using ``pixi build``, the build backends
generate a complete rattler-build recipe that is stored in your
project's build directory. This can be useful for debugging build issues
or understanding exactly how your package is being built.

Recipe Locations\ `# <#recipe-locations>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The build backends generate recipes in two locations:

.. _1-general-recipe-all-outputs:

1. General Recipe (all outputs)\ `# <#1-general-recipe-all-outputs>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. container:: language-text highlight

   ::

      <your_project>/.pixi/build/work/<package-name>--<hash>/debug/

This directory contains:

-  `recipe.yaml` - A general recipe that can build all package outputs
-  ``variants.yaml`` - All variant configurations for the package

.. _2-variant-specific-recipe-single-output:

2. Variant-Specific Recipe (single output)\ `# <#2-variant-specific-recipe-single-output>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. container:: language-text highlight

   ::

      <your_project>/.pixi/build/work/<package-name>--<hash>/debug/recipe/<variant_hash>/

This directory contains:

-  `recipe.yaml` - The complete rattler-build recipe generated by the
   build backend
-  ``variants.yaml`` - The variant configuration used for this specific
   build

Rebuilding a Package\ `# <#rebuilding-a-package>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To debug or rebuild a package using the same configuration, you have two
options:

Option 1: Navigate to the recipe directory\ `# <#option-1-navigate-to-the-recipe-directory>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Navigate to the recipe directory:

   .. container:: language-bash highlight

      ::

         cd .pixi/build/work/<package-name>--<hash>/recipe/<variant_hash>/debug/

#. Use ``rattler-build`` to rebuild the package:

   .. container:: language-bash highlight

      ::

         rattler-build build

Option 2: Point to the recipe directory\ `# <#option-2-point-to-the-recipe-directory>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the ``--recipe`` flag to build without changing directories:

.. container:: language-bash highlight

   ::

      rattler-build build --recipe .pixi/build/work/<package-name>--<hash>/debug/recipe/<variant_hash>/

This allows you to:

-  Inspect the exact recipe that was generated
-  Debug build failures with direct access to ``rattler-build``
-  Understand how the build backend translated your project model
   (``pixi.toml``)

.. admonition::

   Tip

   The ``<variant_hash>`` ensures that each unique combination of build
   variants gets its own recipe directory, making it easy to compare
   different build configurations.

Debugging JSON-RPC\ `# <#debugging-json-rpc>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can find JSON version of your project model and requests/responses
in the same directory alongside ``recipe.yaml``. We store:

-  Project model: ``project_model.json``
-  Requests: ``*_params.json``
-  Responses: ``*_response.json``

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/build/backends.md
