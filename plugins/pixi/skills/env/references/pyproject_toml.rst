|image1|

pyproject.toml
==============

We support the use of the ``pyproject.toml`` as our manifest file in
pixi. This allows the user to keep one file with all configuration. The
``pyproject.toml`` file is a standard for Python projects. We don't
advise to use the ``pyproject.toml`` file for anything else than python
projects, the ``pixi.toml`` is better suited for other types of
projects.

.. _initial-setup-of-the-pyprojecttoml-file:

Initial setup of the ``pyproject.toml`` file\ `# <#initial-setup-of-the-pyprojecttoml-file>`__
----------------------------------------------------------------------------------------------

When you already have a ``pyproject.toml`` file in your project, you can
run ``pixi init`` in that folder. Pixi will automatically

-  Add a ``[tool.pixi.workspace]`` section to the file, with the
   platform and channel information required by pixi;
-  Add the current project as an editable pypi dependency;
-  Add some defaults to the ``.gitignore`` and ``.gitattributes`` files.

If you do not have an existing ``pyproject.toml`` file , you can run
``pixi init --format pyproject`` in your project folder. In that case,
Pixi will create a ``pyproject.toml`` manifest from scratch with some
sane defaults.

Python dependency\ `# <#python-dependency>`__
---------------------------------------------

The ``pyproject.toml`` file supports the ``requires_python`` field. Pixi
understands that field and automatically adds the version to the
dependencies.

This is an example of a ``pyproject.toml`` file with the
``requires_python`` field, which will be used as the python dependency:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      name = "my_project"
      requires-python = ">=3.9"

      [tool.pixi.workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]

Which is equivalent to:

.. container:: language-toml highlight

   equivalent pixi.toml
   ::

      [workspace]
      name = "my_project"
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]

      [dependencies]
      python = ">=3.9"

Dependency section\ `# <#dependency-section>`__
-----------------------------------------------

The ``pyproject.toml`` file supports the ``dependencies`` field. Pixi
understands that field and automatically adds the dependencies to the
workspace as ``[pypi-dependencies]``.

This is an example of a ``pyproject.toml`` file with the
``dependencies`` field:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      name = "my_project"
      requires-python = ">=3.9"
      dependencies = [
          "numpy",
          "pandas",
          "matplotlib",
      ]

      [tool.pixi.workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]

Which is equivalent to:

.. container:: language-toml highlight

   equivalent pixi.toml
   ::

      [workspace]
      name = "my_project"
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]

      [pypi-dependencies]
      numpy = "*"
      pandas = "*"
      matplotlib = "*"

      [dependencies]
      python = ">=3.9"

You can overwrite these with conda dependencies by adding them to the
``dependencies`` field:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      name = "my_project"
      requires-python = ">=3.9"
      dependencies = [
          "numpy",
          "pandas",
          "matplotlib",
      ]

      [tool.pixi.workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]

      [tool.pixi.dependencies]
      numpy = "*"
      pandas = "*"
      matplotlib = "*"

This would result in the conda dependencies being installed and the pypi
dependencies being ignored. As Pixi takes the conda dependencies over
the pypi dependencies.

Optional dependencies\ `# <#optional-dependencies>`__
-----------------------------------------------------

If your python project includes groups of optional dependencies, Pixi
will automatically interpret them as `Pixi
features <../../reference/pixi_manifest/#the-feature-table>`__ of the
same name with the associated ``pypi-dependencies``.

You can add them to Pixi environments manually, or use ``pixi init`` to
setup the workspace, which will create one environment per feature.
Self-references to other groups of optional dependencies are also
handled.

For instance, imagine you have a project folder with a
``pyproject.toml`` file similar to:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      name = "my_project"
      dependencies = ["package1"]

      [project.optional-dependencies]
      test = ["pytest"]
      all = ["package2","my_project[test]"]

