#!/usr/bin/env python3
"""
YabadabaAPQC - PCF Data Pipeline
Extracts, normalizes, joins glossary definitions, decodes change details,
and exports clean JSON and JS dataset files. (Bundled sample: Healthcare Provider v7.2.1 vs v6.1.1).
"""

import os
import re
import json
import pandas as pd

EXCEL_FILE = "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx"
DATA_DIR = "data"

def decode_changes(change_str):
    """
    Decodes the change details string into structured attributes.
    e.g. "+20086, +20087, -10381, c10383, RENAME, WAS:Develop customer service strategy, NEW"
    """
    if pd.isna(change_str) or not str(change_str).strip():
        return {
            "has_changes": False,
            "raw_changes": "",
            "is_new": False,
            "is_renamed": False,
            "renamed_was": "",
            "added_children": [],
            "removed_children": [],
            "changed_children": []
        }
    
    raw = str(change_str).strip()
    is_renamed = False
    renamed_was = ""
    is_new = False
    prefix_part = raw
    
    if "WAS:" in raw:
        is_renamed = True
        parts = raw.split("WAS:", 1)
        prefix_part = parts[0]
        was_content = parts[1].strip()
        
        # Robust trailing NEW detection: case-insensitive, any whitespace around comma, optional trailing period
        m_new = re.search(r',\s*new\s*\.?\s*$', was_content, flags=re.IGNORECASE)
        if m_new:
            was_content = was_content[:m_new.start()].strip()
            is_new = True
        else:
            is_new = bool(re.search(r'\bNEW\b', prefix_part, flags=re.IGNORECASE))
            
        renamed_was = was_content
    else:
        if bool(re.search(r'\bRENAME\b', raw, flags=re.IGNORECASE)):
            is_renamed = True
        is_new = bool(re.search(r'\bNEW\b', raw, flags=re.IGNORECASE))
    
    # Parse child tokens (+, -, c) as whole tokens only from prefix_part.
    # Split the prefix on commas and match each token with ^[+\-c]\d+$
    added = []
    removed = []
    changed = []
    for raw_token in prefix_part.split(","):
        token = raw_token.strip()
        m = re.match(r'^([+\-c])(\d+)$', token)
        if m:
            prefix_char = m.group(1)
            child_id = m.group(2)
            if prefix_char == '+':
                added.append(child_id)
            elif prefix_char == '-':
                removed.append(child_id)
            elif prefix_char == 'c':
                changed.append(child_id)
                
    return {
        "has_changes": True,
        "raw_changes": raw,
        "is_new": is_new,
        "is_renamed": is_renamed,
        "renamed_was": renamed_was,
        "added_children": added,
        "removed_children": removed,
        "changed_children": changed
    }

