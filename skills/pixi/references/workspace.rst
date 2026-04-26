|image1|

Multiple Packages in Workspace
==============================

In this tutorial, we will show you how to integrate multiple Pixi
packages into a single workspace.

.. admonition::

   Warning

   ``pixi-build`` is a preview feature, and will change until it is
   stabilized. Please keep that in mind when you use it for your
   projects.

Why is This Useful?\ `# <#why-is-this-useful>`__
------------------------------------------------

The packages coming from conda channels are already built and ready to
use. If you want to depend on a package you therefore typically get that
package from such a channel. However, there are situations where you
want to depend on the source of a package. This is the case for example
if you want to develop on multiple packages within the same repository.
Or if you need the changes of an unreleased version of one of your
dependencies.

Let's Get Started\ `# <#lets-get-started>`__
--------------------------------------------

In this tutorial we will showcase how to develop two packages in one
workspace. For that we will use the ``python_rich`` Python package
developed in chapter `Building a Python package <../python/>`__ and let
it depend on the ``cpp_math`` C++ package developed in chapter `Building
a C++ package <../cpp/>`__.

We will start with the original setup of ``python_rich`` and copy
``cpp_math`` into a folder called ``packages``. The source directory
structure now looks like this:

.. container:: language-shell highlight

   ::

      .
      ├── packages
      │   └── cpp_math
      │       ├── CMakeLists.txt
      │       ├── pixi.toml
      │       └── src
      │           └── math.cpp
      ├── pixi.lock
      ├── pixi.toml
      ├── pyproject.toml
      └── src
          └── python_rich
              └── __init__.py

Within a Pixi manifest, you can manage a workspace and/or describe a
package. In the case of ``python_rich`` we choose to do both, so the
only thing we have to add ``cpp_math`` as a `run
dependency <../../reference/pixi_manifest/#run-dependencies>`__ of
``python_rich``.

.. container:: language-py highlight

   pixi.toml
   ::

      [package.run-dependencies]
      cpp_math = { path = "packages/cpp_math" }
      rich = "13.9.*"

We only want to use the ``workspace`` table of the top-level manifest.
Therefore, we can remove the workspace section in the manifest of
``cpp_math``.

.. container:: language-diff highlight

   packages/cpp_math/pixi.toml
   ::

      -[workspace]
      -channels = ["https://prefix.dev/conda-forge"]
      -platforms = ["osx-arm64", "osx-64", "linux-64", "win-64"]
      -preview = ["pixi-build"]
      -
      -[dependencies]
      -cpp_math = { path = "." }
      -
      -[tasks]
      -start = "python -c 'import cpp_math as b; print(b.add(1, 2))'"

There is actually one problem with ``python_rich``. The age of every
person is off by one year!

.. container:: language-text highlight

   ::

      ┏━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━┓
      ┃ name         ┃ age ┃ city        ┃
      ┡━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━┩
      │ John Doe     │ 30  │ New York    │
      │ Jane Smith   │ 25  │ Los Angeles │
      │ Tim de Jager │ 35  │ Utrecht     │
      └──────────────┴─────┴─────────────┘

We need to add one year to the age of every person. Luckily ``cpp_math``
exposes a function ``add`` which allows us to do exactly that.

.. container:: language-py highlight

   src/python_rich/\__init\_\_.py
   ::

      from dataclasses import dataclass, fields
      from rich.console import Console
      from rich.table import Table
      import cpp_math


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
              updated_age = cpp_math.add(person.age, 1)
              table.add_row(person.name, str(updated_age), person.city)

          console.print(table)

If you run ``pixi run start``, the age of each person should now be
accurate:

.. container:: language-text highlight

   ::

      ┏━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━┓
      ┃ name         ┃ age ┃ city        ┃
      ┡━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━┩
      │ John Doe     │ 31  │ New York    │
      │ Jane Smith   │ 26  │ Los Angeles │
      │ Tim de Jager │ 36  │ Utrecht     │
      └──────────────┴─────┴─────────────┘

Conclusion\ `# <#conclusion>`__
-------------------------------

In this tutorial, we created a Pixi workspace containing two packages.
The manifest of ``python_rich`` describes the workspace as well as the
package, with ``cpp_math`` only the ``package`` section is used. Feel
free to add more packages, written in different languages to this
workspace!

Thanks for reading! Happy Coding 🚀

Any questions? Feel free to reach out or share this tutorial on
`X <https://twitter.com/prefix_dev>`__, `join our
Discord <https://discord.gg/kKV8ZxyzY4>`__, send us an
`e-mail <mailto:hi@prefix.dev>`__ or follow our
`GitHub <https://github.com/prefix-dev>`__.

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/build/workspace.md
