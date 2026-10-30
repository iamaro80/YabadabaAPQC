# YabadabaAPQC

Interactive, zero-dependency offline Single Page Application (SPA) for exploring, searching, and analyzing any APQC Process Classification Framework® (PCF) workbook, whether cross-industry or industry-specific.

## Empty Startup & Multi-Workbook Support

YabadabaAPQC starts completely empty with zero bundled data and zero network requests. The user loads any standard APQC Process Classification Framework® (PCF) Excel workbook (`.xlsx`) directly from their local machine via the primary **Load workbook** button or drag-and-drop. To close the currently loaded workbook and return to the clean empty state, click **Close workbook**.

## Supported APQC PCF Workbook Layouts

YabadabaAPQC uses a composed Strategy architecture to parse and analyze any standard APQC PCF workbook across both historical and modern workbook layout families:

| Feature / Aspect | Family A: "2023 Comparison" | Family B: "2026 v8.0" |
| :--- | :--- | :--- |
| **Reference Workbooks** | Healthcare Provider, Retail, City Government, Health Insurance Payor | Cross-Industry v8.0, Consumer Products v8.0 |
| **Worksheet Structure** | `Introduction`, `About`, `Categories`, `1.0`..`13.0`, `Combined`, `Glossary terms`, `Copyright and attribution` | `Introduction`, `About`, `Categories`, `1.0`..`13.0`, `Combined`, `Metrics`, `Copyright and Attribution` |
| **Combined Headers** | `PCF ID`, `Hierarchy ID`, `Name`, `Difference Index`, `Change details`, `Metrics available?` | Same plus `Element Description` |
| **Definition Source** | `GlossarySheetDefinitions` (joins `Glossary terms` sheet by PID/HID, ignores Root row 10001) | `InlineColumnDefinitions` (reads `Element Description` column in `Combined`) |
| **Metrics Source** | `FlagOnlyMetrics` (Y/N flag in Combined) | `MetricsSheetMetrics` (reads `Metrics` sheet with Name, Category, Formula, Units) |
| **Hierarchy Depth** | Fully dynamic, supports Level 6 (e.g. 13 Level-6 elements in Health Insurance Payor) | Levels 1–5 |
| **Default Operating Categories** | 1–5 (Healthcare) or 1–6 (Retail, City Gov, Payor); configurable in upload dialog | 1–6; configurable in upload dialog |

### Adding a New Layout Profile (<10 Lines of Code)

The pipeline is decoupled from workbook structures via pluggable layout profiles in both Python (`scripts/build_pcf_json.py`) and JavaScript (`index.html` & `scripts/test_shared_cases.js`). Adding a new profile requires no modifications to the core parsing pipeline:

```javascript
LAYOUT_PROFILES.push({
  id: "custom-layout-2027",
  label: "2027 Custom Framework",
  detect: (sheets, headers) => sheets.includes("combined") && sheets.includes("dictionary"),
  definitionSource: DictionarySheetDefinitions,
  metricsSource: MetricsSheetMetrics,
  defaultOperating: ["1", "2", "3", "4", "5", "6"]
});
```

## Dynamic Capabilities & Pluggable View Registry

After parsing a workbook, the application computes a dynamic capabilities object from the data actually loaded:

```javascript
capabilities = {
  definitions:  count of elements with a non-empty definition > 0,
  metrics:      count of metric records > 0 (Metrics sheet),
  metricsFlag:  any element with Metrics = Y,
  changes:      any element with change details,
  levels:       highest hierarchy level present (5 or 6),
  version:      { label, comparedTo, generatedOn }
}
```

Screens register with the View Registry declaring their own capability requirements:

```javascript
registerView({ id: "explorer",  label: "Explorer",         requires: () => true,            render });
registerView({ id: "matrix",    label: "Change Matrix",    requires: c => c.changes,         render });
registerView({ id: "analytics", label: "Analytics",        requires: () => true,            render });
registerView({ id: "glossary",  label: "Definitions",      requires: c => c.definitions > 0, render });
```

