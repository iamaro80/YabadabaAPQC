# Instructions for AG: start empty, detect the workbook, show only what it contains

This builds on `AG_MULTI_LAYOUT_INSTRUCTIONS.md` (profiles, strategies, canonical dataset). Do that work first, or together with this. Where the two files overlap, the multi-layout file defines the parsing, and this file defines the app shell and which screens are shown.

## 1. Requirements (decided by the product owner)

1. The app **starts empty**. Nothing is loaded at startup. The only action offered is loading a workbook from the local machine (button and drag and drop).
2. **No sample data at all.** There is no "Open sample" link and no bundled dataset.
3. On loading a workbook, the app **recognises the profile**, loads **every sheet that exists**, and shows **only the screens that have data** for that workbook.
4. **The Glossary screen stays available whenever definitions exist, whatever their source.** For Family A workbooks the definitions come from the `Glossary terms` sheet. For Family B workbooks (Cross-Industry, Consumer Products) they come from the inline `Element Description` column. Hide the Glossary screen only when the workbook has no definitions at all.
5. Out of scope: recent workbooks, remembering or auto-reopening the last workbook, and any storage of workbook contents.

## 2. Design

### 2.1 App shell: a small explicit state machine
States: `Empty`, `Loading`, `Loaded`. Transitions:
- `Empty → Loading → Loaded` on a successful load.
- `Loading → Empty` on failure (if nothing was loaded before), with an error message.
- `Loading → Loaded(previous)` on failure when a workbook was already loaded. The previous workbook must stay intact and usable, and the error must be shown.
- `Loaded → Loading → Loaded(new)` when loading another workbook.
- `Loaded → Empty` through a "Close workbook" action (add it).

Rules:
- One function, for example `setAppState(...)`, owns the transitions. Views never check "is data loaded" themselves.
- Views are built only in `Loaded`. In `Empty` and `Loading`, no view code runs against `state.data`, so there are no null accesses.
- The existing `state.data`, `state.isCustomLoaded`, "Back to sample data" button, and the startup code at [index.html:2838](index.html:2838) and [index.html:3225](index.html:3225) are replaced by this. Remove `isCustomLoaded` and the reset-to-sample button.

### 2.2 Recognising the workbook: profiles and strategies
Exactly as specified in `AG_MULTI_LAYOUT_INSTRUCTIONS.md` section 2 (detection registry, `family-a-2023`, `family-b-2026`, composed strategies, header normalisation). Do not duplicate it here. The only addition: the load result carries `profileId` and `capabilities` (next section).

### 2.3 What the workbook contains: capabilities
After parsing, compute a plain object from the data actually loaded, never from the profile name:

```
capabilities = {
  definitions:  count of elements with a non-empty definition > 0,
  metrics:      count of metric rows > 0,        // the Metrics sheet
  metricsFlag:  any element with Metrics = Y,
  changes:      any element with changes,
  levels:       the highest level present (5 or 6),
  version:      { label, comparedTo, generatedOn } // each optional
}
```

Compute these from the loaded data and not from "which sheet exists", so that an empty sheet or an empty column also hides the screen.

### 2.4 Screens declare what they need: a view registry
Each screen (tab or view) is registered once with its own availability rule:

```
registerView({ id: "explorer",  label: "...", requires: () => true,                       render })
registerView({ id: "matrix",    label: "...", requires: c => c.changes,                    render })
registerView({ id: "analytics", label: "...", requires: () => true,                        render })
registerView({ id: "glossary",  label: "...", requires: c => c.definitions > 0,            render })
```

- Navigation is built from the registry after each successful load: only views whose `requires(capabilities)` is true are shown. No view is merely disabled or greyed out. They are not rendered.
- Inside a screen, optional parts use the same rule: the inspector "Metrics" section appears only when the selected element has metrics, and the metric-based filters or analytics (if any are added) appear only when `capabilities.metrics > 0`.
- If the active view becomes unavailable after loading another workbook, switch to the Explorer.
- A URL hash that points to an unavailable view or an unknown element must fall back to the Explorer, with no error.
- Adding a new screen must need only one `registerView` call. Show this in your report.

### 2.5 Glossary screen on Family B
- The Glossary screen reads the definitions from the elements (`element.definition`), whatever their source. It must not read a glossary sheet directly.
- Check the wording: if any text says "glossary sheet", "Glossary terms" or similar, make it neutral (for example "Definitions"), because the source differs by workbook.
- For Family A, the screen's content must be unchanged from today. Regression-test it.

## 3. Work to do

