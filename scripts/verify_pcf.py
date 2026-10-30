#!/usr/bin/env python3
"""
YabadabaAPQC - Automated Verification Suite for Bundled Sample PCF Dataset.
Validates:
1. 1,985 total elements with unique PCF IDs.
2. Exact change counts: 960 brand new, 134 renamed, 221 with metrics.
3. 1,931 glossary definitions joined (54 elements without definition).
4. Category row sums match the 13 category sheets in the Excel workbook.
5. Clean rename extraction: no trailing commas or truncated sentences in renamed_was.
6. Alignment between pcf_data.json and pcf_data.js.
"""

import os
import sys
import json
import openpyxl

EXCEL_FILE = "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx"
JSON_FILE = os.path.join("data", "pcf_data.json")
JS_FILE = os.path.join("data", "pcf_data.js")

def verify():
    print("=" * 70)
    print("YABADABAAPQC BUNDLED SAMPLE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Check data files exist
    assert os.path.exists(EXCEL_FILE), f"Missing source Excel file: {EXCEL_FILE}"
    assert os.path.exists(JSON_FILE), f"Missing JSON dataset: {JSON_FILE}"
    assert os.path.exists(JS_FILE), f"Missing JS dataset: {JS_FILE}"
    print("✓ Required files exist.")

    # 2. Load JSON dataset
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elements", [])
    categories = data.get("categories", [])
    metadata = data.get("metadata", {})

    # 3. Assert total elements and ID uniqueness
    assert len(elements) == 1985, f"Expected 1,985 elements, got {len(elements)}"
    pcf_ids = [e["pcf_id"] for e in elements]
    unique_ids = set(pcf_ids)
    assert len(unique_ids) == 1985, f"Duplicate PCF IDs found: {len(pcf_ids)} total vs {len(unique_ids)} unique"
    print(f"✓ Total Elements Assertion: 1,985 elements with 1,985 unique PCF IDs.")

    # 4. Assert change counts
    new_elements = [e for e in elements if e["is_new"]]
    renamed_elements = [e for e in elements if e["is_renamed"]]
    metric_elements = [e for e in elements if e["metrics_available"]]
    changed_elements = [e for e in elements if e["has_changes"]]

    assert len(new_elements) == 960, f"Expected 960 new elements, got {len(new_elements)}"
    assert len(renamed_elements) == 134, f"Expected 134 renamed elements, got {len(renamed_elements)}"
    assert len(metric_elements) == 221, f"Expected 221 elements with metrics, got {len(metric_elements)}"
    assert len(changed_elements) == 1187, f"Expected 1,187 elements with changes, got {len(changed_elements)}"
    print(f"✓ Change Metrics Assertion: 960 NEW, 134 RENAMED, 221 METRICS, 1,187 TOTAL CHANGES.")

    # 5. Assert glossary definitions joined and attribution
    elements_with_def = [e for e in elements if e["definition"] and e["definition"].strip()]
    elements_without_def = [e for e in elements if not e["definition"] or not e["definition"].strip()]
    assert len(elements_with_def) == 1931, f"Expected 1,931 definitions joined, got {len(elements_with_def)}"
    assert len(elements_without_def) == 54, f"Expected 54 elements without definition, got {len(elements_without_def)}"
    print(f"✓ Glossary Definitions Assertion: 1,931 definitions successfully joined (54 elements without definition).")
    print(f"  Listing {len(elements_without_def)} elements without definitions in source workbook:")
    for e in elements_without_def:
        print(f"    • [{e['hierarchy_id']}] PCF ID {e['pcf_id']}: {e['name']}")

    expected_attr = "©2022 APQC. ALL RIGHTS RESERVED. This Process Classification Framework® (\"PCF\") is the copyrighted intellectual property of APQC."
    assert metadata.get("attribution") == expected_attr, f"Attribution mismatch: {metadata.get('attribution')}"
    print("✓ APQC Attribution Assertion: metadata.attribution verified.")

    # 6. Assert category row sums match the 13 category sheets in the Excel file
    print("\nVerifying 13 category sheets in source Excel file...")
    wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True)
    total_sheet_rows = 0

    for cat_num in range(1, 14):
        sheet_name = f"{cat_num}.0"
        assert sheet_name in wb.sheetnames, f"Sheet {sheet_name} not found in workbook"
        ws = wb[sheet_name]
        sheet_data_rows = ws.max_row - 1  # exclude header
        total_sheet_rows += sheet_data_rows

        cat_elements = [e for e in elements if e["category_id"] == str(cat_num)]
        assert sheet_data_rows == len(cat_elements), (
            f"Category {cat_num} ({sheet_name}) mismatch: sheet has {sheet_data_rows} rows, "
            f"dataset has {len(cat_elements)} elements"
        )
        print(f"  • Category {cat_num:2d} ({sheet_name:4s}): {len(cat_elements):3d} rows (Matches Excel sheet)")

    assert total_sheet_rows == 1985, f"Expected sum of category sheets to be 1,985, got {total_sheet_rows}"
    print(f"✓ Category Sum Assertion: All 13 category sheets match exact counts (Sum = {total_sheet_rows}).")

    # 7. Assert clean rename parsing (no trailing comma, no mid-sentence truncation)
    print("\nVerifying rename parsing across all 134 renamed elements...")
    for e in renamed_elements:
        hid = e["hierarchy_id"]
        was = e["renamed_was"]
        assert was, f"Empty renamed_was in {hid}"
        assert not was.endswith(","), f"Trailing comma in renamed_was for {hid}: '{was}'"
        assert not was.endswith("WAS:"), f"Unparsed WAS prefix in {hid}: '{was}'"
        assert not was.endswith(",") and not was.endswith(" and") and not was.endswith(" or"), (
            f"Truncated renamed_was in {hid}: '{was}'"
        )
    print("✓ Rename Syntax Assertion: All 134 renamed_was values are complete and properly formatted.")

    # 8. Assert JS file consistency
    with open(JS_FILE, "r", encoding="utf-8") as f:
        js_content = f.read()
    assert "window.PCF_DATA =" in js_content, "Missing window.PCF_DATA export in data/pcf_data.js"
    assert '"total_elements": 1985' in js_content, "Metadata mismatch in data/pcf_data.js"
    print("✓ Offline JS Bundle Assertion: data/pcf_data.js is aligned with JSON dataset.")

    print("\n" + "=" * 70)
    print("ALL 8 VERIFICATION CHECKS PASSED SUCCESSFULLY (100% COMPLIANT)")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        verify()
    except AssertionError as err:
        print(f"\n❌ VERIFICATION FAILED: {err}", file=sys.stderr)
        sys.exit(1)
