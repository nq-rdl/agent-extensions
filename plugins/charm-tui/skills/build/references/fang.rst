Fang v2 — CLI Polish Reference
==============================

.. code:: go

   import "charm.land/fang/v2"

Fang wraps a Cobra command to add styled help, errors, man pages, and
shell completions — one function call replaces ``cmd.Execute()``.

--------------

Quick Integration
-----------------

.. code:: go

   package main

   import (
       "context"
       "fmt"
       "os"

       "charm.land/fang/v2"
       tea "charm.land/bubbletea/v2"
       "github.com/spf13/cobra"
   )

   func main() {
       root := &cobra.Command{
           Use:   "myapp",
           Short: "A polished CLI tool",
       }

       // Add subcommands
       root.AddCommand(newTUICommand())

       // Replace root.Execute() with fang.Execute()
       if err := fang.Execute(context.Background(), root); err != nil {
           os.Exit(1)
       }
   }

   func newTUICommand() *cobra.Command {
       return &cobra.Command{
           Use:   "tui",
           Short: "Launch the interactive TUI",
           RunE: func(cmd *cobra.Command, args []string) error {
               _, err := tea.NewProgram(initialModel()).Run()
               return err
           },
       }
   }

--------------

fang.Execute
------------

.. code:: go

   func Execute(ctx context.Context, root *cobra.Command, options ...Option) error

Replaces ``root.Execute()`` (or ``root.ExecuteContext(ctx)``).
Automatically adds: - Styled help output (colors, formatting) - Styled
error messages - ``--version`` flag (if version info provided) - Hidden
``man`` command (man page generation) - ``completion`` command (bash,
zsh, fish, powershell)

--------------

Options
-------

.. code:: go

   // Set version string shown by --version
   fang.WithVersion(version string) Option

   // Set git commit SHA shown alongside version
   fang.WithCommit(commit string) Option

   // Custom color scheme function
   fang.WithColorSchemeFunc(cs ColorSchemeFunc) Option

   // Custom error handler — signature: func(w io.Writer, styles fang.Styles, err error)
   fang.WithErrorHandler(handler ErrorHandler) Option

   // Custom interrupt signals (default: os.Interrupt, syscall.SIGTERM)
   fang.WithNotifySignal(signals ...os.Signal) Option

   // Disable built-in features
   fang.WithoutVersion() Option
   fang.WithoutCompletions() Option
   fang.WithoutManpage() Option

--------------

Version Information
-------------------

.. code:: go

   var (
       version = "dev"
       commit  = "none"
   )

   // Injected at build time:
   // go build -ldflags "-X main.version=v1.2.3 -X main.commit=abc1234"

   func main() {
       root := &cobra.Command{Use: "myapp"}
       if err := fang.Execute(
           context.Background(),
           root,
           fang.WithVersion(version),
           fang.WithCommit(commit),
       ); err != nil {
           os.Exit(1)
       }
   }

--------------

Custom Color Scheme
-------------------

.. code:: go

   import "charm.land/lipgloss/v2"

   fang.Execute(ctx, root,
       fang.WithColorSchemeFunc(func() fang.ColorScheme {
           return fang.ColorScheme{
               // Primary accent color (command names, flags)
               Primary: lipgloss.Color("#7C3AED"),
               // Secondary color (descriptions)
               Secondary: lipgloss.Color("#A78BFA"),
           }
       }),
   )

..

   **Note:** ``fang.ColorScheme`` uses ``lipgloss.Color`` from
   ``charm.land/lipgloss/v2``. If your project also uses
   ``github.com/charmbracelet/lipgloss`` (v0/v1), both versions coexist
   safely but their color types are not interchangeable.

--------------

Error Handling
--------------

Fang formats errors automatically. For custom handling:

.. code:: go

   import "io"

   fang.Execute(ctx, root,
       fang.WithErrorHandler(func(w io.Writer, styles fang.Styles, err error) {
           // w is the output writer, styles contains the active color scheme
           fmt.Fprintf(w, "Error: %v\n", err)
       }),
   )

--------------

Integration Pattern: Cobra + Bubbletea
--------------------------------------

.. code:: go

   package main

   import (
       "context"
       "os"

       "charm.land/fang/v2"
       tea "charm.land/bubbletea/v2"
       "github.com/spf13/cobra"
   )

   var rootCmd = &cobra.Command{
       Use:   "mytool",
       Short: "My polished tool",
       Long:  "A longer description of my tool.",
   }

   var tuiCmd = &cobra.Command{
       Use:   "run",
       Short: "Launch interactive mode",
       RunE: func(cmd *cobra.Command, args []string) error {
           p := tea.NewProgram(
               newModel(),
               tea.WithContext(cmd.Context()),  // propagate context/cancellation
           )
           _, err := p.Run()
           return err
       },
   }

   var listCmd = &cobra.Command{
       Use:   "list",
       Short: "List items non-interactively",
       RunE: func(cmd *cobra.Command, args []string) error {
           // plain text output for scripting
           for _, item := range getItems() {
               fmt.Println(item)
           }
           return nil
       },
   }

   func init() {
       rootCmd.AddCommand(tuiCmd, listCmd)
       tuiCmd.Flags().BoolP("verbose", "v", false, "Verbose output")
   }

   func main() {
       if err := fang.Execute(context.Background(), rootCmd,
           fang.WithVersion("v1.0.0"),
       ); err != nil {
           os.Exit(1)
       }
   }

--------------

What Users Get for Free
-----------------------

After wrapping with Fang, users can:

.. code:: bash

   # Styled --help output
   mytool --help
   mytool run --help

   # Version
   mytool --version

   # Shell completions
   mytool completion bash >> ~/.bashrc
   mytool completion zsh > "${fpath[1]}/_mytool"

   # Man page (hidden command)
   mytool man > /usr/local/share/man/man1/mytool.1

--------------

go.mod Dependency
-----------------

::

   require (
       charm.land/fang/v2 v2.x.x
       github.com/spf13/cobra v1.x.x
   )

Fang does not re-export Cobra — add both as direct dependencies.

   **Transitive dependency note:** Fang v2 transitively pulls
   ``charm.land/lipgloss/v2``. Projects that already use
   ``github.com/charmbracelet/lipgloss`` (v0/v1) will end up with two
   lipgloss versions in their module graph — this is safe, but the types
   are not interchangeable between versions. If you see ``x/ansi``
   version conflicts, run
   ``go get github.com/charmbracelet/x/cellbuf@latest`` to resolve them.

--------------

Fang with Bubbletea v1 Projects
-------------------------------

Fang wraps **Cobra only** — it does not touch Bubbletea models or the
tea event loop. In projects still using Bubbletea v1
(``github.com/charmbracelet/bubbletea``):

- ``RunE`` functions keep using v1 Bubbletea types (``View() string``,
  ``tea.KeyMsg``, ``tea.WithAltScreen()``) unchanged
- Fang handles help rendering, error formatting, and completions at the
  Cobra layer
- The two lipgloss versions (``charm.land/lipgloss/v2`` from Fang,
  ``github.com/charmbracelet/lipgloss`` from your app) coexist safely
  but their types are not interchangeable

Only Fang’s own ``ColorScheme`` uses ``lipgloss.Color`` from
``charm.land/lipgloss/v2``.
