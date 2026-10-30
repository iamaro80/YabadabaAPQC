#!/usr/bin/env python3
"""
Shared test cases for APQC PCF Data Decoders (Python & JavaScript).
Tests both Healthcare Provider and Retail reference workbooks against expected standards.
"""

import os
import sys
import pandas as pd
from build_pcf_json import decode_changes

HC_FILE = "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx"
RETAIL_FILE = "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx"

def run_tests():
    print("=" * 70)
    print("RUNNING SHARED PCF TEST SUITE (HEALTHCARE & RETAIL)")
    print("=" * 70)

    # Test 1: Healthcare Provider Workbook
    print(f"\n1. Testing Healthcare Workbook: {HC_FILE}")
    assert os.path.exists(HC_FILE), f"Missing {HC_FILE}"
    df_hc_comb = pd.read_excel(HC_FILE, sheet_name="Combined")
    df_hc_gloss = pd.read_excel(HC_FILE, sheet_name="Glossary terms")

    hc_gloss_pids = {}
    hc_gloss_hids = {}
    for _, r in df_hc_gloss.iterrows():
        defn = str(r["Definition"]).strip() if pd.notna(r["Definition"]) else ""
        if pd.notna(r["Process Element ID"]):
            hc_gloss_pids[str(r["Process Element ID"]).strip()] = defn
        if pd.notna(r["Hierarchy ID"]):
            hc_gloss_hids[str(r["Hierarchy ID"]).strip()] = defn

    hc_new = 0
    hc_renamed = 0
    hc_metrics = 0
    hc_with_def = 0
    hc_without_def = 0

    for _, r in df_hc_comb.iterrows():
        pid = str(r["PCF ID"]).strip() if pd.notna(r["PCF ID"]) else ""
        hid = str(r["Hierarchy ID"]).strip() if pd.notna(r["Hierarchy ID"]) else ""
        ch = decode_changes(r["Change details"])
        if ch["is_new"]: hc_new += 1
        if ch["is_renamed"]: hc_renamed += 1
        if str(r["Metrics available?"]).strip().upper() == "Y": hc_metrics += 1

        defn = hc_gloss_pids.get(pid) or hc_gloss_hids.get(hid) or ""
        if defn:
            hc_with_def += 1
        else:
            hc_without_def += 1

    print(f"  • Elements: {len(df_hc_comb)} (Expected: 1,985)")
    print(f"  • New: {hc_new} (Expected: 960)")
    print(f"  • Renamed: {hc_renamed} (Expected: 134)")
    print(f"  • Metrics: {hc_metrics} (Expected: 221)")
    print(f"  • Definitions: {hc_with_def} (Expected: 1,931)")
    print(f"  • Without definition: {hc_without_def} (Expected: 54)")

    assert len(df_hc_comb) == 1985
    assert hc_new == 960
    assert hc_renamed == 134
    assert hc_metrics == 221
    assert hc_with_def == 1931
    assert hc_without_def == 54
    print("✓ Healthcare test cases passed 100%.")

    # Test 2: Retail Workbook
    print(f"\n2. Testing Retail Workbook: {RETAIL_FILE}")
    assert os.path.exists(RETAIL_FILE), f"Missing {RETAIL_FILE}"
    df_ret_comb = pd.read_excel(RETAIL_FILE, sheet_name="Combined")
    df_ret_gloss = pd.read_excel(RETAIL_FILE, sheet_name="Glossary terms")

    ret_gloss_pids = {}
    ret_gloss_hids = {}
    for _, r in df_ret_gloss.iterrows():
        defn = str(r["Definition"]).strip() if pd.notna(r["Definition"]) else ""
        if pd.notna(r["Process Element ID"]):
            ret_gloss_pids[str(r["Process Element ID"]).strip()] = defn
        if pd.notna(r["Hierarchy ID"]):
            ret_gloss_hids[str(r["Hierarchy ID"]).strip()] = defn

    ret_new = 0
    ret_renamed = 0
    ret_metrics = 0
    ret_with_def = 0
    ret_without_def = 0
    ret_renames_with_commas = []

    for _, r in df_ret_comb.iterrows():
        pid = str(r["PCF ID"]).strip() if pd.notna(r["PCF ID"]) else ""
        hid = str(r["Hierarchy ID"]).strip() if pd.notna(r["Hierarchy ID"]) else ""
        ch = decode_changes(r["Change details"])
        if ch["is_new"]: ret_new += 1
        if ch["is_renamed"]:
            ret_renamed += 1
            if "," in ch["renamed_was"]:
                ret_renames_with_commas.append((hid, ch["renamed_was"]))
        if str(r["Metrics available?"]).strip().upper() == "Y": ret_metrics += 1

        defn = ret_gloss_pids.get(pid) or ret_gloss_hids.get(hid) or ""
        if defn:
            ret_with_def += 1
        else:
            ret_without_def += 1

    print(f"  • Elements: {len(df_ret_comb)} (Expected: 1,708)")
    print(f"  • New: {ret_new} (Expected: 608)")
    print(f"  • Renamed: {ret_renamed} (Expected: 74)")
    print(f"  • Metrics: {ret_metrics} (Expected: 180)")
    print(f"  • Non-empty definitions: {ret_with_def} (Expected: 1,462, from 1,463 matched minus 1 empty cell at PID 10407)")
    print(f"  • Without definition: {ret_without_def} (Expected: 246)")
    print(f"  • Renames containing commas: {len(ret_renames_with_commas)} (Expected: 9)")

    assert len(df_ret_comb) == 1708
    assert ret_new == 608
    assert ret_renamed == 74
    assert ret_metrics == 180
    assert ret_with_def == 1462
    assert ret_without_def == 246
    assert len(ret_renames_with_commas) == 9
    print("✓ Retail test cases passed 100%.")

    print("\n" + "=" * 70)
    print("ALL SHARED TEST CASES PASSED SUCCESSFULLY")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
