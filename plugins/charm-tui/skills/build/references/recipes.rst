Charm TUI — Recipes
===================

Complete, runnable examples. Each is a single ``main.go`` with a minimal
``go.mod``.

--------------

Recipe 1: Interactive Form
--------------------------

Two text inputs with Tab navigation and Enter to submit.

**Expected output:**

::

   ╭────────────────────────────────────────────────╮
   │ New User                                       │
   │                                                │
   │ Name  > Alice_                                 │
   │                                                │
   │ Email >                                        │
   │                                                │
   │ [Tab] next  [Enter] submit  [Esc] cancel       │
   ╰────────────────────────────────────────────────╯

.. code:: go

   // main.go
   package main

   import (
       "fmt"
       "os"
       "strings"

       "charm.land/bubbles/v2/textinput"
       tea "charm.land/bubbletea/v2"
       "charm.land/lipgloss/v2"
   )

   const (
       fieldName = iota
       fieldEmail
       fieldCount
   )

   type model struct {
       inputs  [fieldCount]textinput.Model
       focused int
       done    bool
       result  struct{ name, email string }
   }

   var (
       boxStyle = lipgloss.NewStyle().
           Border(lipgloss.RoundedBorder()).
           BorderForeground(lipgloss.Color("63")).
           Padding(1, 2).
           Width(34)
       labelStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("240")).Width(6)
       helpStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("241"))
   )

   func initialModel() model {
       m := model{}

       name := textinput.New()
       name.Placeholder = "Alice"
       name.CharLimit = 50
       _ = name.Focus()

       email := textinput.New()
       email.Placeholder = "alice@example.com"
       email.CharLimit = 100

       m.inputs[fieldName] = name
       m.inputs[fieldEmail] = email
       return m
   }

   func (m model) Init() tea.Cmd {
       return m.inputs[m.focused].Focus()
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       switch msg := msg.(type) {
       case tea.KeyPressMsg:
           switch msg.String() {
           case "ctrl+c", "esc":
               return m, tea.Quit
           case "tab", "down":
               m.inputs[m.focused].Blur()
               m.focused = (m.focused + 1) % fieldCount
               return m, m.inputs[m.focused].Focus()
           case "shift+tab", "up":
               m.inputs[m.focused].Blur()
               m.focused = (m.focused - 1 + fieldCount) % fieldCount
               return m, m.inputs[m.focused].Focus()
           case "enter":
               if m.focused == fieldCount-1 {
                   // Submit
                   m.result.name = m.inputs[fieldName].Value()
                   m.result.email = m.inputs[fieldEmail].Value()
                   m.done = true
                   return m, tea.Quit
               }
               m.inputs[m.focused].Blur()
               m.focused++
               return m, m.inputs[m.focused].Focus()
           }
       }

       var cmd tea.Cmd
       m.inputs[m.focused], cmd = m.inputs[m.focused].Update(msg)
       return m, cmd
   }

   func (m model) View() tea.View {
       if m.done {
           return tea.NewView(fmt.Sprintf("Created: %s <%s>\n", m.result.name, m.result.email))
       }

       var sb strings.Builder
       sb.WriteString("New User\n\n")
       sb.WriteString(labelStyle.Render("Name") + " " + m.inputs[fieldName].View() + "\n\n")
       sb.WriteString(labelStyle.Render("Email") + " " + m.inputs[fieldEmail].View() + "\n\n")
       sb.WriteString(helpStyle.Render("[Tab] next  [Enter] submit  [Esc] cancel"))

       return tea.NewView(boxStyle.Render(sb.String()))
   }

   func main() {
       if _, err := tea.NewProgram(initialModel()).Run(); err != nil {
           fmt.Fprintln(os.Stderr, err)
           os.Exit(1)
       }
   }

::

   # go.mod
   module example/form

   go 1.24

   require (
       charm.land/bubbletea/v2 v2.0.2
       charm.land/bubbles/v2 v2.0.0
       charm.land/lipgloss/v2 v2.0.0
   )

