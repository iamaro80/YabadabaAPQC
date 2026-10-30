#!/usr/bin/env python3
"""
YabadabaAPQC - PCF Data Pipeline
Implements the Strategy Pattern (composed across definition and metrics axes)
to support multiple APQC workbook layouts:
- Family A (2023 comparison: Healthcare, Retail, City Government, Health Insurance Payor)
- Family B (2026 v8.0: Cross-Industry, Consumer Products)
"""

import os
import re
import json
import openpyxl

EXCEL_FILE = "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx"
DATA_DIR = "data"

def normalize_header(h):
    """
    Normalizes a table header: trim, lowercase, collapse whitespace/newlines, strip trailing '?'.
    """
    if h is None:
        return ""
    text = str(h).strip().lower()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.rstrip('?').strip()

def decode_changes(change_str):
    """
    Decodes the change details string into structured attributes.
    Child tokens are matched as whole tokens (^([+\\-c])(\\d+)$) from the prefix before WAS:.
    Everything after WAS: is rename text, including commas.
    """
    if change_str is None or not str(change_str).strip():
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

# ======================================================================
# STRATEGY IMPLEMENTATIONS: DEFINITIONS
# ======================================================================

class GlossarySheetDefinitions:
    """Loads definitions from a separate 'Glossary terms' worksheet."""
    @staticmethod
    def load(wb, combined_rows=None):
        sheet_name = next((s for s in wb.sheetnames if "glossary" in s.lower()), None)
        if not sheet_name:
            return {}
        ws = wb[sheet_name]
        raw_rows = list(ws.iter_rows(values_only=True))
        if not raw_rows:
            return {}
        headers = [normalize_header(c) for c in raw_rows[0]]
        
        pid_idx = headers.index("process element id") if "process element id" in headers else (headers.index("pcf id") if "pcf id" in headers else 0)
        hid_idx = headers.index("hierarchy id") if "hierarchy id" in headers else 1
        def_idx = headers.index("definition") if "definition" in headers else 3
        
        defs_by_pid = {}
        defs_by_hid = {}
        for r in raw_rows[1:]:
            pid = str(r[pid_idx]).strip() if pid_idx < len(r) and r[pid_idx] is not None else ""
            hid = str(r[hid_idx]).strip() if hid_idx < len(r) and r[hid_idx] is not None else ""
            d = str(r[def_idx]).strip() if def_idx < len(r) and r[def_idx] is not None else ""
            if pid == "10001" and not hid:
                # Root row to ignore
                continue
            if pid:
                defs_by_pid[pid] = d
            if hid:
                defs_by_hid[hid] = d
                
        def resolver(pcf_id, hierarchy_id, row=None):
            return defs_by_pid.get(pcf_id) or defs_by_hid.get(hierarchy_id) or ""
            
        return resolver

class InlineColumnDefinitions:
    """Reads definitions inline from the 'Element Description' column in Combined."""
    @staticmethod
    def load(wb, combined_rows=None):
        def resolver(pcf_id, hierarchy_id, row=None):
            if row is None:
                return ""
            desc = row.get("element description") or row.get("definition") or ""
            return str(desc).strip()
        return resolver

# ======================================================================
# STRATEGY IMPLEMENTATIONS: METRICS
# ======================================================================

class FlagOnlyMetrics:
    """Family A: Metrics are represented only by the Y/N flag in Combined."""
    @staticmethod
    def load(wb):
        def resolver(hierarchy_id, pcf_id=None):
            return []
        return resolver, 0