Running ``pixi init`` in that project folder will transform the
``pyproject.toml`` file into:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      name = "my_project"
      dependencies = ["package1"]

      [project.optional-dependencies]
      test = ["pytest"]
      all = ["package2","my_project[test]"]

      [tool.pixi.workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64"] # if executed on linux

      [tool.pixi.environments]
      default = {features = [], solve-group = "default"}
      test = {features = ["test"], solve-group = "default"}
      all = {features = ["all"], solve-group = "default"}

In this example, three environments will be created by Pixi:

-  **default** with 'package1' as pypi dependency
-  **test** with 'package1' and 'pytest' as pypi dependencies
-  **all** with 'package1', 'package2' and 'pytest' as pypi dependencies

All environments will be solved together, as indicated by the common
``solve-group``, and added to the lock file. You can edit the
``[tool.pixi.environments]`` section manually to adapt it to your use
case (e.g. if you do not need a particular environment).

Dependency groups\ `# <#dependency-groups>`__
---------------------------------------------

If your python project includes dependency groups, Pixi will
automatically interpret them as `Pixi
features <../../reference/pixi_manifest/#the-feature-table>`__ of the
same name with the associated ``pypi-dependencies``.

You can add them to Pixi environments manually, or use ``pixi init`` to
setup the workspace, which will create one environment per dependency
group.

For instance, imagine you have a project folder with a
``pyproject.toml`` file similar to:

.. container:: language-toml highlight

   ::

      [project]
      name = "my_project"
      dependencies = ["package1"]

      [dependency-groups]
      test = ["pytest"]
      docs = ["sphinx"]
      dev = [{include-group = "test"}, {include-group = "docs"}]

Running ``pixi init`` in that project folder will transform the
``pyproject.toml`` file into:

.. container:: language-toml highlight

   ::

      [project]
      name = "my_project"
      dependencies = ["package1"]

      [dependency-groups]
      test = ["pytest"]
      docs = ["sphinx"]
      dev = [{include-group = "test"}, {include-group = "docs"}]

      [tool.pixi.workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64"] # if executed on linux

      [tool.pixi.environments]
      default = {features = [], solve-group = "default"}
      test = {features = ["test"], solve-group = "default"}
      docs = {features = ["docs"], solve-group = "default"}
      dev = {features = ["dev"], solve-group = "default"}

In this example, four environments will be created by pixi:

-  **default** with 'package1' as pypi dependency
-  **test** with 'package1' and 'pytest' as pypi dependencies
-  **docs** with 'package1', 'sphinx' as pypi dependencies
-  **dev** with 'package1', 'sphinx' and 'pytest' as pypi dependencies

All environments will be solved together, as indicated by the common
``solve-group``, and added to the lock file. You can edit the
``[tool.pixi.environments]`` section manually to adapt it to your use
case (e.g. if you do not need a particular environment).

Example\ `# <#example>`__
-------------------------

As the ``pyproject.toml`` file supports the full Pixi spec with
``[tool.pixi]`` prepended an example would look like this:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      name = "my_project"
      requires-python = ">=3.9"
      dependencies = [
          "numpy",
          "pandas",
          "matplotlib",
          "ruff",
      ]

      [tool.pixi.workspace]
      channels = ["conda-forge"]
      platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]

      [tool.pixi.dependencies]
      compilers = "*"
      cmake = "*"

      [tool.pixi.tasks]
      start = "python my_project/main.py"
      lint = "ruff lint"

      [tool.pixi.system-requirements]
      cuda = "11.0"

      [tool.pixi.feature.test.dependencies]
      pytest = "*"

      [tool.pixi.feature.test.tasks]
      test = "pytest"

      [tool.pixi.environments]
      test = ["test"]

Build-system section\ `# <#build-system-section>`__
---------------------------------------------------

The ``pyproject.toml`` file normally contains a ``[build-system]``
section. Pixi will use this section to build and install the project if
it is added as a pypi path dependency.

If the ``pyproject.toml`` file does not contain any ``[build-system]``
section, Pixi will fall back to
`uv <https://github.com/astral-sh/uv>`__'s default, which is equivalent
to the below:

.. container:: language-toml highlight

   pyproject.toml
   ::

      [build-system]
      requires = ["setuptools >= 40.8.0"]
      build-backend = "setuptools.build_meta:__legacy__"

Including a ``[build-system]`` section is **highly recommended**. If you
are not sure of the
`build-backend <https://packaging.python.org/en/latest/tutorials/packaging-projects/#choosing-build-backend>`__
you want to use, including the ``[build-system]`` section below in your
``pyproject.toml`` is a good starting point.
``pixi init --format pyproject`` defaults to ``hatchling``. The
advantages of ``hatchling`` over ``setuptools`` are outlined on its
`website <https://hatch.pypa.io/latest/why/#build-backend>`__.

.. container:: language-toml highlight

   pyproject.toml
   ::

      [build-system]
      build-backend = "hatchling.build"
      requires = ["hatchling"]

.. _development-dependencies-with-tooluvsources:

Development dependencies with ``[tool.uv.sources]``\ `# <#development-dependencies-with-tooluvsources>`__
---------------------------------------------------------------------------------------------------------

Because pixi is using ``uv`` for building its ``pypi-dependencies``, one
can use the ``tool.uv.sources`` section to specify sources for any
pypi-dependencies referenced from the main pixi manifest.

Why is this useful?\ `# <#why-is-this-useful>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you are setting up a monorepo of some sort and you want to be able
for source dependencies to reference each other, you need to use the
``[tool.uv.sources]`` section to specify the sources for those
dependencies. This is because ``uv`` handles both the resolution of PyPI
dependencies and the building of any source dependencies.

.. _example_1:

Example\ `# <#example_1>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given a source tree:

.. container:: language-text highlight

   ::

      .
      ├── main_project
      │   └── pyproject.toml (references a)
      ├── a
      │   └── pyproject.toml (has a dependency on b)
      └── b
          └── pyproject.toml

Concretely what this looks like in the ``pyproject.toml`` for
``main_project``:

.. container:: language-toml highlight

   ::

      [tool.pixi.pypi-dependencies]
      a = { path = "../a" }

Then the ``pyproject.toml`` for ``a`` should contain a
``[tool.uv.sources]`` section.

.. container:: language-toml highlight

   ::

      [project]
      name = "a"
      # other fields
      dependencies = ["flask", "b"]

      [tool.uv.sources]
      # Override the default source for flask with main git branch
      flask = { git = "github.com/pallets/flask", branch = "main" }
      # Reference to b
      b = { path = "../b" }

More information about what is allowed in this sections is available in
the `uv
docs <https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources>`__

.. admonition::

   Note

   The main ``pixi.toml`` or ``pyproject.toml`` is parsed directly by
   pixi and not processed by ``uv``. This means that you **cannot** use
   the ``[tool.uv.sources]`` section in the main ``pixi.toml`` or
   ``pyproject.toml``. This is a limitation we are aware of, feel free
   to open an issue if you would like support for
   `this <https://github.com/prefix-dev/pixi/issues/new/choose>`__.

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/python/pyproject_toml.md
