---
name: stitch-design-md
license: CC-BY-4.0
description: >-
  Work with Google Stitch's design.md format. Use this skill when generating UI,
  designing with Stitch, or writing design.md specs. Teaches how to structure the
  spec with concrete examples and validation rules.
compatibility: >-
  Requires Google Stitch
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# stitch-design-md — Google Stitch design.md format

Use this skill when tasked with creating, editing, or understanding Google Stitch `design.md` files. This format is used by Stitch for AI-assisted UI design generation.

## Format Overview

The `design.md` file serves as a structured Markdown specification that guides the UI generation process. It must be written in standard Markdown, utilizing headers, lists, and code blocks appropriately. Describe *what* the UI should look like and how it behaves, rather than *how* to implement it in code.

### Core Structure

A well-formed `design.md` typically includes these sections:

1.  **Title and Overview:** A clear heading describing the UI component or page, followed by a brief summary of its purpose.
2.  **Key Requirements / Features:** A bulleted list of essential functionalities and elements that must be present in the UI.
3.  **Visual Style / Theming (Optional):** Instructions regarding color palettes, typography, and general aesthetic guidelines.
4.  **Layout / Structure:** A description of how elements should be arranged on the screen (e.g., header, main content area, sidebar, footer).
5.  **Component Details:** Specific breakdowns of individual components, including their states (hover, active, disabled) and data bindings.
6.  **Interactions:** Descriptions of how the user interacts with the UI and what the expected outcomes are.

### Writing Guidelines & Stitch-specific Constraints

*   **Be specific about layout:** Use terminology familiar to designers and front-end developers (e.g., "flexbox", "padding", "primary button").
*   **Provide examples:** Use example data or content if it helps clarify the layout's intent.
*   **Name components:** If referencing existing components in a design system, explicitly name them.
*   **Keep it declarative:** Avoid prescribing specific HTML/CSS implementations unless strictly necessary. Stitch's AI model handles the translation from declarative design to code.

## Example: User Profile Card

Here is a complete example of a well-structured `design.md` for a User Profile Card:

```markdown
# User Profile Card

Displays user information in a compact card format.

## Key Requirements

* Show user's avatar, name, and email address.
* Include an "Edit Profile" action button.

## Layout & Structure

Use a flex container with a horizontal layout for the main content, inside a card with a subtle shadow.

1.  **Avatar:** 48x48px circular image on the left.
2.  **Details:** Vertical flex container on the right, next to the avatar.
    *   **Name:** Bold, 16px font.
    *   **Email:** Regular, 14px font, gray color.
3.  **Action:** The "Edit Profile" button should be right-aligned within the card.

## Component Details

### Avatar Image
* Fallback to a generic placeholder icon if no image URL is provided.

### Edit Profile Button
* **States:**
    *   **Default:** Outlined button style.
    *   **Hover:** Light gray background.
```

## References

For more detailed examples and advanced usage, see the files in the `references/` directory:

*   Read `references/format-overview.rst` for a deep dive into the structural requirements.
*   Read `references/examples.rst` for additional concrete examples of `design.md` files.

## Official Documentation

*   [Stitch design.md format](https://stitch.withgoogle.com/docs/design-md/format)