--------------

Recipe 2: Data Table Viewer
---------------------------

Scrollable table with keyboard navigation.

**Expected output:**

::

   ┌────────────────────────────────────────────────┐
   │ Users                                          │
   ├───────────────┬─────┬──────────────────────────┤
   │ Name          │ Age │ Email                    │
   ├───────────────┼─────┼──────────────────────────┤
   │▶ Alice        │ 30  │ alice@example.com        │
   │  Bob          │ 25  │ bob@example.com          │
   │  Charlie      │ 35  │ charlie@example.com      │
   ├───────────────┴─────┴──────────────────────────┤
   │ ↑/↓ navigate • enter select • q quit           │
   └────────────────────────────────────────────────┘

.. code:: go

   // main.go
   package main

   import (
       "fmt"
       "os"

       "charm.land/bubbles/v2/table"
       tea "charm.land/bubbletea/v2"
       "charm.land/lipgloss/v2"
   )

   type model struct {
       table  table.Model
       width  int
       height int
   }

   func initialModel() model {
       cols := []table.Column{
           {Title: "Name",  Width: 14},
           {Title: "Age",   Width: 5},
           {Title: "Email", Width: 26},
       }
       rows := []table.Row{
           {"Alice",   "30", "alice@example.com"},
           {"Bob",     "25", "bob@example.com"},
           {"Charlie", "35", "charlie@example.com"},
           {"Diana",   "28", "diana@example.com"},
           {"Evan",    "42", "evan@example.com"},
       }
       t := table.New()
       t.SetColumns(cols)
       t.SetRows(rows)
       t.SetHeight(10)
       t.Focus()
       return model{table: t}
   }

   var (
       titleStyle = lipgloss.NewStyle().
           Bold(true).
           Padding(0, 1).
           Background(lipgloss.Color("62")).
           Foreground(lipgloss.Color("230"))
       helpStyle = lipgloss.NewStyle().
           Foreground(lipgloss.Color("241")).
           Padding(0, 1)
       boxStyle = lipgloss.NewStyle().
           Border(lipgloss.NormalBorder()).
           BorderForeground(lipgloss.Color("240"))
   )

   func (m model) Init() tea.Cmd { return nil }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       switch msg := msg.(type) {
       case tea.WindowSizeMsg:
           m.width, m.height = msg.Width, msg.Height
           m.table.SetHeight(m.height - 6)
       case tea.KeyPressMsg:
           switch msg.String() {
           case "ctrl+c", "q":
               return m, tea.Quit
           case "enter":
               row := m.table.SelectedRow()
               fmt.Printf("\nSelected: %s\n", row[0])
               return m, tea.Quit
           }
       }
       var cmd tea.Cmd
       m.table, cmd = m.table.Update(msg)
       return m, cmd
   }

   func (m model) View() tea.View {
       title := titleStyle.Render(" Users ")
       help  := helpStyle.Render("↑/↓ navigate • enter select • q quit")
       content := fmt.Sprintf("%s\n%s\n%s", title, m.table.View(), help)
       return tea.NewView(boxStyle.Render(content))
   }

   func main() {
       if _, err := tea.NewProgram(initialModel()).Run(); err != nil {
           fmt.Fprintln(os.Stderr, err)
           os.Exit(1)
       }
   }

--------------

Recipe 3: Two-Panel Dashboard
-----------------------------

Sidebar navigation + main content, responsive to terminal size.

**Expected output:**

::

   My Dashboard                              Tab: switch panel
   ┌───────────────┬─────────────────────────────────────┐
   │ [SIDEBAR]     │ [MAIN]                              │
   │               │                                     │
   │ ▶ Overview    │  Overview                           │
   │   Settings    │  ──────────                         │
   │   About       │  Welcome to the dashboard.          │
   │               │  Use Tab to switch between panels.  │
   └───────────────┴─────────────────────────────────────┘