class MetricsSheetMetrics:
    """Family B: Detailed metrics parsed from 'Metrics' worksheet."""
    @staticmethod
    def load(wb):
        sheet_name = next((s for s in wb.sheetnames if s.strip().lower() == "metrics"), None)
        if not sheet_name:
            def empty_resolver(h, p=None): return []
            return empty_resolver, 0
            
        ws = wb[sheet_name]
        raw_rows = list(ws.iter_rows(values_only=True))
        if not raw_rows:
            def empty_resolver(h, p=None): return []
            return empty_resolver, 0
            
        headers = [normalize_header(c) for c in raw_rows[0]]
        
        pid_idx = headers.index("process element id") if "process element id" in headers else 0
        hid_idx = headers.index("hierarchy id") if "hierarchy id" in headers else 1
        cat_idx = headers.index("metric category") if "metric category" in headers else 3
        id_idx = headers.index("metric id") if "metric id" in headers else 4
        name_idx = headers.index("metric name") if "metric name" in headers else 5
        form_idx = headers.index("formula") if "formula" in headers else 6
        unit_idx = headers.index("units") if "units" in headers else 7
        
        metrics_by_hid = {}
        metrics_by_pid = {}
        total_valid = 0
        
        for r in raw_rows[1:]:
            name = str(r[name_idx]).strip() if name_idx < len(r) and r[name_idx] is not None else ""
            if not name:
                continue
            hid = str(r[hid_idx]).strip() if hid_idx < len(r) and r[hid_idx] is not None else ""
            pid = str(r[pid_idx]).strip() if pid_idx < len(r) and r[pid_idx] is not None else ""
            m_cat = str(r[cat_idx]).strip() if cat_idx < len(r) and r[cat_idx] is not None else "General"
            m_id = str(r[id_idx]).strip() if id_idx < len(r) and r[id_idx] is not None else ""
            formula = str(r[form_idx]).strip() if form_idx < len(r) and r[form_idx] is not None else ""
            units = str(r[unit_idx]).strip() if unit_idx < len(r) and r[unit_idx] is not None else ""
            
            metric = {
                "category": m_cat,
                "id": m_id,
                "name": name,
                "formula": formula,
                "units": units
            }
            if hid:
                metrics_by_hid.setdefault(hid, []).append(metric)
            if pid:
                metrics_by_pid.setdefault(pid, []).append(metric)
            total_valid += 1
            
        def resolver(hierarchy_id, pcf_id=None):
            return metrics_by_hid.get(hierarchy_id) or (metrics_by_pid.get(pcf_id) if pcf_id else None) or []
            
        return resolver, total_valid

# ======================================================================
# STRATEGY IMPLEMENTATIONS: VERSION INFO & ATTRIBUTION
# ======================================================================

class VersionInfoStrategy:
    """Scans the Introduction sheet and Copyright sheet for metadata."""
    @staticmethod
    def read(wb, filename=""):
        intro_name = next((s for s in wb.sheetnames if s.strip().lower() == "introduction"), None)
        title = None
        version = None
        compared_to = None
        generated_on = None
        
        if intro_name:
            ws = wb[intro_name]
            cells = []
            for r in range(1, 40):
                for c in range(1, 20):
                    v = ws.cell(r, c).value
                    if v is not None and str(v).strip():
                        cells.append(str(v).strip())
                        
            for text in cells:
                u = text.upper()
                if "PROCESS CLASSIFICATION FRAMEWORK" in u and not title:
                    if not u.startswith("COMPARED TO"):
                        title = "APQC " + " ".join(w.capitalize() if w.upper() not in ("PCF", "APQC") else w.upper() for w in text.split())
                m_ver = re.search(r'VERSION\s+(?:NUMBER\s+)?([0-9]+(?:\.[0-9]+)*)', text, re.IGNORECASE)
                if m_ver and not version:
                    val = m_ver.group(1)
                    version = "v" + val if not val.startswith("v") else val
                m_comp = re.search(r'COMPARED\s+TO.*?(?:VERSION\s+)?([0-9]+(?:\.[0-9]+)*)$', text, re.IGNORECASE)
                if m_comp and not compared_to:
                    val = m_comp.group(1)
                    compared_to = "v" + val if not val.startswith("v") else val
                m_gen = re.search(r'GENERATED\s+ON\s+([0-9]+/[0-9]+/[0-9]+|[A-Za-z]+\s+[0-9]+,\s+[0-9]+|[0-9]{4}-[0-9]{2}-[0-9]{2})', text, re.IGNORECASE)
                if m_gen and not generated_on:
                    generated_on = m_gen.group(1)
                    
        # Check copyright sheet
        copy_sheet = next((s for s in wb.sheetnames if "copyright" in s.lower()), None)
        copy_year = 2022
        attribution = '©2022 APQC. ALL RIGHTS RESERVED. This Process Classification Framework® ("PCF") is the copyrighted intellectual property of APQC.'
        if copy_sheet:
            ws = wb[copy_sheet]
            cells = []
            for r in range(1, 40):
                for c in range(1, 20):
                    v = ws.cell(r, c).value
                    if v and any(w in str(v) for w in ["©", "Copyright", "reserve all rights", "ALL RIGHTS RESERVED"]):
                        cells.append(str(v).strip())
            for c in cells:
                m = re.search(r'©\s*([0-9]{4})', c)
                if m:
                    copy_year = int(m.group(1))
                    attribution = c
                    break
                    
        return {
            "title": title,
            "version_label": version,
            "compared_to": compared_to,
            "generated_on": generated_on,
            "copyright_year": copy_year,
            "attribution": attribution
        }

# ======================================================================
# LAYOUT PROFILES REGISTRY
# ======================================================================

