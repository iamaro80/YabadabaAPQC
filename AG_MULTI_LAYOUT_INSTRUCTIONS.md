# Instructions for AG: support all APQC workbook layouts (6 reviewed)

Read this whole file before coding. Complete the fixes in `AG_FIX_INSTRUCTIONS.md` first, or at least item 2 (Python/JS parser parity), because this work builds on it.

## 1. What the six workbooks look like (all six were read from the files)

Files: Healthcare Provider, Retail, City Government, Health Insurance Payor (all "v7.2.1 vs v6.x", April 2023), Cross-Industry v8.0 and Consumer Products v8.0 (2026).

There are two **layout families**. Within a family the structure is identical, and only the data and the `Introduction` text change.

| Aspect | Family A: "2023 comparison" (Healthcare, Retail, City Gov, Payor) | Family B: "2026 v8.0" (Cross-Industry, Consumer Products) |
|---|---|---|
| Sheets | `Introduction, About, Categories, 1.0 ... 13.0, Combined, Glossary terms, Copyright and attribution` | `Introduction, About, Categories, 1.0 ... 13.0, Combined, Metrics, Copyright and Attribution` (capital "A"; no glossary) |
| `Combined` headers | `PCF ID, Hierarchy ID, Name, Difference Index, Change details, Metrics available?` (6 columns) | Same plus `Element Description`, with `Change Details` and `Metrics Available?` capitalised differently (7 columns) |
| Definitions | Joined from `Glossary terms` (headers `Process Element ID, Hierarchy ID, Process element, Definition`) by ID or Hierarchy ID. Not every element has one (Healthcare 1,931 of 1,985). The glossary has one `Root` row (ID 10001, no Hierarchy ID) that matches nothing and must be ignored | Inline in `Element Description` (Cross-Industry 2,017 of 2,017, Consumer Products 2,019 of 2,039) |
| Metrics | Only the Y/N flag | Flag plus a `Metrics` sheet (Cross-Industry 3,284 rows, Consumer Products 3,347 rows). Headers: `Process Element ID, Hierarchy ID, Process Element, Metric Category, Metric ID\n, Metric Name, Formula, Units`. The `Metric ID` header has a trailing newline |
| `Introduction` | Not parsed today | Version text such as `VERSION NUMBER 8.0` and `COMPARED TO ... VERSION 7.4`. **The text is in column C in Cross-Industry and column D in Consumer Products, and only Cross-Industry has `GENERATED ON`.** Scan every cell on the sheet, never a fixed cell |
| Copyright | ©2022 | ©2026 (read it from the file) |

Measured facts per workbook (use these as expected values in tests, and tell me about any difference you find):

| Workbook | Elements | Levels present | With changes | NEW | RENAME | Metrics = Y | Definitions | Metric rows |
|---|---|---|---|---|---|---|---|---|
| Healthcare Provider | 1,985 | 1-5 | 1,187 | 960 | 134 | 221 | 1,931 (glossary) | none |
| Retail | 1,708 | 1-5 | 762 | 608 | 74 | 180 | 1,463 (glossary) | none |
| City Government | 2,100 | 1-5 | 1,310 | 983 | 201 | 229 | 1,849 (glossary) | none |
| Health Insurance Payor | 2,142 | **1-6** | 1,181 | 994 | 94 | 228 | 1,848 (glossary) | none |
| Cross-Industry v8.0 (vs 7.4) | 2,017 | 1-5 | 171 | 107 | 31 | 319 | 2,017 (inline) | 3,284 |
| Consumer Products v8.0 (vs 7.2.1) | 2,039 | 1-5 | 452 | 253 | 102 | 325 | 2,019 (inline) | 3,347 |

Things that the review found and that the current code does not handle:

