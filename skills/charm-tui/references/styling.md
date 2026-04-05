# Lip Gloss v2 — Styling Reference

```go
import "charm.land/lipgloss/v2"
```

---

## Style Creation and Chaining

Styles are **immutable** — every method returns a new Style. Store the result.

```go
style := lipgloss.NewStyle().
    Bold(true).
    Foreground(lipgloss.Color("#FF75B7")).
    Background(lipgloss.Color("#1a1a2e")).
    Padding(1, 2).
    Width(30)

output := style.Render("Hello, world!")
```

**Render:** `style.Render(text string) string`

---

## Text Attributes

```go
style.Bold(true)
style.Italic(true)
style.Underline(true)
style.Strikethrough(true)
style.Faint(true)     // dim/low-intensity
style.Blink(true)     // blinking text
style.Reverse(true)   // swap fg/bg
```

---

## Colors

### Color Function

```go
lipgloss.Color(s string) color.Color
```

Accepts:
- **ANSI 16:** `"0"`–`"15"` (named: black=0, red=1, green=2, yellow=3, blue=4, magenta=5, cyan=6, white=7; bright: 8–15)
- **ANSI 256:** `"16"`–`"255"`
- **True color hex:** `"#RRGGBB"` e.g. `"#FF5733"`, `"#04B575"`

### Named Constants (ANSI 16)

```go
lipgloss.Black, lipgloss.Red, lipgloss.Green, lipgloss.Yellow
lipgloss.Blue, lipgloss.Magenta, lipgloss.Cyan, lipgloss.White
lipgloss.BrightBlack, lipgloss.BrightRed, lipgloss.BrightGreen, lipgloss.BrightYellow
lipgloss.BrightBlue, lipgloss.BrightMagenta, lipgloss.BrightCyan, lipgloss.BrightWhite
```

### Color Utilities

```go
lipgloss.Darken(c color.Color, pct float64) color.Color      // 0.0–1.0
lipgloss.Lighten(c color.Color, pct float64) color.Color
lipgloss.Complementary(c color.Color) color.Color
lipgloss.Alpha(c color.Color, alpha float64) color.Color     // 0.0–1.0

// Adaptive color: picks light or dark variant based on terminal background
// AdaptiveColor was removed in v2. Use LightDark() instead:
lipgloss.LightDark(hasDark bool)  // returns true if terminal has dark background

// Pattern: choose color based on terminal background
fg := lipgloss.Color("#333333")  // light terminal
if lipgloss.LightDark(true) {
    fg = lipgloss.Color("#DDDDDD")  // dark terminal
}
style.Foreground(fg)

// Migration: compat.AdaptiveColor is available in the compat package for gradual migration
```

### Applying Colors

```go
style.Foreground(lipgloss.Color("#FF75B7"))
style.Background(lipgloss.Color("214"))  // orange from 256-color palette
```

---

## Box Model (Padding and Margin)

CSS-like shorthand:

```go
// All sides
style.Padding(2)               // 2 on all sides
style.Margin(1)

// Vertical, Horizontal
style.Padding(1, 2)            // 1 top/bottom, 2 left/right
style.Margin(0, 4)

// Top, Horizontal, Bottom
style.Padding(1, 2, 1)

// Top, Right, Bottom, Left (clockwise)
style.Padding(1, 2, 1, 2)
style.Margin(2, 4, 2, 4)

// Individual sides
style.PaddingTop(1)
style.PaddingBottom(1)
style.PaddingLeft(2)
style.PaddingRight(2)

style.MarginTop(1)
style.MarginBottom(1)
style.MarginLeft(2)
style.MarginRight(2)
```

---

## Dimensions

```go
style.Width(40)        // minimum width (pads to this width)
style.Height(10)       // minimum height
style.MaxWidth(80)     // clamp at maximum
style.MaxHeight(20)
```

---

## Alignment