def parse_pcf_workbook(excel_file, operating_categories=None):
    """
    Parses any APQC PCF workbook (.xlsx), extracting normalized elements,
    hierarchies, definitions, and change details.
    """
    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"Source file not found: {excel_file}")

    xl = pd.ExcelFile(excel_file)
    comb_sheet = next((s for s in xl.sheet_names if "combined" in s.lower()), None)
    gloss_sheet = next((s for s in xl.sheet_names if "glossary" in s.lower()), None)

    if not comb_sheet:
        raise ValueError("Missing required worksheet: 'Combined'")
    if not gloss_sheet:
        raise ValueError("Missing required worksheet: 'Glossary terms'")

    df_comb = pd.read_excel(excel_file, sheet_name=comb_sheet)
    df_gloss = pd.read_excel(excel_file, sheet_name=gloss_sheet)

    # Build glossary lookup dictionaries
    gloss_by_pid = {}
    gloss_by_hid = {}
    for _, row in df_gloss.iterrows():
        defn = str(row["Definition"]).strip() if pd.notna(row.get("Definition")) else ""
        pid_val = row.get("Process Element ID") if pd.notna(row.get("Process Element ID")) else row.get("PCF ID")
        if pd.notna(pid_val):
            gloss_by_pid[str(pid_val).strip()] = defn
        if pd.notna(row.get("Hierarchy ID")):
            gloss_by_hid[str(row["Hierarchy ID"]).strip()] = defn

    if operating_categories is not None:
        op_cats = {str(c) for c in operating_categories}
    else:
        op_cats = {"1", "2", "3", "4", "5"}

    elements = []
    category_map = {}

    level_names = {
        1: "Category",
        2: "Process group",
        3: "Process",
        4: "Activity",
        5: "Task"
    }

    for idx, row in df_comb.iterrows():
        pcf_val = row.get("PCF ID") if pd.notna(row.get("PCF ID")) else row.get("Process Element ID")
        pcf_id = str(pcf_val).strip() if pd.notna(pcf_val) else ""
        hierarchy_id = str(row.get("Hierarchy ID", "")).strip() if pd.notna(row.get("Hierarchy ID")) else ""
        name = str(row.get("Name", "")).strip() if pd.notna(row.get("Name")) else ""
        diff_index = int(row.get("Difference Index", 0)) if pd.notna(row.get("Difference Index")) else 0
        metrics_available = str(row.get("Metrics available?", "")).strip().upper() == "Y"
        raw_change = row.get("Change details", "")

        if not hierarchy_id:
            continue

        parts = hierarchy_id.split(".")
        level = len(parts)
        category_num = parts[0]

        if not category_num.isdigit():
            raise ValueError(f"Invalid Hierarchy ID '{hierarchy_id}': category segment must be a numeric integer.")

        is_category_root = (level == 2 and parts[1] == "0")
        if is_category_root:
            level = 1
            level_name = "Category"
            parent_hid = ""
        else:
            level_name = level_names.get(level, f"Level {level}")
            parent_hid = ".".join(parts[:-1]) if len(parts) > 1 else ""
            if len(parts) == 2 and parts[1] != "0":
                parent_hid = f"{parts[0]}.0"

        defn = gloss_by_pid.get(pcf_id) or gloss_by_hid.get(hierarchy_id) or ""
        change_info = decode_changes(raw_change)
        process_type = "Operating Processes" if category_num in op_cats else "Management & Support Services"

        item = {
            "id": pcf_id if pcf_id else hierarchy_id,
            "pcf_id": pcf_id,
            "hierarchy_id": hierarchy_id,
            "name": name,
            "level": level,
            "level_name": level_name,
            "category_id": category_num,
            "parent_hierarchy_id": parent_hid,
            "diff_index": diff_index,
            "metrics_available": metrics_available,
            "process_type": process_type,
            "definition": defn,
            "change_details": change_info["raw_changes"],
            "has_changes": change_info["has_changes"],
            "is_new": change_info["is_new"],
            "is_renamed": change_info["is_renamed"],
            "renamed_was": change_info["renamed_was"],
            "added_children": change_info["added_children"],
            "removed_children": change_info["removed_children"],
            "changed_children": change_info["changed_children"]
        }
        elements.append(item)

        if is_category_root:
            category_map[category_num] = {
                "category_id": category_num,
                "hierarchy_id": hierarchy_id,
                "pcf_id": pcf_id,
                "name": name,
                "process_type": process_type,
                "diff_index": diff_index,
                "metrics_available": metrics_available,
                "change_details": change_info["raw_changes"]
            }

    # Category statistics
    cat_stats = []
    for cat_num, cat_info in sorted(category_map.items(), key=lambda x: int(x[0])):
        cat_elements = [e for e in elements if e["category_id"] == cat_num]
        total_count = len(cat_elements)
        new_count = sum(1 for e in cat_elements if e["is_new"])
        renamed_count = sum(1 for e in cat_elements if e["is_renamed"])
        changes_count = sum(1 for e in cat_elements if e["has_changes"])
        metrics_count = sum(1 for e in cat_elements if e["metrics_available"])
        max_diff = max((e["diff_index"] for e in cat_elements), default=0)
        sum_diff = sum(e["diff_index"] for e in cat_elements)

        cat_stats.append({
            "category_id": cat_num,
            "hierarchy_id": cat_info["hierarchy_id"],
            "pcf_id": cat_info["pcf_id"],
            "name": cat_info["name"],
            "process_type": cat_info["process_type"],
            "total_elements": total_count,
            "elements_with_changes": changes_count,
            "new_elements": new_count,
            "renamed_elements": renamed_count,
            "metrics_available": metrics_count,
            "max_diff_index": max_diff,
            "sum_diff_index": sum_diff
        })

    return {
        "categories": cat_stats,
        "elements": elements
    }

def main():
    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError(f"Source file not found: {EXCEL_FILE}")
        
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print(f"Loading {EXCEL_FILE}...")
    parsed = parse_pcf_workbook(EXCEL_FILE)
    elements = parsed["elements"]
    cat_stats = parsed["categories"]
    
    print(f"Extracted {len(elements)} elements across {len(cat_stats)} categories.")

    attribution_text = "©2022 APQC. ALL RIGHTS RESERVED. This Process Classification Framework® (\"PCF\") is the copyrighted intellectual property of APQC."
    attribution_line = f"# {attribution_text}\n"

    df_cat_stats = pd.DataFrame(cat_stats)
    cat_summary_path = os.path.join(DATA_DIR, "pcf_category_summary.csv")
    with open(cat_summary_path, "w", encoding="utf-8") as f:
        f.write(attribution_line)
        df_cat_stats.to_csv(f, index=False)
    print(f"Saved category summary to {cat_summary_path}")

    # Export changes inventory
    changes_list = [e for e in elements if e["has_changes"]]
    df_changes = pd.DataFrame(changes_list)
    changes_path = os.path.join(DATA_DIR, "pcf_changes_inventory.csv")
    with open(changes_path, "w", encoding="utf-8") as f:
        f.write(attribution_line)
        df_changes.to_csv(f, index=False)
    print(f"Saved changes inventory ({len(changes_list)} rows) to {changes_path}")

    # Build full bundle JSON
    bundle = {
        "metadata": {
            "source_document": EXCEL_FILE,
            "version": "7.2.1 vs 6.1.1 (April 2023)",
            "framework": "APQC Process Classification Framework (PCF) - Healthcare Provider",
            "attribution": attribution_text,
            "total_elements": len(elements),
            "total_with_changes": len(changes_list),
            "total_new": sum(1 for e in elements if e["is_new"]),
            "total_renamed": sum(1 for e in elements if e["is_renamed"]),
            "total_with_metrics": sum(1 for e in elements if e["metrics_available"]),
            "categories_count": len(cat_stats)
        },
        "categories": cat_stats,
        "elements": elements
    }
    
    json_path = os.path.join(DATA_DIR, "pcf_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    print(f"Saved complete dataset JSON ({os.path.getsize(json_path) / 1024:.1f} KB) to {json_path}")
    
    js_path = os.path.join(DATA_DIR, "pcf_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.PCF_DATA = ")
        json.dump(bundle, f, ensure_ascii=False)
        f.write(";\n")
    print(f"Saved dataset JS for offline file:// loading to {js_path}")
    
    print("\nExtraction & Transformation Complete!")

if __name__ == "__main__":
    main()