.. code:: go

   // main.go
   package main

   import (
       "fmt"
       "os"

       "charm.land/bubbles/v2/list"
       "charm.land/bubbles/v2/viewport"
       tea "charm.land/bubbletea/v2"
       "charm.land/lipgloss/v2"
   )

   type panel int
   const (
       panelNav panel = iota
       panelContent
   )

   type navItem struct{ title, content string }
   func (i navItem) FilterValue() string { return i.title }
   func (i navItem) Title() string       { return i.title }
   func (i navItem) Description() string { return "" }

   type model struct {
       width, height int
       focused       panel
       nav           list.Model
       viewport      viewport.Model
       pages         []navItem
   }

   func initialModel() model {
       pages := []navItem{
           {"Overview", "Welcome to the dashboard.\nUse Tab to switch between panels.\nArrow keys to navigate."},
           {"Settings", "Settings page.\n\nTheme: Dark\nFont size: 14\nAuto-save: On"},
           {"About",    "My Dashboard v1.0\n\nBuilt with Bubbletea v2\nand Lip Gloss v2."},
       }

       items := make([]list.Item, len(pages))
       for i, p := range pages {
           items[i] = p
       }

       nav := list.New(items, list.NewDefaultDelegate(), 20, 10)
       nav.SetShowTitle(false)
       nav.SetShowFilter(false)
       nav.SetShowHelp(false)
       nav.SetShowStatusBar(false)

       vp := viewport.New()
       vp.SetContent(pages[0].content)

       return model{nav: nav, viewport: vp, pages: pages}
   }

   func (m model) Init() tea.Cmd { return nil }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       var cmd tea.Cmd

       switch msg := msg.(type) {
       case tea.WindowSizeMsg:
           m.width, m.height = msg.Width, msg.Height
           navW    := m.width / 4
           mainW   := m.width - navW - 3
           bodyH   := m.height - 3
           m.nav.SetSize(navW, bodyH)
           m.viewport.SetWidth(mainW)
           m.viewport.SetHeight(bodyH)

       case tea.KeyPressMsg:
           switch msg.String() {
           case "ctrl+c", "q":
               return m, tea.Quit
           case "tab":
               if m.focused == panelNav {
                   m.focused = panelContent
               } else {
                   m.focused = panelNav
               }
               return m, nil
           }
       }

       switch m.focused {
       case panelNav:
           m.nav, cmd = m.nav.Update(msg)
           // Update viewport content when selection changes
           if sel, ok := m.nav.SelectedItem().(navItem); ok {
               m.viewport.SetContent(sel.content)
           }
       case panelContent:
           m.viewport, cmd = m.viewport.Update(msg)
       }

       return m, cmd
   }

   var (
       activePanel   = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("62"))
       inactivePanel = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("240"))
       titleBar      = lipgloss.NewStyle().Bold(true).Padding(0, 1)
       helpBar       = lipgloss.NewStyle().Foreground(lipgloss.Color("241")).Padding(0, 1)
   )

   func (m model) View() tea.View {
       if m.width == 0 {
           return tea.NewView("Loading...")
       }
       navW  := m.width / 4
       mainW := m.width - navW - 3

       navStyle  := inactivePanel.Width(navW)
       mainStyle := inactivePanel.Width(mainW)
       if m.focused == panelNav {
           navStyle = activePanel.Width(navW)
       } else {
           mainStyle = activePanel.Width(mainW)
       }

       nav  := navStyle.Render(m.nav.View())
       main := mainStyle.Render(m.viewport.View())

       header := titleBar.Render("My Dashboard") +
           helpBar.Render("Tab: switch panel • q: quit")
       body := lipgloss.JoinHorizontal(lipgloss.Top, nav, main)

       return tea.NewView(lipgloss.JoinVertical(lipgloss.Left, header, body))
   }

   func main() {
       if _, err := tea.NewProgram(initialModel()).Run(); err != nil {
           fmt.Fprintln(os.Stderr, err)
           os.Exit(1)
       }
   }

--------------

Recipe 4: Progress Tracker with Async Work
------------------------------------------

