Bubbles v2 — Components Reference
=================================

   **All imports:** ``charm.land/bubbles/v2/<name>`` Do NOT invent
   methods. Use ONLY the signatures listed here.

--------------

textinput — Single-line text field
----------------------------------

.. code:: go

   import "charm.land/bubbles/v2/textinput"

**Constructor:** ``textinput.New() Model``

**Key Model fields:** \| Field \| Type \| Purpose \| \|——-\|——\|———\| \|
``Prompt`` \| ``string`` \| Prefix shown before input (default ``"> "``)
\| \| ``Placeholder`` \| ``string`` \| Ghost text when empty \| \|
``EchoMode`` \| ``EchoMode`` \| ``EchoNormal``, ``EchoPassword``,
``EchoNone`` \| \| ``CharLimit`` \| ``int`` \| Max characters (0 =
unlimited) \| \| ``Validate`` \| ``func(string) error`` \| Real-time
validation \| \| ``Err`` \| ``error`` \| Last validation error \|

**Key methods:**

.. code:: go

   func (m *Model) Focus() tea.Cmd    // focus the input, returns cursor blink Cmd
   func (m *Model) Blur()             // unfocus
   func (m Model) Focused() bool
   func (m *Model) SetValue(s string)
   func (m Model) Value() string
   func (m *Model) SetWidth(w int)
   func (m Model) Width() int
   func (m *Model) Reset()
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string       // component View returns string, not tea.View

**Usage:**

.. code:: go

   ti := textinput.New()
   ti.Placeholder = "Enter name..."
   ti.CharLimit = 50
   cmd := ti.Focus()  // returns blink Cmd

   // In parent Update:
   case tea.KeyPressMsg:
       // delegate to component
   var cmd tea.Cmd
   m.input, cmd = m.input.Update(msg)  // MUST reassign

   // In parent View:
   return tea.NewView(m.input.View())

--------------

textarea — Multi-line text editor
---------------------------------

.. code:: go

   import "charm.land/bubbles/v2/textarea"

**Constructor:** ``textarea.New() Model``

**Key Model fields:** \| Field \| Type \| Purpose \| \|——-\|——\|———\| \|
``Placeholder`` \| ``string`` \| Ghost text \| \| ``ShowLineNumbers`` \|
``bool`` \| Show line numbers \| \| ``CharLimit`` \| ``int`` \| Max
characters \| \| ``MaxHeight`` \| ``int`` \| Max rendered height \| \|
``MaxWidth`` \| ``int`` \| Max rendered width \| \| ``Err`` \| ``error``
\| Last error \|

**Key methods:**

.. code:: go

   func (m *Model) Focus() tea.Cmd
   func (m *Model) Blur()
   func (m Model) Focused() bool
   func (m *Model) SetValue(s string)
   func (m Model) Value() string
   func (m Model) LineCount() int
   func (m Model) Line() int        // current line number
   func (m Model) Column() int      // current column
   func (m *Model) SetWidth(w int)
   func (m *Model) SetHeight(h int)
   func (m *Model) InsertString(s string)
   func (m *Model) Reset()
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

--------------

table — Sortable data table
---------------------------

.. code:: go

   import "charm.land/bubbles/v2/table"

**Constructor:** ``table.New(opts ...Option) Model``

**Types:**

.. code:: go

   type Column struct {
       Title string
       Width int
   }
   type Row []string

**Key methods:**

.. code:: go

   func (m *Model) SetColumns(c []Column)
   func (m Model) Columns() []Column
   func (m *Model) SetRows(r []Row)
   func (m Model) Rows() []Row
   func (m Model) SelectedRow() Row
   func (m Model) Cursor() int
   func (m *Model) SetCursor(n int)
   func (m *Model) MoveUp(n int)
   func (m *Model) MoveDown(n int)
   func (m *Model) GotoTop()
   func (m *Model) GotoBottom()
   func (m *Model) Focus()
   func (m *Model) Blur()
   func (m Model) Focused() bool
   func (m *Model) SetWidth(w int)
   func (m *Model) SetHeight(h int)
   func (m *Model) SetStyles(s Styles)
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string
   func (m Model) HelpView() string

**Usage:**

