Bubbletea v2 — Architecture Reference
=====================================

Model Interface
---------------

.. code:: go

   type Model interface {
       Init() Cmd
       Update(Msg) (Model, Cmd)
       View() View
   }

``Msg`` is a type alias: ``type Msg = uv.Event`` (treat it as ``any``).
``Cmd`` is ``type Cmd func() Msg`` — an async I/O function. ``View`` is
a struct (see below) — NOT a ``string``.

--------------

Lifecycle
---------

::

   main() → tea.NewProgram(model).Run()
              │
              ▼
           model.Init()  ←── returns optional startup Cmd
              │
              ▼
       ┌──────────────────────────────────┐
       │  Event arrives (key, resize…)    │
       │       │                          │
       │       ▼                          │
       │  model.Update(msg)               │
       │    returns (newModel, cmd)       │
       │       │                          │
       │       ├──► cmd != nil → run async│
       │       │    result re-enters loop │
       │       ▼                          │
       │  model.View() → tea.View         │
       │    renderer draws to terminal    │
       └──────────────────────────────────┘
              │
              ▼
       QuitMsg received → p.Run() returns (finalModel, err)

--------------

tea.Program
-----------

.. code:: go

   // Constructor
   func NewProgram(model Model, opts ...ProgramOption) *Program

   // Run starts the event loop (blocks until quit)
   func (p *Program) Run() (Model, error)

   // Send injects a message from outside the loop (goroutine-safe)
   func (p *Program) Send(msg Msg)

   // Quit sends a QuitMsg (safe to call if not running)
   func (p *Program) Quit()

   // Kill terminates without cleanup
   func (p *Program) Kill()

   // Wait blocks until the program exits (use after Send + Quit)
   func (p *Program) Wait() error

   // Println / Printf write to stdout without disturbing the TUI
   func (p *Program) Println(args ...any)
   func (p *Program) Printf(format string, args ...any)

ProgramOption Functions
~~~~~~~~~~~~~~~~~~~~~~~

+----------------------------------------------+-------------------------------------------+
| Option                                       | Description                               |
+==============================================+===========================================+
| ``WithContext(ctx)``                         | External cancellation via context         |
+----------------------------------------------+-------------------------------------------+
| ``WithOutput(w io.Writer)``                  | Redirect output (default: stdout)         |
+----------------------------------------------+-------------------------------------------+
| ``WithInput(r io.Reader)``                   | Override input (nil = disable)            |
+----------------------------------------------+-------------------------------------------+
| ``WithEnvironment(env []string)``            | Environment variables (SSH sessions)      |
+----------------------------------------------+-------------------------------------------+
| ``WithFPS(fps int)``                         | Renderer FPS cap (1–120, default 60)      |
+----------------------------------------------+-------------------------------------------+
| ``WithColorProfile(p colorprofile.Profile)`` | Force color profile                       |
+----------------------------------------------+-------------------------------------------+
| ``WithWindowSize(w, h int)``                 | Initial dimensions for tests              |
+----------------------------------------------+-------------------------------------------+
| ``WithFilter(fn func(Model, Msg) Msg)``      | Pre-process messages                      |
+----------------------------------------------+-------------------------------------------+
| ``WithoutSignalHandler()``                   | Disable built-in signal handler           |
+----------------------------------------------+-------------------------------------------+
| ``WithoutCatchPanics()``                     | Disable panic recovery                    |
+----------------------------------------------+-------------------------------------------+
| ``WithoutRenderer()``                        | Disable TUI rendering (plain output)      |
+----------------------------------------------+-------------------------------------------+

**Note:** ``tea.WithAltScreen()`` does NOT exist in v2. Set
``v.AltScreen = true`` in your ``View()`` method instead.

--------------

View Type
---------

``View()`` returns ``tea.View``, not ``string``. Create with
``tea.NewView``:

.. code:: go

   func NewView(s string) View

   // Key fields you can set before returning:
   type View struct {
       // Terminal features — set declaratively in View(), not via NewProgram options
       AltScreen                bool   // use alternate screen buffer
       MouseMode                ...    // enable mouse tracking
       ReportFocus              bool   // receive FocusMsg/BlurMsg
       WindowTitle              string
       KeyboardEnhancements     ...
       Cursor                   Cursor // cursor position, shape, color, blink (replaces v1 hide/show commands)
       ForegroundColor          color.Color // query/set terminal foreground
       BackgroundColor          color.Color // query/set terminal background
       DisableBracketedPasteMode bool  // disable bracketed paste
       ProgressBar              float64     // native terminal progress indicator (0.0–1.0)
       // internal content field
   }

   // Mutate content after creation if needed:
   func (v *View) SetContent(s string)