Spinner while loading, animated progress bar, async Cmd pattern.

**Expected output (during loading):**

::

   ⣾ Fetching data...

   ████████████░░░░░░░░░  62%

   Step 3/5: Processing records...

.. code:: go

   // main.go
   package main

   import (
       "fmt"
       "os"
       "time"

       "charm.land/bubbles/v2/progress"
       "charm.land/bubbles/v2/spinner"
       tea "charm.land/bubbletea/v2"
       "charm.land/lipgloss/v2"
   )

   type stepDoneMsg struct{ step int }
   type allDoneMsg struct{}

   type model struct {
       spinner  spinner.Model
       progress progress.Model
       step     int
       steps    []string
       done     bool
       err      error
   }

   var steps = []string{
       "Connecting to server",
       "Fetching data",
       "Processing records",
       "Validating results",
       "Writing output",
   }

   func initialModel() model {
       s := spinner.New(spinner.WithSpinner(spinner.Dot))
       p := progress.New()
       p.ShowPercentage = true
       return model{
           spinner:  s,
           progress: p,
           steps:    steps,
       }
   }

   func simulateStep(step int) tea.Cmd {
       return func() tea.Msg {
           duration := time.Duration(300+step*100) * time.Millisecond
           time.Sleep(duration)
           if step >= len(steps)-1 {
               return allDoneMsg{}
           }
           return stepDoneMsg{step + 1}
       }
   }

   func (m model) Init() tea.Cmd {
       return tea.Batch(
           m.spinner.Tick,
           simulateStep(0),
       )
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       var cmds []tea.Cmd

       switch msg := msg.(type) {
       case tea.KeyPressMsg:
           if msg.String() == "ctrl+c" || msg.String() == "q" {
               return m, tea.Quit
           }

       case stepDoneMsg:
           m.step = msg.step
           pct := float64(m.step) / float64(len(m.steps))
           cmds = append(cmds, m.progress.SetPercent(pct))
           cmds = append(cmds, simulateStep(msg.step))

       case allDoneMsg:
           m.done = true
           cmds = append(cmds, m.progress.SetPercent(1.0))
           return m, tea.Batch(cmds...)

       case progress.FrameMsg:
           var cmd tea.Cmd
           m.progress, cmd = m.progress.Update(msg)
           cmds = append(cmds, cmd)

       case spinner.TickMsg:
           var cmd tea.Cmd
           m.spinner, cmd = m.spinner.Update(msg)
           cmds = append(cmds, cmd)
       }

       return m, tea.Batch(cmds...)
   }

   var (
       stepStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("241"))
       doneStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("42")).Bold(true)
   )

   func (m model) View() tea.View {
       if m.done {
           return tea.NewView(doneStyle.Render("✓ All done!\n") + "\nPress q to quit.\n")
       }

       stepText := ""
       if m.step < len(m.steps) {
           stepText = stepStyle.Render(
               fmt.Sprintf("Step %d/%d: %s", m.step+1, len(m.steps), m.steps[m.step]),
           )
       }

       s := fmt.Sprintf(
           "\n %s %s\n\n %s\n\n %s\n\n%s",
           m.spinner.View(),
           m.steps[m.step],
           m.progress.View(),
           stepText,
           helpStyle.Render("q: quit"),
       )
       return tea.NewView(s)
   }

   var helpStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("241"))

   func main() {
       if _, err := tea.NewProgram(initialModel()).Run(); err != nil {
           fmt.Fprintln(os.Stderr, err)
           os.Exit(1)
       }
   }

--------------

Recipe 5: File Browser with Preview
-----------------------------------

Filepicker on the left, viewport preview on the right.

**Expected output:**