LAYOUT_PROFILES = [
    {
        "id": "family-b-2026",
        "label": "2026 v8.0 (Inline Definitions & Metrics Sheet)",
        "detect": lambda sheet_names, headers: "combined" in sheet_names and "metrics" in sheet_names and "element description" in headers,
        "definition_source": InlineColumnDefinitions,
        "metrics_source": MetricsSheetMetrics,
        "default_operating": ["1", "2", "3", "4", "5", "6"]
    },
    {
        "id": "family-a-2023",
        "label": "2023 Comparison (Glossary Sheet & Flag-Only Metrics)",
        "detect": lambda sheet_names, headers: "combined" in sheet_names and any("glossary" in s for s in sheet_names),
        "definition_source": GlossarySheetDefinitions,
        "metrics_source": FlagOnlyMetrics,
        "default_operating": ["1", "2", "3", "4", "5"]
    }
]

def detect_layout(sheet_names, headers):
    s_names_lower = [s.strip().lower() for s in sheet_names]
    if not any("combined" in s for s in s_names_lower):
        raise ValueError("Missing required worksheet: 'Combined'")
    h_lower = [normalize_header(h) for h in headers]
    for p in LAYOUT_PROFILES:
        if p["detect"](s_names_lower, h_lower):
            return p
    raise ValueError(
        f"Unknown workbook layout.\n"
        f"Sheets found: {sheet_names}\n"
        f"Combined headers found: {headers}\n"
        f"Expected either:\n"
        f"  - Family A (2023 comparison): Sheets 'Combined' and 'Glossary terms'\n"
        f"  - Family B (2026 v8.0): Sheets 'Combined' and 'Metrics' with 'Element Description' in Combined"
    )

# ======================================================================
# SHARED CANONICAL PIPELINE
# ======================================================================