Example with alt screen:

.. code:: go

   func (m model) View() tea.View {
       v := tea.NewView(renderContent(m))
       v.AltScreen = true
       return v
   }

--------------

Message Types (tea.Msg)
-----------------------

Keyboard
~~~~~~~~

.. code:: go

   tea.KeyPressMsg    // key pressed — use this in Update
   tea.KeyReleaseMsg  // key released (less common)

   // Match with msg.String():
   // "a", "A", "ctrl+c", "alt+enter", "shift+tab", "space", "up", "down",
   // "left", "right", "enter", "backspace", "delete", "esc", "f1"–"f12"

Window & Terminal
~~~~~~~~~~~~~~~~~

.. code:: go

   tea.WindowSizeMsg{Width int, Height int}   // terminal resized
   tea.FocusMsg    // terminal gained focus
   tea.BlurMsg     // terminal lost focus

Mouse
~~~~~

.. code:: go

   tea.MouseClickMsg   // button click
   tea.MouseReleaseMsg // button release
   tea.MouseMotionMsg  // cursor moved (requires MouseMode)
   tea.MouseWheelMsg   // scroll wheel

Program Control
~~~~~~~~~~~~~~~

.. code:: go

   tea.QuitMsg      // exit signal (sent by tea.Quit)
   tea.InterruptMsg // Ctrl+C signal
   tea.SuspendMsg   // Ctrl+Z
   tea.ResumeMsg    // resumed after suspend

Clipboard & Paste
~~~~~~~~~~~~~~~~~

.. code:: go

   tea.PasteMsg       // bracketed paste content
   tea.PasteStartMsg  // paste sequence began
   tea.PasteEndMsg    // paste sequence ended

Color Queries
~~~~~~~~~~~~~

.. code:: go

   tea.BackgroundColorMsg  // terminal background color response
   tea.ForegroundColorMsg  // terminal foreground color response

--------------

Command Functions (tea.Cmd)
---------------------------

.. code:: go

   // Quit the program (function reference, no parens!)
   tea.Quit   // type: Cmd — NOT tea.Quit()

   // Combine multiple Cmds — all run concurrently
   tea.Batch(cmds ...Cmd) Cmd

   // Run Cmds in sequence — each waits for the previous
   tea.Sequence(cmds ...Cmd) Cmd

   // Fire once after a duration
   tea.Tick(d time.Duration, fn func(time.Time) Msg) Cmd

   // Fire repeatedly at an interval
   tea.Every(d time.Duration, fn func(time.Time) Msg) Cmd

   // Request current window size (triggers WindowSizeMsg)
   tea.RequestWindowSize() Cmd

   // Clear the terminal screen
   tea.ClearScreen() Cmd

Custom Commands
~~~~~~~~~~~~~~~

Any function matching ``func() tea.Msg`` is a valid Cmd:

.. code:: go

   type fetchDoneMsg struct{ data []byte; err error }

   func fetchData(url string) tea.Cmd {
       return func() tea.Msg {
           data, err := http.Get(url)
           // ... read body ...
           return fetchDoneMsg{data: body, err: err}
       }
   }

   // In Update:
   case tea.KeyPressMsg:
       if msg.String() == "enter" {
           return m, fetchData("https://api.example.com/data")
       }

   // Handle result:
   case fetchDoneMsg:
       if msg.err != nil {
           m.err = msg.err
           return m, nil
       }
       m.data = msg.data
       return m, nil

--------------

Minimal Runnable Program
------------------------

.. code:: go

   package main

   import (
       "fmt"
       "os"

       tea "charm.land/bubbletea/v2"
   )

   type model struct{}

   func (m model) Init() tea.Cmd                         { return nil }
   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       if k, ok := msg.(tea.KeyPressMsg); ok && k.String() == "q" {
           return m, tea.Quit
       }
       return m, nil
   }
   func (m model) View() tea.View { return tea.NewView("Press q to quit\n") }

   func main() {
       if _, err := tea.NewProgram(model{}).Run(); err != nil {
           fmt.Fprintln(os.Stderr, err)
           os.Exit(1)
       }
   }