1. **Family B fails today.** The parser throws `Sheet 'Glossary terms' wasn't found` ([index.html:4782](index.html:4782)) and reads the exact headers `Change details` and `Metrics available?`.
2. **Health Insurance Payor has 13 level-6 elements** (for example `2.1.1.3.5.1`). The app assumes levels 1-5: `level_names` stops at 5 ([index.html:4804](index.html:4804)), and the level filter offers only up to "Level 5: Task" ([index.html:2139](index.html:2139)). Level 6 currently falls back to the label `Level 6`. Check the tree indentation, breadcrumbs, level filter, analytics by level, text scaling at 85%-150%, and the Change Matrix for level 6.
3. **Category names differ by industry** (for example `2.0` is `Develop and Manage City Services` in City Government and `Develop and Manage Health Care Services` in Healthcare; `4.0` is `Deliver City Products`, `Merchandise Products and Services`, `Deliver Physical Products`, etc.). Never hard-code or look up category names. Always take them from the root rows (`N.0`).
4. **Operating vs Support split.** No workbook marks it, so it is a heuristic. In all six workbooks `7.0` is the Human Resources/Human Capital category and `8.0`-`13.0` are the same support categories, so "1-6 operating, 7-13 management and support" fits all six. The existing bundled Healthcare sample uses 1-5, which is inconsistent with that and with Retail. **AG: do not change this silently. Report this inconsistency to me with the current numbers and the numbers after the change, and wait for my decision.** Until then, keep each profile's operating set as an explicit setting with the user override in the upload dialog.
5. **Rename text with commas** (`WAS:` text containing commas) occurs in every workbook: Cross-Industry 3, Consumer Products 20, City Government 19, Healthcare 16, Payor 13, Retail 9. Everything after `WAS:` is text.
6. **Change-detail strings are otherwise clean**: tokens are only `+id`, `-id`, `cid`, `NEW`, `RENAME` and `WAS:text`. There are no duplicate Hierarchy IDs or PCF IDs in any workbook, and every Hierarchy ID is numeric and dot-separated.

## 2. Design recommendation

**Use the Strategy pattern, but composed, not as one strategy per file type.**

There are two independent axes of variation:
- **Where definitions come from:** a glossary sheet joined by ID, or an inline column.
- **Where metric detail comes from:** a flag only, or a `Metrics` sheet.

A single "HealthcareParser / CrossIndustryParser" strategy per workbook would copy the shared logic (hierarchy derivation, change decoding, category stats) and create a new class for every new industry combination. Use small strategies for each axis instead, and put the shared logic in one pipeline.

```
Workbook ──> LayoutDetector (registry, ordered) ──> LayoutProfile
                                                      │
   shared pipeline (single implementation):           ▼
   read rows → normalise headers → HeaderMap ─> DefinitionSource strategy
                                                   MetricsSource strategy
                                                   VersionInfo strategy
                                                   OperatingCategoryRule
   → decode hierarchy → decode changes → category stats → canonical dataset
```

- **Canonical dataset** (the single output shape the UI already consumes): `metadata`, `categories`, `elements`. Add `metrics: []` on an element (empty when none) and `metadata.source_layout`, `metadata.version_label`, `metadata.compared_to`, `metadata.copyright_year`. The UI must never branch on layout. It only checks whether data exists (for example, shows a metrics section when `element.metrics.length > 0`).
- **Strategy interfaces** (same names and behaviour in JS and Python):
  - `DefinitionSource.load(workbook, rows) -> Map<elementKey, text>`: `GlossarySheetDefinitions` (current behaviour), `InlineColumnDefinitions` (reads `Element Description`).
  - `MetricsSource.load(workbook) -> Map<hierarchyId, Metric[]>`: `FlagOnlyMetrics` (returns an empty map, keeps the Y/N flag), `MetricsSheetMetrics`.
  - `VersionInfo.read(workbook) -> {label, comparedTo, generatedOn}`: parse `Introduction` when present, with a fallback to the file name.
  - `OperatingCategoryRule`: a set of category numbers, read from the profile and not hard-coded.
- **Layout profile**: plain data plus the strategies it uses.
  ```
  { id: "cross-industry-v8", detect(wb), headers: {...aliases...}, definitions: InlineColumnDefinitions, metrics: MetricsSheetMetrics, operatingCategories: [1..6] }
  ```
