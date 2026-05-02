Extensions
==========

Quarto extensions add custom functionality including shortcodes,
filters, formats, and RevealJS plugins.

Extension Types
---------------

================ =========================================
Type             Description
================ =========================================
Shortcodes       Custom ``{{< shortcode >}}`` commands
Filters          Pandoc filters for content transformation
Formats          Custom output formats
RevealJS Plugins Presentation enhancements
================ =========================================

Finding Extensions
------------------

Official Repository
~~~~~~~~~~~~~~~~~~~

- `Quarto Extensions <https://quarto.org/docs/extensions/>`__
- Browse by category: filters, shortcodes, formats, etc.

Community Extensions
~~~~~~~~~~~~~~~~~~~~

- `Community Extensions
  List <https://m.canouil.dev/quarto-extensions/>`__
- `Extensions
  JSON <https://m.canouil.dev/quarto-extensions/extensions.json>`__
- Search GitHub for ``quarto-extension``

Installing Extensions
---------------------

Basic Installation
~~~~~~~~~~~~~~~~~~

.. code:: bash

   quarto add username/repository

From GitHub
~~~~~~~~~~~

.. code:: bash

   quarto add quarto-ext/fontawesome
   quarto add shafayetShafee/bsicons

Specific Version
~~~~~~~~~~~~~~~~

.. code:: bash

   quarto add username/repository@v1.0.0

From URL
~~~~~~~~

.. code:: bash

   quarto add https://github.com/user/repo/archive/main.zip

Interactive Installation
~~~~~~~~~~~~~~~~~~~~~~~~

When prompted, confirm trust in the extension source.

Using Extensions
----------------

In Document YAML
~~~~~~~~~~~~~~~~

.. code:: yaml

   ---
   filters:
     - extension-name
   ---

Shortcode Extensions
~~~~~~~~~~~~~~~~~~~~

After installing, use in document:

.. code:: markdown

   {{< fa brands github >}} # Font Awesome icon

Format Extensions
~~~~~~~~~~~~~~~~~

.. code:: yaml

   format: custom-format

Managing Extensions
-------------------

Location
~~~~~~~~

Extensions are stored in ``_extensions/`` directory:

.. code:: txt

   project/
   ├── _extensions/
   │   └── fontawesome/
   │       ├── _extension.yml
   │       └── fontawesome.lua
   ├── document.qmd
   └── _quarto.yml

List Installed Extensions
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   ls _extensions/

Update Extensions
~~~~~~~~~~~~~~~~~

.. code:: bash

   quarto add username/repository  # Re-run to update

Remove Extensions
~~~~~~~~~~~~~~~~~

Delete the folder from ``_extensions/``:

.. code:: bash

   rm -rf _extensions/extension-name

Project vs Document Extensions
------------------------------

Project-Wide
~~~~~~~~~~~~

Install in project root. Available to all documents:

.. code:: txt

   project/
   ├── _extensions/
   ├── chapter1.qmd
   └── chapter2.qmd

Global Extensions
~~~~~~~~~~~~~~~~~

Install in user config (less common):

.. code:: bash

   quarto add --global username/repository

Location: ``~/.local/share/quarto/extensions/``

Popular Extensions
------------------

Icons
~~~~~

.. code:: bash

   quarto add quarto-ext/fontawesome

.. code:: markdown

   {{< fa brands github >}} GitHub
   {{< fa solid envelope >}} Email

Lightbox
~~~~~~~~

.. code:: bash

   quarto add quarto-ext/lightbox

.. code:: yaml

   lightbox: true

Include Code from Files
~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   quarto add quarto-ext/include-code-files

.. code:: markdown

   {{< include-code example.py >}}

Fancy Text
~~~~~~~~~~

.. code:: bash

   quarto add quarto-ext/fancy-text

.. code:: markdown

   {{< lipsum 1 >}}

Social Cards
~~~~~~~~~~~~

.. code:: bash

   quarto add gadenbuie/quarto-social-embeds

.. code:: markdown

   {{< tweet user=username id=123456789 >}}

Extension Configuration
-----------------------

Some extensions have configuration options:

.. code:: yaml

   lightbox:
     match: auto
     effect: zoom
     loop: true

   fontawesome:
     version: 6

Creating Custom Extensions
--------------------------

Basic Structure
~~~~~~~~~~~~~~~

.. code:: txt

   _extensions/
   └── my-extension/
       ├── _extension.yml
       └── my-extension.lua

Extension YAML
~~~~~~~~~~~~~~

In ``_extension.yml``:

.. code:: yaml

   title: My Extension
   author: Your Name
   version: 1.0.0
   contributes:
     shortcodes:
       - my-extension.lua

Shortcode Lua
~~~~~~~~~~~~~

In ``my-extension.lua``:

.. code:: lua

   return {
     ['my-shortcode'] = function(args)
       local text = args[1] or "default"
       return pandoc.Str("Processed: " .. text)
     end
   }

Use
~~~

.. code:: markdown

   {{< my-shortcode "Hello" >}}

Troubleshooting
---------------

Extension Not Found
~~~~~~~~~~~~~~~~~~~

.. code:: txt

   ERROR: Extension not found

- Check extension is in ``_extensions/``
- Verify extension name matches folder

Trust Warning
~~~~~~~~~~~~~

When installing, Quarto asks about trust. Extensions run code during
render.

Conflicts
~~~~~~~~~

If extensions conflict, try:

1. Check extension documentation for compatibility
2. Update extensions to latest versions
3. Report issue to extension maintainer

Extension Sources
-----------------

GitHub Organizations
~~~~~~~~~~~~~~~~~~~~

- ``quarto-ext`` - Official Quarto extensions
- ``quarto-journals`` - Academic journal formats

Popular Repositories
~~~~~~~~~~~~~~~~~~~~

================================= =====================
Extension                         Description
================================= =====================
``quarto-ext/fontawesome``        Font Awesome icons
``quarto-ext/lightbox``           Image lightbox
``quarto-ext/include-code-files`` Include external code
``shafayetShafee/bsicons``        Bootstrap icons
``mcanouil/quarto-letter``        Letter format
``jmbuhr/quarto-molstar``         Molecular viewer
================================= =====================

Best Practices
--------------

Before Installing
~~~~~~~~~~~~~~~~~

1. Check extension source is trustworthy
2. Read the documentation
3. Check compatibility with your Quarto version

In Projects
~~~~~~~~~~~

1. Document which extensions are used
2. Include ``_extensions/`` in version control
3. Pin versions for reproducibility

Updating
~~~~~~~~

1. Test updates in development first
2. Check changelogs for breaking changes
3. Update one at a time

Resources
---------

- `Quarto Extensions Guide <https://quarto.org/docs/extensions/>`__
- `Creating
  Extensions <https://quarto.org/docs/extensions/creating.html>`__
- `Community Extensions <https://m.canouil.dev/quarto-extensions/>`__
- `Extensions JSON
  API <https://m.canouil.dev/quarto-extensions/extensions.json>`__