### Adding a New View (Exactly 1 Call)

Adding a new screen to the application requires only a single `registerView` call. The panel container is generated on demand, and navigation automatically shows or hides the tab based on the workbook's capabilities:

```javascript
registerView({
  id: "benchmarks",
  label: "Benchmarks",
  requires: c => c.metrics > 0,
  render: targetEl => {
    targetEl.innerHTML = `
      <div style="padding: 2rem;">
        <h2>Benchmarking Metrics Overview</h2>
        <p>Total metrics loaded: ${state.capabilities.metrics.toLocaleString()}</p>
      </div>
    `;
  }
});
```

* **No Disabled Placeholders**: Screens whose requirements are not met are not rendered in navigation.
* **Automatic Fallback**: If an active screen becomes unavailable upon loading another workbook, or if a deep link hash points to an unavailable view or unknown element, the app safely falls back to the Explorer view.
* **State Machine Resilience**: The application transitions cleanly between `Empty`, `Loading`, and `Loaded`. If a file read or layout parse fails, the app preserves the previous workbook intact or returns to `Empty` with an actionable error dialog.

## Independent Tool Disclaimer

> **YabadabaAPQC is an independent tool. It is not affiliated with or endorsed by APQC.**  
> Process Classification Framework® and PCF® are registered trademarks of APQC.

## Architecture & Single Source of Truth

* **`index.html` is the single source of truth** for application markup, styling, and client-side logic. All UI components, inspector layouts, event delegations, keyboard shortcuts, and storage safety routines are implemented directly in `index.html`.
* **Zero external network dependencies**: Works entirely offline, including over the `file://` protocol or any local static HTTP server.
* **Storage Safety**: All browser storage interactions route through safe `storeGet` and `storeSet` wrapper functions with `try/catch` guards to support privacy modes, restricted iframe contexts, or storage exceptions gracefully.
* **Themes**: Supports 4 high-contrast themes: **Dark** (default, key `"dark"`), **Light**, **Indigo Rose**, and **Electric Canary**. All text combinations pass WCAG 2.1 AA contrast requirements ($\ge 4.5:1$).
* **Reference Tooling**: `scripts/build_pcf_json.py` acts as a reference CLI parser used by automated test suites to ensure 100% parity across all 16 fields with the client-side JavaScript parser without writing bundled data to disk.

## Vendor Libraries

| Library | Version | Purpose | License | Location |
| :--- | :--- | :--- | :--- | :--- |
| **SheetJS (xlsx)** | 0.17.5 | Client-side in-browser `.xlsx` workbook parsing for workbook upload without server dependencies | Apache-2.0 | `vendor/xlsx.full.min.js` |

## Documentation

Project documentation and design reviews are housed in the [`docs/`](docs/) directory:
* [`docs/APQC_Healthcare_Provider_v721_vs_v611_Review.md`](docs/APQC_Healthcare_Provider_v721_vs_v611_Review.md): Detailed comparative review of APQC Healthcare Provider PCF v7.2.1 vs v6.1.1.
* [`docs/screenshots/`](docs/screenshots/): Comprehensive visual regression captures across desktop, tablet, text scaling levels, and theme palettes.

---

## Testing

### Prerequisites

* **Python 3.10+** (with virtual environment)
* **Node.js 18+** (for `scripts/test_shared_cases.js`)
* **Google Chrome / Chromium** (required for `scripts/verify_browser.py` headless browser E2E tests)
* **websocket-client** Python package (`pip install websocket-client`, required for Chrome DevTools Protocol automation)

### Setup Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

### One-Command Test Runner

To run all automated test suites sequentially:

```bash
./scripts/run_all_tests.sh
```

If Google Chrome or Chromium is not present on your system, `run_all_tests.sh` will print a clear warning, skip the browser E2E tests, and complete the Python and Node.js test suites without failing.

