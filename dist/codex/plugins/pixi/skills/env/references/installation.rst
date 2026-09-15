|image1|

Installation
============

To install ``pixi`` you can run the following command in your terminal:

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      Linux & macOS
      Windows

   .. container:: tabbed-content

      .. container:: tabbed-block

         .. container:: language-bash highlight

            ::

               curl -fsSL https://pixi.sh/install.sh | sh

         If your system doesn't have ``curl``, you can use ``wget``:

         .. container:: language-bash highlight

            ::

               wget -qO- https://pixi.sh/install.sh | sh

         What does this do?
         The above invocation will automatically download the latest
         version of ``pixi``, extract it, and move the ``pixi`` binary
         to ``~/.pixi/bin``. The script will also extend the ``PATH``
         environment variable in the startup script of your shell to
         include ``~/.pixi/bin``. This allows you to invoke ``pixi``
         from anywhere.

      .. container:: tabbed-block

         `Download
         installer <https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-pc-windows-msvc.msi>`__

         Or run:

         .. container:: language-powershell highlight

            ::

               powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"

         What does this do?
         The above invocation will automatically download the latest
         version of ``pixi``, extract it, and move the ``pixi`` binary
         to ``%UserProfile%\.pixi\bin``. The command will also add
         ``%UserProfile%\.pixi\bin`` to your ``PATH`` environment
         variable, allowing you to invoke ``pixi`` from anywhere.

Now restart your terminal or shell to make the installation take effect.

Don't trust our link? Check the script!

You can check the installation ``sh`` script:
`download <https://pixi.sh/install.sh>`__ and the ``ps1``:
`download <https://pixi.sh/install.ps1>`__. The scripts are open source
and available on
`GitHub <https://github.com/prefix-dev/pixi/tree/main/install>`__.

.. admonition::

   Don't forget to add autocompletion!

   After installing Pixi, you can enable autocompletion for your shell.
   See the `Autocompletion <#autocompletion>`__ section below for
   instructions.

Update\ `# <#update>`__
-----------------------

Updating is as simple as installing, rerunning the installation script
gets you the latest version.

.. container:: language-shell highlight

   ::

      pixi self-update

Or get a specific Pixi version using:

.. container:: language-shell highlight

   ::

      pixi self-update --version x.y.z

.. admonition::

   Note

   If you've used a package manager like ``brew``, ``mamba``, ``conda``,
   ``paru`` etc. to install ``pixi`` you must use the built-in update
   mechanism. e.g. ``brew upgrade pixi``.

Alternative Installation Methods\ `# <#alternative-installation-methods>`__
---------------------------------------------------------------------------

Although we recommend installing Pixi through the above method we also
provide additional installation methods.

Homebrew\ `# <#homebrew>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pixi is available via homebrew. To install Pixi via homebrew simply run:

.. container:: language-shell highlight

   ::

      brew install pixi

Windows Installer\ `# <#windows-installer>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We provide an ``msi`` installer on `our GitHub releases
page <https://github.com/prefix-dev/pixi/releases/latest>`__. The
installer will download Pixi and add it to the ``PATH``.

Winget\ `# <#winget>`__
~~~~~~~~~~~~~~~~~~~~~~~

.. container:: language-text highlight

   ::

      winget install prefix-dev.pixi

Scoop\ `# <#scoop>`__
~~~~~~~~~~~~~~~~~~~~~

.. container:: language-text highlight

   ::

      scoop install main/pixi

Download From GitHub Releases\ `# <#download-from-github-releases>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pixi is a single executable and can be run without any external
dependencies. That means you can manually download the suitable archive
for your architecture and operating system from our `GitHub
releases <https://github.com/prefix-dev/pixi/releases>`__, unpack it and
then use it as is. If you want ``pixi`` itself or the executables
installed via ``pixi global`` to be available in your ``PATH``, you have
to add them manually. The executables are located in
`PIXI_HOME <../reference/environment_variables/>`__/bin.

Install From Source\ `# <#install-from-source>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

pixi is 100% written in Rust, and therefore it can be installed, built
and tested with cargo. To start using Pixi from a source build run:

.. container:: language-shell highlight

   ::

      cargo install --locked --git https://github.com/prefix-dev/pixi.git pixi

We don't publish to ``crates.io`` anymore, so you need to install it
from the repository. The reason for this is that we depend on some
unpublished crates which disallows us to publish to ``crates.io``.

or when you want to make changes use:

.. container:: language-shell highlight

   ::

      cargo build
      cargo test

If you have any issues building because of the dependency on ``rattler``
check out its `compile
steps <https://github.com/conda/rattler/tree/main#give-it-a-try>`__.

