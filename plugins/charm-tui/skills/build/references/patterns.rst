Bubbletea v2 — Composition Patterns
===================================

--------------

Pattern 1: Flat Model (State Enum)
----------------------------------

Best for: simple apps with sequential states (wizard, multi-step form).

.. code:: go

   type state int

   const (
       stateInput state = iota
       stateLoading
       stateResult
   )

   type model struct {
       state   state
       input   textinput.Model
       spinner spinner.Model
       result  string
       err     error
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       switch m.state {
       case stateInput:
           return m.updateInput(msg)
       case stateLoading:
           return m.updateLoading(msg)
       case stateResult:
           return m.updateResult(msg)
       }
       return m, nil
   }

   func (m model) View() tea.View {
       switch m.state {
       case stateInput:
           return tea.NewView(m.viewInput())
       case stateLoading:
           return tea.NewView(m.viewLoading())
       case stateResult:
           return tea.NewView(m.viewResult())
       }
       return tea.NewView("")
   }

--------------

Pattern 2: Model Stack (Child Models as Fields)
-----------------------------------------------

Best for: dashboards, multi-panel UIs where components are always
visible.

.. code:: go

   type model struct {
       width, height int
       list          list.Model
       viewport      viewport.Model
       focused       int  // 0 = list, 1 = viewport
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       var cmds []tea.Cmd
       var cmd tea.Cmd

       // Always route to active component
       switch msg := msg.(type) {
       case tea.WindowSizeMsg:
           m.width, m.height = msg.Width, msg.Height
           m.list.SetSize(msg.Width/2, msg.Height)
           m.viewport.SetWidth(msg.Width / 2)
           m.viewport.SetHeight(msg.Height)

       case tea.KeyPressMsg:
           switch msg.String() {
           case "tab":
               m.focused = (m.focused + 1) % 2
           case "ctrl+c", "q":
               return m, tea.Quit
           }
       }

       // Delegate to focused component
       switch m.focused {
       case 0:
           m.list, cmd = m.list.Update(msg)  // MUST reassign
           cmds = append(cmds, cmd)
       case 1:
           m.viewport, cmd = m.viewport.Update(msg)
           cmds = append(cmds, cmd)
       }

       return m, tea.Batch(cmds...)
   }

   func (m model) View() tea.View {
       left  := m.renderPanel(m.list.View(), m.focused == 0)
       right := m.renderPanel(m.viewport.View(), m.focused == 1)
       return tea.NewView(lipgloss.JoinHorizontal(lipgloss.Top, left, right))
   }

--------------

Pattern 3: Hybrid (Stack + Mode Enum)
-------------------------------------

Best for: apps where the visible components change based on mode.

.. code:: go

   type mode int
   const (
       modeBrowse mode = iota
       modeEdit
       modeConfirm
   )

   type model struct {
       mode    mode
       list    list.Model
       form    formModel  // custom sub-model
       confirm confirmModel
       width, height int
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       // Global handlers (always active)
       if k, ok := msg.(tea.KeyPressMsg); ok {
           switch k.String() {
           case "ctrl+c":
               return m, tea.Quit
           case "esc":
               if m.mode != modeBrowse {
                   m.mode = modeBrowse
                   return m, nil
               }
           }
       }

       // Mode-specific handlers
       switch m.mode {
       case modeBrowse:
           return m.updateBrowse(msg)
       case modeEdit:
           return m.updateEdit(msg)
       case modeConfirm:
           return m.updateConfirm(msg)
       }
       return m, nil
   }

--------------

Focus Management
----------------

Tab Cycling Pattern
~~~~~~~~~~~~~~~~~~~

.. code:: go

   type model struct {
       inputs  []textinput.Model
       focused int
   }

   func (m *model) focusNext() tea.Cmd {
       m.inputs[m.focused].Blur()
       m.focused = (m.focused + 1) % len(m.inputs)
       return m.inputs[m.focused].Focus()
   }

   func (m *model) focusPrev() tea.Cmd {
       m.inputs[m.focused].Blur()
       m.focused = (m.focused - 1 + len(m.inputs)) % len(m.inputs)
       return m.inputs[m.focused].Focus()
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       switch msg := msg.(type) {
       case tea.KeyPressMsg:
           switch msg.String() {
           case "tab", "down":
               return m, m.focusNext()
           case "shift+tab", "up":
               return m, m.focusPrev()
           case "enter":
               if m.focused == len(m.inputs)-1 {
                   return m.submit()
               }
               return m, m.focusNext()
           }
       }

       // Only update the focused input
       var cmd tea.Cmd
       m.inputs[m.focused], cmd = m.inputs[m.focused].Update(msg)
       return m, cmd
   }