### Test Suites & Execution

#### 1. Data Integrity Suite (`scripts/verify_pcf.py`)
Validates the Python reference parser across all 6 reference workbooks against the expected counts fixture (`data/workbooks_expected.json`), asserting element counts, new/renamed metrics, definition counts, metric records, and category counts.

```bash
python3 scripts/verify_pcf.py
```

#### 2. Python Multi-Workbook Decoder & Parity Tests (`scripts/test_shared_cases.py`)
Tests Python workbook parsing logic against all six reference workbooks (Healthcare Provider, Retail, City Government, Health Insurance Payor, Cross-Industry v8.0, and Consumer Products v8.0), exercises edge cases (such as whole-token child changes and regex trailing `NEW` handling), verifies layout detection without filename dependency, tests actionable unknown layout errors, and asserts complete field-by-field equality between Python and JavaScript parsers across all elements and 16 properties (including metrics arrays).

```bash
python3 scripts/test_shared_cases.py
```

#### 3. Client-Side JavaScript Decoder Tests (`scripts/test_shared_cases.js`)
Validates client-side workbook decoding in JavaScript via Node.js using `vendor/xlsx.full.min.js`, testing all six reference workbooks, structure-based layout detection, actionable unknown layout error reporting, Category ID regex validation (`/^\d+$/`), comma preservation in previous names, and unit test strings.

```bash
node scripts/test_shared_cases.js
```

#### 4. End-to-End Headless Chrome Verification (`scripts/verify_browser.py`)
Performs automated browser tests over a local HTTP server (`port 8765`), utilizing modular test runners located in `scripts/browser_tests/`:
* `test_empty_start.py`: Clean empty startup verification, zero network calls for bundled data, state machine transitions (`Empty` -> `Loading` -> `Loaded`), actionable error dialogs on corrupt/unknown files from Empty and Loaded states (leaving previous state intact), screen hiding (0 definitions & 0 changes hides Matrix and Glossary tabs), and deep link fallback to Explorer.
* `test_data.py`: Dynamic header and attribution, Retail workbook upload, Close workbook action (`Loaded` -> `Empty`), and corrupt file handling.
* `test_layout.py`: Collapsible sidebar rail and inspector drawer with keyboard shortcuts (`[` and `]`), inspector reference details, squashed section height verification ($\ge$ summary height), view scrolling, and print stylesheet rules.
* `test_scaling.py`: Proportional text scaling at 85%, 100%, 115%, 130%, and 150%, confirming proportional row heights, indentations, and $\Delta$ bars without horizontal page overflow, plus Category 8 expand-all timing benchmarks.
* `test_storage.py`: Storage safety under restricted environments (confirms graceful fallback when `Storage.prototype.getItem` / `setItem` throw `SecurityError`).
* `test_escaping.py`: XSS injection prevention for element fields and Category ID security validation (rejects invalid category segments not matching `/^\d+$/` and verifies zero attribute injection in DOM templates).
* `test_themes.py`: Theme switching across Dark, Light, Indigo Rose, and Electric Canary, automated WCAG 2.1 AA contrast ratio tests, and visual screenshot generation in `docs/screenshots/`.
* `test_multi_workbook.py`: End-to-end browser upload of all six workbooks with parse timing benchmarks (~120–180ms), Family B Glossary verification (2,017 definitions in Cross-Industry and 2,019 in Consumer Products matching raw `Element Description`), benchmarking metrics inspector UI testing (presence when metrics exist, complete omission when none), Level 6 hierarchy indentation and dynamic `#level-filter` options, actionable error handling in upload dialog, and XSS sanitization across metric fields and descriptions.

```bash
python3 scripts/verify_browser.py
```

**Exit Codes:**
* `0`: All tests passed.
* `2`: Chrome or Chromium binary not found on PATH.
* `3`: `websocket-client` Python package not installed.
