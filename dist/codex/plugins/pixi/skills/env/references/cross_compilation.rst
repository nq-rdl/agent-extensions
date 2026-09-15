|image1|

Cross Compilation using rattler-build
=====================================

In this tutorial, we will show you how to set up a
`nanobind <https://github.com/wjakob/nanobind>`__ Python binding project
that supports **cross-compilation**: we will demonstrate how to compile
for the ``linux-aarch64`` platform on a ``linux-64`` host. In this
tutorial we assume that you've read the `Building a C++
Package <../cpp/>`__ tutorial. If you haven't read it yet, we recommend
you to do so before continuing, as the project structure and the source
code will be the same as in the previous tutorial, so we may skip
explicit explanations of some parts.

.. admonition::

   Warning

   ``pixi-build`` is a preview feature and will change until it is
   stabilized.

``pixi-build`` has built-in cross-compilation capabilities: if the build
process of a package supports it, building a package for a platform
(``linux-aarch64``) different from the host platform (``linux-64``) can
be done simply with ``pixi build --target-platform linux-aarch64``.
However, a typical `nanobind <https://github.com/wjakob/nanobind>`__
project, as described in the `Building a C++ Package
tutorial <../cpp/>`__, doesn't cross-compile out of the box. There are a
couple of issues:

.. _1-finding-python-and-nanobind:

1. Finding Python and nanobind\ `# <#1-finding-python-and-nanobind>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The
``find_package(Python 3.8 COMPONENTS Interpreter Development.Module REQUIRED)``
(note the ``Interpreter`` component) tries to find a usable Python
interpreter on the host. When cross-compiling, the python from the
``host-dependencies`` is the ``target-platform`` python, which can not
be executed.

The ``cross-python_${{ host_platform }}`` package can usually be used to
circumvent this issue, as `documented by
conda-forge <https://conda-forge.org/docs/how-to/advanced/cross-compilation/#details-about-cross-compiled-python-packages>`__.
However, the ``find_package`` search logic for the ``Interpreter`` is
still not able to correctly determine the Python path in this case.

.. _2-generating-stubs-requires-importing-the-wrapper-library:

2. Generating stubs requires importing the wrapper library\ `# <#2-generating-stubs-requires-importing-the-wrapper-library>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``stub_gen.py`` script that produces the Python stubs (that provide
type hints for wrapped objects) *imports* the library of the wrapped
objects. When cross-compiling, the library is built for the target
platform, so it can not be imported with a Python executable on the
host.

Multi-output recipe solution\ `# <#multi-output-recipe-solution>`__
-------------------------------------------------------------------

When using Pixi, the Python path can be determined based on the
``$PREFIX`` and the ``$PY_VER`` variables available during the build:
for instance ``$ENV{PREFIX}/lib/python$ENV{PY_VER}/site-packages`` gives
the path to the site-packages directory for installation. Using these
paths allows to not rely on the ``find_package``, solving the first
issue.

Python stubs only provide type hints about the wrapped objects, they do
not link to the compiled library. The stub files are actually platform
independent! Therefore, it is possible to use the stubs for the host
platform (no cross-compilation) for any target platform.

This can be conveniently done using the `pixi-build-rattler-build
backend <../backends/pixi-build-rattler-build/>`__, which is able to
build multiple outputs from a single recipe. We will use it to build
**two packages**: a platform-specific (supporting cross-compilation)
library package, and a ``noarch`` stub package.

================== ================== ================= ===============
Package            Type               Built on          Installed on
================== ================== ================= ===============
``cpp_math``       native ``.so``     host platform     target platform
``cpp_math-stubs`` ``noarch: python`` ``linux-64`` only all platforms
================== ================== ================= ===============

Workspace structure\ `# <#workspace-structure>`__
-------------------------------------------------

We use the same directory structure than the `Building a C++ Package
tutorial <../cpp/>`__:

.. container:: language-bash highlight

   ::

      .
      ├── CMakeLists.txt
      ├── pixi.toml
      ├── recipe/
      │   └── recipe.yml
      └── src/
          └── math.cpp

The source file\ `# <#the-source-file>`__
-----------------------------------------

``src/math.cpp`` exposes a single ``add`` function using nanobind:

.. container:: language-cpp highlight

   ::

      #include <nanobind/nanobind.h>

      int add(int a, int b) { return a + b; }

      NB_MODULE(cpp_math, m)
      {
          m.def("add", &add);
      }

.. _the-cmakeliststxt:

The ``CMakeLists.txt``\ `# <#the-cmakeliststxt>`__
--------------------------------------------------

The CMake file needs to handle three scenarios:

#. **Cross-compiling using pixi**: Python is not executable on the host,
   so we locate Python and nanobind directly based on ``$PREFIX``.
#. **Native build with or without pixi**: we can use the typical
   nanobind configuration.
#. **Stubs-only build** (``STUBS_ONLY=ON``): the ``.so`` is assumed
   already installed; we only call ``nanobind_add_stub`` to generate the
   platform independent stub file.

