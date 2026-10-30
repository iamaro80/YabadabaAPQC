#!/usr/bin/env python3
"""
YabadabaAPQC - Shared Test Cases for PCF Data Decoders (Python).
Tests both Healthcare Provider and Retail reference workbooks against expected standards,
verifies decode_changes edge cases, and enforces full field-by-field parity with JS parser.
"""

import os
import sys
import json
import subprocess
import pandas as pd
from build_pcf_json import decode_changes, parse_pcf_workbook

HC_FILE = "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx"
RETAIL_FILE = "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx"

def run_tests():
    print("=" * 70)
    print("RUNNING SHARED PCF TEST SUITE (HEALTHCARE & RETAIL)")
    print("=" * 70)

    # 1. Testing Healthcare Provider Workbook
    print(f"\n1. Testing Healthcare Workbook: {HC_FILE}")
    assert os.path.exists(HC_FILE), f"Missing {HC_FILE}"
    hc_result = parse_pcf_workbook(HC_FILE, operating_categories={"1", "2", "3", "4", "5"})
    hc_elements = hc_result["elements"]

    hc_new = sum(1 for e in hc_elements if e["is_new"])
    hc_renamed = sum(1 for e in hc_elements if e["is_renamed"])
    hc_metrics = sum(1 for e in hc_elements if e["metrics_available"])
    hc_with_def = sum(1 for e in hc_elements if e["definition"] and e["definition"].strip())
    hc_without_def = sum(1 for e in hc_elements if not (e["definition"] and e["definition"].strip()))

    print(f"  • Elements: {len(hc_elements)} (Expected: 1,985)")
    print(f"  • New: {hc_new} (Expected: 960)")
    print(f"  • Renamed: {hc_renamed} (Expected: 134)")
    print(f"  • Metrics: {hc_metrics} (Expected: 221)")
    print(f"  • Definitions: {hc_with_def} (Expected: 1,931)")
    print(f"  • Without definition: {hc_without_def} (Expected: 54)")

    assert len(hc_elements) == 1985
    assert hc_new == 960
    assert hc_renamed == 134
    assert hc_metrics == 221
    assert hc_with_def == 1931
    assert hc_without_def == 54
    print("✓ Healthcare test cases passed 100%.")

    # 2. Testing Retail Workbook
    print(f"\n2. Testing Retail Workbook: {RETAIL_FILE}")
    assert os.path.exists(RETAIL_FILE), f"Missing {RETAIL_FILE}"
    ret_result = parse_pcf_workbook(RETAIL_FILE, operating_categories={"1", "2", "3", "4", "5", "6"})
    ret_elements = ret_result["elements"]

    ret_new = sum(1 for e in ret_elements if e["is_new"])
    ret_renamed = sum(1 for e in ret_elements if e["is_renamed"])
    ret_metrics = sum(1 for e in ret_elements if e["metrics_available"])
    ret_with_def = sum(1 for e in ret_elements if e["definition"] and e["definition"].strip())
    ret_without_def = sum(1 for e in ret_elements if not (e["definition"] and e["definition"].strip()))
    ret_renames_with_commas = [e for e in ret_elements if e["is_renamed"] and "," in e["renamed_was"]]

    print(f"  • Elements: {len(ret_elements)} (Expected: 1,708)")
    print(f"  • New: {ret_new} (Expected: 608)")
    print(f"  • Renamed: {ret_renamed} (Expected: 74)")
    print(f"  • Metrics: {ret_metrics} (Expected: 180)")
    print(f"  • Non-empty definitions: {ret_with_def} (Expected: 1,462, from 1,463 matched minus 1 empty cell at PID 10407)")
    print(f"  • Without definition: {ret_without_def} (Expected: 246)")
    print(f"  • Renames containing commas: {len(ret_renames_with_commas)} (Expected: 9)")

    assert len(ret_elements) == 1708
    assert ret_new == 608
    assert ret_renamed == 74
    assert ret_metrics == 180
    assert ret_with_def == 1462
    assert ret_without_def == 246
    assert len(ret_renames_with_commas) == 9
    print("✓ Retail test cases passed 100%.")

    # 3. Unit test cases for decode_changes
    print("\n3. Testing decode_changes Edge Cases")
    case1 = decode_changes("-10381, c10383, RENAME, WAS:Foo-123, NEW")
    assert case1["is_new"] is True, f"case1 is_new expected True, got {case1['is_new']}"
    assert case1["is_renamed"] is True, f"case1 is_renamed expected True, got {case1['is_renamed']}"
    assert case1["renamed_was"] == "Foo-123", f"case1 renamed_was expected 'Foo-123', got '{case1['renamed_was']}'"
    assert case1["removed_children"] == ["10381"], f"case1 removed_children expected ['10381'], got {case1['removed_children']}"
    assert case1["changed_children"] == ["10383"], f"case1 changed_children expected ['10383'], got {case1['changed_children']}"
    assert case1["added_children"] == [], f"case1 added_children expected [], got {case1['added_children']}"
    print("  ✓ Case 1 '-10381, c10383, RENAME, WAS:Foo-123, NEW': passed")

    case2 = decode_changes("WAS:Foo , new")
    assert case2["is_new"] is True, f"case2 is_new expected True, got {case2['is_new']}"
    assert case2["is_renamed"] is True, f"case2 is_renamed expected True, got {case2['is_renamed']}"
    assert case2["renamed_was"] == "Foo", f"case2 renamed_was expected 'Foo', got '{case2['renamed_was']}'"
    assert case2["added_children"] == [] and case2["removed_children"] == [] and case2["changed_children"] == []
    print("  ✓ Case 2 'WAS:Foo , new': passed")

    case3 = decode_changes("+1, +2")
    assert case3["is_new"] is False, f"case3 is_new expected False, got {case3['is_new']}"
    assert case3["is_renamed"] is False, f"case3 is_renamed expected False, got {case3['is_renamed']}"
    assert case3["renamed_was"] == "", f"case3 renamed_was expected empty, got '{case3['renamed_was']}'"
    assert case3["added_children"] == ["1", "2"], f"case3 added_children expected ['1', '2'], got {case3['added_children']}"
    print("  ✓ Case 3 '+1, +2': passed")

    # 4. Parity test between Python and JavaScript parsers
    print("\n4. Testing Parity Between Python Pipeline and JS Parser")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_test_path = os.path.join(script_dir, "test_shared_cases.js")
    dump_file = os.path.join(script_dir, "../data/.parity_dump.json")

    try:
        subprocess.run(
            ["node", js_test_path, "--dump-json", dump_file],
            capture_output=True,
            text=True,
            check=True
        )
        with open(dump_file, "r", encoding="utf-8") as f:
            js_data = json.load(f)
    finally:
        if os.path.exists(dump_file):
            os.remove(dump_file)

    js_hc_elements = js_data["healthcare"]
    js_ret_elements = js_data["retail"]

    fields_to_check = [
        "id", "hierarchy_id", "name", "level", "level_name", "category_id",
        "parent_hierarchy_id", "process_type", "is_new", "is_renamed",
        "renamed_was", "added_children", "removed_children", "changed_children",
        "definition"
    ]

    # Check Healthcare parity
    assert len(hc_elements) == len(js_hc_elements), (
        f"Healthcare count mismatch: Python={len(hc_elements)} vs JS={len(js_hc_elements)}"
    )
    for idx, (py_elem, js_elem) in enumerate(zip(hc_elements, js_hc_elements)):
        for f in fields_to_check:
            assert py_elem[f] == js_elem[f], (
                f"Healthcare element [{idx}] (HID {py_elem.get('hierarchy_id')}) field '{f}' mismatch:\n"
                f"  Python: {py_elem[f]!r}\n"
                f"  JS:     {js_elem[f]!r}"
            )
    print(f"  ✓ Healthcare parity: All {len(hc_elements)} elements match 100% across all 15 fields.")

    # Check Retail parity
    assert len(ret_elements) == len(js_ret_elements), (
        f"Retail count mismatch: Python={len(ret_elements)} vs JS={len(js_ret_elements)}"
    )
    for idx, (py_elem, js_elem) in enumerate(zip(ret_elements, js_ret_elements)):
        for f in fields_to_check:
            assert py_elem[f] == js_elem[f], (
                f"Retail element [{idx}] (HID {py_elem.get('hierarchy_id')}) field '{f}' mismatch:\n"
                f"  Python: {py_elem[f]!r}\n"
                f"  JS:     {js_elem[f]!r}"
            )
    print(f"  ✓ Retail parity: All {len(ret_elements)} elements match 100% across all 15 fields.")

    print("\n" + "=" * 70)
    print("ALL SHARED TEST CASES AND PARITY CHECKS PASSED SUCCESSFULLY")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(1)
