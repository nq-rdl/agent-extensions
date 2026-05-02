Special Inputs in bslib
=======================

bslib provides specialized input widgets that enhance standard Shiny
inputs with modern features.

Table of Contents
-----------------

- `input_switch() <#input_switch>`__
- `input_dark_mode() <#input_dark_mode>`__
- `input_task_button() <#input_task_button>`__
- `input_code_editor() <#input_code_editor>`__
- `input_submit_textarea() <#input_submit_textarea>`__
- `Choosing the Right Input <#choosing-the-right-input>`__

input_switch()
--------------

A modern toggle switch, alternative to ``checkboxInput()`` for on/off
states with immediate effect.

.. code:: r

   input_switch("enable_feature", "Enable advanced features")
   input_switch("notifications", "Enable notifications", value = TRUE)

Use ``input_switch()`` freely in sidebars, card bodies, or toolbars
wherever a boolean toggle fits. Update from the server with
``update_switch("id", value = FALSE)`` or flip the current state with
``toggle_switch("id")``.

input_dark_mode()
-----------------

Toggle between Bootstrap 5.3 light/dark color modes. Automatically
switches the ``data-bs-theme`` attribute on the page.

.. code:: r

   input_dark_mode(id = "mode")                # Follow OS preference
   input_dark_mode(id = "mode", mode = "dark") # Start in dark mode

**Placing in a navbar:** wrap in ``nav_item()`` and use ``nav_spacer()``
before it to push it to the right edge:

.. code:: r

   page_navbar(
     title = "My App",
     nav_panel("Dashboard", ...),
     nav_spacer(),
     nav_item(input_dark_mode(id = "mode"))
   )

**Hidden mode (OS-aware without a toggle button):** use
``style = css(display = "none")`` to activate Bootstrap’s color mode
system without rendering a UI control. The app follows the user’s OS
``prefers-color-scheme`` by default and can still be controlled from the
server:

.. code:: r

   nav_item(input_dark_mode(id = "mode", style = css(display = "none")))

Omit ``id`` if you don’t need the server to read or change the mode.

**Server access:** ``input$mode`` returns ``"light"`` or ``"dark"``.

**Programmatic toggle:** ``toggle_dark_mode()``,
``toggle_dark_mode("light")``, ``toggle_dark_mode("dark")``.

For full custom theme switching (different color palettes beyond
light/dark), combine with ``session$setCurrentTheme()``. See the
**shiny-bslib-theming** skill for details.

input_task_button()
-------------------

Action button for long-running operations with built-in loading state.
Auto-disables while running.

.. code:: r

   # UI
   input_task_button("run_analysis", "Run Analysis")

   # Server
   observeEvent(input$run_analysis, {
     result <- expensive_computation()
     output$result <- renderText(result)
   })

With ExtendedTask
~~~~~~~~~~~~~~~~~

For truly long-running tasks, combine with ``ExtendedTask`` and
``bind_task_button()``:

.. code:: r

   library(future)
   plan(multisession)

   server <- function(input, output, session) {
     long_task <- ExtendedTask$new(function() {
       future({ Sys.sleep(10); "Task complete!" }, seed = TRUE)
     }) |> bind_task_button("run")

     observeEvent(input$run, { long_task$invoke() })
     output$result <- renderText({ long_task$result() })
   }

**``bind_task_button(target_task, button_id)``** keeps the button in
“busy” state while the task runs. Does NOT auto-trigger on click — you
still need ``observeEvent()``.

**Update button:**
``update_task_button("run", label = "Done", icon = bsicons::bs_icon("check"))``

input_code_editor()
-------------------

Lightweight code editor with syntax highlighting, powered by
`prism-code-editor <https://prism-code-editor.netlify.app/>`__.
Auto-switches themes with dark mode. Try
``shiny::runExample("code-editor", package = "bslib")``.

**Value updates reach the server** when the user moves focus away or
presses ``Ctrl/Cmd+Enter`` (not on every keystroke).

.. code:: r

   input_code_editor(
     id = "code",
     language = "r",
     value = "# Enter R code here\n"
   )

**Languages:** ``"r"``, ``"python"``, ``"julia"``, ``"sql"``,
``"javascript"``, ``"typescript"``, ``"html"``, ``"css"``, ``"scss"``,
``"sass"``, ``"json"``, ``"markdown"``, ``"yaml"``, ``"xml"``,
``"toml"``, ``"ini"``, ``"bash"``, ``"docker"``, ``"latex"``, ``"cpp"``,
``"rust"``, ``"diff"``, ``"plain"``.

Configuration
~~~~~~~~~~~~~