.. container:: language-cmake highlight

   ::

      cmake_minimum_required(VERSION 3.15)

      project(cpp_math)

      option(STUBS_ONLY "Only generate stubs (module already installed)" OFF)

      # ── Cross-compilation ─────────────────────────────────────────────────────────
      if(CMAKE_CROSSCOMPILING AND DEFINED ENV{PREFIX})
        message(STATUS "Cross-compiling, detecting Python from sysroot…")

        set(nanobind_ROOT        "$ENV{PREFIX}/lib/python$ENV{PY_VER}/site-packages/nanobind/cmake")
        set(PYTHON_SITE_PACKAGES "$ENV{PREFIX}/lib/python$ENV{PY_VER}/site-packages")

        find_package(Python $ENV{PY_VER} EXACT COMPONENTS Development.Module REQUIRED)

      elseif(CMAKE_CROSSCOMPILING)
        message(FATAL_ERROR "Cross-compiling is not available when building without pixi.")

      else()
          # bare-metal or pixi build without cross-compilation. Use find_package with python >=3.12
        find_package(Python 3.12 COMPONENTS Interpreter Development.Module REQUIRED)
        execute_process(
          COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
          OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT
        )
        execute_process(
          COMMAND "${Python_EXECUTABLE}" -c
            "import sysconfig; print(sysconfig.get_path('purelib'))"
          OUTPUT_VARIABLE PYTHON_SITE_PACKAGES
          OUTPUT_STRIP_TRAILING_WHITESPACE
        )
      endif()
      # ─────────────────────────────────────────────────────────────────────────────

      find_package(nanobind CONFIG REQUIRED)

      # ── Compiled extension ────────────────────────────────────────────────────────
      if(NOT STUBS_ONLY)
        nanobind_add_module(cpp_math src/math.cpp)

        install(
          TARGETS cpp_math
          LIBRARY DESTINATION ${PYTHON_SITE_PACKAGES}/cpp_math
          ARCHIVE DESTINATION ${PYTHON_SITE_PACKAGES}/cpp_math
        )
      endif()

      # ── Stubs ─────────────────────────────────────────────────────────────────────
      if(STUBS_ONLY)
        # The .so is assumed already installed.
        nanobind_add_stub(
          cpp_math_stub
          MODULE    cpp_math
          RECURSIVE
          OUTPUT    cpp_math.pyi
          MARKER_FILE py.typed
          OUTPUT_PATH ${PYTHON_SITE_PACKAGES}/cpp_math
          PYTHON_PATH ${PYTHON_SITE_PACKAGES}/cpp_math
        )
      endif()

**Key points:**

Cross-compilation:

-  ``find_package(Python … Development.Module)`` (no ``Interpreter``
   component) finds the *target* headers in ``$PREFIX`` without needing
   a runnable interpreter.
-  ``nanobind_ROOT`` is set manually to the nanobind CMake helpers
   bundled in the target ``$PREFIX`` Stub-generation:
-  ``STUBS_ONLY`` lets the same CMake project build just the ``.pyi``
   files. It is meant to be used in a second, native-only pass.

--------------

.. _the-pixitoml:

The ``pixi.toml``\ `# <#the-pixitoml>`__
----------------------------------------

.. container:: language-toml highlight

   ::

      [workspace]
      channels  = ["https://prefix.dev/conda-forge"]
      platforms = ["linux-64", "linux-aarch64"]
      preview   = ["pixi-build"]

      [dependencies]
      cpp_math = { path = "." }
      python   = "*"

      [package]
      name    = "cpp_math"
      version = "0.1.0"

      [package.build]
      backend = { name = "pixi-build-rattler-build", version = "*" }

      [tasks]
      start = "python -c 'import cpp_math; print(cpp_math.add(1, 2))'"

The workspace lists **both** ``linux-64`` and ``linux-aarch64``
platforms. Pixi will cross-compile the ``linux-aarch64`` variant on a
``linux-64`` host when called with
``pixi build --target-platform linux-aarch64``.

--------------

.. _the-reciperecipeyml:

The ``recipe/recipe.yml``\ `# <#the-reciperecipeyml>`__
-------------------------------------------------------

This is the heart of the build. The recipe declares **two outputs** from
the same source tree.

