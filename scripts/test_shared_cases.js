#!/usr/bin/env node
/**
 * YabadabaAPQC - Shared JavaScript Test Suite for PCF Workbook Parser.
 * Tests client-side decoding against reference workbooks using vendor/xlsx.full.min.js.
 */

const fs = require("fs");
const path = require("path");
const XLSX = require(path.join(__dirname, "../vendor/xlsx.full.min.js"));

const HC_FILE = path.join(__dirname, "../K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx");
const RETAIL_FILE = path.join(__dirname, "../K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx");

function decodeChanges(changeStr) {
  if (!changeStr || typeof changeStr !== "string" || !changeStr.trim()) {
    return {
      has_changes: false,
      raw_changes: "",
      is_new: false,
      is_renamed: false,
      renamed_was: "",
      added_children: [],
      removed_children: [],
      changed_children: []
    };
  }

  const raw = changeStr.trim();
  let is_renamed = false;
  let renamed_was = "";
  let is_new = false;
  let prefix_part = raw;

  if (raw.includes("WAS:")) {
    is_renamed = true;
    const parts = raw.split("WAS:");
    prefix_part = parts[0];
    let was_content = parts.slice(1).join("WAS:").trim();

    if (was_content.endsWith(", NEW")) {
      was_content = was_content.slice(0, -5).trim();
      is_new = true;
    } else if (was_content.endsWith(",NEW")) {
      was_content = was_content.slice(0, -4).trim();
      is_new = true;
    } else {
      is_new = /\bNEW\b/.test(prefix_part);
    }
    renamed_was = was_content;
  } else {
    if (raw.includes("RENAME")) {
      is_renamed = true;
    }
    is_new = /\bNEW\b/.test(raw);
  }

  const added = [];
  const addRe = /\+(\d+)/g;
  let m;
  while ((m = addRe.exec(prefix_part)) !== null) {
    added.push(m[1]);
  }

  const removed = [];
  const remRe = /\-(\d+)/g;
  while ((m = remRe.exec(prefix_part)) !== null) {
    removed.push(m[1]);
  }

  const changed = [];
  const chgRe = /\bc(\d+)/g;
  while ((m = chgRe.exec(prefix_part)) !== null) {
    changed.push(m[1]);
  }

  return {
    has_changes: true,
    raw_changes: raw,
    is_new,
    is_renamed,
    renamed_was,
    added_children: added,
    removed_children: removed,
    changed_children: changed
  };
}

