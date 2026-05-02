Converting blogdown to Quarto
=============================

Guide for converting blogdown (Hugo-based) sites to Quarto websites or
blogs.

Overview
--------

Key differences:

1. Configuration: ``config.toml`` or ``config.yaml`` → ``_quarto.yml``
2. Content: Hugo templates → Quarto layouts
3. Shortcodes: Hugo → Quarto shortcodes
4. Themes: Hugo themes → Quarto themes

Quick Start
-----------

1. Create Quarto Config
~~~~~~~~~~~~~~~~~~~~~~~

Replace ``config.toml`` or ``config.yaml`` with ``_quarto.yml``:

.. code:: yaml

   project:
     type: website

   website:
     title: "My Site"
     navbar:
       left:
         - href: index.qmd
           text: Home
         - href: about.qmd
           text: About
         - href: blog.qmd
           text: Blog

   format:
     html:
       theme: cosmo

2. Rename Files
~~~~~~~~~~~~~~~

.. code:: bash

   for f in content/**/*.Rmd; do
     mv "$f" "${f%.Rmd}.qmd"
   done

3. Update Front Matter
~~~~~~~~~~~~~~~~~~~~~~

Blogdown
^^^^^^^^

.. code:: yaml

   title: "Post Title"
   author: "Author"
   date: "2024-01-15"
   slug: "post-slug"
   categories: ["R"]
   tags: ["data"]

Quarto
^^^^^^

.. code:: yaml

   title: "Post Title"
   author: "Author"
   date: 2024-01-15
   categories:
     - R
     - data

Project Structure
-----------------

.. _blogdown-1:

blogdown
~~~~~~~~

.. code:: txt

   config.toml (or config.yaml)
   content/
     _index.md
     about.md
     post/
       2024-01-01-first/
         index.Rmd
   static/
     images/
   themes/
     hugo-theme/
   public/

.. _quarto-1:

Quarto
~~~~~~

.. code:: txt

   _quarto.yml
   index.qmd
   about.qmd
   posts/
     first-post/
       index.qmd
   images/
   _site/

Configuration Mapping
---------------------

Basic Site Config
~~~~~~~~~~~~~~~~~

Blogdown (``config.yaml``)
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

   baseURL: "https://example.com/"
   title: "My Site"
   theme: "hugo-theme"

   params:
     description: "Site description"
     author: "Author Name"

   menu:
     main:
       - name: "Home"
         url: "/"
         weight: 1
       - name: "About"
         url: "/about/"
         weight: 2

Quarto (``_quarto.yml``)
^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

   project:
     type: website
     output-dir: _site

   website:
     title: "My Site"
     description: "Site description"
     site-url: https://example.com/
     navbar:
       left:
         - href: index.qmd
           text: Home
         - href: about.qmd
           text: About
         - href: blog.qmd
           text: Blog

   format:
     html:
       theme: cosmo

   author: "Author Name"

The same mapping applies to ``config.toml`` — convert TOML keys to the
equivalent Quarto YAML.

Blog Setup
----------

Listing Page
~~~~~~~~~~~~

Create ``blog.qmd``:

.. code:: yaml

   title: "Blog"
   listing:
     contents: posts
     type: default
     sort: "date desc"
     categories: true
     feed: true

Post Structure
~~~~~~~~~~~~~~

.. code:: txt

   posts/
     2024-01-15-first-post/
       index.qmd
       images/
         figure1.png
     2024-01-20-second-post/
       index.qmd

Post Front Matter
~~~~~~~~~~~~~~~~~

.. code:: yaml

   title: "Post Title"
   description: "Brief description for listing"
   author: "Author Name"
   date: 2024-01-15
   categories:
     - R
     - Tutorial
   image: images/preview.png
   draft: false

Hugo Shortcodes
---------------

Figure
~~~~~~

Hugo
^^^^

.. code:: markdown

   {{</* figure src="image.png" caption="Caption" */>}}

.. _quarto-2:

Quarto
^^^^^^

.. code:: markdown

   ![Caption](image.png)

Tweet
~~~~~

.. _hugo-1:

Hugo
^^^^

.. code:: markdown

   {{</* tweet user="username" id="1234567890" */>}}

Quarto (with extension)
^^^^^^^^^^^^^^^^^^^^^^^

.. code:: markdown

   {{< tweet username 1234567890 >}}

Install extension: ``quarto add sellorm/quarto-social-embeds``

YouTube
~~~~~~~

.. _hugo-2:

Hugo
^^^^

.. code:: markdown

   {{</* youtube VIDEO_ID */>}}
   ```

   #### Quarto

   ````markdown
   {{< video https://www.youtube.com/embed/VIDEO_ID >}}

Gist
~~~~

.. _hugo-3:

Hugo
^^^^

.. code:: markdown

   {{</* gist user gist_id */>}}

Highlight
~~~~~~~~~

.. _hugo-4:

Hugo
^^^^

.. code:: markdown

   {{</* highlight r */>}}
   code here
   {{</* /highlight */>}}
   ```

   #### Quarto

   ````markdown
   ```{.r}
   code here
   ```

