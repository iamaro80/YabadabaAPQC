# YabadabaAPQC

Interactive, zero-dependency offline Single Page Application (SPA) for exploring, searching, and analyzing any APQC Process Classification Framework® (PCF) workbook, whether cross-industry or industry-specific.

## Sample Data

The application bundles the APQC Healthcare Provider PCF (v7.2.1 vs v6.1.1) as an out-of-the-box demonstration dataset. Users can upload any standard APQC PCF Excel workbook (`.xlsx`) via the upload dialog or drag-and-drop. Clicking **Back to sample data** restores the bundled Healthcare Provider reference dataset.

## Independent Tool Disclaimer

> **YabadabaAPQC is an independent tool. It is not affiliated with or endorsed by APQC.**  
> Process Classification Framework® and PCF® are registered trademarks of APQC.

## Architecture & Single Source of Truth

* **`index.html` is the single source of truth** for the application markup, styles, and client-side logic. All UI components, inspector layouts, event delegations, keyboard shortcuts, and storage safety routines are implemented directly in `index.html`.
* **Script Table of Contents**: The primary `<script>` block in `index.html` is organized into 18 well-defined sections:
  1. State Management & Constants
  2. Safe Local Storage Utilities
  3. Text Scaling Management
  4. Theme System & Color Scheme Management
  5. HTML Escaping & Formatting Utilities
  6. Data Initialization & Sample Loading
  7. Process Type & Hierarchy Helpers
  8. Change Decoding & Analysis
  9. Tree Navigation & Node Rendering
  10. Change Table (Matrix) View
  11. Analytics & Visualizations
  12. Glossary Terms & Search
  13. Inspector Drawer & Deep Metadata
  14. Global Search & Autocomplete
  15. Layout Panels & View Switching
  16. Keyboard Shortcuts & A11y
  17. Excel Workbook Parser (SheetJS integration)
  18. Application Bootstrap & Event Delegation
* **Zero external network dependencies**: Works entirely offline, including over the `file://` protocol or any local static HTTP server.
* **Storage Safety**: All browser storage interactions route through safe `storeGet` and `storeSet` wrapper functions with `try/catch` guards to support privacy modes, restricted iframe contexts, or storage exceptions gracefully.
* **Themes**: Supports 4 high-contrast themes: **Dark** (default, key `"dark"`), **Light**, **Indigo Rose**, and **Electric Canary**. All text combinations pass WCAG 2.1 AA contrast requirements ($\ge 4.5:1$).
* **Dual Data Formats (`data/pcf_data.js` & `data/pcf_data.json`)**:
  * **`data/pcf_data.js`**: Exposes `window.PCF_DATA = { ... }`, enabling instant out-of-the-box offline exploration over `file://` URLs where browser CORS restrictions prevent `fetch()` from reading local `.json` files.
  * **`data/pcf_data.json`**: Provides standard, clean JSON for headless pipelines, automated verification tools (`verify_pcf.py`), API clients, and data pipelines.
  * Both files are generated synchronously from the source workbook using `scripts/build_pcf_json.py` and strictly validated by `scripts/verify_pcf.py`.

## Vendor Libraries

| Library | Version | Purpose | License | Location |
| :--- | :--- | :--- | :--- | :--- |
| **SheetJS (xlsx)** | 0.17.5 | Client-side in-browser `.xlsx` workbook parsing for workbook upload without server dependencies | Apache-2.0 | `vendor/xlsx.full.min.js` |

## Documentation

Project documentation and design reviews are housed in the [`docs/`](docs/) directory:
* [`docs/APQC_Healthcare_Provider_v721_vs_v611_Review.md`](docs/APQC_Healthcare_Provider_v721_vs_v611_Review.md): Detailed comparative review of APQC Healthcare Provider PCF v7.2.1 vs v6.1.1.
* [`docs/screenshots/`](docs/screenshots/): Comprehensive visual regression captures across desktop, tablet, text scaling levels, and theme palettes.

## Copyright & Attribution

> **©2022 APQC. ALL RIGHTS RESERVED.**  
> This Process Classification Framework® ("PCF") is the copyrighted intellectual property of APQC.

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
Validates that the generated Healthcare JS bundle (`data/pcf_data.js`) exactly matches the source Excel workbook (`K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx`), verifying all 13 category counts, renames, definitions, and APQC attribution.

```bash
python3 scripts/verify_pcf.py
```

**Expected Output:**
```text
======================================================================
APQC HEALTHCARE PCF AUTOMATED VERIFICATION SUITE
======================================================================
✓ Required files exist.
✓ Total Elements Assertion: 1,985 elements with 1,985 unique PCF IDs.
✓ Change Metrics Assertion: 960 NEW, 134 RENAMED, 221 METRICS, 1,187 TOTAL CHANGES.
✓ Glossary Definitions Assertion: 1,931 definitions successfully joined (54 elements without definition).
...
✓ Category Sum Assertion: All 13 category sheets match exact counts (Sum = 1985).
✓ Rename Syntax Assertion: All 134 renamed_was values are complete and properly formatted.
✓ Offline JS Bundle Assertion: data/pcf_data.js is aligned with JSON dataset.
======================================================================
ALL 8 VERIFICATION CHECKS PASSED SUCCESSFULLY (100% COMPLIANT)
======================================================================
```

#### 2. Python Workbook Decoder & Parity Tests (`scripts/test_shared_cases.py`)
Tests Python workbook parsing logic against both Healthcare and Retail reference workbooks, exercises edge cases (such as whole-token child changes and regex trailing `NEW` handling), and asserts field-by-field equality between Python and JavaScript parsers across all elements and properties.

```bash
python3 scripts/test_shared_cases.py
```

