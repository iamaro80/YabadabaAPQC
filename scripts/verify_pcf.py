#!/usr/bin/env python3
"""
YabadabaAPQC - Python PCF Parser Verification Suite.
Validates the Python reference parser (`scripts/build_pcf_json.py`) against all 6
reference APQC workbooks using `data/workbooks_expected.json`.

Validates:
1. Total elements and uniqueness of PCF IDs & Hierarchy IDs across all 6 workbooks.
2. Layout detection profile correctness (family-a-2023 vs family-b-2026).
3. Exact change counts: with_changes, new_elements, renamed_elements.
4. Metrics counts: Metrics flag = Y, and Metrics sheet records (Family B).
5. Definitions count (Glossary sheet for Family A, inline Element Description for Family B).
6. Hierarchy depth validation (Levels 1-5 for standard, Level 6 for Payor).
7. Clean rename parsing with comma support (WAS: ...).
8. Introduction metadata parsing (title, version, compared_to, copyright attribution).
"""

import os
import sys
import json
import time

# Add scripts directory to path to import build_pcf_json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pcf_json import parse_pcf_workbook

EXPECTED_FIXTURE = os.path.join(os.path.dirname(__file__), "..", "data", "workbooks_expected.json")

def verify_all_workbooks():
    print("=" * 70)
    print("YABADABAAPQC PYTHON PARSER MULTI-WORKBOOK VERIFICATION SUITE")
    print("=" * 70)

    if not os.path.exists(EXPECTED_FIXTURE):
        raise FileNotFoundError(f"Missing expected fixture: {EXPECTED_FIXTURE}")

    with open(EXPECTED_FIXTURE, "r", encoding="utf-8") as f:
        expected_data = json.load(f)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    passed_count = 0
    total_count = len(expected_data)

    for key, exp in expected_data.items():
        wb_name = exp["name"]
        filename = exp["filename"]
        wb_path = os.path.join(project_root, filename)

        print(f"\n• Verifying {wb_name} ({filename})...")
        if not os.path.exists(wb_path):
            raise FileNotFoundError(f"Workbook not found: {wb_path}")

        t0 = time.time()
        parsed = parse_pcf_workbook(wb_path)
        elapsed = (time.time() - t0) * 1000

        elements = parsed["elements"]
        categories = parsed["categories"]
        meta = parsed["metadata"]

        # 1. Element Count & ID Uniqueness
        assert len(elements) == exp["elements"], (
            f"Element count mismatch for {wb_name}: expected {exp['elements']}, got {len(elements)}"
        )
        pcf_ids = [e["pcf_id"] for e in elements]
        assert len(set(pcf_ids)) == exp["elements"], (
            f"Duplicate PCF IDs found in {wb_name}: {len(pcf_ids)} total vs {len(set(pcf_ids))} unique"
        )
        hids = [e["hierarchy_id"] for e in elements]
        assert len(set(hids)) == exp["elements"], (
            f"Duplicate Hierarchy IDs found in {wb_name}: {len(hids)} total vs {len(set(hids))} unique"
        )

        # 2. Layout Profile
        assert meta["source_layout"] == exp["layout_profile"], (
            f"Layout mismatch for {wb_name}: expected {exp['layout_profile']}, got {meta['source_layout']}"
        )

        # 3. Change Counts
        new_elems = [e for e in elements if e["is_new"]]
        renamed_elems = [e for e in elements if e["is_renamed"]]
        changed_elems = [e for e in elements if e["has_changes"]]
        metrics_flag_elems = [e for e in elements if e["metrics_available"]]

        assert len(new_elems) == exp["new_count"], (
            f"New elements mismatch for {wb_name}: expected {exp['new_count']}, got {len(new_elems)}"
        )
        assert len(renamed_elems) == exp["renamed_count"], (
            f"Renamed elements mismatch for {wb_name}: expected {exp['renamed_count']}, got {len(renamed_elems)}"
        )
        assert len(changed_elems) == exp["with_changes"], (
            f"Changed elements mismatch for {wb_name}: expected {exp['with_changes']}, got {len(changed_elems)}"
        )
        assert len(metrics_flag_elems) == exp["metrics_y"], (
            f"Metrics flag mismatch for {wb_name}: expected {exp['metrics_y']}, got {len(metrics_flag_elems)}"
        )

        # 4. Definitions Count
        defs_non_empty = [e for e in elements if e["definition"] and e["definition"].strip()]
        expected_defs = exp.get("definitions_non_empty", exp.get("definitions_count"))
        assert len(defs_non_empty) == expected_defs, (
            f"Definitions mismatch for {wb_name}: expected {expected_defs}, got {len(defs_non_empty)}"
        )

        # 5. Metric Rows Count
        total_metric_records = meta.get("total_metric_records", 0)
        assert total_metric_records == exp["metric_rows"], (
            f"Metric records mismatch for {wb_name}: expected {exp['metric_rows']}, got {total_metric_records}"
        )

        # 6. Levels & Level 6
        levels_present = sorted(list(set(e["level"] for e in elements)))
        assert levels_present == exp["levels"], (
            f"Levels mismatch for {wb_name}: expected {exp['levels']}, got {levels_present}"
        )
        if "level_6_count" in exp:
            l6_elems = [e for e in elements if e["level"] == 6]
            assert len(l6_elems) == exp["level_6_count"], (
                f"Level 6 count mismatch for {wb_name}: expected {exp['level_6_count']}, got {len(l6_elems)}"
            )

        # 7. Rename parsing WAS: with commas
        if "was_sample_with_commas" in exp:
            for e in renamed_elems:
                was = e["renamed_was"]
                assert was, f"Empty renamed_was in {e['hierarchy_id']}"
                assert not was.endswith(","), f"Trailing comma in renamed_was for {e['hierarchy_id']}: '{was}'"
                assert not was.startswith("WAS:"), f"Unparsed WAS prefix in {e['hierarchy_id']}: '{was}'"

        # 8. Attribution & Copyright
        assert meta.get("attribution"), f"Missing attribution in {wb_name}"

        print(f"  ✓ {wb_name} passed all assertions ({len(elements)} elements, {len(categories)} categories, {elapsed:.1f}ms).")
        passed_count += 1

    print("\n" + "=" * 70)
    print(f"ALL {passed_count}/{total_count} WORKBOOK VERIFICATIONS PASSED SUCCESSFULLY (100% COMPLIANT)")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        verify_all_workbooks()
    except AssertionError as err:
        print(f"\n❌ VERIFICATION FAILED: {err}", file=sys.stderr)
        sys.exit(1)
