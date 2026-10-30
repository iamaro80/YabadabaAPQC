#!/usr/bin/env python3
"""
YabadabaAPQC - Shared Test Cases for PCF Data Decoders (Python).
Tests all six APQC reference workbooks against expected standards,
verifies decode_changes edge cases, tests layout detection and errors,
and enforces full field-by-field parity with the JavaScript parser.
"""

import os
import sys
import json
import subprocess
import openpyxl
from build_pcf_json import (
    decode_changes,
    normalize_header,
    detect_layout,
    parse_pcf_workbook,
    VersionInfoStrategy,
    LAYOUT_PROFILES
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
FIXTURE_FILE = os.path.join(PROJECT_DIR, "data", "workbooks_expected.json")

def run_tests():
    print("=" * 70)
    print("RUNNING PYTHON WORKBOOK PARSER TEST SUITE (6 WORKBOOKS)")
    print("=" * 70)

    with open(FIXTURE_FILE, "r", encoding="utf-8") as f:
        expected_fixture = json.load(f)

    # 1. Testing All 6 Workbooks Against Fixture Table
    print("\n1. Testing All 6 Workbooks Against Fixture Table")
    parsed_py_workbooks = {}

    for key, exp in expected_fixture.items():
        file_path = os.path.join(PROJECT_DIR, exp["filename"])
        assert os.path.exists(file_path), f"File not found: {file_path}"

        print(f"\n• Testing {exp['name']} ({exp['filename']}):")
        
        # Parse workbook
        res = parse_pcf_workbook(file_path, filename=exp["filename"])
        parsed_py_workbooks[key] = res
        
        meta = res["metadata"]
        elems = res["elements"]

        print(f"  - Elements: {len(elems)} (Expected: {exp['elements']})")
        print(f"  - Layout Profile: {meta['source_layout']} (Expected: {exp['layout_profile']})")
        print(f"  - New Elements: {meta['total_new']} (Expected: {exp['new_count']})")
        print(f"  - Renamed Elements: {meta['total_renamed']} (Expected: {exp['renamed_count']})")
        print(f"  - With Changes: {meta['total_with_changes']} (Expected: {exp['with_changes']})")
        print(f"  - Metrics Available = Y: {meta['total_with_metrics']} (Expected: {exp['metrics_y']})")
        expected_defs = exp.get("definitions_non_empty", exp["definitions_count"])
        print(f"  - Definitions: {meta['definitions_count']} (Expected: {expected_defs})")
        print(f"  - Metric Rows: {meta['total_metric_records']} (Expected: {exp['metric_rows']})")

        assert len(elems) == exp["elements"], f"{exp['name']}: Elements count mismatch"
        assert meta["source_layout"] == exp["layout_profile"], f"{exp['name']}: Layout profile mismatch"
        assert meta["total_new"] == exp["new_count"], f"{exp['name']}: New count mismatch"
        assert meta["total_renamed"] == exp["renamed_count"], f"{exp['name']}: Renamed count mismatch"
        assert meta["total_with_changes"] == exp["with_changes"], f"{exp['name']}: Changes count mismatch"
        assert meta["total_with_metrics"] == exp["metrics_y"], f"{exp['name']}: Metrics Y count mismatch"
        assert meta["definitions_count"] == expected_defs, f"{exp['name']}: Definitions count mismatch"
        assert meta["total_metric_records"] == exp["metric_rows"], f"{exp['name']}: Metric rows mismatch"

        levels_present = sorted(list(set(e["level"] for e in elems)))
        assert levels_present == exp["levels"], f"{exp['name']}: Levels mismatch {levels_present} vs {exp['levels']}"

        if "level_6_count" in exp:
            l6_count = sum(1 for e in elems if e["level"] == 6)
            print(f"  - Level 6 Elements: {l6_count} (Expected: {exp['level_6_count']})")
            assert l6_count == exp["level_6_count"], f"{exp['name']}: Level 6 count mismatch"

        print(f"  ✓ {exp['name']} passed 100%.")

    # 2. Testing Layout Detection Without Filename (Renamed Copies)
    print("\n2. Testing Layout Detection (Structure-Based, No Filename Dependency)")
    for key, exp in expected_fixture.items():
        file_path = os.path.join(PROJECT_DIR, exp["filename"])
        res = parse_pcf_workbook(file_path, filename="random_dummy_filename_12345.xlsx")
        assert res["metadata"]["source_layout"] == exp["layout_profile"], (
            f"Structure-based layout detection failed for {exp['name']} under dummy filename."
        )
    print("  ✓ All 6 workbooks correctly detected with arbitrary filenames.")

    # 3. Testing Actionable Error on Unknown Layout
    print("\n3. Testing Actionable Error on Unknown Layout")
    # Test missing Combined
    try:
        detect_layout(["Sheet1", "Summary"], ["Col A", "Col B"])
        assert False, "Should have raised ValueError on missing Combined"
    except ValueError as e:
        msg = str(e)
        assert "Missing required worksheet: 'Combined'" in msg, f"Unexpected message: {msg}"
        print(f"  ✓ Caught missing Combined: '{msg}'")

    # Test unknown layout with Combined
    try:
        detect_layout(["Introduction", "Combined"], ["Col A", "Col B"])
        assert False, "Should have raised ValueError on unknown layout"
    except ValueError as e:
        msg = str(e)
        assert "Unknown workbook layout" in msg and "Expected either" in msg, f"Actionable error missing: {msg}"
        print("  ✓ Actionable layout error correctly reported:")
        print("    " + msg.replace("\n", "\n    "))

    # 4. Testing Introduction Sheet Parsing Across Families
    print("\n4. Testing Introduction Sheet Parsing Across Families")
    ci_path = os.path.join(PROJECT_DIR, expected_fixture["cross_industry"]["filename"])
    ci_wb = openpyxl.load_workbook(ci_path, read_only=True)
    ci_intro = VersionInfoStrategy.read(ci_wb, expected_fixture["cross_industry"]["filename"])
    print("  • Cross-Industry Intro:", ci_intro)
    assert ci_intro["version_label"] == "v8.0", f"Cross-Industry version mismatch: {ci_intro['version_label']}"
    assert ci_intro["compared_to"] == "v7.4", f"Cross-Industry compared_to mismatch: {ci_intro['compared_to']}"
    assert ci_intro["generated_on"] == "2/25/2026", f"Cross-Industry generated_on mismatch: {ci_intro['generated_on']}"
    assert ci_intro["copyright_year"] == 2026, f"Cross-Industry copyright mismatch: {ci_intro['copyright_year']}"

    cp_path = os.path.join(PROJECT_DIR, expected_fixture["consumer_products"]["filename"])
    cp_wb = openpyxl.load_workbook(cp_path, read_only=True)
    cp_intro = VersionInfoStrategy.read(cp_wb, expected_fixture["consumer_products"]["filename"])
    print("  • Consumer Products Intro:", cp_intro)
    assert cp_intro["version_label"] == "v8.0", f"Consumer Products version mismatch: {cp_intro['version_label']}"
    assert cp_intro["compared_to"] == "v7.2.1", f"Consumer Products compared_to mismatch: {cp_intro['compared_to']}"
    assert cp_intro["generated_on"] is None, f"Consumer Products generated_on mismatch: {cp_intro['generated_on']}"
    assert cp_intro["copyright_year"] == 2026, f"Consumer Products copyright mismatch: {cp_intro['copyright_year']}"
    print("  ✓ Introduction parsing verified.")

    # 5. Testing Header Normalization
    print("\n5. Testing Header Normalization")
    variations = ["Change Details", "Change details", " Change  Details? ", "CHANGE DETAILS?", "Change\nDetails\r\n"]
    for v in variations:
        norm = normalize_header(v)
        assert norm == "change details", f"Header norm mismatch for '{v}': '{norm}'"
    assert normalize_header("Metric ID\r\n") == "metric id", "Metric ID newline strip failed"
    print("  ✓ All header normalization variations verified.")

    # 6. Testing decode_changes Unit Test Edge Cases
    print("\n6. Testing decode_changes Unit Test Edge Cases")
    edge_cases = [
        (
            "-10381, c10383, RENAME, WAS:Foo-123, NEW",
            {"added": [], "removed": ["10381"], "changed": ["10383"], "was": "Foo-123", "is_new": True, "is_renamed": True}
        ),
        (
            "WAS:Foo , new",
            {"added": [], "removed": [], "changed": [], "was": "Foo", "is_new": True, "is_renamed": True}
        ),
        (
            "+1, +2",
            {"added": ["1", "2"], "removed": [], "changed": [], "was": "", "is_new": False, "is_renamed": False}
        )
    ]
    for raw, exp in edge_cases:
        res = decode_changes(raw)
        assert res["added_children"] == exp["added"], f"added mismatch on '{raw}': {res['added_children']}"
        assert res["removed_children"] == exp["removed"], f"removed mismatch on '{raw}': {res['removed_children']}"
        assert res["changed_children"] == exp["changed"], f"changed mismatch on '{raw}': {res['changed_children']}"
        assert res["renamed_was"] == exp["was"], f"renamed_was mismatch on '{raw}': {res['renamed_was']}"
        assert res["is_new"] == exp["is_new"], f"is_new mismatch on '{raw}': {res['is_new']}"
        assert res["is_renamed"] == exp["is_renamed"], f"is_renamed mismatch on '{raw}': {res['is_renamed']}"

    # Real WAS samples with commas from all 6 workbooks
    for key, exp in expected_fixture.items():
        sample = exp["was_sample_with_commas"]
        res = decode_changes(sample["raw"])
        assert res["renamed_was"] == sample["expected_was"], (
            f"decode_changes failed on {key} comma sample:\n"
            f"  got:      '{res['renamed_was']}'\n"
            f"  expected: '{sample['expected_was']}'"
        )
        print(f"  ✓ Sample from {exp['name']} passed: '{res['renamed_was'][:45]}...'")
    print("  ✓ All decode_changes unit test edge cases passed.")

    # 7. Parity Test Between Python Pipeline and JS Parser across All 6 Workbooks
    print("\n7. Testing Parity Between Python Pipeline and JS Parser Across All 6 Workbooks")
    js_test_path = os.path.join(SCRIPT_DIR, "test_shared_cases.js")
    dump_file = os.path.join(PROJECT_DIR, "data", ".parity_dump.json")

    fields_to_check = [
        "id", "hierarchy_id", "name", "level", "level_name", "category_id",
        "parent_hierarchy_id", "process_type", "is_new", "is_renamed",
        "renamed_was", "added_children", "removed_children", "changed_children",
        "definition", "metrics"
    ]

    for key, exp in expected_fixture.items():
        try:
            subprocess.run(
                ["node", js_test_path, "--dump-json", key, dump_file],
                capture_output=True,
                text=True,
                check=True
            )
            with open(dump_file, "r", encoding="utf-8") as f:
                js_data = json.load(f)
        finally:
            if os.path.exists(dump_file):
                os.remove(dump_file)

        py_res = parsed_py_workbooks[key]
        py_elems = py_res["elements"]
        js_elems = js_data["elements"]

        assert len(py_elems) == len(js_elems), (
            f"{exp['name']} count mismatch: Python={len(py_elems)} vs JS={len(js_elems)}"
        )
        assert py_res["metadata"]["source_layout"] == js_data["metadata"]["source_layout"], (
            f"{exp['name']} layout mismatch: Python={py_res['metadata']['source_layout']} vs JS={js_data['metadata']['source_layout']}"
        )
        assert py_res["metadata"]["total_metric_records"] == js_data["metadata"]["total_metric_records"], (
            f"{exp['name']} metric records mismatch"
        )

        for idx, (pe, je) in enumerate(zip(py_elems, js_elems)):
            for f in fields_to_check:
                assert pe[f] == je[f], (
                    f"{exp['name']} element [{idx}] (HID {pe.get('hierarchy_id')}) field '{f}' mismatch:\n"
                    f"  Python: {pe[f]!r}\n"
                    f"  JS:     {je[f]!r}"
                )

        print(f"  ✓ {exp['name']} parity: All {len(py_elems)} elements match 100% across all 16 fields (including metrics).")

    print("\n" + "=" * 70)
    print("ALL PYTHON WORKBOOK PARSER AND PARITY TESTS PASSED 100%")
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