def parse_pcf_workbook(excel_source, operating_categories=None, filename=None):
    """
    Parses any APQC PCF workbook (.xlsx), detecting layout profile,
    resolving definitions and metrics via strategies, and returning canonical dataset.
    """
    if isinstance(excel_source, str):
        if not os.path.exists(excel_source):
            raise FileNotFoundError(f"Source file not found: {excel_source}")
        wb = openpyxl.load_workbook(excel_source, data_only=True)
        fname = filename or os.path.basename(excel_source)
    else:
        wb = excel_source
        fname = filename or "uploaded_workbook.xlsx"
        
    comb_sheet_name = next((s for s in wb.sheetnames if "combined" in s.lower()), None)
    if not comb_sheet_name:
        raise ValueError("Missing required worksheet: 'Combined'")
        
    comb_ws = wb[comb_sheet_name]
    raw_comb_rows = list(comb_ws.iter_rows(values_only=True))
    if not raw_comb_rows:
        raise ValueError("Worksheet 'Combined' has no rows")
        
    raw_headers = list(raw_comb_rows[0])
    normalized_headers = [normalize_header(h) for h in raw_headers]
    
    # Detect Layout Profile
    profile = detect_layout(wb.sheetnames, raw_headers)
    
    # Header Mapping
    def find_col_idx(aliases):
        for a in aliases:
            if a in normalized_headers:
                return normalized_headers.index(a)
        return None
        
    pcf_idx = find_col_idx(["pcf id", "process element id", "element id"])
    hid_idx = find_col_idx(["hierarchy id", "hierarchy"])
    name_idx = find_col_idx(["name", "process element", "process name", "element name"])
    diff_idx = find_col_idx(["difference index", "diff index"])
    change_idx = find_col_idx(["change details", "change detail"])
    metric_flag_idx = find_col_idx(["metrics available", "metrics available?"])
    desc_idx = find_col_idx(["element description", "definition", "description"])
    
    if hid_idx is None:
        raise ValueError("Worksheet 'Combined' is missing required 'Hierarchy ID' column")
        
    # Read rows into dictionaries for strategy consumers
    combined_records = []
    for r in raw_comb_rows[1:]:
        if hid_idx < len(r) and r[hid_idx] is not None and str(r[hid_idx]).strip():
            rec = {
                "pcf_id": str(r[pcf_idx]).strip() if pcf_idx is not None and pcf_idx < len(r) and r[pcf_idx] is not None else "",
                "hierarchy_id": str(r[hid_idx]).strip(),
                "name": str(r[name_idx]).strip() if name_idx is not None and name_idx < len(r) and r[name_idx] is not None else "",
                "diff_index": int(r[diff_idx]) if diff_idx is not None and diff_idx < len(r) and r[diff_idx] is not None and str(r[diff_idx]).strip().isdigit() else 0,
                "metrics_available": str(r[metric_flag_idx]).strip().upper() in ("Y", "YES") if metric_flag_idx is not None and metric_flag_idx < len(r) and r[metric_flag_idx] is not None else False,
                "change_details": str(r[change_idx]).strip() if change_idx is not None and change_idx < len(r) and r[change_idx] is not None else "",
                "element description": str(r[desc_idx]).strip() if desc_idx is not None and desc_idx < len(r) and r[desc_idx] is not None else ""
            }
            combined_records.append(rec)
            
    # Load Strategies
    def_resolver = profile["definition_source"].load(wb, combined_records)
    metric_resolver, total_metric_records = profile["metrics_source"].load(wb)
    v_info = VersionInfoStrategy.read(wb, fname)
    
    # Determine Operating Categories
    if operating_categories is not None:
        op_cats = {str(c) for c in operating_categories}
    else:
        # Check Retail heuristic if in Family A
        is_retail = "retail" in fname.lower() or (v_info["title"] and "retail" in v_info["title"].lower())
        if is_retail:
            op_cats = {"1", "2", "3", "4", "5", "6"}
        else:
            op_cats = {str(c) for c in profile["default_operating"]}
            
    elements = []
    category_map = {}
    
    level_names = {
        1: "Category",
        2: "Process group",
        3: "Process",
        4: "Activity",
        5: "Task"
    }
    
    for row in combined_records:
        hierarchy_id = row["hierarchy_id"]
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
                
        pcf_id = row["pcf_id"]
        name = row["name"]
        diff_index = row["diff_index"]
        metrics_available = row["metrics_available"]
        change_info = decode_changes(row["change_details"])
        process_type = "Operating Processes" if category_num in op_cats else "Management & Support Services"
        
        definition = def_resolver(pcf_id, hierarchy_id, row)
        metrics_list = metric_resolver(hierarchy_id, pcf_id)
        
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
            "definition": definition,
            "change_details": change_info["raw_changes"],
            "has_changes": change_info["has_changes"],
            "is_new": change_info["is_new"],
            "is_renamed": change_info["is_renamed"],
            "renamed_was": change_info["renamed_was"],
            "added_children": change_info["added_children"],
            "removed_children": change_info["removed_children"],
            "changed_children": change_info["changed_children"],
            "metrics": metrics_list
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
        
    framework_title = v_info["title"] or (
        "APQC Healthcare Provider PCF" if "healthcare" in fname.lower()
        else ("APQC Retail PCF" if "retail" in fname.lower()
        else ("APQC City Government PCF" if "city" in fname.lower()
        else ("APQC Health Insurance Payor PCF" if "payor" in fname.lower() or "insurance" in fname.lower()
        else "APQC Process Classification Framework")))
    )
    
    version_text = v_info["version_label"] or (
        "7.2.1 vs 6.1.1 (April 2023)" if "healthcare" in fname.lower()
        else ("v7.2.1" if "721" in fname else "v8.0")
    )
    
    metadata = {
        "source_document": fname,
        "source_layout": profile["id"],
        "layout_label": profile["label"],
        "framework": framework_title,
        "version": version_text,
        "version_label": v_info["version_label"] or "v7.2.1",
        "compared_to": v_info["compared_to"],
        "generated_on": v_info["generated_on"],
        "copyright_year": v_info["copyright_year"],
        "attribution": v_info["attribution"],
        "total_elements": len(elements),
        "total_with_changes": sum(1 for e in elements if e["has_changes"]),
        "total_new": sum(1 for e in elements if e["is_new"]),
        "total_renamed": sum(1 for e in elements if e["is_renamed"]),
        "total_with_metrics": sum(1 for e in elements if e["metrics_available"]),
        "total_metric_records": total_metric_records,
        "definitions_count": sum(1 for e in elements if e["definition"]),
        "categories_count": len(cat_stats)
    }
    
    return {
        "metadata": metadata,
        "categories": cat_stats,
        "elements": elements
    }

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else EXCEL_FILE
    if not os.path.exists(target):
        raise FileNotFoundError(f"Source file not found: {target}")
        
    print(f"Parsing reference workbook: {target}...")
    parsed = parse_pcf_workbook(target)
    elements = parsed["elements"]
    cat_stats = parsed["categories"]
    metadata = parsed["metadata"]
    
    print(f"Extracted {len(elements)} elements across {len(cat_stats)} categories.")
    print(f"  Layout Profile: {metadata['source_layout']} ({metadata['layout_label']})")
    print(f"  Version: {metadata['version_label']} (Compared to: {metadata['compared_to']})")
    print(f"  New: {metadata['total_new']}, Renamed: {metadata['total_renamed']}, Metrics Flag = Y: {metadata['total_with_metrics']}")
    print(f"  Definitions: {metadata['definitions_count']}, Metric records: {metadata['total_metric_records']}")
    print("\nReference parsing complete (no files written to disk).")

if __name__ == "__main__":
    import sys
    main()

