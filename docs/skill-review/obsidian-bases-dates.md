# Obsidian Bases date arithmetic evidence

Obsidian 1.13.7 returns a Duration when Bases subtracts two dates.
The existing `.days` conversion and rounding examples work in this version.
The correction adds version-specific evidence and explains elapsed days across daylight saving time (DST).

This application pilot addresses [#428](https://github.com/nq-rdl/agent-extensions/issues/428).
It ran on 29 September 2026.
The offline regression tests check captured evidence and guidance.
They do not launch Obsidian or establish behaviour in another version.

## Application and disposable vault

The official [desktop installer](https://github.com/obsidianmd/obsidian-releases/releases/tag/v1.13.7) supplied Obsidian 1.13.7.
Its SHA-256 matched the published release asset digest:

```text
17dc33b49cb3e785ecc27edd2ea0c79e40207798b554fd2886e36ebee7af9ae0
```

The app ran inside the existing Playwright Ubuntu container with Xvfb.
Electron reported version 43.3.0 and Chromium reported version 150.0.7871.212.
Each run used disposable application configuration and the same fixture vault.
The app loaded the `.base` file through the enabled Bases core plugin.
No community plugins, user vaults, credentials, or global settings were involved.

The [fixture directory](../../tests/fixtures/obsidian-bases-dates/) contains these review artifacts:

- `vault/`: the `.base` file, two notes, and the core-plugin selection
- `cases.json`: the exact local dates and times
- `america-new-york.json` and `utc.json`: complete application captures
- `america-new-york.png`: screenshot of the displayed table
- `metadata.json`: application versions, installer digest, container digest, and canonical source identifiers

The checked-in `.base` file uses YAML syntax.
It defines 88 formulas and includes both notes.
Each capture records the loaded formulas, returned types, numeric values, and display text.

Electron's DevTools protocol captured the running application through `Runtime.evaluate`.
The capture reads the active Bases view's result objects after Obsidian evaluates the formulas.
It does not copy the evaluator into another runtime or replace it with a mock.
`Page.captureScreenshot` captured the displayed table.
These internal inspection methods are evidence tooling, not supported Obsidian plugin APIs.

The raw Duration object's `fields` record internal storage components.
The separate `.days`, `.hours`, and `.milliseconds` formula results record the public numeric conversions.
For example, subtraction stores milliseconds internally even when its public `.days` formula returns `1`.

## Observed results

The following inputs use local time in `America/New_York`.
The subtraction expression is `date(end) - date(start)`.
Every raw subtraction returned Duration.
Every `.days`, `.hours`, and `.milliseconds` conversion returned Number.
The capture also checks `.isType("duration") == true` and `.isType("number") == false`.

| Case | Start | End | Milliseconds | `.hours` | `.days` | `.days.round(0)` | `.days.floor()` | `.days.ceil()` |
|---|---|---|---:|---:|---:|---:|---:|---:|
| One day | 2026-01-01 00:00:00 | 2026-01-02 00:00:00 | 86400000 | 24 | 1 | 1 | 1 | 1 |
| Fractional | 2026-01-01 00:00:00 | 2026-01-02 12:30:00 | 131400000 | 36.5 | 1.5208333333333333 | 2 | 1 | 2 |
| Zero | 2026-01-01 | 2026-01-01 | 0 | 0 | 0 | 0 | 0 | 0 |
| Negative | 2026-01-02 12:00:00 | 2026-01-01 00:00:00 | -129600000 | -36 | -1.5 | -1 | -2 | -1 |
| Spring DST | 2026-03-08 00:00:00 | 2026-03-09 00:00:00 | 82800000 | 23 | 0.9583333333333334 | 1 | 0 | 1 |
| Autumn DST | 2026-11-01 00:00:00 | 2026-11-02 00:00:00 | 90000000 | 25 | 1.0416666666666667 | 1 | 1 | 2 |

The UTC repeat returned 86400000 milliseconds, 24 hours, and 1 day for both DST date pairs.
All other fixed-date cases matched the New York run.
`.days.round(3)` returned `1.521` for the fractional case.
It returned `0.958` and `1.042` for the New York spring and autumn cases.

`.days` therefore measures elapsed 24-hour periods.
It does not count calendar-date boundaries.
Nearest rounding produces `1` for these two DST cases.
That observation does not establish a general calendar-date counting formula.
Negative rounding also matters: `-1.5` rounds to `-1`, floors to `-2`, and ceils to `-1`.

The following formulas test conversion, supported arithmetic, and known failures:

| Formula | Observed type | Observed value |
|---|---|---|
| `duration("1d")` | Duration | 86400000 total milliseconds |
| `duration("36h").days` | Number | 1.5 |
| `duration("36h").hours` | Number | 36 |
| `duration("36h").milliseconds` | Number | 129600000 |
| `duration("36h").days.round(0)` | Number | 2 |
| `duration("36h").round(0)` | Error | `Cannot find function "round" on type Duration` |
| `(date(end) - date(start)).round(0)` | Error | `Cannot find function "round" on type Duration` |
| `((date(end) - date(start)) / 86400000).round(0)` | Error | `Cannot find function "round" on type Duration` |
| `(number(date(end)) - number(date(start))) / 86400000` | Number | Same elapsed-day value as `.days` for each case |
| `date("2026-01-01") + (duration("1d") * 2)` | Date | 2026-01-03 |
| `if(due, (date(due) - today()).days, "")` on `missing-due.md` | String | Empty string |

The fixture also records duration-string shifts at spring DST.
Both `date("2026-03-08") + "1d"` and `+ "24h"` displayed `2026-03-09 00:00:00 -04:00`.
Those observations apply only to the recorded version and inputs.
They do not justify extending a fixed 24-hour interpretation to all date-offset operations.

## Canonical documentation comparison

The official help source was checked at commit `9cf8c2913e56830e75c13f33ba198d7e70b6d9ef` on 29 September 2026.
The [pinned syntax page](https://github.com/obsidianmd/obsidian-help/blob/9cf8c2913e56830e75c13f33ba198d7e70b6d9ef/en/Bases/Bases%20syntax.md#date-arithmetic) describes date subtraction as a millisecond difference.
The [pinned functions page](https://github.com/obsidianmd/obsidian-help/blob/9cf8c2913e56830e75c13f33ba198d7e70b6d9ef/en/Bases/Functions.md#duration) documents duration parsing and scalar arithmetic.
It does not document the `.days` conversion fields.

The syntax description does not identify the Duration wrapper observed in Obsidian 1.13.7.
The captured millisecond magnitude agrees with the description, but the application result is not Number.
Replacing `.days` with division followed by `.round()` fails in the recorded application.
The existing conversion examples therefore remain unchanged.
The skill now identifies the tested version and warns about elapsed-day semantics and other versions.
Both generated plugin packages receive the same guidance.

## Repeating the application check

Use Obsidian 1.13.7 and a copy of the fixture vault.
Keep the application configuration disposable.

1. Set the process timezone to `America/New_York` before launching Obsidian.
2. Open the copied vault and confirm that the Bases core plugin is enabled.
3. Open `date-arithmetic.base` and wait for both result rows.
4. Compare the numeric conversion columns with the table above.
5. Check the Duration errors and the guarded missing-property result.
6. Close Obsidian before changing the timezone.
7. Set the process timezone to `UTC` and repeat the same check.

The `TZ` environment variable set each timezone in the Linux container.
The running renderer confirmed it with `Intl.DateTimeFormat().resolvedOptions().timeZone`.
A desktop environment might require an equivalent operating-system timezone setting.
Confirm the renderer timezone before comparing results.

For an exact result capture, run this inspection in the application's developer console after opening the base:

```javascript
const view = app.workspace.getLeaf().view;
const evidence = {
  title: document.title,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  formulas: view.query.getSerializable().formulas,
  rows: Array.from(view.controller.results.values()).map(row => ({
    file: row.file.path,
    values: Object.keys(view.query.formulas).map(name => {
      const value = row.getValue('formula.' + name);
      return {
        name,
        type: value?.type?.type,
        text: value?.toString(),
        data: value?.data,
        milliseconds: typeof value?.getMilliseconds === 'function'
          ? value.getMilliseconds() : undefined
      };
    })
  }))
};
console.log(JSON.stringify(evidence, null, 2));
```

The checked-in captures also retain internal Duration fields and the rendered body text.
The screenshot shows selected columns from the same New York run.
It does not display all 88 formulas at once.

## Regression coverage and limits

The guidance contracts first failed because version-specific and DST guidance was absent.
After the skill changes, the contracts passed.
Self-review added a failing contract for the reference table's ambiguous
"Total days" label; it passed after the table and example comments specified elapsed days.
The eight offline tests also check complete formula capture and both rows.
They cover known durations, zero, negative fractions, both DST transitions,
explicit numeric-date conversion, decimal rounding, rounding errors, and a missing optional property.

The pilot does not establish behaviour in older Obsidian versions.
It does not cover all timezones, leap-second handling, invalid dates, month lengths, or calendar-day counting conventions.
No live model-routing pilot was performed.
The offline tests preserve this application evidence without claiming to rerun it.