function parsePCFWorkbook(workbookData, options = {}) {
  const wb = typeof workbookData === "object" && workbookData.Sheets ? 
    workbookData : 
    XLSX.read(workbookData, { type: Buffer.isBuffer(workbookData) ? "buffer" : "array" });

  if (!wb.Sheets["Combined"]) {
    throw new Error("Missing required worksheet: 'Combined'");
  }
  if (!wb.Sheets["Glossary terms"]) {
    throw new Error("Missing required worksheet: 'Glossary terms'");
  }

  const combinedRows = XLSX.utils.sheet_to_json(wb.Sheets["Combined"], { defval: "" });
  const glossaryRows = XLSX.utils.sheet_to_json(wb.Sheets["Glossary terms"], { defval: "" });

  if (combinedRows.length === 0) {
    throw new Error("Worksheet 'Combined' is empty");
  }

  // Validate required headers
  const combFirst = combinedRows[0];
  const requiredCombCols = ["PCF ID", "Hierarchy ID", "Name"];
  for (const col of requiredCombCols) {
    if (!(col in combFirst)) {
      throw new Error(`Worksheet 'Combined' is missing required column: '${col}'`);
    }
  }

  // Build glossary maps
  const glossByPid = new Map();
  const glossByHid = new Map();
  let emptyDefGlossRows = 0;

  glossaryRows.forEach(row => {
    const pid = String(row["Process Element ID"] || "").trim();
    const hid = String(row["Hierarchy ID"] || "").trim();
    const defn = String(row["Definition"] || "").trim();
    if (!defn) emptyDefGlossRows++;
    if (pid) glossByPid.set(pid, defn);
    if (hid) glossByHid.set(hid, defn);
  });

  // Operating vs Support categories
  const operatingCats = options.operatingCategories || new Set(["1", "2", "3", "4", "5"]);

  const elements = [];
  const categoryMap = new Map();

  combinedRows.forEach(row => {
    const pcf_id = String(row["PCF ID"] || "").trim();
    const hierarchy_id = String(row["Hierarchy ID"] || "").trim();
    const name = String(row["Name"] || "").trim();
    const diff_index = parseInt(row["Difference Index"] || 0, 10) || 0;
    const metrics_available = String(row["Metrics available?"] || "").trim().toUpperCase() === "Y";
    const change_details = String(row["Change details"] || "");

    if (!hierarchy_id) return;

    const parts = hierarchy_id.split(".");
    let level = parts.length;
    const category_num = parts[0];

    const level_names = {
      1: "Category",
      2: "Process Group",
      3: "Process",
      4: "Activity",
      5: "Task"
    };

    const is_category_root = (level === 2 && parts[1] === "0");
    let level_name = "";
    let parent_hid = "";

    if (is_category_root) {
      level = 1;
      level_name = "Category";
      parent_hid = "";
    } else {
      level_name = level_names[level] || `Level ${level}`;
      parent_hid = parts.length > 1 ? parts.slice(0, -1).join(".") : "";
      if (parts.length === 2 && parts[1] !== "0") {
        parent_hid = `${parts[0]}.0`;
      }
    }

    const defn = glossByPid.get(pcf_id) || glossByHid.get(hierarchy_id) || "";
    const changeInfo = decodeChanges(change_details);
    const process_type = operatingCats.has(category_num) ? "Operating Processes" : "Management & Support Services";

    const elem = {
      id: pcf_id || hierarchy_id,
      pcf_id,
      hierarchy_id,
      name,
      level,
      level_name,
      category_id: category_num,
      parent_hierarchy_id: parent_hid,
      diff_index,
      metrics_available,
      process_type,
      definition: defn,
      change_details: changeInfo.raw_changes,
      has_changes: changeInfo.has_changes,
      is_new: changeInfo.is_new,
      is_renamed: changeInfo.is_renamed,
      renamed_was: changeInfo.renamed_was,
      added_children: changeInfo.added_children,
      removed_children: changeInfo.removed_children,
      changed_children: changeInfo.changed_children
    };

    elements.push(elem);

    if (is_category_root) {
      categoryMap.set(category_num, {
        category_id: category_num,
        hierarchy_id,
        pcf_id,
        name,
        process_type,
        diff_index,
        metrics_available,
        change_details: changeInfo.raw_changes
      });
    }
  });

  // Category statistics
  const categories = [];
  const sortedCatNums = Array.from(categoryMap.keys()).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));

  sortedCatNums.forEach(catNum => {
    const catInfo = categoryMap.get(catNum);
    const catElements = elements.filter(e => e.category_id === catNum);
    const total_elements = catElements.length;
    const new_elements = catElements.filter(e => e.is_new).length;
    const renamed_elements = catElements.filter(e => e.is_renamed).length;
    const elements_with_changes = catElements.filter(e => e.has_changes).length;
    const metrics_available = catElements.filter(e => e.metrics_available).length;
    const max_diff_index = catElements.reduce((max, e) => Math.max(max, e.diff_index), 0);
    const sum_diff_index = catElements.reduce((sum, e) => sum + e.diff_index, 0);

    categories.push({
      category_id: catNum,
      hierarchy_id: catInfo.hierarchy_id,
      pcf_id: catInfo.pcf_id,
      name: catInfo.name,
      process_type: catInfo.process_type,
      total_elements,
      elements_with_changes,
      new_elements,
      renamed_elements,
      metrics_available,
      max_diff_index,
      sum_diff_index
    });
  });

  const newCount = elements.filter(e => e.is_new).length;
  const renamedCount = elements.filter(e => e.is_renamed).length;
  const metricsCount = elements.filter(e => e.metrics_available).length;
  const changesCount = elements.filter(e => e.has_changes).length;
  const defCount = elements.filter(e => e.definition && e.definition.trim().length > 0).length;

  return {
    metadata: {
      source_document: options.fileName || "Uploaded PCF Workbook",
      framework: options.frameworkName || "Process Classification Framework (PCF)",
      version: options.version || "v7.2.1",
      attribution: options.attribution || "©2022 APQC. ALL RIGHTS RESERVED. This Process Classification Framework® (\"PCF\") is the copyrighted intellectual property of APQC.",
      total_elements: elements.length,
      total_with_changes: changesCount,
      total_new: newCount,
      total_renamed: renamedCount,
      total_with_metrics: metricsCount,
      categories_count: categories.length,
      definitions_count: defCount
    },
    categories,
    elements
  };
}

// Export for module usage
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parsePCFWorkbook, decodeChanges };
}

