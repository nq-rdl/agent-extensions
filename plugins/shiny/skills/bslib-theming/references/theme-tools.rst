Sass Layers, Theme Tools, and Inspection
========================================

Low-level functions for customizations beyond ``bs_theme()``'s named
arguments, the interactive themer, and theme inspection. The Sass
placement rule (``.where = "declarations"`` for variables that reference
other Bootstrap variables) is in SKILL.md.

Table of Contents
-----------------

- `Common Bootstrap Sass variables <#common-bootstrap-sass-variables>`__
- `bs_add_rules() <#bs-add-rules>`__
- `bs_add_functions() and bs_add_mixins() <#bs-add-functions-and-bs-add-mixins>`__
- `bs_bundle() <#bs-bundle>`__
- `Interactive theming tools <#interactive-theming-tools>`__
- `Theme inspection <#theme-inspection>`__
- `Organizing a complex theme <#organizing-a-complex-theme>`__

Common Bootstrap Sass variables
-------------------------------

Pass any Bootstrap 5 Sass variable through ``bs_theme(...)`` or
``bs_add_variables()``. Find names at
https://rstudio.github.io/bslib/articles/bs5-variables/ .

.. code:: r

   bs_theme(
     "border-radius" = "0.5rem",
     "card-border-radius" = "1rem",
     "card-bg" = "lighten($bg, 5%)",
     "navbar-bg" = "$primary",
     "link-color" = "$primary",
     "font-size-base" = "1rem",
     "spacer" = "1rem",
     "btn-padding-y" = ".5rem",
     "btn-padding-x" = "1rem",
     "input-border-color" = "#dee2e6"
   )

Values can be Sass expressions that use variables, functions, and math.

bs_add_rules()
--------------

Add Sass/CSS rules that can use Bootstrap variables and mixins:

.. code:: r

   theme <- bs_theme(primary = "#007bff") |>
     bs_add_rules("
       .custom-card {
         background: mix($bg, $primary, 95%);
         border: 1px solid $primary;
         padding: $spacer;

         @include media-breakpoint-up(md) {
           padding: $spacer * 2;
         }
       }
     ")

From an external file: ``bs_add_rules(sass::sass_file("www/custom.scss"))``.

Useful Sass functions: ``lighten()``, ``darken()``, ``mix()``, ``rgba()``,
``color-contrast()``. Bootstrap mixins: ``@include media-breakpoint-up()``,
``@include box-shadow()``, ``@include border-radius()``.

bs_add_functions() and bs_add_mixins()
--------------------------------------

Add custom Sass functions or mixins to the theme bundle:

.. code:: r

   theme |>
     bs_add_functions("@function my-tint($color) { @return mix(white, $color, 20%); }") |>
     bs_add_rules(".highlight { background: my-tint($primary); }")

bs_bundle()
-----------

Append ``sass::sass_bundle()`` objects to a theme, for example to package a
reusable theme extension:

.. code:: r

   my_extension <- sass::sass_layer(
     defaults = list("my-var" = "red !default"),
     rules = ".my-class { color: $my-var; }"
   )
   theme <- bs_theme() |> bs_bundle(my_extension)

Interactive theming tools
-------------------------

All three tools print the resulting ``bs_theme()`` code to the R console.
**Limitations:** Bootstrap 5+ only; Shiny apps and ``runtime: shiny`` R
Markdown only; they do not affect third-party widgets that do not use
``bs_dependency_defer()``.

``bs_theme_preview()`` runs a standalone demo app with many example
components. It includes the themer by default (``with_themer = TRUE``).

.. code:: r

   bslib::bs_theme_preview()
   bslib::bs_theme_preview(bs_theme(preset = "darkly"))

``run_with_themer()`` runs an existing app with the theme editor overlay
instead of ``shiny::runApp()``:

.. code:: r

   run_with_themer(shinyApp(ui, server))
   run_with_themer("path/to/app")

``bs_themer()`` adds the editor to your own server function. Remove it for
production.

.. code:: r

   server <- function(input, output, session) {
     bs_themer()
     # ...
   }

Theme inspection
----------------

Retrieve computed Sass variable values:

.. code:: r

   vars <- c("body-bg", "body-color", "primary", "border-radius")
   bs_get_variables(bs_theme(), varnames = vars)
   bs_get_variables(bs_theme(preset = "darkly"), varnames = vars)

For contrast checks with ``bs_get_contrast()``, see SKILL.md.

Organizing a complex theme
--------------------------

Keep a complex theme in its own ``theme.R``:

.. code:: r

   # theme.R
   app_theme <- function() {
     bs_theme(
       version = 5,
       primary = "#2c3e50",
       base_font = font_google("Lato"),
       heading_font = font_google("Montserrat", wght = c(400, 700))
     ) |>
       bs_add_rules(sass::sass_file("www/custom.scss"))
   }