```go
style.Align(lipgloss.Center)                    // horizontal text alignment
style.AlignHorizontal(lipgloss.Left)
style.AlignVertical(lipgloss.Top)
style.AlignVertical(lipgloss.Center)
style.AlignVertical(lipgloss.Bottom)
```

---

## Borders

### Pre-defined Border Styles

```go
lipgloss.NormalBorder()        // +--+
lipgloss.RoundedBorder()       // ╭──╮
lipgloss.ThickBorder()         // ┏━━┓
lipgloss.DoubleBorder()        // ╔══╗
lipgloss.HiddenBorder()        // invisible (for spacing)
lipgloss.ASCIIBorder()         // ASCII-only: +--+
lipgloss.BlockBorder()         // ▄▄▄
lipgloss.MarkdownBorder()      // markdown-style
```

### Applying Borders

```go
// Full border
style.Border(lipgloss.RoundedBorder())

// Selective borders (top, right, bottom, left)
style.Border(lipgloss.NormalBorder(), true, false, true, false)  // top+bottom only
style.Border(lipgloss.NormalBorder(), true)                      // all sides

// Border color
style.BorderForeground(lipgloss.Color("63"))
style.BorderBackground(lipgloss.Color("240"))

// Individual border sides
style.BorderTop(true)
style.BorderBottom(true)
style.BorderLeft(true)
style.BorderRight(true)

// Combine border style with selective sides
style.BorderStyle(lipgloss.RoundedBorder()).
    BorderTop(true).
    BorderBottom(true).
    BorderLeft(false).
    BorderRight(false)
```

---

## String Width Utilities

```go
// Measure rendered string width (handles ANSI codes, emoji, CJK)
lipgloss.Width(s string) int
lipgloss.Height(s string) int

// Get both at once
w, h := lipgloss.Size(s string)
```

---

## Style Inspection and Mutation

```go
// Copy a style — Copy() is removed in v2 (styles are value types, not pointers)
copy := original  // simple assignment works — no Copy() needed

// Unset a property
style.UnsetBold()
style.UnsetBorderLeft()

// Check if bold is set
style.GetBold() bool

// Get padding values
style.GetPaddingTop() int
style.GetPaddingLeft() int
```

---

## Common Patterns

### Panel with title

```go
titleStyle := lipgloss.NewStyle().
    Bold(true).
    Foreground(lipgloss.Color("#FAFAFA")).
    Background(lipgloss.Color("#7D56F4")).
    Padding(0, 1)

boxStyle := lipgloss.NewStyle().
    Border(lipgloss.RoundedBorder()).
    BorderForeground(lipgloss.Color("63")).
    Padding(1, 2)

title := titleStyle.Render("My Panel")
content := "Some content here"
panel := boxStyle.Render(title + "\n" + content)
```

### Status bar

```go
statusStyle := lipgloss.NewStyle().
    Background(lipgloss.Color("62")).
    Foreground(lipgloss.Color("230")).
    Width(termWidth).
    Padding(0, 1)

bar := statusStyle.Render(fmt.Sprintf(" %s  %s ", leftItem, rightItem))
```

### Highlighted selection

```go
normalItem   := lipgloss.NewStyle().Padding(0, 2)
selectedItem := lipgloss.NewStyle().
    Foreground(lipgloss.Color("170")).
    Bold(true).
    Padding(0, 2)

for i, item := range items {
    if i == cursor {
        s += selectedItem.Render("> " + item) + "\n"
    } else {
        s += normalItem.Render("  " + item) + "\n"
    }
}
```

---

## v2 Output Functions

Lipgloss v2 moved color downsampling to print time. Use these instead of `fmt.Println(style.Render(text))` for correct color handling across terminal capabilities:

```go
// Print to stdout with automatic color downsampling
lipgloss.Println(s string)

// Print to a specific writer
lipgloss.Fprintln(w io.Writer, s string)

// Render to string with color downsampling
result := lipgloss.Sprint(s string)
```

These functions detect the terminal's color profile and downsample true-color to 256/16/no-color as needed.