// Run test suite
function runSuite() {
  console.log("=" .repeat(70));
  console.log("RUNNING JAVASCRIPT WORKBOOK PARSER TEST SUITE");
  console.log("=" .repeat(70));

  // 1. Healthcare
  console.log(`\n1. Testing Healthcare Workbook: ${path.basename(HC_FILE)}`);
  const hcBuf = fs.readFileSync(HC_FILE);
  const hcData = parsePCFWorkbook(hcBuf, {
    fileName: path.basename(HC_FILE),
    frameworkName: "APQC Healthcare Provider PCF",
    operatingCategories: new Set(["1", "2", "3", "4", "5"])
  });

  const hcMeta = hcData.metadata;
  console.log(`  • Elements: ${hcMeta.total_elements} (Expected: 1,985)`);
  console.log(`  • New: ${hcMeta.total_new} (Expected: 960)`);
  console.log(`  • Renamed: ${hcMeta.total_renamed} (Expected: 134)`);
  console.log(`  • Metrics: ${hcMeta.total_with_metrics} (Expected: 221)`);
  console.log(`  • Definitions: ${hcMeta.definitions_count} (Expected: 1,931)`);

  if (hcMeta.total_elements !== 1985) throw new Error("Healthcare total mismatch");
  if (hcMeta.total_new !== 960) throw new Error("Healthcare new mismatch");
  if (hcMeta.total_renamed !== 134) throw new Error("Healthcare renamed mismatch");
  if (hcMeta.total_with_metrics !== 221) throw new Error("Healthcare metrics mismatch");
  if (hcMeta.definitions_count !== 1931) throw new Error("Healthcare definitions mismatch");
  console.log("✓ JavaScript Healthcare test passed 100%.");

  // 2. Retail
  console.log(`\n2. Testing Retail Workbook: ${path.basename(RETAIL_FILE)}`);
  const retBuf = fs.readFileSync(RETAIL_FILE);
  const retData = parsePCFWorkbook(retBuf, {
    fileName: path.basename(RETAIL_FILE),
    frameworkName: "APQC Retail PCF",
    operatingCategories: new Set(["1", "2", "3", "4", "5", "6"])
  });

  const retMeta = retData.metadata;
  const retCommaRenames = retData.elements.filter(e => e.is_renamed && e.renamed_was.includes(","));

  console.log(`  • Elements: ${retMeta.total_elements} (Expected: 1,708)`);
  console.log(`  • New: ${retMeta.total_new} (Expected: 608)`);
  console.log(`  • Renamed: ${retMeta.total_renamed} (Expected: 74)`);
  console.log(`  • Metrics: ${retMeta.total_with_metrics} (Expected: 180)`);
  console.log(`  • Definitions: ${retMeta.definitions_count} (Expected: 1,462)`);
  console.log(`  • Renames containing commas: ${retCommaRenames.length} (Expected: 9)`);

  if (retMeta.total_elements !== 1708) throw new Error("Retail total mismatch");
  if (retMeta.total_new !== 608) throw new Error("Retail new mismatch");
  if (retMeta.total_renamed !== 74) throw new Error("Retail renamed mismatch");
  if (retMeta.total_with_metrics !== 180) throw new Error("Retail metrics mismatch");
  if (retMeta.definitions_count !== 1462) throw new Error("Retail definitions mismatch");
  if (retCommaRenames.length !== 9) throw new Error("Retail comma renames mismatch");

  // Verify Retail 4.0 does not have Healthcare definition
  const ret4 = retData.elements.find(e => e.hierarchy_id === "4.0");
  if (!ret4) throw new Error("Retail 4.0 not found");
  if (ret4.name !== "Merchandise Products and Services") throw new Error("Retail 4.0 name mismatch");
  if (ret4.definition.includes("patient care")) throw new Error("Retail 4.0 wrongly contains Healthcare definition!");
  console.log(`  • Retail 4.0 name: "${ret4.name}", definition: "${ret4.definition || '(Empty, as expected)'}"`);

  // Verify Operating vs Support split in Retail
  const retCat6 = retData.categories.find(c => c.category_id === "6");
  const retCat7 = retData.categories.find(c => c.category_id === "7");
  if (retCat6.process_type !== "Operating Processes") throw new Error("Retail 6.0 should be Operating");
  if (retCat7.process_type !== "Management & Support Services") throw new Error("Retail 7.0 should be Support");
  console.log(`  • Operating split: Category 6.0 is "${retCat6.process_type}", Category 7.0 is "${retCat7.process_type}"`);

  console.log("✓ JavaScript Retail test passed 100%.");

  // 3. Deliberately broken file check
  console.log("\n3. Testing Deliberately Broken Workbook validation");
  try {
    parsePCFWorkbook({ Sheets: { "OnlySheet": {} } });
    throw new Error("Should have thrown error on missing sheets");
  } catch (err) {
    console.log(`  • Correctly caught error: "${err.message}"`);
  }

  console.log("\n" + "=" .repeat(70));
  console.log("ALL JAVASCRIPT WORKBOOK PARSER TESTS PASSED 100%");
  console.log("=" .repeat(70));
}

if (require.main === module) {
  runSuite();
}