- **Detection registry**: an ordered list of profiles. Each has a `detect(workbook)` returning true/false based on structure (sheet names and header names), never on file name. The first match wins. If none matches, fail with an actionable error that lists the sheets found, the headers found in `Combined`, and what was expected.
- **Header normalisation** (a shared helper, not a strategy): lower-case, trim, collapse whitespace and newlines, strip a trailing `?`. `Change Details` and `Change details` become the same key. Match columns by normalised name, never by position. Support aliases: `PCF ID` / `Process Element ID`, `Element Description` / `Definition`.
- **Operating vs Support**: a prompt in the upload dialog already exists (`options.operatingCategories`). Pre-fill it from the profile and still let the user change it. See finding 4 in section 1: do not change the Healthcare default without my answer.

Why this and not the alternatives:
- *One big if/else on sheet names*: this is the current state. It works for two layouts and turns into a maintenance problem at the third.
- *Subclass per industry*: it duplicates the shared logic and breaks on any new combination of the two axes.
- *Config-only (a JSON mapping)*: enough for header aliases, but joining a sheet or reading an extra sheet is behaviour, so it needs code. Hence strategies for behaviour and data for configuration.
- Keep it proportionate: no dependency-injection framework or class hierarchies. In JS, a profile is an object literal holding plain functions. In Python, a small dataclass or module-level functions.

## 3. Work to do

### 3.1 Shared parsing core
- Refactor the JS parser in `index.html` into the structure above (profiles, registry, strategies, header normaliser). Keep it inside the file, or in `<script src>` files that work over `file://` (no ES modules).
- Mirror the same structure in `scripts/build_pcf_json.py`. The two implementations must produce identical output on the same workbook. The parity test from `AG_FIX_INSTRUCTIONS.md` item 2 must cover all three workbooks.
- Fix `decode_changes` as described in `AG_FIX_INSTRUCTIONS.md` item 3. Everything after `WAS:` is rename text, including commas. Check this against the Cross-Industry file: 31 renames, and make sure no token such as `policies` or `and strategies` appears as a child or a separate token.

### 3.2 Layout profiles
- Two profiles are enough for all six workbooks: `family-a-2023` (glossary sheet, flag-only metrics) and `family-b-2026` (inline description, `Metrics` sheet). Cross-Industry and Consumer Products use the same profile, and so do all four 2023 workbooks. Do **not** create a profile per industry. The industry name comes from the `Introduction` sheet or the file, and is data.
- `family-b-2026`: `InlineColumnDefinitions`, `MetricsSheetMetrics`, header aliases from section 1.
- `MetricsSheetMetrics`: group by Hierarchy ID (fall back to Process Element ID). Keep the sheet order. Trim headers (including `Metric ID\n`). Map to `{ category, id, name, formula, units }`. Skip rows with no metric name, and report the number of skipped rows in the parse summary.
- Check the Metrics sheet's Hierarchy IDs against `Combined`. I checked that every metric Hierarchy ID exists in `Combined` today. If a metric points to an unknown element in a future file, keep a count in the parse summary and do not crash.
- Parse the `Introduction` sheet by scanning all cells: framework name (the line containing `PROCESS CLASSIFICATION FRAMEWORK`), `VERSION NUMBER x`, `COMPARED TO ... VERSION y`, and `GENERATED ON` when present (it is absent in Consumer Products). Family A workbooks have an `Introduction` sheet too, so check what it holds and fall back to the file name where it holds nothing. The version label and the comparison are optional fields: the UI must display a missing one cleanly, without "undefined". Use these in the header, the upload summary, `metadata.version`, and the copyright line.
- Copyright: read the year from the `Copyright and Attribution` sheet (©2026 here) and do not hard-code ©2022 for uploaded files. The README's static ©2022 refers only to the bundled Healthcare sample.

### 3.2b Level 6 (Health Insurance Payor)
- Make hierarchy depth data-driven. Derive the levels present from the Hierarchy IDs. The level filter options, the Analytics breakdown and the level legends must come from the levels that exist, not a fixed list of five. Keep the names `Category, Process group, Process, Activity, Task` for levels 1-5. Use `Level 6` for the sixth level.
- Verify parent derivation, tree indentation, breadcrumbs (which collapse when deep), the Change Matrix and text scaling for 6 levels.

