Shiny and promises with mirai
=============================

A ``mirai`` is accepted anywhere a promise is: Shiny ``ExtendedTask``,
``promises::then()``, and the ``%...>%`` pipe. The example below was executed
with shiny 1.14.0, bslib 0.12.0, mirai 2.7.2, and promises 1.5.0 on
2026-09-29 (``ExtendedTask`` needs shiny >= 1.8.1; ``input_task_button()``
and ``bind_task_button()`` need bslib >= 0.7.0).

ExtendedTask pattern
--------------------

Rules that the example follows:

- Start daemons once at app start-up and reset them in ``onStop()``.
- The task function receives every value it needs as an argument and passes
  it to ``mirai()`` through ``.args``. Reactive values such as ``input$n``
  cannot be read on the daemon.
- Every ``input$...`` read in the server must exist in the UI. If the UI has
  no ``n`` input, ``input$n`` is ``NULL`` and the task fails with
  ``Error in rnorm(n): invalid arguments``.

.. code:: r

   library(shiny)
   library(bslib)
   library(mirai)

   daemons(4)
   onStop(function() daemons(0))

   ui <- page_fluid(
     numericInput("n", "Sample size", value = 100, min = 1),
     input_task_button("run", "Run analysis"),
     plotOutput("result")
   )

   server <- function(input, output, session) {
     task <- ExtendedTask$new(
       function(n) mirai(rnorm(n), .args = list(n = n))
     ) |> bind_task_button("run")

     observeEvent(input$run, task$invoke(input$n))
     output$result <- renderPlot(hist(task$result()))
   }

   shinyApp(ui, server)

``task$status()`` is ``"running"``, ``"success"``, or ``"error"``. A mirai
that resolves to an error value makes ``task$result()`` raise that error in
the output that reads it.

Promise piping
--------------

.. code:: r

   library(promises)
   mirai({Sys.sleep(1); "done"}) %...>% cat()

   # Equivalent with then()
   then(mirai(Sys.sleep(1)), onFulfilled = function(value) message("done"))

Outside Shiny, promise callbacks run only when the ``later`` event loop runs
(for example at the console prompt, or with ``later::run_now()``).
