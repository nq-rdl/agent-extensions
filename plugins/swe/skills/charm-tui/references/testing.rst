Bubbletea v2 — Testing Reference
================================

--------------

Unit Testing Update() Directly
------------------------------

The simplest approach — no tea.Program needed.

.. code:: go

   func TestCounterIncrement(t *testing.T) {
       m := initialModel()

       // Simulate a key press
       newModel, cmd := m.Update(tea.KeyPressMsg{
           Code: tea.KeyUp,
       })

       counter := newModel.(model)
       if counter.count != 1 {
           t.Errorf("expected count=1, got %d", counter.count)
       }
       if cmd != nil {
           t.Error("expected no command")
       }
   }

   func TestQuit(t *testing.T) {
       m := initialModel()
       _, cmd := m.Update(tea.KeyPressMsg{})

       // Simulate 'q' press using String() matching
       _, cmd = m.Update(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "q"})
       // Note: tea.Quit is a func() Msg, compare by calling it
       if cmd == nil {
           t.Fatal("expected quit command")
       }
       if _, ok := cmd().(tea.QuitMsg); !ok {
           t.Error("expected QuitMsg from command")
       }
   }

--------------

teatest — Integration Testing
-----------------------------

teatest runs your full tea.Program in a test environment.

**Import:** ``charm.land/bubbletea/v2/teatest``

.. code:: go

   import (
       "testing"
       "time"

       tea "charm.land/bubbletea/v2"
       "charm.land/bubbletea/v2/teatest"
   )

NewTestModel
~~~~~~~~~~~~

.. code:: go

   // Create a test model wrapping your program
   tm := teatest.NewTestModel(
       t,
       initialModel(),
       teatest.WithInitialTermSize(80, 24),
   )

Sending Messages
~~~~~~~~~~~~~~~~

.. code:: go

   // Send a key press
   tm.Send(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "q"})

   // Send any Msg type
   tm.Send(tea.WindowSizeMsg{Width: 100, Height: 40})
   tm.Send(myCustomMsg{data: "test"})

WaitFor — Assert on Output
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // Wait until output matches condition, with timeout
   teatest.WaitFor(
       t,
       tm.Output(),
       func(bts []byte) bool {
           return strings.Contains(string(bts), "Count: 3")
       },
       teatest.WithDuration(3*time.Second),
       teatest.WithCheckInterval(50*time.Millisecond),
   )

FinalModel — Get Final State
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // Quit the program and get the final model
   tm.Send(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "q"})
   tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

   final := tm.FinalModel(t).(model)
   if final.count != 5 {
       t.Errorf("expected count=5, got %d", final.count)
   }

WaitFinished — Wait for Program Exit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   tm.WaitFinished(t, teatest.WithFinalTimeout(5*time.Second))

--------------

Golden File Testing
-------------------

Compare terminal output against stored golden files.

RequireEqualOutput
~~~~~~~~~~~~~~~~~~

.. code:: go

   func TestOutput(t *testing.T) {
       tm := teatest.NewTestModel(
           t,
           initialModel(),
           teatest.WithInitialTermSize(80, 24),
       )

       // Let the UI render
       teatest.WaitFor(t, tm.Output(), func(bts []byte) bool {
           return strings.Contains(string(bts), "My App")
       }, teatest.WithDuration(2*time.Second))

       tm.Send(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "q"})
       tm.WaitFinished(t)

       // Compare against golden file
       teatest.RequireEqualOutput(t, tm.FinalOutput(t))
   }

Golden files are stored in ``testdata/`` with ``.golden`` extension.

**Update golden files:**

.. code:: bash

   go test ./... -update

TestMain Setup (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   var update = flag.Bool("update", false, "update golden files")

   func TestMain(m *testing.M) {
       flag.Parse()
       os.Exit(m.Run())
   }

--------------

VHS — Visual Recording
----------------------

VHS records terminal sessions from tape scripts for visual regression
and documentation.

**Install:** ``go install github.com/charmbracelet/vhs@latest``

Tape File Format
~~~~~~~~~~~~~~~~

.. code:: vhs

   # demo.tape

   Output demo.gif

   Set Shell "bash"
   Set FontSize 14
   Set Width 1200
   Set Height 600
   Set Theme "Catppuccin Mocha"

   # Launch the program
   Type "go run ."
   Enter
   Sleep 500ms

   # Interact with it
   Type "hello world"
   Enter
   Sleep 300ms

   # Navigate
   Down
   Down
   Sleep 200ms
   Enter
   Sleep 500ms

   # Quit
   Type "q"
   Sleep 300ms

**Run:**

.. code:: bash

   vhs demo.tape

Testing with VHS Output
~~~~~~~~~~~~~~~~~~~~~~~

For visual regression, diff GIFs are not practical — instead, record
text output:

.. code:: vhs

   Output output.txt

   # ... same commands ...

Then compare ``output.txt`` in CI.

--------------

Testing Patterns
----------------

Test Multiple Key Sequences
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   func TestNavigation(t *testing.T) {
       tm := teatest.NewTestModel(t, initialModel(),
           teatest.WithInitialTermSize(80, 24))

       // Navigate down 3 times
       for i := 0; i < 3; i++ {
           tm.Send(tea.KeyPressMsg{Code: tea.KeyDown})
           time.Sleep(50 * time.Millisecond)
       }

       teatest.WaitFor(t, tm.Output(), func(bts []byte) bool {
           return strings.Contains(string(bts), "> Item 4")  // cursor on 4th item
       }, teatest.WithDuration(2*time.Second))

       tm.Send(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "q"})
       tm.WaitFinished(t)
   }

Test Async Commands
~~~~~~~~~~~~~~~~~~~

.. code:: go

   func TestAsyncLoad(t *testing.T) {
       tm := teatest.NewTestModel(t, initialModel(),
           teatest.WithInitialTermSize(80, 24))

       // Trigger load
       tm.Send(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "l"})

       // Wait for loading to complete
       teatest.WaitFor(t, tm.Output(), func(bts []byte) bool {
           return strings.Contains(string(bts), "Loaded 10 items")
       }, teatest.WithDuration(5*time.Second))

       tm.Send(tea.KeyPressMsg{Code: tea.KeyRunes, Text: "q"})
       tm.WaitFinished(t)
   }

Test View Rendering Directly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   func TestView(t *testing.T) {
       m := model{
           items: []string{"Apple", "Banana", "Cherry"},
           cursor: 1,
       }
       view := m.View()
       // view is tea.View — get the string content
       content := view.String()  // if available, or test via teatest output

       if !strings.Contains(content, "> Banana") {
           t.Error("expected cursor on Banana")
       }
   }
