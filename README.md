# YabadabaAPQC

Interactive, zero-dependency offline Single Page Application (SPA) for exploring, searching, and analyzing any APQC Process Classification Framework® (PCF) workbook, whether cross-industry or industry-specific.

## Sample Data

The application bundles the APQC Healthcare Provider PCF (v7.2.1 vs v6.1.1) as an out-of-the-box demonstration dataset. Users can upload any standard APQC PCF Excel workbook (`.xlsx`) via the upload dialog or drag-and-drop. Clicking **Back to sample data** restores the bundled Healthcare Provider reference dataset.

## Independent Tool Disclaimer

> **YabadabaAPQC is an independent tool. It is not affiliated with or endorsed by APQC.**  
> Process Classification Framework® and PCF® are registered trademarks of APQC.

## Architecture & Single Source of Truth

* **`index.html` is the single source of truth** for the application markup, styles, and client-side logic. All UI enhancements, inspector layouts, event delegations, and storage safety routines are implemented directly in `index.html`.
* **Zero external network dependencies**: Works entirely offline, including over the `file://` protocol or any local static HTTP server.
* **Storage Safety**: All browser storage interactions route through safe `storeGet` and `storeSet` wrapper functions with `try/catch` guards to support privacy modes, restricted iframe contexts, or storage exceptions gracefully.
* **Cache & Temporary Files**: A `.gitignore` file excludes Python `__pycache__/`, virtual environments, OS metadata (`.DS_Store`), and LibreOffice/Excel lock files (`.~lock.*`).

## Vendor Libraries

| Library | Version | Purpose | License | Location |
| :--- | :--- | :--- | :--- | :--- |
| **SheetJS (xlsx)** | 0.17.5 | Client-side in-browser `.xlsx` workbook parsing for workbook upload without server dependencies | Apache-2.0 | `vendor/xlsx.full.min.js` |

## Copyright & Attribution

> **©2022 APQC. ALL RIGHTS RESERVED.**  
> This Process Classification Framework® ("PCF") is the copyrighted intellectual property of APQC.

---

## Testing

### Prerequisites

* **Python 3.10+** (with virtual environment)
* **Node.js 18+** (for `scripts/test_shared_cases.js`)
* **Google Chrome** (for `scripts/verify_browser.py` headless browser E2E tests)

### Setup Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

### Test Scripts & Execution

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

#### 2. Python Workbook Decoder Tests (`scripts/test_shared_cases.py`)
Tests Python workbook parsing logic against both Healthcare and Retail reference workbooks.

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
======================================================================
ALL PYTHON WORKBOOK PARSER TESTS PASSED 100%
======================================================================
```

#### 3. Client-Side JavaScript Decoder Tests (`scripts/test_shared_cases.js`)
Validates client-side workbook decoding in JavaScript via Node.js using `vendor/xlsx.full.min.js`, testing Healthcare, Retail, and corrupted workbook rejection.

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

3. Testing Deliberately Broken Workbook validation
  • Correctly caught error: "Missing required worksheet: 'Combined'"
======================================================================
ALL JAVASCRIPT WORKBOOK PARSER TESTS PASSED 100%
======================================================================
```

#### 4. End-to-End Headless Chrome Verification (`scripts/verify_browser.py`)
Performs automated browser tests over a local HTTP server (`port 8765`), validating:
* Data integrity and attribution
* Collapsible rail and inspector drawer with keyboard shortcuts (`[` and `]`)
* Inspector reference entry, key terms, children, siblings, and cross-cutting related items
* Squashed sections fix: asserts every `.ref-section` height $\ge$ summary row height
* Escaping and event delegation: uploads workbook with `'`, `"`, `<script>`, `\` in PCF ID and name, ensuring zero code execution and proper text rendering
* Storage safety: verifies error-free operation when `Storage.prototype.getItem` throws
* Text size scaling at 85%, 100%, 115%, 130%, and 150%, confirming proportional row heights, indentations, and $\Delta$ bars without horizontal overflow
* Screenshots saved to `docs/screenshots/`

```bash
python3 scripts/verify_browser.py
```
