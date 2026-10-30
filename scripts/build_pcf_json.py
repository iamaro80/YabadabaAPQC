#!/usr/bin/env python3
"""
APQC PCF Healthcare Provider v7.2.1 vs v6.1.1 Data Pipeline
Extracts, normalizes, joins glossary definitions, decodes change details,
and exports clean JSON and CSV files.
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
    prefix_part = raw
    
    if "WAS:" in raw:
        is_renamed = True
        parts = raw.split("WAS:", 1)
        prefix_part = parts[0]
        was_content = parts[1].strip()
        
        # Handle trailing ', NEW'
        if was_content.endswith(", NEW"):
            was_content = was_content[:-5].strip()
            is_new = True
        elif was_content.endswith(",NEW"):
            was_content = was_content[:-4].strip()
            is_new = True
        else:
            is_new = bool(re.search(r'\bNEW\b', prefix_part))
            
        renamed_was = was_content
    else:
        if "RENAME" in raw:
            is_renamed = True
        is_new = bool(re.search(r'\bNEW\b', raw))
    
    # Parse child tokens (+, -, c) ONLY from the non-WAS prefix portion
    added = re.findall(r'\+(\d+)', prefix_part)
    removed = re.findall(r'\-(\d+)', prefix_part)
    changed = re.findall(r'\bc(\d+)', prefix_part)
    
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

def main():
    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError(f"Source file not found: {EXCEL_FILE}")
        
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print(f"Loading {EXCEL_FILE}...")
    df_comb = pd.read_excel(EXCEL_FILE, sheet_name="Combined")
    df_gloss = pd.read_excel(EXCEL_FILE, sheet_name="Glossary terms")
    
    print(f"Combined sheet rows: {len(df_comb)}")
    print(f"Glossary sheet rows: {len(df_gloss)}")
    
    # Build glossary lookup dictionaries
    gloss_by_pid = {}
    gloss_by_hid = {}
    for _, row in df_gloss.iterrows():
        defn = str(row["Definition"]).strip() if pd.notna(row["Definition"]) else ""
        if pd.notna(row["Process Element ID"]):
            gloss_by_pid[str(row["Process Element ID"]).strip()] = defn
        if pd.notna(row["Hierarchy ID"]):
            gloss_by_hid[str(row["Hierarchy ID"]).strip()] = defn

    # Parse and enrich elements
    elements = []
    category_map = {}
    
    for idx, row in df_comb.iterrows():
        pcf_id = str(row["PCF ID"]).strip() if pd.notna(row["PCF ID"]) else ""
        hierarchy_id = str(row["Hierarchy ID"]).strip() if pd.notna(row["Hierarchy ID"]) else ""
        name = str(row["Name"]).strip() if pd.notna(row["Name"]) else ""
        diff_index = int(row["Difference Index"]) if pd.notna(row["Difference Index"]) else 0
        metrics_available = str(row["Metrics available?"]).strip().upper() == "Y"
        raw_change = row["Change details"]
        
        # Determine hierarchy level
        parts = hierarchy_id.split(".")
        level = len(parts)
        category_num = parts[0]
        
        # Level naming
        level_name = {
            1: "Category",
            2: "Process Group",
            3: "Process",
            4: "Activity",
            5: "Task"
        }.get(level, f"Level {level}")
        
        # If level 2 and ends with .0, it's actually the Category root element (e.g. 1.0, 2.0)
        is_category_root = (level == 2 and parts[1] == "0")
        if is_category_root:
            level = 1
            level_name = "Category"
            parent_hid = ""
        else:
            parent_hid = ".".join(parts[:-1]) if len(parts) > 1 else ""
            if len(parts) == 2 and parts[1] != "0":
                parent_hid = f"{parts[0]}.0"

        # Definition lookup
        defn = gloss_by_pid.get(pcf_id) or gloss_by_hid.get(hierarchy_id) or ""
        
        # Decode changes
        change_info = decode_changes(raw_change)
        
        # Determine Operating vs Support
        try:
            cat_int = int(category_num)
            process_type = "Operating Processes" if cat_int <= 5 else "Management & Support Services"
        except ValueError:
            process_type = "Other"

        item = {
            "id": pcf_id,
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
                "category_num": category_num,
                "hierarchy_id": hierarchy_id,
                "pcf_id": pcf_id,
                "name": name,
                "process_type": process_type,
                "diff_index": diff_index,
                "metrics_available": metrics_available,
                "change_details": change_info["raw_changes"]
            }

    # Summary by Category
    cat_stats = []
    for cat_num, cat_info in sorted(category_map.items(), key=lambda x: int(x[0])):
        cat_elements = [e for e in elements if e["category_id"] == cat_num]
        total_count = len(cat_elements)
        new_count = sum(1 for e in cat_elements if e["is_new"])
        renamed_count = sum(1 for e in cat_elements if e["is_renamed"])
        changes_count = sum(1 for e in cat_elements if e["has_changes"])
        metrics_count = sum(1 for e in cat_elements if e["metrics_available"])
        max_diff = max(e["diff_index"] for e in cat_elements)
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