or

.. code:: markdown

   ```r
   code here
   ```

Ref/Relref
~~~~~~~~~~

.. _hugo-5:

Hugo
^^^^

.. code:: markdown

   [Link]({{</* ref "other-post.md" */>}})

.. _quarto-3:

Quarto
^^^^^^

.. code:: markdown

   [Link](other-post.qmd)

Taxonomies
----------

blogdown Categories and Tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

   categories: ["R", "Data Science"]
   tags: ["ggplot2", "visualization"]

Quarto Categories
~~~~~~~~~~~~~~~~~

.. code:: yaml

   categories:
     - R
     - Data Science
     - ggplot2
     - visualization

Enable category listing:

.. code:: yaml

   # In blog.qmd
   listing:
     contents: posts
     categories: true

Static Files
------------

.. _blogdown-2:

blogdown
~~~~~~~~

Static files in ``static/`` are copied to site root.

.. _quarto-4:

Quarto
~~~~~~

Put files in project root or use ``resources``:

.. code:: yaml

   # _quarto.yml
   project:
     resources:
       - images/
       - files/

Themes and Styling
------------------

.. _blogdown-3:

blogdown
~~~~~~~~

Uses Hugo themes from ``themes/`` directory.

.. _quarto-5:

Quarto
~~~~~~

Use built-in themes or custom SCSS:

.. code:: yaml

   format:
     html:
       theme:
         - cosmo
         - custom.scss

Custom SCSS
~~~~~~~~~~~

.. code:: scss

   // custom.scss
   $body-bg: #ffffff;
   $body-color: #333333;
   $link-color: #0066cc;

   // Custom rules
   .quarto-title {
     font-size: 2.5rem;
   }

RSS Feed
--------

.. _blogdown-4:

blogdown
~~~~~~~~

Hugo generates RSS automatically.

.. _quarto-6:

Quarto
~~~~~~

Enable in listing:

- ``blog.qmd``

  .. code:: markdown

     ---
     listing:
       feed: true
     ---

Or in ``_quarto.yml``:

.. code:: yaml

   website:
     site-url: https://example.com

   listing:
     feed:
       title: "My Blog"
       description: "Blog description"

Comments
--------

.. _quarto-7:

Quarto
~~~~~~

In ``_quarto.yml``:

.. code:: yaml

   website:
     comments:
       giscus:
         repo: username/repo
         category: "Comments"

Or per-post:

.. code:: yaml

   comments:
     giscus:
       repo: username/repo

Syntax Highlighting
-------------------

.. _blogdown-5:

blogdown
~~~~~~~~

Configured in Hugo config or theme.

.. _quarto-8:

Quarto
~~~~~~

.. code:: yaml

   format:
     html:
       highlight-style: github
       code-line-numbers: true
       code-fold: true

Draft Posts
-----------

.. _blogdown-6:

blogdown
~~~~~~~~

.. code:: yaml

   draft: true

.. _quarto-9:

Quarto
~~~~~~

Same syntax:

.. code:: yaml

   draft: true

Render drafts with:

.. code:: bash

   quarto render --profile drafts

With profile config:

.. code:: yaml

   # _quarto-drafts.yml
   execute:
     echo: true

   website:
     drafts: true

Deployment
----------

Netlify
~~~~~~~

.. code:: yaml

   # netlify.toml
   [build]
     command = "quarto render"
     publish = "_site"

GitHub Pages
~~~~~~~~~~~~

.. code:: yaml

   # .github/workflows/publish.yml
   name: Publish

   on:
     push:
       branches: [main]

   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: quarto-dev/quarto-actions/setup@v2
         - run: quarto render
         - uses: peaceiris/actions-gh-pages@v3
           with:
             github_token: ${{ secrets.GITHUB_TOKEN }}
             publish_dir: ./_site

Common Issues
-------------

Missing Shortcodes
~~~~~~~~~~~~~~~~~~

Install Quarto extensions for missing functionality.

Broken Internal Links
~~~~~~~~~~~~~~~~~~~~~

Update ``.md`` and ``.Rmd`` extensions to ``.qmd``.

Theme Differences
~~~~~~~~~~~~~~~~~

Quarto themes differ from Hugo themes; expect visual changes.

Build Errors
~~~~~~~~~~~~

Check for Hugo-specific template syntax in content files.

Resources
---------

- `Quarto Websites <https://quarto.org/docs/websites/>`__
- `Quarto Blogs <https://quarto.org/docs/websites/website-blog.html>`__
- `Quarto
  Themes <https://quarto.org/docs/output-formats/html-themes.html>`__