.. code:: go

   t := table.New()
   t.SetColumns([]table.Column{
       {Title: "Name", Width: 20},
       {Title: "Age",  Width: 5},
   })
   t.SetRows([]table.Row{
       {"Alice", "30"},
       {"Bob",   "25"},
   })
   t.Focus()

--------------

list — Scrollable item list with filtering
------------------------------------------

.. code:: go

   import "charm.land/bubbles/v2/list"

**Constructor:**
``list.New(items []Item, delegate ItemDelegate, width, height int) Model``

**Interfaces:**

.. code:: go

   // Minimum Item interface
   type Item interface {
       FilterValue() string  // value used for filtering
   }

   // Item with built-in rendering (use with list.NewDefaultDelegate())
   type DefaultItem interface {
       Item
       Title() string
       Description() string
   }

**Key methods:**

.. code:: go

   func (m Model) SelectedItem() Item
   func (m Model) Index() int          // index in current page
   func (m Model) GlobalIndex() int    // index across all items
   func (m Model) Items() []Item
   func (m *Model) SetItems(i []Item) tea.Cmd
   func (m *Model) InsertItem(index int, item Item) tea.Cmd
   func (m *Model) RemoveItem(index int)
   func (m *Model) SetSize(width, height int)
   func (m *Model) SetShowTitle(v bool)
   func (m *Model) SetShowFilter(v bool)
   func (m *Model) SetShowHelp(v bool)
   func (m *Model) NewStatusMessage(s string) tea.Cmd
   func (m *Model) StartSpinner() tea.Cmd
   func (m *Model) StopSpinner()
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

**Usage:**

.. code:: go

   type item struct{ title, desc string }
   func (i item) FilterValue() string { return i.title }
   func (i item) Title() string       { return i.title }
   func (i item) Description() string { return i.desc }

   items := []list.Item{
       item{"Apple", "A red fruit"},
       item{"Banana", "A yellow fruit"},
   }
   delegate := list.NewDefaultDelegate()
   l := list.New(items, delegate, 40, 20)
   l.Title = "Fruits"

--------------

viewport — Scrollable content pane
----------------------------------

.. code:: go

   import "charm.land/bubbles/v2/viewport"

**Constructor:** ``viewport.New(opts ...Option) Model``

Options: ``viewport.WithWidth(w int)``, ``viewport.WithHeight(h int)``

**Key Model fields:** \| Field \| Type \| Purpose \| \|——-\|——\|———\| \|
``SoftWrap`` \| ``bool`` \| Wrap long lines \| \| ``FillHeight`` \|
``bool`` \| Expand to fill height \| \| ``MouseWheelEnabled`` \|
``bool`` \| Mouse wheel scrolling \| \| ``Style`` \| ``lipgloss.Style``
\| Container style \|

**Key methods:**

.. code:: go

   func (m *Model) SetContent(s string)
   func (m Model) GetContent() string
   func (m *Model) SetWidth(w int)
   func (m *Model) SetHeight(h int)
   func (m Model) Width() int
   func (m Model) Height() int
   func (m *Model) ScrollUp(n int)
   func (m *Model) ScrollDown(n int)
   func (m *Model) PageUp()
   func (m *Model) PageDown()
   func (m *Model) GotoTop() []string
   func (m *Model) GotoBottom() []string
   func (m *Model) SetYOffset(n int)
   func (m Model) YOffset() int
   func (m Model) AtTop() bool
   func (m Model) AtBottom() bool
   func (m Model) ScrollPercent() float64
   func (m Model) TotalLineCount() int
   func (m Model) VisibleLineCount() int
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

**Usage:**

.. code:: go

   vp := viewport.New(viewport.WithWidth(80), viewport.WithHeight(20))
   vp.SetContent(longText)
   // In Update: m.viewport, cmd = m.viewport.Update(msg)

--------------

spinner — Animated loading indicator
------------------------------------

.. code:: go

   import "charm.land/bubbles/v2/spinner"

**Constructor:** ``spinner.New(opts ...Option) Model``

Options: ``spinner.WithSpinner(s Spinner)``,
``spinner.WithStyle(style lipgloss.Style)``

**Pre-defined spinners:** ``spinner.Line``, ``spinner.Dot``,
``spinner.MiniDot``, ``spinner.Jump``, ``spinner.Pulse``,
``spinner.Points``, ``spinner.Globe``, ``spinner.Moon``,
``spinner.Monkey``, ``spinner.Meter``, ``spinner.Hamburger``,
``spinner.Ellipsis``

