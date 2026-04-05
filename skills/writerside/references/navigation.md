# Writerside Navigation Reference

Navigation in Writerside is controlled by a **tree file** (`.tree`) that defines the table of contents sidebar shown in the published documentation.

---

## Tree File Structure

The tree file contains nested `<toc-element>` tags that map directly to the sidebar hierarchy:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE instance-profile SYSTEM "https://resources.jetbrains.com/writerside/1.0/product-profile.dtd">

<instance-profile id="hi" name="Help" start-page="overview.topic">

    <toc-element topic="overview.topic"/>

    <toc-element toc-title="Getting Started">
        <toc-element topic="installation.topic"/>
        <toc-element topic="quickstart.topic"/>
    </toc-element>

    <toc-element topic="configuration.topic">
        <toc-element topic="advanced-config.topic"/>
    </toc-element>

</instance-profile>
```

- `start-page` on the root element sets the documentation home page.
- Nesting `<toc-element>` tags creates sub-sections in the sidebar.

---

## Navigation Ordering

Topics appear in the sidebar in the order they appear in the tree file.

**Manual ordering:** Edit the tree file directly, or drag-and-drop topics in the Writerside tool window.

**Alphabetical sort:** Right-click any parent node in the Writerside tool window → **Sort Children Alphabetically**. Useful for command references or option listings.

---

## Section Pages (Wrappers)

A wrapper is a TOC entry that groups topics without having its own content file — it acts as a section header only.

```xml
<!-- Section header with no topic file — just a group label -->
<toc-element toc-title="Administration">
    <toc-element topic="user-management.topic"/>
    <toc-element topic="permissions.topic"/>
    <toc-element topic="audit-log.topic"/>
</toc-element>
```

Create via: **New Topic → Empty Group** in the Writerside tool window, or add manually in the tree file.

Use wrappers when you want to group topics logically but do not have (or need) an introductory page for that section.

---

## Hiding Topics

Add `hidden="true"` to exclude a topic from the sidebar while keeping it accessible via direct URL or internal link:

```xml
<toc-element topic="legacy-api.topic" hidden="true"/>
```

Hidden topics:
- Do not appear in the sidebar navigation
- Remain searchable
- Can still be linked to from other topics
- Useful for deprecated content, deep reference pages, or topics linked only from other topics

---

## External Links in the TOC

Include non-topic URLs as TOC entries:

```xml
<toc-element toc-title="API Reference" href="https://api.example.com/docs"/>
```

---

## `toc-title` Override

By default the sidebar uses the topic's `title`. Use `toc-title` to show a shorter label without changing the topic title:

```xml
<!-- Full title in topic: "Configuring the Application Server" -->
<toc-element topic="app-server-config.topic" toc-title="App Server"/>
```

---

## Summary

| Need | Solution |
|------|----------|
| Reorder topics | Drag in tool window, or edit tree file directly |
| Group without an intro page | Empty wrapper with `toc-title` |
| Hide from sidebar but keep accessible | `hidden="true"` on `<toc-element>` |
| Set documentation home page | `start-page="topic-id.topic"` on `<instance-profile>` |
| Shorten sidebar label | `toc-title` attribute on `<toc-element>` |
| Alphabetical section | Right-click → Sort Children Alphabetically |
