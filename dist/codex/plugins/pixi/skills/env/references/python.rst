|image1|

Building a Python Package
=========================

In this tutorial, we will show you how to create a simple Python package
with pixi. To read more about how building packages work with Pixi see
the `Getting Started <../getting_started/>`__ guide. You might also want
to check out the `documentation <../backends/pixi-build-python/>`__ for
the ``pixi-build-python`` backend.

.. admonition::

   Warning

   ``pixi-build`` is a preview feature, and will change until it is
   stabilized. Please keep that in mind when you use it for your
   projects.

Why is This Useful?\ `# <#why-is-this-useful>`__
------------------------------------------------

Pixi builds upon the conda ecosystem, which allows you to create a
Python environment with all the dependencies you need. Unlike PyPI, the
conda ecosystem is cross-language and also offers packages written in
Rust, R, C, C++ and many other languages.

By building a Python package with pixi, you can:

#. manage Python packages and packages written in other languages in the
   same workspace
#. build both conda and Python packages with the same tool

In this tutorial we will focus on point 1.

Let's Get Started\ `# <#lets-get-started>`__
--------------------------------------------

First, we create a simple Python package with a ``pyproject.toml`` and a
single Python file. The package will be called ``python_rich``, so we
will create the following structure:

.. container:: language-shell highlight

   ::

      ├── src # (1)!
      │   └── python_rich
      │       └── __init__.py
      └── pyproject.toml

#. This project uses a src-layout, but Pixi supports both `flat- and
   src-layouts <https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/#src-layout-vs-flat-layout>`__.

The Python package has a single function ``main``. Calling that, will
print a table containing the name, age and city of three people.

.. container:: language-py highlight

   src/python_rich/\__init\_\_.py
   ::

      from dataclasses import dataclass, fields
      from rich.console import Console
      from rich.table import Table


      @dataclass
      class Person:
          name: str
          age: int
          city: str


      def main() -> None:
          console = Console()

          people = [
              Person("John Doe", 30, "New York"),
              Person("Jane Smith", 25, "Los Angeles"),
              Person("Tim de Jager", 35, "Utrecht"),
          ]

          table = Table()

          for column in fields(Person):
              table.add_column(column.name)

          for person in people:
              table.add_row(person.name, str(person.age), person.city)

          console.print(table)

The metadata of the Python package is defined in ``pyproject.toml``.

.. container:: language-toml highlight

   pyproject.toml
   ::

      [project]
      dependencies = ["rich"]                              # (1)!
      name = "python_rich"
      requires-python = ">= 3.11"
      scripts = { rich-example-main = "python_rich:main" } # (2)!
      version = "0.1.0"

      [build-system] # (3)!
      build-backend = "hatchling.build"
      requires = ["hatchling"]

#. We use the ``rich`` package to print the table in the terminal.
#. By specifying a script, the executable ``rich-example-main`` will be
   available in the environment. When being called it will in return
   call the ``main`` function of the ``python_rich`` module.
#. One can choose multiple backends to build a Python package, we choose
   ``hatchling`` which works well without additional configuration.

.. _adding-a-pixitoml:

Adding a ``pixi.toml``\ `# <#adding-a-pixitoml>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What we have in the moment, constitutes a full Python package. It could
be uploaded to `PyPI <https://pypi.org/>`__ as-is.

However, we still need a tool to manage our environments and if we want
other Pixi projects to depend on our tool, we need to include more
information. We will do exactly that by creating a ``pixi.toml``.

.. admonition::

   Note

   The Pixi manifest can be in its own ``pixi.toml`` file or integrated
   in ``pyproject.toml`` In this tutorial, we will use ``pixi.toml``. If
   you want everything integrated in ``pyproject.toml`` just copy the
   content of ``pixi.toml`` in this tutorial to your ``pyproject.toml``
   and prepend ``tool.pixi.`` to each table.

Let's initialize a Pixi project.

.. container:: language-text highlight

   ::

      pixi init --format pixi

We pass ``--format pixi`` in order to communicate to pixi, that we want
a ``pixi.toml`` rather than extending ``pyproject.toml``.

.. container:: language-shell highlight

   ::

      ├── src
      │   └── python_rich
      │       └── __init__.py
      ├── .gitignore
      ├── pixi.toml
      └── pyproject.toml

This is the content of the ``pixi.toml``:

.. container:: language-toml highlight

   pixi.toml
   ::

      [workspace] # (1)!
      channels = ["https://prefix.dev/conda-forge"]
      platforms = ["win-64", "linux-64", "osx-arm64", "osx-64"]
      preview = ["pixi-build"]

      [dependencies] # (2)!
      python_rich = { path = "." }

      [tasks] # (3)!
      start = "rich-example-main"

      [package] # (4)!
      name = "python_rich"
      version = "0.1.0"

      [package.build] # (5)!
      backend = { name = "pixi-build-python", version = "0.*" }

      [package.host-dependencies] # (6)!
      hatchling = "==1.26.3"

      [package.run-dependencies] # (7)!
      rich = "13.9.*"

#. In ``workspace`` information is set that is shared across all
   packages in the workspace.
#. In ``dependencies`` you specify all of your Pixi packages. Here, this
   includes only our own package that is defined further below under
   ``package``
#. We define a task that runs the ``rich-example-main`` executable we
   defined earlier. You can learn more about tasks in this
   `section <../../workspace/advanced_tasks/>`__
#. In ``package`` we define the actual Pixi package. This information
   will be used when other Pixi packages or workspaces depend on our
   package or when we upload it to a conda channel.
#. The same way, Python uses build backends to build a Python package,
   Pixi uses build backends to build Pixi packages.
   ``pixi-build-python`` creates a Pixi package out of a Python package.
#. In ``package.host-dependencies``, we add Python dependencies that are
   necessary to build the Python package. By adding them here as well,
   the dependencies will come from the conda channel rather than PyPI.
#. In ``package.run-dependencies``, we add the Python dependencies
   needed during runtime.

When we now run ``pixi run start``, we get the following output:

.. container:: language-text highlight

   ::

      ┏━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━┓
      ┃ name         ┃ age ┃ city        ┃
      ┡━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━┩
      │ John Doe     │ 30  │ New York    │
      │ Jane Smith   │ 25  │ Los Angeles │
      │ Tim de Jager │ 35  │ Utrecht     │
      └──────────────┴─────┴─────────────┘

Conclusion\ `# <#conclusion>`__
-------------------------------

In this tutorial, we created a Pixi package based on Python. It can be
used as-is, to upload to a conda channel or to PyPI. In another tutorial
we will learn how to add multiple Pixi packages to the same workspace
and let one Pixi package use another.

Thanks for reading! Happy Coding 🚀

Any questions? Feel free to reach out or share this tutorial on
`X <https://twitter.com/prefix_dev>`__, `join our
Discord <https://discord.gg/kKV8ZxyzY4>`__, send us an
`e-mail <mailto:hi@prefix.dev>`__ or follow our
`GitHub <https://github.com/prefix-dev>`__.

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/build/python.md