**Key fields:**

.. code:: go

   type Model struct {
       Spinner spinner.Spinner  // set to change animation
       Style   lipgloss.Style
   }

**Key methods:**

.. code:: go

   func (m Model) Tick() tea.Msg   // use as Init Cmd: return m.spinner.Tick
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

**Usage:**

.. code:: go

   s := spinner.New(spinner.WithSpinner(spinner.Dot))

   func (m model) Init() tea.Cmd {
       return m.spinner.Tick  // NOT m.spinner.Tick() — no parens
   }

   // In Update:
   case spinner.TickMsg:
       m.spinner, cmd = m.spinner.Update(msg)
       return m, cmd

--------------

progress — Animated progress bar
--------------------------------

.. code:: go

   import "charm.land/bubbles/v2/progress"

**Constructor:** ``progress.New(opts ...Option) Model``

**Key Model fields:**

.. code:: go

   type Model struct {
       Full            rune
       FullColor       color.Color
       Empty           rune
       EmptyColor      color.Color
       ShowPercentage  bool
       PercentFormat   string
   }

**Key methods:**

.. code:: go

   func (m Model) Init() tea.Cmd
   func (m *Model) SetPercent(p float64) tea.Cmd   // animated, returns Cmd
   func (m *Model) IncrPercent(v float64) tea.Cmd
   func (m *Model) DecrPercent(v float64) tea.Cmd
   func (m Model) Percent() float64
   func (m Model) ViewAs(percent float64) string    // static, no Cmd needed
   func (m *Model) SetWidth(w int)
   func (m Model) Width() int
   func (m *Model) IsAnimating() bool
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

**Usage:**

.. code:: go

   p := progress.New()
   p.ShowPercentage = true

   // Animate to 75%:
   cmd := p.SetPercent(0.75)  // returns animation Cmd — must process in Update
   return m, cmd

   // Static render without animation:
   bar := p.ViewAs(0.75)

--------------

filepicker — File system navigator
----------------------------------

.. code:: go

   import "charm.land/bubbles/v2/filepicker"

**Constructor:** ``filepicker.New() Model``

**Key Model fields:**

.. code:: go

   type Model struct {
       CurrentDirectory string
       AllowedTypes     []string  // e.g. []string{".go", ".md"}
       ShowHidden       bool
       DirAllowed       bool
       FileAllowed      bool
       AutoHeight       bool
       FileSelected     string   // last selected file
       Styles           Styles
   }

**Key methods:**

.. code:: go

   func (m Model) Init() tea.Cmd
   func (m Model) DidSelectFile(msg tea.Msg) (bool, string)          // check in Update
   func (m Model) DidSelectDisabledFile(msg tea.Msg) (bool, string)  // check in Update
   func (m Model) HighlightedPath() string
   func (m *Model) SetHeight(h int)
   func (m Model) Height() int
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

**Usage:**

.. code:: go

   fp := filepicker.New()
   fp.AllowedTypes = []string{".go"}
   fp.CurrentDirectory, _ = os.UserHomeDir()

   // In parent Update, check after delegating:
   m.fp, cmd = m.fp.Update(msg)
   if ok, path := m.fp.DidSelectFile(msg); ok {
       m.selectedFile = path
   }

--------------

help — Key binding help renderer
--------------------------------

.. code:: go

   import "charm.land/bubbles/v2/help"

**Constructor:** ``help.New() Model``

**KeyMap interface (implement on your model’s KeyMap field):**

.. code:: go

   type KeyMap interface {
       ShortHelp() []key.Binding    // one-line help
       FullHelp() [][]key.Binding   // multi-column full help
   }

**Key methods:**

.. code:: go

   func (m Model) View(k KeyMap) string              // render with your KeyMap
   func (m Model) ShortHelpView(b []key.Binding) string
   func (m Model) FullHelpView(groups [][]key.Binding) string
   func (m *Model) SetWidth(w int)
   func (m Model) Width() int

**Usage:**