**Expected Output:**
```text
======================================================================
RUNNING PYTHON WORKBOOK PARSER TEST SUITE
======================================================================
1. Testing Healthcare Workbook: K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx
  • Elements: 1985 (Expected: 1,985)
  • New: 960 (Expected: 960)
  • Renamed: 134 (Expected: 134)
  • Metrics: 221 (Expected: 221)
  • Definitions: 1931 (Expected: 1,931)
✓ Python Healthcare test passed 100%.

2. Testing Retail Workbook: K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx
  • Elements: 1708 (Expected: 1,708)
  • New: 608 (Expected: 608)
  • Renamed: 74 (Expected: 74)
  • Metrics: 180 (Expected: 180)
  • Definitions: 1462 (Expected: 1,462)
✓ Python Retail test passed 100%.

3. Testing decode_changes Unit Test Edge Cases
  • Case 1 (-10381, c10383, RENAME, WAS:Foo-123, NEW):
    - Added: [] (Expected: [])
    - Removed: ['10381'] (Expected: ['10381'])
    - Changed: ['10383'] (Expected: ['10383'])
    - Renamed Was: 'Foo-123' (Expected: 'Foo-123')
    - Is Renamed: True, Is New: False
  • Case 2 (WAS:Foo , new):
    - Renamed Was: 'Foo' (Expected: 'Foo')
    - Is Renamed: True, Is New: False
  • Case 3 (+1, +2):
    - Added: ['1', '2'] (Expected: ['1', '2'])
✓ decode_changes unit tests passed 100%.

4. Testing Python vs JavaScript Parser Parity
  • Healthcare dataset: 1985 elements compared field-by-field.
  • Retail dataset: 1708 elements compared field-by-field.
✓ Full Python vs JavaScript parser parity verified!
======================================================================
ALL PYTHON WORKBOOK PARSER TESTS PASSED 100%
======================================================================
```

#### 3. Client-Side JavaScript Decoder Tests (`scripts/test_shared_cases.js`)
Validates client-side workbook decoding in JavaScript via Node.js using `vendor/xlsx.full.min.js`, testing Healthcare, Retail, corrupted workbook rejection, Category ID regex validation (`/^\d+$/`), and unit test strings.

```bash
node scripts/test_shared_cases.js
```

**Expected Output:**
```text
======================================================================
RUNNING JAVASCRIPT WORKBOOK PARSER TEST SUITE
======================================================================
1. Testing Healthcare Workbook: K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx
  • Elements: 1985 (Expected: 1,985)
  • New: 960 (Expected: 960)
  • Renamed: 134 (Expected: 134)
  • Metrics: 221 (Expected: 221)
  • Definitions: 1931 (Expected: 1,931)
✓ JavaScript Healthcare test passed 100%.

2. Testing Retail Workbook: K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx
  • Elements: 1708 (Expected: 1,708)
  • New: 608 (Expected: 608)
  • Renamed: 74 (Expected: 74)
  • Metrics: 180 (Expected: 180)
  • Definitions: 1462 (Expected: 1,462)
  • Renames containing commas: 9 (Expected: 9)
  • Retail 4.0 name: "Merchandise Products and Services", definition: "(Empty, as expected)"
  • Operating split: Category 6.0 is "Operating Processes", Category 7.0 is "Management & Support Services"
✓ JavaScript Retail test passed 100%.

3. Testing decodeChanges Unit Test Edge Cases
  • Case 1 (-10381, c10383, RENAME, WAS:Foo-123, NEW):
    - Added: [] (Expected: [])
    - Removed: ["10381"] (Expected: ["10381"])
    - Changed: ["10383"] (Expected: ["10383"])
    - Renamed Was: "Foo-123" (Expected: "Foo-123")
    - Is Renamed: true, Is New: false
  • Case 2 (WAS:Foo , new):
    - Renamed Was: "Foo" (Expected: "Foo")
    - Is Renamed: true, Is New: false
  • Case 3 (+1, +2):
    - Added: ["1","2"] (Expected: ["1","2"])
✓ decodeChanges unit tests passed 100%.

4. Testing Deliberately Broken Workbook validation
  • Correctly caught error: "Missing required worksheet: 'Combined'"
======================================================================
ALL JAVASCRIPT WORKBOOK PARSER TESTS PASSED 100%
======================================================================
```

#### 4. End-to-End Headless Chrome Verification (`scripts/verify_browser.py`)
Performs automated browser tests over a local HTTP server (`port 8765`), utilizing modular test runners located in `scripts/browser_tests/`:
* `test_data.py`: Data integrity, brand elements, attribution, Retail workbook upload and recovery
* `test_layout.py`: Collapsible sidebar rail and inspector drawer with keyboard shortcuts (`[` and `]`), inspector reference details, squashed section height verification ($\ge$ summary height), view scrolling, and print stylesheet rules
* `test_scaling.py`: Proportional text scaling at 85%, 100%, 115%, 130%, and 150%, confirming proportional row heights, indentations, and $\Delta$ bars without horizontal page overflow, plus Category 8 expand-all timing benchmarks
* `test_storage.py`: Storage safety under restricted environments (confirms graceful fallback when `Storage.prototype.getItem` / `setItem` throw `SecurityError`)
* `test_escaping.py`: XSS injection prevention for element fields and Category ID security validation (rejects invalid category segments not matching `/^\d+$/` and verifies zero attribute injection in DOM templates)
* `test_themes.py`: Theme switching across Dark, Light, Indigo Rose, and Electric Canary, automated WCAG 2.1 AA contrast ratio tests, and visual screenshot generation in `docs/screenshots/`

```bash
python3 scripts/verify_browser.py
```

**Exit Codes:**
* `0`: All tests passed.
* `2`: Chrome or Chromium binary not found on PATH.
* `3`: `websocket-client` Python package not installed.