Installer Script Options\ `# <#installer-script-options>`__
-----------------------------------------------------------

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      Linux & macOS
      Windows

   .. container:: tabbed-content

      .. container:: tabbed-block

         The installation script has several options that can be
         manipulated through environment variables.

         .. list-table::
            :header-rows: 1
            :widths: 24 44 32

            * - Variable
              - Description
              - Default Value
            * - ``PIXI_VERSION``
              - The version of Pixi getting installed, can be used to
                up- or down-grade.
              - ``latest``
            * - ``PIXI_HOME``
              - The location of the pixi home folder containing global
                environments and configs.
              - ``$HOME/.pixi``
            * - ``PIXI_BIN_DIR``
              - The location where the standalone pixi binary should be
                installed.
              - ``$PIXI_HOME/bin``
            * - ``PIXI_ARCH``
              - The architecture the Pixi version was built for.
              - ``uname -m``
            * - ``PIXI_NO_PATH_UPDATE``
              - If set the ``$PATH`` will not be updated to add
                ``pixi`` to it.
              -
            * - ``PIXI_DOWNLOAD_URL``
              - Overrides the download URL for the Pixi binary (useful
                for mirrors or custom builds).
              - GitHub releases, e.g.
                `linux-64 asset <https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-unknown-linux-musl.tar.gz>`__
            * - ``NETRC``
              - Path to a custom ``.netrc`` file for authentication with
                private repositories.
              -
            * - ``TMP_DIR``
              - The temporary directory the script uses to download to
                and unpack the binary from.
              - ``/tmp``

         For example, on Apple Silicon, you can force the installation
         of the x86 version:

         .. container:: language-shell highlight

            ::

               curl -fsSL https://pixi.sh/install.sh | PIXI_ARCH=x86_64 bash

         Or set the version

         .. container:: language-shell highlight

            ::

               curl -fsSL https://pixi.sh/install.sh | PIXI_VERSION=v0.18.0 bash

         To make a "drop-in" installation of pixi directly in the user
         ``$PATH``:

         .. container:: language-shell highlight

            ::

               curl -fsSL https://pixi.sh/install.sh | PIXI_BIN_DIR=/usr/local/bin PIXI_NO_PATH_UPDATE=1 bash

         .. rubric:: Using ``.netrc`` for
            Authentication\ `# <#using-netrc-for-authentication>`__
            :name: using-netrc-for-authentication

         If you need to download Pixi from a private repository that
         requires authentication, you can use a ``.netrc`` file instead
         of hardcoding credentials in the ``PIXI_DOWNLOAD_URL``.

         The install script automatically uses ``.netrc`` for
         authentication with ``curl`` and ``wget``. By default, it looks
         for ``~/.netrc``. You can specify a custom location using the
         ``NETRC`` environment variable:

         .. container:: language-shell highlight

            ::

               # Use the default ~/.netrc file
               curl -fsSL https://pixi.sh/install.sh | PIXI_DOWNLOAD_URL=https://private.example.com/pixi-latest.tar.gz bash

         .. container:: language-shell highlight

            ::

               # Use a custom .netrc file
               curl -fsSL https://pixi.sh/install.sh | NETRC=/path/to/custom/.netrc PIXI_DOWNLOAD_URL=https://private.example.com/pixi-latest.tar.gz bash

         Your ``.netrc`` file should contain credentials in the
         following format:

         .. container:: language-text highlight

            ::

               machine private.example.com
               login your-username
               password your-token-or-password

         .. admonition::

            Security Recommendation

            Using ``.netrc`` is more secure than embedding credentials
            directly in the ``PIXI_DOWNLOAD_URL`` (e.g.,
            ``https://user:pass@example.com/file``), as it keeps
            credentials separate from the URL and prevents them from
            appearing in logs or process listings.

         .. admonition::

            Security Note

            The install script automatically masks any credentials
            embedded in the download URL when displaying messages,
            replacing them with ``***:***@`` to prevent credentials from
            appearing in logs or console output.

      .. container:: tabbed-block

         The installation script has several options that can be
         manipulated through environment variables.

         .. list-table::
            :header-rows: 1
            :widths: 24 44 32

            * - Environment variable
              - Description
              - Default Value
            * - ``PIXI_VERSION``
              - The version of Pixi getting installed, can be used to
                up- or down-grade.
              - ``latest``
            * - ``PIXI_HOME``
              - The location of the installation.
              - ``$Env:USERPROFILE\.pixi``
            * - ``PIXI_NO_PATH_UPDATE``
              - If set, the ``$PATH`` will not be updated to add
                ``pixi`` to it.
              - ``false``
            * - ``PIXI_DOWNLOAD_URL``
              - Overrides the download URL for the Pixi binary (useful
                for mirrors or custom builds).
              - GitHub releases, e.g.
                `win-64 asset <https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-pc-windows-msvc.zip>`__

         For example, set the version:

         .. container:: language-powershell highlight

            ::

               $env:PIXI_VERSION='v0.18.0'; powershell -ExecutionPolicy Bypass -Command "iwr -useb https://pixi.sh/install.ps1 | iex"

         .. rubric:: Authentication for Private
            Repositories\ `# <#authentication-for-private-repositories>`__
            :name: authentication-for-private-repositories

         If you need to download Pixi from a private repository that
         requires authentication, you can embed credentials in the
         ``PIXI_DOWNLOAD_URL``. The install script will automatically
         mask credentials in its output for security.

         .. container:: language-powershell highlight

            ::

               $env:PIXI_DOWNLOAD_URL='https://username:token@private.example.com/pixi-latest.zip'; powershell -ExecutionPolicy Bypass -Command "iwr -useb https://pixi.sh/install.ps1 | iex"

         .. admonition::

            Security Note

            The PowerShell install script automatically masks any
            credentials embedded in the download URL when displaying
            messages, replacing them with ``***:***@`` to prevent
            credentials from appearing in logs or console output.

Autocompletion\ `# <#autocompletion>`__
---------------------------------------

To get autocompletion follow the instructions for your shell.
Afterwards, restart the shell or source the shell config file.

.. container:: tabbed-set tabbed-alternate

   .. container:: tabbed-labels

      Bash
      Zsh
      PowerShell
      Fish
      Nushell
      Elvish

   .. container:: tabbed-content

      .. container:: tabbed-block

         Add the following to the end of ``~/.bashrc``:

         .. container:: language-bash highlight

            ~/.bashrc
            ::

               eval "$(pixi completion --shell bash)"

      .. container:: tabbed-block

         Add the following to the end of ``~/.zshrc``:

         .. container:: language-zsh highlight

            ~/.zshrc
            ::

               autoload -Uz compinit && compinit  # redundant with Oh My Zsh
               eval "$(pixi completion --shell zsh)"

      .. container:: tabbed-block

         Add the following to the end of
         ``Microsoft.PowerShell_profile.ps1``. You can check the
         location of this file by querying the ``$PROFILE`` variable in
         PowerShell. Typically the path is
         ``~\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`` or
         ``~/.config/powershell/Microsoft.PowerShell_profile.ps1`` on
         -Nix.

         .. container:: language-pwsh highlight

            ::

               (& pixi completion --shell powershell) | Out-String | Invoke-Expression

      .. container:: tabbed-block

         Add the following to the end of ``~/.config/fish/config.fish``:

         .. container:: language-fish highlight

            ~/.config/fish/config.fish
            ::

               pixi completion --shell fish | source

      .. container:: tabbed-block

         Add the following to your Nushell config file (find it by
         running ``$nu.config-path`` in Nushell):

         .. container:: language-text highlight

            ::

               mkdir $"($nu.data-dir)/vendor/autoload"
               pixi completion --shell nushell | save --force $"($nu.data-dir)/vendor/autoload/pixi-completions.nu"

      .. container:: tabbed-block

         Add the following to the end of ``~/.elvish/rc.elv``:

         .. container:: language-text highlight

            ~/.elvish/rc.elv
            ::

               eval (pixi completion --shell elvish | slurp)

Uninstall\ `# <#uninstall>`__
-----------------------------

Before un-installation you might want to delete any files pixi managed.

#. Remove any cached data:

   .. container:: language-shell highlight

      ::

         pixi clean cache

#. Remove the environments from your pixi workspaces:

   .. container:: language-shell highlight

      ::

         cd path/to/workspace && pixi clean

#. Remove the ``pixi`` and its global environments

   .. container:: language-shell highlight

      ::

         rm -r ~/.pixi

#. Remove the pixi binary from your ``PATH``:

   -  For Linux and macOS, remove ``~/.pixi/bin`` from your ``PATH`` in
      your shell configuration file (e.g., ``~/.bashrc``, ``~/.zshrc``).
   -  For Windows, remove ``%UserProfile%\.pixi\bin`` from your ``PATH``
      environment variable.

.. |image1| image:: data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTIwLjcxIDcuMDRjLjM5LS4zOS4zOS0xLjA0IDAtMS40MWwtMi4zNC0yLjM0Yy0uMzctLjM5LTEuMDItLjM5LTEuNDEgMGwtMS44NCAxLjgzIDMuNzUgMy43NU0zIDE3LjI1VjIxaDMuNzVMMTcuODEgOS45M2wtMy43NS0zLjc1eiI+PC9wYXRoPjwvc3ZnPg==
   :target: https://github.com/prefix-dev/pixi/edit/main/docs/installation.md
