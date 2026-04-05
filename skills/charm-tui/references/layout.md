# Lip Gloss v2 — Layout Reference

```go
import "charm.land/lipgloss/v2"
```

---

## JoinHorizontal — Side-by-side blocks

```go
func JoinHorizontal(pos Position, strs ...string) string
```

Joins rendered string blocks side-by-side, aligning them vertically by `pos`.

**Position constants:**
```go
lipgloss.Top    // = 0.0  — align tops
lipgloss.Center // = 0.5  — center vertically
lipgloss.Bottom // = 1.0  — align bottoms
// Or any float64 between 0.0 and 1.0
```

```go
left  := "Line 1\nLine 2\nLine 3"
right := "A\nB"

// Align tops:
lipgloss.JoinHorizontal(lipgloss.Top, left, right)
// Line 1 A
// Line 2 B
// Line 3

// Align centers:
lipgloss.JoinHorizontal(lipgloss.Center, left, right)
// Line 1
// Line 2 A
// Line 3 B

// Three columns:
lipgloss.JoinHorizontal(lipgloss.Top, sidebar, main, panel)
```

---

## JoinVertical — Stacked blocks

```go
func JoinVertical(pos Position, strs ...string) string
```

Stacks rendered string blocks vertically, aligning them horizontally by `pos`.

```go
lipgloss.Left   // = 0.0
lipgloss.Center // = 0.5
lipgloss.Right  // = 1.0
```

```go
header := headerStyle.Render("My App")
body   := bodyStyle.Render(content)
footer := footerStyle.Render("Press q to quit")

full := lipgloss.JoinVertical(lipgloss.Left, header, body, footer)
```

---

## Place — Position content in a bounding box

```go
// Place in a width×height box, position with hPos (horizontal) and vPos (vertical)
func Place(width, height int, hPos, vPos Position, str string, opts ...WhitespaceOption) string

// Horizontal only — center in a width-wide space
func PlaceHorizontal(width int, pos Position, str string, opts ...WhitespaceOption) string

// Vertical only — position in a height-tall space
func PlaceVertical(height int, pos Position, str string, opts ...WhitespaceOption) string
```

```go
// Center in a 80×24 terminal:
centered := lipgloss.Place(80, 24, lipgloss.Center, lipgloss.Center, content)

// Right-align in terminal width:
rightAligned := lipgloss.PlaceHorizontal(termWidth, lipgloss.Right, text)

// Bottom of terminal:
atBottom := lipgloss.PlaceVertical(termHeight, lipgloss.Bottom, text)

// Bottom-right corner:
corner := lipgloss.Place(termWidth, termHeight, lipgloss.Right, lipgloss.Bottom, text)
```

---

## Responsive Layout Pattern

Store terminal dimensions in the model; recalculate in View.

```go
type model struct {
    width  int
    height int
    // ... other fields
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.WindowSizeMsg:
        m.width = msg.Width
        m.height = msg.Height
        // Update child component sizes:
        m.list.SetSize(msg.Width/2, msg.Height-4)
        m.viewport.SetWidth(msg.Width / 2)
        m.viewport.SetHeight(msg.Height - 4)
    }
    // ...
}

func (m model) View() tea.View {
    if m.width == 0 {
        return tea.NewView("Loading...")  // not yet sized
    }
    sidebar := m.renderSidebar(m.width/3, m.height)
    main    := m.renderMain(m.width*2/3, m.height)
    return tea.NewView(lipgloss.JoinHorizontal(lipgloss.Top, sidebar, main))
}
```

---

## Two-Column Layout

```
┌────────────┬───────────────────────────┐
│  Sidebar   │       Main Content        │
│  (30%)     │          (70%)            │
│            │                           │
└────────────┴───────────────────────────┘
```

```go
func (m model) View() tea.View {
    sidebarWidth := m.width / 3
    mainWidth    := m.width - sidebarWidth

    sidebarStyle := lipgloss.NewStyle().
        Width(sidebarWidth).
        Height(m.height).
        Border(lipgloss.NormalBorder(), false, true, false, false). // right border only
        BorderForeground(lipgloss.Color("240"))

    mainStyle := lipgloss.NewStyle().
        Width(mainWidth).
        Height(m.height).
        Padding(0, 1)

    sidebar := sidebarStyle.Render(m.list.View())
    main    := mainStyle.Render(m.viewport.View())

    return tea.NewView(lipgloss.JoinHorizontal(lipgloss.Top, sidebar, main))
}
```

---

## Header + Body + Footer Layout

```
┌──────────────────────────────────────┐
│              Header                   │  ← fixed height
├──────────────────────────────────────┤
│                                       │
│              Body                     │  ← fills remaining space
│                                       │
├──────────────────────────────────────┤
│              Footer                   │  ← fixed height
└──────────────────────────────────────┘
```

```go
const headerHeight = 3
const footerHeight = 1

func (m model) View() tea.View {
    bodyHeight := m.height - headerHeight - footerHeight

    headerStyle := lipgloss.NewStyle().
        Width(m.width).
        Height(headerHeight).
        Bold(true).
        Background(lipgloss.Color("62")).
        Foreground(lipgloss.Color("230")).
        Align(lipgloss.Center)

    footerStyle := lipgloss.NewStyle().
        Width(m.width).
        Foreground(lipgloss.Color("240"))

    m.viewport.SetWidth(m.width)
    m.viewport.SetHeight(bodyHeight)

    header := headerStyle.Render(m.title)
    body   := m.viewport.View()
    footer := footerStyle.Render(m.statusLine())

    return tea.NewView(lipgloss.JoinVertical(lipgloss.Left, header, body, footer))
}
```

---

## Grid Layout

Arrange items in a fixed-width grid:

```go
func renderGrid(items []string, cols, colWidth int) string {
    var rows []string
    for i := 0; i < len(items); i += cols {
        end := i + cols
        if end > len(items) {
            end = len(items)
        }
        rowItems := make([]string, end-i)
        for j, item := range items[i:end] {
            rowItems[j] = lipgloss.NewStyle().Width(colWidth).Render(item)
        }
        rows = append(rows, lipgloss.JoinHorizontal(lipgloss.Top, rowItems...))
    }
    return lipgloss.JoinVertical(lipgloss.Left, rows...)
}
```

---

## ASCII Art Layout Mockups

Use these when writing comments or planning:

```
Simple list:               Two-panel:
┌────────────┐             ┌──────────┬──────────────────┐
│ Item 1     │             │ Nav      │ Detail           │
│ Item 2     │             │ ─────    │                  │
│▶ Item 3    │             │ Option 1 │ Title            │
│ Item 4     │             │ Option 2 │                  │
│            │             │▶Option 3 │ Long content...  │
│ 3/10 items │             │          │                  │
└────────────┘             └──────────┴──────────────────┘

Dashboard:
┌─────────────────────────────────────────────────────┐
│ My Dashboard                              [q] quit  │
├──────────────┬────────────────┬────────────────────┤
│ Stats        │ Activity       │ Log                 │
│ CPU: 34%     │ ████░░░░ 50%  │ 12:01 info msg      │
│ Mem: 2.1 GB  │ █████████ 90% │ 12:02 warn msg      │
└──────────────┴────────────────┴────────────────────┘
```