.. code:: go

   import (
       "charm.land/bubbles/v2/help"
       "charm.land/bubbles/v2/key"
   )

   type keyMap struct {
       Up   key.Binding
       Down key.Binding
       Quit key.Binding
   }
   func (k keyMap) ShortHelp() []key.Binding { return []key.Binding{k.Up, k.Down, k.Quit} }
   func (k keyMap) FullHelp() [][]key.Binding { return [][]key.Binding{{k.Up, k.Down}, {k.Quit}} }

   var keys = keyMap{
       Up:   key.NewBinding(key.WithKeys("up", "k"), key.WithHelp("↑/k", "up")),
       Down: key.NewBinding(key.WithKeys("down", "j"), key.WithHelp("↓/j", "down")),
       Quit: key.NewBinding(key.WithKeys("q", "ctrl+c"), key.WithHelp("q", "quit")),
   }

   h := help.New()
   // In View:
   return tea.NewView(h.View(keys))

--------------

key — Key binding definitions
-----------------------------

.. code:: go

   import "charm.land/bubbles/v2/key"

.. code:: go

   // Define a binding
   func NewBinding(opts ...BindingOpt) Binding

   // Options
   func WithKeys(keys ...string) BindingOpt    // key names to match
   func WithHelp(key, desc string) BindingOpt  // display string for help
   func WithDisabled() BindingOpt              // start disabled

   // On a Binding
   func (b Binding) Keys() []string
   func (b Binding) Help() HelpData            // .Key and .Desc
   func (b *Binding) SetEnabled(v bool)
   func (b Binding) Enabled() bool

   // Match a KeyPressMsg against a binding
   func Matches(k tea.KeyPressMsg, b ...Binding) bool

**Usage:**

.. code:: go

   var quitKey = key.NewBinding(
       key.WithKeys("q", "ctrl+c"),
       key.WithHelp("q", "quit"),
   )

   // In Update:
   case tea.KeyPressMsg:
       if key.Matches(msg, quitKey) {
           return m, tea.Quit
       }

--------------

paginator — Page counter
------------------------

.. code:: go

   import "charm.land/bubbles/v2/paginator"

**Constructor:** ``paginator.New() Model``

**Key Model fields:**

.. code:: go

   type Model struct {
       Type        Type    // paginator.Dots or paginator.Arabic
       Page        int     // current page (0-indexed)
       PerPage     int     // items per page
       TotalPages  int
       ActiveDot   string  // active page indicator
       InactiveDot string
   }

**Key methods:**

.. code:: go

   func (m *Model) SetTotalPages(items int) int  // returns total pages
   func (m Model) ItemsOnPage(totalItems int) int
   func (m Model) GetSliceBounds(length int) (start, end int)
   func (m *Model) NextPage()
   func (m *Model) PrevPage()
   func (m *Model) First()
   func (m *Model) Last()
   func (m Model) OnFirstPage() bool
   func (m Model) OnLastPage() bool
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

--------------

timer — Countdown timer
-----------------------

.. code:: go

   import "charm.land/bubbles/v2/timer"

**Constructor:** ``timer.New(timeout time.Duration) Model``

.. code:: go

   func (m Model) Init() tea.Cmd            // start the timer
   func (m Model) Timedout() bool
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

**Messages:** ``timer.TickMsg``, ``timer.TimeoutMsg``

--------------

stopwatch — Elapsed time tracker
--------------------------------

.. code:: go

   import "charm.land/bubbles/v2/stopwatch"

**Constructor:** ``stopwatch.New(opts ...Option) Model``

Options: ``stopwatch.WithInterval(d time.Duration)``

.. code:: go

   func (m Model) Init() tea.Cmd
   func (m Model) Elapsed() time.Duration
   func (m Model) Running() bool
   func (m *Model) Start() tea.Cmd
   func (m *Model) Stop() tea.Cmd
   func (m *Model) Toggle() tea.Cmd
   func (m *Model) Reset() tea.Cmd
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
   func (m Model) View() string

--------------

cursor — Text cursor blink control
----------------------------------

.. code:: go

   import "charm.land/bubbles/v2/cursor"

Used internally by ``textinput`` and ``textarea``. Direct use is
uncommon but available.

**Constructor:** ``cursor.New() Model``

.. code:: go

   func (m *Model) Focus() tea.Cmd
   func (m *Model) Blur()
   func (m Model) Focused() bool
   func (m Model) SetMode(mode Mode)   // CursorBlink, CursorStatic, CursorHide
   func (m Model) View() string        // renders as cursor character or space
   func (m Model) Update(msg tea.Msg) (Model, tea.Cmd)