### 3.3 UI
- Inspector: when `element.metrics` is non-empty, add a "Metrics" section (collapsible, grouped by metric category, showing name, formula, units). Escape all values. Show nothing for flag-only files.
- Analytics and the Glossary view must keep working for a file with no glossary sheet. The definitions now come from the element description. Check any text that says "glossary" is still accurate for this layout (for example, say "definition" instead).
- Change Matrix, filters and the category summary must work with the new numbers (2,017 elements, 171 changed).
- Upload dialog: show the detected layout ("Detected layout: Cross-Industry v8.0") in the preview summary.
- Error handling: a corrupt file, a missing `Combined`, or an unknown layout must show the actionable error from section 2, and never an uncaught exception.

### 3.4 Bundled data and the README
- Keep Healthcare as the bundled sample. Do not bundle Cross-Industry unless I ask, because the file is large.
- Update the README: the Sample Data section, the supported layouts table (copy section 1's table), the testing section, and how to add a new layout profile in under 10 lines.

## 4. Tests (all must be added and pass)
- **All six workbooks** load in both parsers and match the measured table in section 1 (elements, levels, with changes, NEW, RENAME, Metrics = Y, definitions, metric rows). Put the expected values in one shared fixture file that both the JS and Python tests read.
- Layout detection: each workbook is detected as the right profile (four as `family-a-2023`, two as `family-b-2026`). Detection must not use the file name (rename a copy and test again). An unknown workbook gives the actionable error.
- Introduction parsing: Cross-Industry (text in column C, with `GENERATED ON`), Consumer Products (column D, no `GENERATED ON`, compared to 7.2.1), and a Family A workbook.
- Level 6: Payor shows 13 level-6 elements, the level filter includes level 6, and the tree, breadcrumbs and Change Matrix render them at 85%, 100% and 150% text scale with no horizontal overflow.
- Header normalisation: `Change Details` / `Change details` / ` Change  Details? ` all resolve to the same column. `Metric ID\n` resolves to `metric id`.
- Glossary join: the `Root` row (no Hierarchy ID) is ignored, and the number of joined definitions matches the table.
- `decode_changes` cases from `AG_FIX_INSTRUCTIONS.md` item 3, plus one real `WAS:` string with commas from each workbook.
- Parity: JS and Python outputs identical field by field for all six workbooks, including `metrics`.
- Browser (`verify_browser.py`): upload one Family A file and one Family B file, check the detected-layout text and counts, the inspector Metrics section for an element that has metrics, and no empty Metrics section for one that has none. Include the escaping test from `AG_FIX_INSTRUCTIONS.md`, with injection strings in a metric name and in an element description.
- Regression: all earlier Healthcare and Retail assertions must still pass unchanged (unless I decide to change the operating split, see section 1 finding 4).
- Performance: uploading the largest file (Consumer Products, 3,347 metric rows) must stay responsive. Report the parse time for all six. The UI must not freeze for more than about 1 second at 100% text scale.

## 5. Out of scope
- No new runtime dependencies. SheetJS stays the only vendored library.
- No server, no network calls.
- No redesign of the existing views beyond the Metrics section.

## 6. More industry workbooks
APQC publishes more industry workbooks than these six. Do not guess their layouts. When I provide another file:
1. Diff its sheet names and the `Combined` headers against the table in section 1.
2. If it fits an existing profile, add only its row to the shared fixture and its tests. If it needs behaviour that no existing strategy provides, add a strategy or a profile.
3. Add its detection test, expected counts and parity case.

If a file reaches the "unknown layout" error, the message must give me enough information to send you the file for step 1.

## 7. Done when
- All Healthcare and Retail tests still pass, plus all new tests, with real output pasted in your report.
- All six workbooks upload, explore, search and analyse correctly, with metrics visible in the inspector for Family B and level 6 working for Payor.
- Adding a fourth layout needs only a new profile object and a test, with no change to the pipeline. Show this in your report by pointing to the exact lines for the `family-b-2026` profile.