================ ================== ========================
Parameter        Default            Description
================ ================== ========================
``height``       ``"auto"``         CSS height
``theme_light``  ``"github-light"`` Light mode theme
``theme_dark``   ``"github-dark"``  Dark mode theme
``read_only``    ``FALSE``          Disable editing
``line_numbers`` ``TRUE``           Show line numbers
``word_wrap``                       Enable word wrapping
``tab_size``     ``2``              Tab width
``indentation``  ``"space"``        ``"space"`` or ``"tab"``
``fill``         ``TRUE``           Fill container
================ ================== ========================

**Available themes:** ``"atom-one-dark"``, ``"dracula"``,
``"github-dark-dimmed"``, ``"github-dark"``, ``"github-light"``,
``"night-owl-light"``, ``"night-owl"``, ``"prism-okaidia"``,
``"prism-solarized-light"``, ``"prism-tomorrow"``, ``"prism-twilight"``,
``"prism"``, ``"vs-code-dark"``, ``"vs-code-light"``.

**Keyboard shortcuts:** ``Ctrl/Cmd+Enter`` (submit), ``Ctrl/Cmd+Z``
(undo), ``Tab``/``Shift+Tab`` (indent/dedent).

**Dynamic language switching:**

.. code:: r

   observeEvent(input$language, {
     update_code_editor("code", language = input$language)
   })

input_submit_textarea()
-----------------------

Textarea with explicit submission — prevents reactive updates on every
keystroke. Auto-grows as user types. Ideal for chat boxes, comments, or
inputs where users compose before submitting.

**Important:** Initial server value is always ``""``. Updates only on
explicit submit.

.. code:: r

   input_submit_textarea(
     id = "user_input",
     label = "Enter text:",
     placeholder = "Type here...",
     rows = 4
   )

Submission Behavior
~~~~~~~~~~~~~~~~~~~

- **Default (``submit_key = "enter+modifier"``):** ``Ctrl/Cmd+Enter`` to
  submit
- **Enter-only:** ``submit_key = "enter"`` — submit with Enter,
  Shift+Enter for new lines

Custom Button and Toolbar
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``button`` parameter accepts any HTML element.
``input_task_button()`` recommended for built-in busy state:

.. code:: r

   input_submit_textarea(
     id = "query",
     placeholder = "Ask a question...",
     button = input_task_button("submit", "Send", icon = bsicons::bs_icon("send")),
     toolbar = list(
       actionLink("attach", bsicons::bs_icon("paperclip"))
     )
   )

Update
~~~~~~

``update_submit_textarea()`` accepts ``value`` to change the text,
``submit = TRUE`` to trigger submission programmatically, and
``focus = TRUE`` to move keyboard focus to the textarea.

Chat Interface Pattern
~~~~~~~~~~~~~~~~~~~~~~

.. code:: r

   # UI
   card(
     card_header("Chat"),
     card_body(uiOutput("chat_messages"), fillable = FALSE, fill = TRUE),
     card_footer(
       input_submit_textarea("chat_input", placeholder = "Type a message...", submit_key = "enter")
     )
   )

   # Server
   observeEvent(input$chat_input, {
     req(nchar(input$chat_input) > 0)
     add_message(input$chat_input)
     update_submit_textarea("chat_input", value = "")
   })

Choosing the Right Input
------------------------

+-----------------------+-----------------------------+-----------------------------+
| Need                  | Use                         | Instead of                  |
+=======================+=============================+=============================+
| On/off toggle,        | ``input_switch()``          | ``checkboxInput()``         |
| immediate effect      |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Selection/agreement,  | ``checkboxInput()``         | ``input_switch()``          |
| form submit           |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Long operation (>2s), | ``input_task_button()``     | ``actionButton()``          |
| prevent duplicates    |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Quick action, custom  | ``actionButton()``          | ``input_task_button()``     |
| loading               |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Code with syntax      | ``input_code_editor()``     | ``textAreaInput()``         |
| highlighting          |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Expensive downstream, | ``input_submit_textarea()`` | ``textAreaInput()``         |
| compose then submit   |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Live preview, cheap   | ``textAreaInput()``         | ``input_submit_textarea()`` |
| updates               |                             |                             |
+-----------------------+-----------------------------+-----------------------------+
| Light/dark mode       | ``input_dark_mode()``       | Custom toggle               |
| toggle                |                             |                             |
+-----------------------+-----------------------------+-----------------------------+

Feedback for Task Buttons
~~~~~~~~~~~~~~~~~~~~~~~~~

Show completion feedback after long operations:

.. code:: r

   observeEvent(input$process, {
     result <- process_data()
     show_toast(toast("Processing complete", header = "Done", type = "success"))
   })