1. **Remove the bundled sample**: delete the `<script src="data/pcf_data.js">` tag, the `fetch("data/pcf_data.json")` fallback, the `data/pcf_data.js`, `data/pcf_data.json` and the two CSV files (they are derived outputs of the sample), and the sample-related text in the README ("Sample Data", "Back to sample data").
2. **Build the Empty screen**: the app name, one primary "Load workbook…" button, a drop zone, one line saying which workbooks are supported (APQC PCF Excel files, "Combined" sheet), the independent-tool disclaimer and APQC attribution. It must work with keyboard only, show a visible focus state, and look right in both themes and at all text scales (85%-150%).
3. **Hide everything that needs data while empty**: category rail, inspector, search, filters, theme and scale controls that are still useful may stay (theme and scale must work in the Empty state), and anything that needs data must not be shown.
4. **Loading state**: show a clear loading indicator while parsing (the largest file has about 3,300 metric rows). The UI must stay responsive. Prevent a second load starting while one runs, or cancel the first cleanly.
5. **Error messages** (shown in a dialog or inline, readable by a screen reader): not an APQC workbook, `Combined` sheet missing, unknown layout (with the details from `AG_MULTI_LAYOUT_INSTRUCTIONS.md` section 2), unreadable or corrupt file, empty file. In all cases the app returns to a working state (`Empty` or the previous workbook).
6. **View registry and capabilities** exactly as in 2.3 and 2.4. Move the existing Explorer, Change Matrix, Analytics and Glossary screens onto the registry, and add the Metrics screen or section only if you already built it for Family B inspector support.
7. **Header and metadata**: show the loaded workbook's framework name and version from the `Introduction` parsing (fall back to the file name). Show nothing about a sample.
8. **Close workbook** action (returns to `Empty`).
9. **Python tooling**: the Python pipeline and `verify_pcf.py` validated the bundled data against the Healthcare workbook. With no bundle, keep `scripts/build_pcf_json.py` only as the Python reference parser used by the parity tests (rename or move it so its purpose is clear, and make it write nothing into `data/`). Delete or rewrite `verify_pcf.py` so it checks the Python parser output against the expected-counts fixture from the multi-layout file.

## 4. Tests (add all of these; real output in your report)

`verify_browser.py` currently assumes the sample is loaded at startup. Change it to load fixtures through the file input or drag and drop, from the six workbooks in the project root. Add a helper like `load_workbook(path)` and use it everywhere.

- **Empty start**: on a fresh page load (with storage cleared), no dataset is loaded, only the Empty screen is visible, there are no console errors, and the network log shows no request for `data/pcf_data.*`. Also check it with `Storage.prototype.getItem` throwing.
- **Each of the six workbooks**: load it, check the detected profile, the counts from the table in `AG_MULTI_LAYOUT_INSTRUCTIONS.md` section 1, and the visible screens.
- **Visible screens per family**:
  - Family A (for example Healthcare): Explorer, Change Matrix, Analytics, Glossary shown (definitions from the glossary sheet). No Metrics detail.
  - Family B (Cross-Industry and Consumer Products): Explorer, Change Matrix, Analytics, **Glossary shown with definitions from `Element Description`**, and metrics detail in the inspector.
- **Glossary on Family B**: the term count equals the number of non-empty definitions (Cross-Industry 2,017, Consumer Products 2,019), and the text matches `Element Description` for at least three sampled elements.
- **Hiding**: a test workbook (create it in the test, by editing a copy of a fixture in memory) with no definitions at all and no changes must hide the Glossary and Change Matrix screens, and must not show disabled placeholders for them. Also test loading such a workbook after loading a full one: the active view that became unavailable falls back to the Explorer.
- **Failures**: a corrupt file, a missing `Combined` sheet and an unknown layout each show the right message and leave the app working. Run each once from `Empty` and once from `Loaded` (the previous workbook must be unchanged afterwards).
- **State machine**: the transitions in 2.1, including `Loaded → Empty` through Close workbook, and loading a second workbook of the other family (screens change accordingly, no stale content from the first).
- **Deep link**: a hash that references an unavailable view or element falls back to the Explorer.
- **Escaping, Level 6 (Payor) and text-scale tests** from the other two instruction files still pass, now through the new load helper.
- **No regression** for Healthcare and Retail screens, apart from the removed startup load.

## 5. Out of scope
- Recent workbooks and any persistence of workbook data.
- New runtime dependencies. SheetJS stays the only vendored library.
- Visual redesign beyond the Empty screen.

## 6. Done when
- A fresh page load shows the Empty screen only, and the sample data is gone from the code, the data folder and the README.
- All six workbooks load, are recognised, and show exactly the screens that have data, with the Glossary present for all six (definitions from the glossary sheet for Family A and from `Element Description` for Family B).
- Adding a screen needs one `registerView` call, shown in your report with the exact lines.
- All existing and new tests pass, with the real output pasted in your report.
- The README describes the empty start, supported workbooks, the layout profiles, and how to add a profile and a view.