.. container:: language-yaml highlight

   ::

      context:
        version: 0.1.0

      source:
        path: ../   # (1)

      outputs:

        # ── 1. Compiled extension — built for every target platform ─────────────────
        - package:
            name: cpp_math
            version: ${{ version }}
          build:
            number: 0
            script:
              - if: true
                then: |
                  mkdir -p build && rm -rf build/*
                  cmake -GNinja -Bbuild -S .    \
                    ${CMAKE_ARGS}               \
                    -DSTUBS_ONLY=OFF            \
                    -DCMAKE_INSTALL_PREFIX=$PREFIX \
                    -DCMAKE_BUILD_TYPE=Release
                  ninja -C build
                  ninja -C build install
          requirements:
            build:    # (2)
              - ${{ compiler('cxx') }}
              - cmake
              - ninja
            host:     # (3)
              - python
              - nanobind >=2.0.0
            run:
              - python

        # ── 2. Stubs — noarch, built only on the host (linux-64) ───────────────────
        - package:
            name: cpp_math-stubs
            version: ${{ version }}
          build:
            number: 0
            noarch: python    # (4)
            skip:
              - build_platform == "linux-aarch64"   # (5)
            script: |
              mkdir -p build && rm -rf build/*
              cmake -GNinja -Bbuild -S . \
                ${CMAKE_ARGS} \
                -DSTUBS_ONLY=ON \
                -DCMAKE_INSTALL_PREFIX=$PREFIX \
                -DCMAKE_PREFIX_PATH=$PREFIX \
                -DCMAKE_MODULE_PATH=$PREFIX/share/cmake/Modules \
                -DCMAKE_BUILD_TYPE=Release
              ninja -C build py_phoenix_socket_backend_stub
          requirements:
            run_constraints:
              - cpp_math ==${{ version }}
            build:
              - cmake
              - ninja
            host:
              - python
              - nanobind >=2.0.0
              - ${{ pin_subpackage("cpp_math") }}   # (6)
            run:
              - python

#. **``source.path: ../``** — points to the workspace root.
   rattler-build may skip untracked files; make sure your source files
   are tracked by git, or use ``git_url`` instead.
#. **``build`` dependencies** run on the *host machine*.
   ``${{ compiler('cxx') }}`` resolves to the right cross-compiler
   automatically.
#. **``host`` dependencies** are installed in the *target prefix*
   (``$PREFIX``). Python and nanobind headers are there, not in the
   build environment.
#. **``noarch: python``** means the stubs package contains only Python
   files (``.pyi``, ``py.typed``) and can be installed on any platform.
#. **``skip`` on ``linux-aarch64``** prevents rattler-build from trying
   to run stubs on a cross-compiled build where the ``.so`` cannot be
   imported natively.
#. **``${{ pin_subpackage("cpp_math") }}`` in ``host``** installs the
   native ``.so`` from the native package into the stub-generation build
   environment so ``nanobind_add_stub`` can import it to generate the
   stubs.

--------------

Testing\ `# <#testing>`__
-------------------------

Native build on linux-64 host\ `# <#native-build-on-linux-64-host>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. container:: language-bash highlight

   ::

      pixi build --output-dir output

This produces two packages under ``output/``:

.. container:: language-text highlight

   ::

      output/
      └── cpp_math-0.1.0-Linux64Hash_0.conda          ← compiled extension for linux-64
      └── cpp_math-stubs-0.1.0-Linux64Hash_0.conda    ← stubs (platform-independent)

Cross-compilation build on linux-64 host\ `# <#cross-compilation-build-on-linux-64-host>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. container:: language-bash highlight

   ::

      pixi build --target-platform linux-aarch64 --output-dir output

A third package is added:

.. container:: language-text highlight

   ::

      output/
      └── cpp_math-0.1.0-Linux64Hash_0.conda          ← compiled extension for linux-64
      └── cpp_math-stubs-0.1.0-Linux64Hash_0.conda    ← stubs (platform-independent)
      └── cpp_math-0.1.0-LinuxAarch64Hash_0.conda     ← compiled extension for linux-64

The stubs package is **not** rebuilt: since it is ``noarch``, the one
produced during the native build can be reused on ``linux-aarch64`` as
well.

Verifying the ELF architecture\ `# <#verifying-the-elf-architecture>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To check that the packages have the correct architecture, run :

.. container:: language-bash highlight

   ::

      cd output && \
      rattler-build package extract YOUR_PACKAGE_NAME
      jq '.platform, .subdir' YOUR_PACKAGE_DIR/info/index.json && \
      rm -rf YOUR_PACKAGE_DIR && \
      cd ..

Example using ``cpp_math`` project :

.. container:: language-bash highlight

   ::

      cd output && \
      rattler-build package extract cpp_math-0.1.0-hb0f4dca_0.conda
      jq '.platform, .subdir' cpp_math-0.1.0-hb0f4dca_0/info/index.json && \
      rm -rf cpp_math-0.1.0-hb0f4dca_0 && \
      cd ..

For the ``linux-64`` package, output should be

.. container:: language-bash highlight

   ::

      "linux"
      "linux-64"

For the ``linux-aarch64`` package, output should be

.. container:: language-bash highlight

   ::

      "linux"
      "linux-aarch64"

For the ``stub`` package, output should be

.. container:: language-bash highlight

   ::

      "null"
      "noarch"

--------------

Summary\ `# <#summary>`__
-------------------------

+----------------------------------+----------------------------------+
| Issue                            | Solution                         |
+==================================+==================================+
| Cross-compilation breaks         | Locate nanobind/Python manually  |
| ``find_package(Python)``         | via ``$PREFIX``                  |
+----------------------------------+----------------------------------+
| Stubs require importing the      | Separate ``noarch`` package for  |
| platform-specific ``.so``        | stubs, skipped on cross builds   |
+----------------------------------+----------------------------------+
| Single CMakeLists to build both  | ``STUBS_ONLY`` option switches   |
| packages                         | behavior                         |
+----------------------------------+----------------------------------+
| Stubs still available on other   | ``noarch: python`` package is    |
| platform                         | platform-independent             |
+----------------------------------+----------------------------------+

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/build/cross_compilation.md
