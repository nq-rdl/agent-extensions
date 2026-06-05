|image1|

Rust
====

In this tutorial, we will show you how to develop a Rust package using
``pixi``. The tutorial is written to be executed from top to bottom,
missing steps might result in errors.

The audience for this tutorial is developers who are familiar with Rust
and ``cargo`` and who are interested to try Pixi for their development
workflow. The benefit would be within a Rust workflow that you lock both
Rust and the C/System dependencies your project might be using. For
example Tokio users might depend on ``openssl`` for Linux.

Prerequisites\ `# <#prerequisites>`__
-------------------------------------

-  You need to have ``pixi`` installed. If you haven't installed it yet,
   you can follow the instructions in the `installation
   guide <../../>`__. The crux of this tutorial is to show you only need
   pixi!

Create a Pixi workspace\ `# <#create-a-pixi-workspace>`__
---------------------------------------------------------

.. container:: language-shell highlight

   ::

      pixi init my_rust_project
      cd my_rust_project

It should have created a directory structure like this:

.. container:: language-shell highlight

   ::

      my_rust_project
      ├── .gitattributes
      ├── .gitignore
      └── pixi.toml

The ``pixi.toml`` file is the manifest file for your workspace. It
should look like this:

.. container:: language-toml highlight

   pixi.toml
   ::

      [workspace]
      name = "my_rust_project"
      version = "0.1.0"
      description = "Add a short description here"
      authors = ["User Name <user.name@email.url>"]
      channels = ["conda-forge"] # (1)!
      platforms = ["linux-64"] # (2)!

      [tasks]

      [dependencies]

#. ``conda-forge`` is the default conda channel for Pixi. You can change
   it to any compatible conda channel. Or include multiple conda
   channels, e.g. ``["robostack", "bioconda"]``.

#. The ``platforms`` is set to your system's platform by default. You
   can change it to any platform you want to support. e.g.
   ``["linux-64", "osx-64", "osx-arm64", "win-64"]``.

Add Rust dependencies\ `# <#add-rust-dependencies>`__
-----------------------------------------------------

To use a Pixi workspace you don't need any dependencies on your system,
all the dependencies you need should be added through pixi, so other
users can use your workspace without any issues.

.. container:: language-shell highlight

   ::

      pixi add rust

This will add the ``rust`` package to your ``pixi.toml`` file under
``[dependencies]``. Which includes the ``rust`` toolchain, and
``cargo``.

Add a ``cargo`` project\ `# <#add-a-cargo-project>`__
-----------------------------------------------------

Now that you have Rust installed, you can create a ``cargo`` project in
your ``pixi`` workspace.

.. container:: language-shell highlight

   ::

      pixi run cargo init

``pixi run`` is Pixi's way to run commands in an environment. It will
make sure that the environment is activated for the command to run. It
runs its own cross-platform shell, if you want more information checkout
the `tasks documentation <../../workspace/advanced_tasks/>`__. You
can also activate the environment in a shell by running ``pixi shell``,
after that you don't need ``pixi run`` anymore.

Now we can build a ``cargo`` project using ``pixi``.

.. container:: language-shell highlight

   ::

      pixi run cargo build

To simplify the build process, you can add a ``build`` task to your
``pixi.toml`` file using the following command:

.. container:: language-shell highlight

   ::

      pixi task add build "cargo build"

Which creates this field in the ``pixi.toml`` file:

.. container:: language-toml highlight

   pixi.toml
   ::

      [tasks]
      build = "cargo build"

And now you can build your project using:

.. container:: language-shell highlight

   ::

      pixi run build

You can also run your project using:

.. container:: language-shell highlight

   ::

      pixi run cargo run

Which you can simplify with a task again.

.. container:: language-shell highlight

   ::

      pixi task add start "cargo run"

So you should get the following output:

.. container:: language-shell highlight

   ::

      pixi run start
      Hello, world!

Congratulations, you have a Rust project running on your machine with
Pixi!

Next steps, why is this useful when there is ``rustup``?\ `# <#next-steps-why-is-this-useful-when-there-is-rustup>`__
---------------------------------------------------------------------------------------------------------------------

Cargo is not a binary package manager, but a source-based package
manager. This means that you need to have the Rust compiler installed on
your system to use it. And possibly other dependencies that are not
included in the ``cargo`` package manager. For example, you might need
to install ``openssl`` or ``libssl-dev`` on your system to build a
package. This is the case for ``pixi`` as well, but ``pixi`` will
install these dependencies in your workspace folder, so you don't have
to worry about them.

Add the following dependencies to your cargo project:

.. container:: language-shell highlight

   ::

      pixi run cargo add git2

If your system is not preconfigured to build C and have the
``libssl-dev`` package installed you will not be able to build the
project:

.. container:: language-shell highlight

   ::

      pixi run build
      ...
      Could not find directory of OpenSSL installation, and this `-sys` crate cannot
      proceed without this knowledge. If OpenSSL is installed and this crate had
      trouble finding it,  you can set the `OPENSSL_DIR` environment variable for the
      compilation process.

      Make sure you also have the development packages of openssl installed.
      For example, `libssl-dev` on Ubuntu or `openssl-devel` on Fedora.

      If you are in a situation where you think the directory *should* be found
      automatically, please open a bug at https://github.com/sfackler/rust-openssl
      and include information about your system as well as this message.

      $HOST = x86_64-unknown-linux-gnu
      $TARGET = x86_64-unknown-linux-gnu
      openssl-sys = 0.9.102


      It looks like you are compiling on Linux and also targeting Linux. Currently this
      requires the `pkg-config` utility to find OpenSSL but unfortunately `pkg-config`
      could not be found. If you have OpenSSL installed you can likely fix this by
      installing `pkg-config`.
      ...

You can fix this, by adding the necessary dependencies for building
git2, with pixi:

.. container:: language-shell highlight

   ::

      pixi add openssl pkg-config compilers

Now you should be able to build your project again:

.. container:: language-shell highlight

   ::

      pixi run build
      ...
         Compiling git2 v0.18.3
         Compiling my_rust_project v0.1.0 (/my_rust_project)
          Finished dev [unoptimized + debuginfo] target(s) in 7.44s
           Running `target/debug/my_rust_project`

Extra: Add more tasks\ `# <#extra-add-more-tasks>`__
----------------------------------------------------

You can add more tasks to your ``pixi.toml`` file to simplify your
workflow.

For example, you can add a ``test`` task to run your tests:

.. container:: language-shell highlight

   ::

      pixi task add test "cargo test"

And you can add a ``clean`` task to clean your project:

.. container:: language-shell highlight

   ::

      pixi task add clean "cargo clean"

You can add a formatting task to your project:

.. container:: language-shell highlight

   ::

      pixi task add fmt "cargo fmt"

You can extend these tasks to run multiple commands with the use of the
``depends-on`` field.

.. container:: language-shell highlight

   ::

      pixi task add lint "cargo clippy" --depends-on fmt

Conclusion\ `# <#conclusion>`__
-------------------------------

In this tutorial, we showed you how to create a Rust project using
``pixi``. We also showed you how to **add dependencies** to your project
using ``pixi``. This way you can make sure that your project is
**reproducible** on **any system** that has ``pixi`` installed.

Show Off Your Work!\ `# <#show-off-your-work>`__
------------------------------------------------

Finished with your project? We'd love to see what you've created! Share
your work on social media using the hashtag #pixi and tag us
@prefix_dev. Let's inspire the community together!

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/tutorials/rust.md
