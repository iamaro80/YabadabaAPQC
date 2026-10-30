#!/usr/bin/env node
/**
 * YabadabaAPQC - Shared JavaScript Test Suite for PCF Workbook Parser.
 * Tests client-side decoding against all 6 reference workbooks using vendor/xlsx.full.min.js:
 * - Family A (2023): Healthcare Provider, Retail, City Government, Health Insurance Payor
 * - Family B (2026 v8.0): Cross-Industry, Consumer Products
 */

const fs = require("fs");
const path = require("path");
const XLSX = require(path.join(__dirname, "../vendor/xlsx.full.min.js"));

const PROJECT_DIR = path.join(__dirname, "..");
const FIXTURE_FILE = path.join(PROJECT_DIR, "data/workbooks_expected.json");

function normalizeHeader(h) {
  if (h === null || h === undefined) return "";
  return String(h)
    .trim()
    .toLowerCase()
    .replace(/[\r\n\t]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\?+$/, "")
    .trim();
}

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

    // Robust trailing NEW detection: case-insensitive, any whitespace around comma, optional trailing period
    const mNew = /,\s*new\s*\.?\s*$/i.exec(was_content);
    if (mNew) {
      was_content = was_content.slice(0, mNew.index).trim();
      is_new = true;
    } else {
      is_new = /\bNEW\b/i.test(prefix_part);
    }
    renamed_was = was_content;
  } else {
    if (/\bRENAME\b/i.test(raw)) {
      is_renamed = true;
    }
    is_new = /\bNEW\b/i.test(raw);
  }

  // Parse child tokens (+, -, c) as whole tokens only from prefix_part.
  // Split prefix on commas and match each token with ^[+\-c]\d+$
  const added = [];
  const removed = [];
  const changed = [];
  const tokens = prefix_part.split(",");
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i].trim();
    const m = /^([+\-c])(\d+)$/.exec(token);
    if (m) {
      const prefixChar = m[1];
      const childId = m[2];
      if (prefixChar === "+") added.push(childId);
      else if (prefixChar === "-") removed.push(childId);
      else if (prefixChar === "c") changed.push(childId);
    }
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

// ======================================================================
// STRATEGY IMPLEMENTATIONS: DEFINITIONS
// ======================================================================

const GlossarySheetDefinitions = {
  load(wb) {
    const sheetName = wb.SheetNames.find(s => s.toLowerCase().includes("glossary"));
    if (!sheetName || !wb.Sheets[sheetName]) return () => "";
    const rawRows = XLSX.utils.sheet_to_json(wb.Sheets[sheetName], { header: 1, defval: "" });
    if (!rawRows || rawRows.length === 0) return () => "";
    const headers = rawRows[0].map(normalizeHeader);
    const pidIdx = headers.indexOf("process element id") !== -1 ? headers.indexOf("process element id") : (headers.indexOf("pcf id") !== -1 ? headers.indexOf("pcf id") : 0);
    const hidIdx = headers.indexOf("hierarchy id") !== -1 ? headers.indexOf("hierarchy id") : 1;
    const defIdx = headers.indexOf("definition") !== -1 ? headers.indexOf("definition") : 3;

    const defsByPid = new Map();
    const defsByHid = new Map();
    for (let i = 1; i < rawRows.length; i++) {
      const r = rawRows[i];
      const pid = String(r[pidIdx] || "").trim();
      const hid = String(r[hidIdx] || "").trim();
      const d = String(r[defIdx] || "").trim();
      if (pid === "10001" && !hid) continue; // Ignore Root row
      if (pid) defsByPid.set(pid, d);
      if (hid) defsByHid.set(hid, d);
    }
    return (pcfId, hierarchyId) => defsByPid.get(pcfId) || defsByHid.get(hierarchyId) || "";
  }
};

const InlineColumnDefinitions = {
  load(wb) {
    return (pcfId, hierarchyId, row) => {
      if (!row) return "";
      return String(row["element description"] || row["definition"] || "").trim();
    };
  }
};

// ======================================================================
// STRATEGY IMPLEMENTATIONS: METRICS
// ======================================================================

const FlagOnlyMetrics = {
  load(wb) {
    return {
      resolver: () => [],
      totalRecords: 0
    };
  }
};