::

   ┌──────────────────┬───────────────────────────────┐
   │ /home/user/docs  │ Preview: README.md            │
   │                  │ ───────────────────────────── │
   │ 📁 ..            │ # My Project                  │
   │ 📁 projects/     │                               │
   │ 📄 README.md     │ A short description of what   │
   │ 📄 notes.txt     │ this project does.            │
   │                  │                               │
   ├──────────────────┴───────────────────────────────┤
   │ ↑/↓ navigate • Enter select • q quit             │
   └──────────────────────────────────────────────────┘

.. code:: go

   // main.go
   package main

   import (
       "fmt"
       "os"

       "charm.land/bubbles/v2/filepicker"
       "charm.land/bubbles/v2/viewport"
       tea "charm.land/bubbletea/v2"
       "charm.land/lipgloss/v2"
   )

   type model struct {
       fp           filepicker.Model
       viewport     viewport.Model
       selectedFile string
       width        int
       height       int
       err          error
   }

   func initialModel() model {
       fp := filepicker.New()
       fp.CurrentDirectory, _ = os.UserHomeDir()
       fp.AllowedTypes = []string{".md", ".txt", ".go", ".yaml", ".json"}
       fp.FileAllowed = true
       fp.DirAllowed = false

       vp := viewport.New()
       vp.SetContent("Select a file to preview")

       return model{fp: fp, viewport: vp}
   }

   func (m model) Init() tea.Cmd {
       return m.fp.Init()
   }

   func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
       var cmds []tea.Cmd
       var cmd tea.Cmd

       switch msg := msg.(type) {
       case tea.WindowSizeMsg:
           m.width, m.height = msg.Width, msg.Height
           fpW  := m.width / 3
           vpW  := m.width - fpW - 3
           bodyH := m.height - 3
           m.fp.SetHeight(bodyH)
           m.viewport.SetWidth(vpW)
           m.viewport.SetHeight(bodyH)

       case tea.KeyPressMsg:
           switch msg.String() {
           case "ctrl+c", "q":
               return m, tea.Quit
           }
       }

       m.fp, cmd = m.fp.Update(msg)
       cmds = append(cmds, cmd)

       if ok, path := m.fp.DidSelectFile(msg); ok {
           m.selectedFile = path
           content, err := os.ReadFile(path)
           if err != nil {
               m.viewport.SetContent("Error reading file: " + err.Error())
           } else {
               m.viewport.SetContent(string(content))
           }
       }

       m.viewport, cmd = m.viewport.Update(msg)
       cmds = append(cmds, cmd)

       return m, tea.Batch(cmds...)
   }

   var (
       panelStyle = lipgloss.NewStyle().
           Border(lipgloss.NormalBorder()).
           BorderForeground(lipgloss.Color("240"))
       helpStyle = lipgloss.NewStyle().
           Foreground(lipgloss.Color("241")).
           Padding(0, 1)
   )

   func (m model) View() tea.View {
       if m.width == 0 {
           return tea.NewView("Loading...")
       }

       fpW := m.width / 3
       vpW := m.width - fpW - 3

       fpPanel := panelStyle.Width(fpW).Render(m.fp.View())

       previewTitle := ""
       if m.selectedFile != "" {
           previewTitle = "Preview: " + m.selectedFile + "\n"
       }
       vpContent := previewTitle + m.viewport.View()
       vpPanel   := panelStyle.Width(vpW).Render(vpContent)

       body := lipgloss.JoinHorizontal(lipgloss.Top, fpPanel, vpPanel)
       help := helpStyle.Render("↑/↓ navigate • Enter select • q quit")

       return tea.NewView(lipgloss.JoinVertical(lipgloss.Left, body, help))
   }

   func main() {
       if _, err := tea.NewProgram(initialModel()).Run(); err != nil {
           fmt.Fprintln(os.Stderr, err)
           os.Exit(1)
       }
   }

--------------

go.mod Template
---------------

For all recipes:

::

   module example/myapp

   go 1.24

   require (
       charm.land/bubbletea/v2 v2.0.2
       charm.land/bubbles/v2 v2.0.0
       charm.land/lipgloss/v2 v2.0.0
   )

Run ``go mod tidy`` after creating go.mod to populate ``go.sum``.