--------------

Custom Message Types
--------------------

Use custom messages for inter-component communication and async results.

.. code:: go

   // Define message types as structs
   type statusMsg string
   type errMsg struct{ err error }
   type dataLoadedMsg struct{ items []Item }

   func (e errMsg) Error() string { return e.err.Error() }

   // Async command that produces a custom message
   func loadItems(db *sql.DB) tea.Cmd {
       return func() tea.Msg {
           rows, err := db.Query("SELECT * FROM items")
           if err != nil {
               return errMsg{err}
           }
           var items []Item
           // ... scan rows ...
           return dataLoadedMsg{items}
       }
   }

   // Handle in Update:
   case dataLoadedMsg:
       m.items = msg.items
       m.loading = false
       return m, nil

   case errMsg:
       m.err = msg.err
       return m, nil

--------------

Error Handling
--------------

Error State in Model
~~~~~~~~~~~~~~~~~~~~

.. code:: go

   type model struct {
       err     error
       content string
       // ...
   }

   func (m model) View() tea.View {
       if m.err != nil {
           errStyle := lipgloss.NewStyle().
               Foreground(lipgloss.Color("196")).
               Bold(true)
           return tea.NewView(errStyle.Render("Error: " + m.err.Error()) + "\n\nPress q to quit.")
       }
       // normal view ...
   }

Transient Error Messages
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   type model struct {
       errMsg  string
       errTime time.Time
   }

   type clearErrMsg struct{}

   func clearErrAfter(d time.Duration) tea.Cmd {
       return tea.Tick(d, func(t time.Time) tea.Msg {
           return clearErrMsg{}
       })
   }

   // In Update when error occurs:
   m.errMsg = "Something went wrong"
   return m, clearErrAfter(3 * time.Second)

   // In Update to clear:
   case clearErrMsg:
       m.errMsg = ""
       return m, nil

--------------

Common Bugs and Their Fixes
---------------------------

Bug 1: Forgetting to Reassign Child Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // WRONG — silently does nothing; m.list is unchanged
   m.list.Update(msg)

   // CORRECT — reassign the result
   var cmd tea.Cmd
   m.list, cmd = m.list.Update(msg)
   return m, cmd

Bug 2: Blocking I/O in Update
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // WRONG — blocks the UI event loop
   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       if k, ok := msg.(tea.KeyPressMsg); ok && k.String() == "enter" {
           m.result, _ = http.Get("https://api.example.com")  // BLOCKS!
       }
   }

   // CORRECT — return a Cmd
   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       if k, ok := msg.(tea.KeyPressMsg); ok && k.String() == "enter" {
           m.loading = true
           return m, fetchCmd()
       }
   }

Bug 3: Hardcoded Dimensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // WRONG — breaks on non-standard terminal sizes
   vp := viewport.New(viewport.WithWidth(80), viewport.WithHeight(24))

   // CORRECT — store WindowSizeMsg and use model dimensions
   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       if sz, ok := msg.(tea.WindowSizeMsg); ok {
           m.width, m.height = sz.Width, sz.Height
           m.viewport.SetWidth(sz.Width)
           m.viewport.SetHeight(sz.Height - m.headerHeight())
       }
       // ...
   }

Bug 4: Init Not Returning Component Cmds
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // WRONG — spinner never starts
   func (m model) Init() tea.Cmd {
       return nil
   }

   // CORRECT — return component init Cmds
   func (m model) Init() tea.Cmd {
       return tea.Batch(
           m.spinner.Tick,
           m.textinput.Focus(),
       )
   }

Bug 5: Using tea.Quit() with Parentheses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: go

   // WRONG — calls Quit() which returns a Msg, not a Cmd
   return m, tea.Quit()

   // CORRECT — pass the function reference as Cmd
   return m, tea.Quit