const MetricsSheetMetrics = {
  load(wb) {
    const sheetName = wb.SheetNames.find(s => s.trim().toLowerCase() === "metrics");
    if (!sheetName || !wb.Sheets[sheetName]) {
      return { resolver: () => [], totalRecords: 0 };
    }
    const rawRows = XLSX.utils.sheet_to_json(wb.Sheets[sheetName], { header: 1, defval: "" });
    if (!rawRows || rawRows.length === 0) return { resolver: () => [], totalRecords: 0 };

    const headers = rawRows[0].map(normalizeHeader);
    const pidIdx = headers.indexOf("process element id") !== -1 ? headers.indexOf("process element id") : 0;
    const hidIdx = headers.indexOf("hierarchy id") !== -1 ? headers.indexOf("hierarchy id") : 1;
    const catIdx = headers.indexOf("metric category") !== -1 ? headers.indexOf("metric category") : 3;
    const idIdx = headers.indexOf("metric id") !== -1 ? headers.indexOf("metric id") : 4;
    const nameIdx = headers.indexOf("metric name") !== -1 ? headers.indexOf("metric name") : 5;
    const formIdx = headers.indexOf("formula") !== -1 ? headers.indexOf("formula") : 6;
    const unitIdx = headers.indexOf("units") !== -1 ? headers.indexOf("units") : 7;

    const byHid = new Map();
    const byPid = new Map();
    let totalRecords = 0;

    for (let i = 1; i < rawRows.length; i++) {
      const r = rawRows[i];
      const name = String(r[nameIdx] || "").trim();
      if (!name) continue;
      const hid = String(r[hidIdx] || "").trim();
      const pid = String(r[pidIdx] || "").trim();
      const mCat = String(r[catIdx] || "").trim() || "General";
      const mId = String(r[idIdx] || "").trim();
      const formula = String(r[formIdx] || "").trim();
      const units = String(r[unitIdx] || "").trim();

      const metric = { category: mCat, id: mId, name, formula, units };
      if (hid) {
        if (!byHid.has(hid)) byHid.set(hid, []);
        byHid.get(hid).push(metric);
      }
      if (pid) {
        if (!byPid.has(pid)) byPid.set(pid, []);
        byPid.get(pid).push(metric);
      }
      totalRecords++;
    }

    return {
      resolver: (hierarchyId, pcfId) => byHid.get(hierarchyId) || (pcfId ? byPid.get(pcfId) : null) || [],
      totalRecords
    };
  }
};

// ======================================================================
// STRATEGY IMPLEMENTATIONS: VERSION INFO & ATTRIBUTION
// ======================================================================

const VersionInfoStrategy = {
  read(wb, filename = "") {
    let title = null;
    let version = null;
    let compared_to = null;
    let generated_on = null;

    const introName = wb.SheetNames.find(s => s.trim().toLowerCase() === "introduction");
    if (introName && wb.Sheets[introName]) {
      const rawRows = XLSX.utils.sheet_to_json(wb.Sheets[introName], { header: 1, defval: "" });
      for (const row of rawRows) {
        for (const cell of row) {
          if (!cell) continue;
          const text = String(cell).trim();
          const u = text.toUpperCase();
          if (u.includes("PROCESS CLASSIFICATION FRAMEWORK") && !title) {
            if (!u.startsWith("COMPARED TO")) {
              title = "APQC " + text.split(/\s+/).map(w => ["PCF", "APQC"].includes(w.toUpperCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
            }
          }
          const mVer = text.match(/VERSION\s+(?:NUMBER\s+)?([0-9]+(?:\.[0-9]+)*)/i);
          if (mVer && !version) {
            const val = mVer[1];
            version = val.startsWith("v") ? val : "v" + val;
          }
          const mComp = text.match(/COMPARED\s+TO.*?(?:VERSION\s+)?([0-9]+(?:\.[0-9]+)*)$/i);
          if (mComp && !compared_to) {
            const val = mComp[1];
            compared_to = val.startsWith("v") ? val : "v" + val;
          }
          const mGen = text.match(/GENERATED\s+ON\s+([0-9]+\/[0-9]+\/[0-9]+|[A-Za-z]+\s+[0-9]+,\s+[0-9]+|[0-9]{4}-[0-9]{2}-[0-9]{2})/i);
          if (mGen && !generated_on) {
            generated_on = mGen[1];
          }
        }
      }
    }

    const copyName = wb.SheetNames.find(s => s.toLowerCase().includes("copyright"));
    let copyYear = 2022;
    let attribution = '©2022 APQC. ALL RIGHTS RESERVED. This Process Classification Framework® ("PCF") is the copyrighted intellectual property of APQC.';
    if (copyName && wb.Sheets[copyName]) {
      const rawRows = XLSX.utils.sheet_to_json(wb.Sheets[copyName], { header: 1, defval: "" });
      for (const row of rawRows) {
        for (const cell of row) {
          if (!cell) continue;
          const text = String(cell).trim();
          const m = text.match(/©\s*([0-9]{4})/);
          if (m) {
            copyYear = parseInt(m[1], 10);
            attribution = text;
            break;
          }
        }
        if (copyYear !== 2022) break;
      }
    }

    return { title, version_label: version, compared_to, generated_on, copyright_year: copyYear, attribution };
  }
};

// ======================================================================
// LAYOUT PROFILES REGISTRY
// ======================================================================

const LAYOUT_PROFILES = [
  {
    id: "family-b-2026",
    label: "2026 v8.0 (Inline Definitions & Metrics Sheet)",
    detect: (sNames, headers) => sNames.includes("combined") && sNames.includes("metrics") && headers.includes("element description"),
    definitionSource: InlineColumnDefinitions,
    metricsSource: MetricsSheetMetrics,
    defaultOperating: ["1", "2", "3", "4", "5", "6"]
  },
  {
    id: "family-a-2023",
    label: "2023 Comparison (Glossary Sheet & Flag-Only Metrics)",
    detect: (sNames, headers) => sNames.includes("combined") && sNames.some(s => s.includes("glossary")),
    definitionSource: GlossarySheetDefinitions,
    metricsSource: FlagOnlyMetrics,
    defaultOperating: ["1", "2", "3", "4", "5"]
  }
];

function detectLayout(sheetNames, headers) {
  const sLower = sheetNames.map(s => s.trim().toLowerCase());
  if (!sLower.some(s => s.includes("combined"))) {
    throw new Error("Missing required worksheet: 'Combined'");
  }
  const hLower = headers.map(normalizeHeader);
  for (const p of LAYOUT_PROFILES) {
    if (p.detect(sLower, hLower)) return p;
  }
  throw new Error(
    "Unknown workbook layout.\n" +
    "Sheets found: " + JSON.stringify(sheetNames) + "\n" +
    "Combined headers found: " + JSON.stringify(headers) + "\n" +
    "Expected either:\n" +
    "  - Family A (2023 comparison): Sheets 'Combined' and 'Glossary terms'\n" +
    "  - Family B (2026 v8.0): Sheets 'Combined' and 'Metrics' with 'Element Description' in Combined"
  );
}

// ======================================================================
// SHARED CANONICAL PIPELINE
// ======================================================================

function parsePCFWorkbook(workbookData, fileName = "", options = {}) {
  let wb;
  if (typeof workbookData === "object" && workbookData.SheetNames) {
    wb = workbookData;
  } else {
    wb = XLSX.read(workbookData, { type: Buffer.isBuffer(workbookData) ? "buffer" : "array" });
  }

  const combName = wb.SheetNames.find(s => s.toLowerCase().includes("combined"));
  if (!combName || !wb.Sheets[combName]) {
    throw new Error("Missing required worksheet: 'Combined'");
  }

  const combWs = wb.Sheets[combName];
  const rawRows = XLSX.utils.sheet_to_json(combWs, { header: 1, defval: "" });
  if (!rawRows || rawRows.length === 0) {
    throw new Error("Worksheet 'Combined' has no rows");
  }

  const rawHeaders = rawRows[0];
  const normalizedHeaders = rawHeaders.map(normalizeHeader);

  const profile = detectLayout(wb.SheetNames, rawHeaders);

  const findIdx = (aliases) => {
    for (const a of aliases) {
      const idx = normalizedHeaders.indexOf(a);
      if (idx !== -1) return idx;
    }
    return -1;
  };

  const pcfIdx = findIdx(["pcf id", "process element id", "element id"]);
  const hidIdx = findIdx(["hierarchy id", "hierarchy"]);
  const nameIdx = findIdx(["name", "process element", "process name", "element name"]);
  const diffIdx = findIdx(["difference index", "diff index"]);
  const chIdx = findIdx(["change details", "change detail"]);
  const mFlagIdx = findIdx(["metrics available", "metrics available?"]);
  const descIdx = findIdx(["element description", "definition", "description"]);

  if (hidIdx === -1) throw new Error("Worksheet 'Combined' is missing required 'Hierarchy ID' column");

  const combinedRecords = [];
  for (let i = 1; i < rawRows.length; i++) {
    const r = rawRows[i];
    const hid = String(hidIdx !== -1 && r[hidIdx] !== undefined ? r[hidIdx] : "").trim();
    if (!hid) continue;
    combinedRecords.push({
      pcf_id: String(pcfIdx !== -1 && r[pcfIdx] !== undefined ? r[pcfIdx] : "").trim(),
      hierarchy_id: hid,
      name: String(nameIdx !== -1 && r[nameIdx] !== undefined ? r[nameIdx] : "").trim(),
      diff_index: parseInt(diffIdx !== -1 && r[diffIdx] !== undefined ? r[diffIdx] : 0, 10) || 0,
      metrics_available: ["Y", "YES"].includes(String(mFlagIdx !== -1 && r[mFlagIdx] !== undefined ? r[mFlagIdx] : "").trim().toUpperCase()),
      change_details: String(chIdx !== -1 && r[chIdx] !== undefined ? r[chIdx] : "").trim(),
      "element description": String(descIdx !== -1 && r[descIdx] !== undefined ? r[descIdx] : "").trim()
    });
  }

  const defResolver = profile.definitionSource.load(wb, combinedRecords);
  const { resolver: metricResolver, totalRecords: totalMetricRecords } = profile.metricsSource.load(wb);
  const vInfo = VersionInfoStrategy.read(wb, fileName);

  let opCats;
  if (options.operatingCategories) {
    opCats = new Set(Array.from(options.operatingCategories).map(String));
  } else {
    const isRetail = fileName.toLowerCase().includes("retail") || (vInfo.title && vInfo.title.toLowerCase().includes("retail"));
    if (isRetail) {
      opCats = new Set(["1", "2", "3", "4", "5", "6"]);
    } else {
      opCats = new Set(profile.defaultOperating);
    }
  }

  const elements = [];
  const categoryMap = new Map();
  const levelNames = {
    1: "Category",
    2: "Process group",
    3: "Process",
    4: "Activity",
    5: "Task"
  };

  combinedRecords.forEach(row => {
    const hierarchy_id = row.hierarchy_id;
    const parts = hierarchy_id.split(".");
    let level = parts.length;
    const category_num = parts[0];

    if (!/^\d+$/.test(category_num)) {
      throw new Error(`Invalid Hierarchy ID "${hierarchy_id}": category segment must be a numeric integer.`);
    }

    const is_category_root = (level === 2 && parts[1] === "0");
    let level_name = "";
    let parent_hid = "";

    if (is_category_root) {
      level = 1;
      level_name = "Category";
      parent_hid = "";
    } else {
      level_name = levelNames[level] || `Level ${level}`;
      parent_hid = parts.length > 1 ? parts.slice(0, -1).join(".") : "";
      if (parts.length === 2 && parts[1] !== "0") {
        parent_hid = `${parts[0]}.0`;
      }
    }

    const pcf_id = row.pcf_id;
    const name = row.name;
    const diff_index = row.diff_index;
    const metrics_available = row.metrics_available;
    const changeInfo = decodeChanges(row.change_details);
    const process_type = opCats.has(category_num) ? "Operating Processes" : "Management & Support Services";

    const definition = defResolver(pcf_id, hierarchy_id, row);
    const metricsList = metricResolver(hierarchy_id, pcf_id);

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
      definition,
      change_details: changeInfo.raw_changes,
      has_changes: changeInfo.has_changes,
      is_new: changeInfo.is_new,
      is_renamed: changeInfo.is_renamed,
      renamed_was: changeInfo.renamed_was,
      added_children: changeInfo.added_children,
      removed_children: changeInfo.removed_children,
      changed_children: changeInfo.changed_children,
      metrics: metricsList
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

  const categories = [];
  const sortedCatNums = Array.from(categoryMap.keys()).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
  sortedCatNums.forEach(catNum => {
    const catInfo = categoryMap.get(catNum);
    const catElements = elements.filter(e => e.category_id === catNum);
    const totalCount = catElements.length;
    const newCount = catElements.filter(e => e.is_new).length;
    const renamedCount = catElements.filter(e => e.is_renamed).length;
    const changesCount = catElements.filter(e => e.has_changes).length;
    const metricsCount = catElements.filter(e => e.metrics_available).length;
    const maxDiff = catElements.reduce((max, e) => Math.max(max, e.diff_index), 0);
    const sumDiff = catElements.reduce((sum, e) => sum + e.diff_index, 0);

    categories.push({
      category_id: catNum,
      hierarchy_id: catInfo.hierarchy_id,
      pcf_id: catInfo.pcf_id,
      name: catInfo.name,
      process_type: catInfo.process_type,
      total_elements: totalCount,
      elements_with_changes: changesCount,
      new_elements: newCount,
      renamed_elements: renamedCount,
      metrics_available: metricsCount,
      max_diff_index: maxDiff,
      sum_diff_index: sumDiff
    });
  });

  const frameworkTitle = vInfo.title || (
    fileName.toLowerCase().includes("healthcare") ? "APQC Healthcare Provider PCF" :
    (fileName.toLowerCase().includes("retail") ? "APQC Retail PCF" :
    (fileName.toLowerCase().includes("city") ? "APQC City Government PCF" :
    (fileName.toLowerCase().includes("payor") || fileName.toLowerCase().includes("insurance") ? "APQC Health Insurance Payor PCF" :
    "APQC Process Classification Framework")))
  );

  const versionText = vInfo.version_label || (
    fileName.toLowerCase().includes("healthcare") ? "7.2.1 vs 6.1.1 (April 2023)" :
    (fileName.includes("721") ? "v7.2.1" : "v8.0")
  );

  const metadata = {
    source_document: fileName,
    source_layout: profile.id,
    layout_label: profile.label,
    framework: frameworkTitle,
    version: versionText,
    version_label: vInfo.version_label || "v7.2.1",
    compared_to: vInfo.compared_to,
    generated_on: vInfo.generated_on,
    copyright_year: vInfo.copyright_year,
    attribution: vInfo.attribution,
    total_elements: elements.length,
    total_with_changes: elements.filter(e => e.has_changes).length,
    total_new: elements.filter(e => e.is_new).length,
    total_renamed: elements.filter(e => e.is_renamed).length,
    total_with_metrics: elements.filter(e => e.metrics_available).length,
    total_metric_records: totalMetricRecords,
    definitions_count: elements.filter(e => e.definition && e.definition.trim().length > 0).length,
    categories_count: categories.length
  };

  return { metadata, categories, elements };
}

// Check for --dump-json argument
const dumpIdx = process.argv.indexOf("--dump-json");
if (dumpIdx !== -1 && dumpIdx + 2 < process.argv.length) {
  const targetKey = process.argv[dumpIdx + 1];
  const dumpFilePath = process.argv[dumpIdx + 2];
  const expectedFixture = JSON.parse(fs.readFileSync(FIXTURE_FILE, "utf-8"));
  const targetInfo = expectedFixture[targetKey];
  if (!targetInfo) {
    console.error(`Target key "${targetKey}" not found in fixture.`);
    process.exit(1);
  }
  const fullPath = path.join(PROJECT_DIR, targetInfo.filename);
  const buf = fs.readFileSync(fullPath);
  const parsed = parsePCFWorkbook(buf, targetInfo.filename);
  fs.writeFileSync(dumpFilePath, JSON.stringify(parsed), "utf-8");
  process.exit(0);
}

// ======================================================================
// MAIN TEST SUITE
// ======================================================================

function runTests() {
  console.log("======================================================================");
  console.log("RUNNING JAVASCRIPT WORKBOOK PARSER TEST SUITE (6 WORKBOOKS)");
  console.log("======================================================================");

  const expectedFixture = JSON.parse(fs.readFileSync(FIXTURE_FILE, "utf-8"));

  // 1. Test All Six Workbooks against Fixture
  console.log("\n1. Testing All 6 Workbooks Against Fixture Table");
  for (const key of Object.keys(expectedFixture)) {
    const exp = expectedFixture[key];
    const fullPath = path.join(PROJECT_DIR, exp.filename);
    const buf = fs.readFileSync(fullPath);
    const res = parsePCFWorkbook(buf, exp.filename);
    const meta = res.metadata;
    const elems = res.elements;

    console.log(`\n• Testing ${exp.name} (${exp.filename}):`);
    console.log(`  - Elements: ${elems.length} (Expected: ${exp.elements})`);
    console.log(`  - Layout Profile: ${meta.source_layout} (Expected: ${exp.layout_profile})`);
    console.log(`  - New Elements: ${meta.total_new} (Expected: ${exp.new_count})`);
    console.log(`  - Renamed Elements: ${meta.total_renamed} (Expected: ${exp.renamed_count})`);
    console.log(`  - With Changes: ${meta.total_with_changes} (Expected: ${exp.with_changes})`);
    console.log(`  - Metrics Available = Y: ${meta.total_with_metrics} (Expected: ${exp.metrics_y})`);
    console.log(`  - Definitions: ${meta.definitions_count} (Expected: ${exp.definitions_non_empty || exp.definitions_count})`);
    console.log(`  - Metric Rows: ${meta.total_metric_records} (Expected: ${exp.metric_rows})`);

    if (elems.length !== exp.elements) throw new Error(`${exp.name}: Elements mismatch`);
    if (meta.source_layout !== exp.layout_profile) throw new Error(`${exp.name}: Layout profile mismatch`);
    if (meta.total_new !== exp.new_count) throw new Error(`${exp.name}: New mismatch`);
    if (meta.total_renamed !== exp.renamed_count) throw new Error(`${exp.name}: Renamed mismatch`);
    if (meta.total_with_changes !== exp.with_changes) throw new Error(`${exp.name}: Changes mismatch`);
    if (meta.total_with_metrics !== exp.metrics_y) throw new Error(`${exp.name}: Metrics Y mismatch`);
    if (meta.definitions_count !== (exp.definitions_non_empty || exp.definitions_count)) throw new Error(`${exp.name}: Definitions mismatch`);
    if (meta.total_metric_records !== exp.metric_rows) throw new Error(`${exp.name}: Metric rows mismatch`);

    const levelsPresent = Array.from(new Set(elems.map(e => e.level))).sort((a, b) => a - b);
    if (JSON.stringify(levelsPresent) !== JSON.stringify(exp.levels)) throw new Error(`${exp.name}: Levels mismatch`);

    if (exp.level_6_count) {
      const l6Count = elems.filter(e => e.level === 6).length;
      if (l6Count !== exp.level_6_count) throw new Error(`${exp.name}: Level 6 count mismatch: ${l6Count} vs ${exp.level_6_count}`);
      console.log(`  - Level 6 Elements: ${l6Count} (Expected: ${exp.level_6_count})`);
    }

    console.log(`  ✓ ${exp.name} passed 100%.`);
  }

  // 2. Test Layout Detection Without Filename (Renamed Copies)
  console.log("\n2. Testing Layout Detection (Structure-Based, No Filename Dependency)");
  for (const key of Object.keys(expectedFixture)) {
    const exp = expectedFixture[key];
    const fullPath = path.join(PROJECT_DIR, exp.filename);
    const buf = fs.readFileSync(fullPath);
    // Pass completely random dummy filename
    const dummyName = "random_unrelated_name_12345.xlsx";
    const res = parsePCFWorkbook(buf, dummyName);
    if (res.metadata.source_layout !== exp.layout_profile) {
      throw new Error(`Structure-based detection failed for ${exp.name} under dummy filename.`);
    }
  }
  console.log("  ✓ All 6 workbooks correctly detected with arbitrary filenames.");

  // 3. Test Unknown Layout Actionable Error
  console.log("\n3. Testing Actionable Error on Unknown Layout");
  let caughtUnknown = false;
  try {
    const dummyWb = { SheetNames: ["Sheet1", "Summary"], Sheets: { Sheet1: {}, Summary: {} } };
    parsePCFWorkbook(dummyWb, "unknown.xlsx");
  } catch (err) {
    caughtUnknown = true;
    const msg = err.message;
    if (!msg.includes("Missing required worksheet: 'Combined'")) {
      throw new Error(`Unexpected error message for missing combined: ${msg}`);
    }
    console.log(`  ✓ Caught missing Combined: "${msg}"`);
  }
  if (!caughtUnknown) throw new Error("Failed to catch missing Combined error");

  let caughtLayoutError = false;
  try {
    const dummyWb = {
      SheetNames: ["Introduction", "Combined"],
      Sheets: {
        Introduction: {},
        Combined: XLSX.utils.aoa_to_sheet([["Col A", "Col B"], [1, 2]])
      }
    };
    parsePCFWorkbook(dummyWb, "unknown_layout.xlsx");
  } catch (err) {
    caughtLayoutError = true;
    const msg = err.message;
    if (!msg.includes("Unknown workbook layout") || !msg.includes("Expected either")) {
      throw new Error(`Actionable layout error missing expected guidance: ${msg}`);
    }
    console.log("  ✓ Actionable layout error correctly reported:");
    console.log("    " + msg.split("\n").join("\n    "));
  }
  if (!caughtLayoutError) throw new Error("Failed to catch unknown layout error");

  // 4. Test Introduction Sheet Parsing
  console.log("\n4. Testing Introduction Sheet Parsing Across Families");
  const ciBuf = fs.readFileSync(path.join(PROJECT_DIR, expectedFixture.cross_industry.filename));
  const ciWb = XLSX.read(ciBuf, { type: "buffer" });
  const ciIntro = VersionInfoStrategy.read(ciWb, expectedFixture.cross_industry.filename);
  console.log("  • Cross-Industry Intro:", ciIntro);
  if (ciIntro.version_label !== "v8.0" || ciIntro.compared_to !== "v7.4" || ciIntro.generated_on !== "2/25/2026") {
    throw new Error("Cross-Industry intro parse mismatch");
  }

  const cpBuf = fs.readFileSync(path.join(PROJECT_DIR, expectedFixture.consumer_products.filename));
  const cpWb = XLSX.read(cpBuf, { type: "buffer" });
  const cpIntro = VersionInfoStrategy.read(cpWb, expectedFixture.consumer_products.filename);
  console.log("  • Consumer Products Intro:", cpIntro);
  if (cpIntro.version_label !== "v8.0" || cpIntro.compared_to !== "v7.2.1" || cpIntro.generated_on !== null) {
    throw new Error("Consumer Products intro parse mismatch");
  }
  console.log("  ✓ Introduction parsing verified.");

  // 5. Test Header Normalization
  console.log("\n5. Testing Header Normalization");
  const variations = ["Change Details", "Change details", " Change  Details? ", "CHANGE DETAILS?", "Change\nDetails\r\n"];
  for (const v of variations) {
    const norm = normalizeHeader(v);
    if (norm !== "change details") throw new Error(`Header norm mismatch for '${v}': '${norm}'`);
  }
  if (normalizeHeader("Metric ID\r\n") !== "metric id") throw new Error("Metric ID newline strip failed");
  console.log("  ✓ All header normalization variations verified.");

  // 6. Test decodeChanges Unit Test Edge Cases
  console.log("\n6. Testing decodeChanges Unit Test Edge Cases");
  const edgeCases = [
    {
      input: "-10381, c10383, RENAME, WAS:Foo-123, NEW",
      exp: { added: [], removed: ["10381"], changed: ["10383"], was: "Foo-123", is_new: true, is_renamed: true }
    },
    {
      input: "WAS:Foo , new",
      exp: { added: [], removed: [], changed: [], was: "Foo", is_new: true, is_renamed: true }
    },
    {
      input: "+1, +2",
      exp: { added: ["1", "2"], removed: [], changed: [], was: "", is_new: false, is_renamed: false }
    }
  ];

  for (const tc of edgeCases) {
    const res = decodeChanges(tc.input);
    if (JSON.stringify(res.added_children) !== JSON.stringify(tc.exp.added) ||
        JSON.stringify(res.removed_children) !== JSON.stringify(tc.exp.removed) ||
        JSON.stringify(res.changed_children) !== JSON.stringify(tc.exp.changed) ||
        res.renamed_was !== tc.exp.was ||
        res.is_new !== tc.exp.is_new ||
        res.is_renamed !== tc.exp.is_renamed) {
      throw new Error(`decodeChanges failed on '${tc.input}': ${JSON.stringify(res)}`);
    }
  }

  // Real WAS samples with commas from all 6 workbooks
  for (const key of Object.keys(expectedFixture)) {
    const sample = expectedFixture[key].was_sample_with_commas;
    const res = decodeChanges(sample.raw);
    if (res.renamed_was !== sample.expected_was) {
      throw new Error(`decodeChanges failed on ${key} comma sample: got '${res.renamed_was}', expected '${sample.expected_was}'`);
    }
    console.log(`  ✓ Sample from ${expectedFixture[key].name} passed: '${res.renamed_was.slice(0, 45)}...'`);
  }
  console.log("  ✓ All decodeChanges unit test edge cases passed.");

  console.log("\n======================================================================");
  console.log("ALL JAVASCRIPT WORKBOOK PARSER TESTS PASSED 100%");
  console.log("======================================================================");
}

runTests();
