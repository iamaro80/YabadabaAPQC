#!/usr/bin/env python3
"""
Comprehensive End-to-End Browser Verification & Screenshot Capture for APQC PCF Navigator.
Tests Phases 1A–1D & Phase 3 (Refreshed UI, Theme, Keyboard Nav, Performance, Contrast).
Captures all 8 required screenshots under docs/screenshots/.
"""

import os
import sys
import time
import json
import base64
import urllib.request
import subprocess
import signal

PORT = 8765
CHROME_PORT = 9222
HTTP_URL = f"http://127.0.0.1:{PORT}/index.html"
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(PROJECT_DIR, "docs", "screenshots")

def start_server():
    print(f"Starting HTTP server on port {PORT}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1)
    return proc

def start_chrome():
    print(f"Starting headless Chrome on debug port {CHROME_PORT}...")
    chrome_cmd = [
        "/usr/bin/google-chrome",
        "--headless=new",
        f"--remote-debugging-port={CHROME_PORT}",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        HTTP_URL
    ]
    proc = subprocess.Popen(
        chrome_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    return proc

def get_websocket_url():
    url = f"http://127.0.0.1:{CHROME_PORT}/json"
    for _ in range(25):
        try:
            req = urllib.request.urlopen(url)
            pages = json.loads(req.read().decode())
            for p in pages:
                if p.get("type") == "page":
                    return p["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError("Could not connect to Chrome debugging endpoint")

class CDPClient:
    def __init__(self, ws_url):
        import websocket
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.msg_id = 0
        self.console_errors = []

    def send(self, method, params=None):
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))
        while True:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if "method" in msg:
                if msg["method"] == "Runtime.consoleAPICalled":
                    if msg["params"]["type"] == "error":
                        self.console_errors.append(msg["params"])
                continue
            if msg.get("id") == self.msg_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP Error in {method}: {msg['error']}")
                return msg.get("result", {})

    def evaluate(self, expr):
        res = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True
        })
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS Exception evaluating: {res['exceptionDetails']}")
        val = res.get("result", {})
        if val.get("type") == "undefined":
            return None
        return val.get("value")

    def set_viewport(self, width, height, mobile=False):
        self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": mobile
        })
        time.sleep(0.4)

    def capture_screenshot(self, filename):
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        res = self.send("Page.captureScreenshot", {"format": "png"})
        raw_b64 = res.get("data", "")
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(raw_b64))
        print(f"  ✓ Saved screenshot: docs/screenshots/{filename} ({os.path.getsize(filepath):,} bytes)")

    def wait_for_load(self):
        self.send("Page.enable")
        self.send("Runtime.enable")
        t_start = time.time()
        ready = False
        while time.time() - t_start < 15:
            time.sleep(0.4)
            try:
                res = self.evaluate("Boolean(window.state && window.state.data && window.state.data.elements)")
                if res:
                    ready = True
                    break
            except Exception:
                pass
        if not ready:
            raise RuntimeError("Page did not load window.state.data within 15 seconds")
        time.sleep(0.5)

    def close(self):
        self.ws.close()

def run_tests():
    server_proc = start_server()
    chrome_proc = start_chrome()

    try:
        ws_url = get_websocket_url()
        client = CDPClient(ws_url)
        client.wait_for_load()
        print("Connected to Chrome and loaded page.")

        # Set default desktop viewport 1440x900
        client.set_viewport(1440, 900)

        print("\n" + "="*70)
        print("PHASE 1A: DATA INTEGRITY & ATTRIBUTION CHECKS")
        print("="*70)

        totals = client.evaluate("""({
            framework: state.data.metadata.framework,
            version: state.data.metadata.version,
            elements: state.data.elements.length,
            newCount: state.data.elements.filter(e => e.is_new).length,
            renamedCount: state.data.elements.filter(e => e.is_renamed).length,
            metricsCount: state.data.elements.filter(e => e.metrics_available).length,
            defsCount: state.data.elements.filter(e => e.definition && e.definition.trim().length > 0).length,
            attribution: state.data.metadata.attribution
        })""")
        print(f"Framework: {totals['framework']} ({totals['version']})")
        print(f"Elements: {totals['elements']} (expected 1985)")
        print(f"New: {totals['newCount']} (expected 960)")
        print(f"Renamed: {totals['renamedCount']} (expected 134)")
        print(f"Metrics: {totals['metricsCount']} (expected 221)")
        print(f"Definitions: {totals['defsCount']} (expected 1931)")
        
        assert totals['elements'] == 1985, f"Expected 1985 elements, got {totals['elements']}"
        assert totals['newCount'] == 960, f"Expected 960 new, got {totals['newCount']}"
        assert totals['renamedCount'] == 134, f"Expected 134 renamed, got {totals['renamedCount']}"
        assert totals['metricsCount'] == 221, f"Expected 221 metrics, got {totals['metricsCount']}"
        assert totals['defsCount'] == 1931, f"Expected 1931 definitions, got {totals['defsCount']}"
        assert "©2022 APQC" in totals['attribution'], "Attribution missing from metadata"

        footer_attr = client.evaluate("document.getElementById('footer-attribution').textContent.trim()")
        assert "©2022 APQC" in footer_attr, "Footer attribution missing"
        print(f"Footer Attribution: {footer_attr[:60]}... [OK]")

        print("\n" + "="*70)
        print("PHASE 1B: COLLAPSIBLE PANELS & KEYBOARD SHORTCUTS")
        print("="*70)

        # Sidebar toggle via button
        client.evaluate("document.getElementById('toggle-sidebar-btn').click()")
        is_sidebar_collapsed = client.evaluate("document.getElementById('app-sidebar').classList.contains('collapsed')")
        print(f"Sidebar collapsed after button click: {is_sidebar_collapsed}")
        assert is_sidebar_collapsed, "Sidebar did not collapse on button click"

        # Sidebar category nav items have tooltips (title)
        has_titles = client.evaluate("Array.from(document.querySelectorAll('.category-nav-item')).every(el => el.hasAttribute('title') && el.getAttribute('title').length > 5)")
        print(f"All category nav items have title tooltips: {has_titles}")
        assert has_titles, "Category nav items lack title attribute for rail mode"

        # Sidebar toggle via '[' shortcut
        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: '[' }))")
        is_sidebar_collapsed = client.evaluate("document.getElementById('app-sidebar').classList.contains('collapsed')")
        print(f"Sidebar collapsed after '[' shortcut: {is_sidebar_collapsed}")
        assert not is_sidebar_collapsed, "Sidebar did not expand on '[' shortcut"

        # Inspector toggle via button & reopen tab
        client.evaluate("document.getElementById('close-inspector-btn').click()")
        is_drawer_collapsed = client.evaluate("document.getElementById('inspector-drawer').classList.contains('collapsed')")
        reopen_tab_visible = client.evaluate("window.getComputedStyle(document.getElementById('reopen-inspector-tab')).display !== 'none'")
        print(f"Inspector collapsed on close button: {is_drawer_collapsed}, reopen tab visible: {reopen_tab_visible}")
        assert is_drawer_collapsed, "Inspector drawer did not collapse"
        assert reopen_tab_visible, "Reopen floating tab is not visible"

        client.evaluate("document.getElementById('reopen-inspector-tab').click()")
        is_drawer_collapsed = client.evaluate("document.getElementById('inspector-drawer').classList.contains('collapsed')")
        print(f"Inspector reopened on tab click: {not is_drawer_collapsed}")
        assert not is_drawer_collapsed, "Inspector did not reopen on tab click"

        # Inspector toggle via ']' shortcut
        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: ']' }))")
        is_drawer_collapsed = client.evaluate("document.getElementById('inspector-drawer').classList.contains('collapsed')")
        print(f"Inspector collapsed on ']' shortcut: {is_drawer_collapsed}")
        assert is_drawer_collapsed, "Inspector did not collapse on ']' shortcut"

        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: ']' }))")
        is_drawer_collapsed = client.evaluate("document.getElementById('inspector-drawer').classList.contains('collapsed')")
        print(f"Inspector expanded on ']' shortcut: {not is_drawer_collapsed}")
        assert not is_drawer_collapsed, "Inspector did not expand on ']' shortcut"

        # Input guard: shortcuts do not trigger when focus is in input
        guard_test = client.evaluate("""(() => {
            const input = document.getElementById('global-search');
            input.focus();
            window.dispatchEvent(new KeyboardEvent('keydown', { key: '[' }));
            const sbCollapsed = document.getElementById('app-sidebar').classList.contains('collapsed');
            window.dispatchEvent(new KeyboardEvent('keydown', { key: ']' }));
            const drCollapsed = document.getElementById('inspector-drawer').classList.contains('collapsed');
            input.blur();
            return { sbCollapsed, drCollapsed };
        })()""")
        print(f"Input guard: sidebar collapsed={guard_test['sbCollapsed']}, drawer collapsed={guard_test['drCollapsed']}")
        assert not guard_test['sbCollapsed'], "Sidebar shortcut fired while input focused"
        assert not guard_test['drCollapsed'], "Inspector shortcut fired while input focused"

        print("\n" + "="*70)
        print("PHASE 1C & PHASE 3: REFERENCE INSPECTOR & DISTINCTIVE TERMS")
        print("="*70)

        build_time = client.evaluate("state._indexBuildTimeMs")
        term_count = client.evaluate("state.termIndex.size")
        print(f"Term index built in {build_time} ms with {term_count} terms (Target: < 1000ms)")
        assert build_time < 1000, f"Index build time {build_time} ms exceeds 1000 ms"

        # Jump to element 10378 (Process in Category 2)
        client.evaluate("jumpToElement('10378')")
        time.sleep(0.4)

        inspector_data = client.evaluate("""(() => {
            const hasTerms = Boolean(document.querySelector('.ref-terms-strip .ref-term-pill'));
            const termCount = document.querySelectorAll('.ref-terms-strip .ref-term-pill').length;
            const breadcrumbLinks = Array.from(document.querySelectorAll('.ref-breadcrumb a')).map(a => a.textContent.trim());
            const hasDef = Boolean(document.querySelector('.ref-definition-text'));
            const defText = document.querySelector('.ref-definition-text')?.textContent.trim() || '';
            const sections = Array.from(document.querySelectorAll('.ref-section summary span')).map(s => s.textContent.trim());
            const childrenCount = document.querySelectorAll('.ref-section:nth-of-type(1) .ref-item-row').length;
            const hasChildExcerpt = Boolean(document.querySelector('.ref-section:nth-of-type(1) .ref-item-excerpt'));
            const hasSiblings = sections.some(s => s.includes('Siblings'));
            const relatedCount = document.querySelectorAll('.ref-section:nth-of-type(2) .ref-item-row').length;
            const hasSharedTags = Boolean(document.querySelector('.related-shared-tags .term-pill-tag'));
            return {
                hasTerms,
                termCount,
                breadcrumbLinks,
                hasDef,
                defText,
                sections,
                childrenCount,
                hasChildExcerpt,
                hasSiblings,
                relatedCount,
                hasSharedTags
            };
        })()""")

        print(f"Breadcrumb: {inspector_data['breadcrumbLinks']}")
        print(f"Key Terms present: {inspector_data['hasTerms']} (Count: {inspector_data['termCount']})")
        print(f"Definition present: {inspector_data['hasDef']} ({len(inspector_data['defText'])} chars)")
        print(f"Sections present: {inspector_data['sections']}")
        print(f"Children Count: {inspector_data['childrenCount']}, has excerpts: {inspector_data['hasChildExcerpt']}")
        print(f"Siblings section present: {inspector_data['hasSiblings']}")
        print(f"Related by Term Count: {inspector_data['relatedCount']} (top 10), has shared tags: {inspector_data['hasSharedTags']}")

        assert inspector_data['hasTerms'], "Key terms strip is missing"
        assert inspector_data['termCount'] > 0, "No distinctive terms found for element"
        assert len(inspector_data['breadcrumbLinks']) > 0, "Breadcrumb links missing"
        assert inspector_data['hasDef'], "Definition box missing"
        assert inspector_data['relatedCount'] > 0, "Related elements list missing"
        assert inspector_data['hasSharedTags'], "Shared term tags missing in related list"

        # Test clicking a term pill activates global search
        client.evaluate("""(() => {
            const firstPill = document.querySelector('.ref-terms-strip .ref-term-pill');
            if (firstPill) firstPill.click();
        })()""")
        time.sleep(0.3)
        search_val = client.evaluate("document.getElementById('global-search').value")
        print(f"Clicking key term set global search to: '{search_val}'")
        assert search_val, "Key term pill did not populate search box"

        # Reset search
        client.evaluate("document.getElementById('clear-search-btn').click()")
        time.sleep(0.2)

        print("\n" + "="*70)
        print("ACCESSIBILITY: ARIA TREE & KEYBOARD NAVIGATION")
        print("="*70)

        tree_a11y = client.evaluate("""(() => {
            const container = document.getElementById('process-nodes-container');
            const hasRoleTree = container.getAttribute('role') === 'tree';
            const rows = Array.from(document.querySelectorAll('.tree-row'));
            const allHaveTreeItem = rows.length > 0 && rows.every(r => r.getAttribute('role') === 'treeitem');
            const allHaveAriaLevel = rows.every(r => r.hasAttribute('aria-level'));
            const expandableHaveExpanded = rows.filter(r => r.querySelector('.tree-toggle:not(.placeholder)')).every(r => r.hasAttribute('aria-expanded'));
            return {
                hasRoleTree,
                rowCount: rows.length,
                allHaveTreeItem,
                allHaveAriaLevel,
                expandableHaveExpanded
            };
        })()""")
        print(f"Tree container role='tree': {tree_a11y['hasRoleTree']}")
        print(f"Outline rows count: {tree_a11y['rowCount']}")
        print(f"All rows role='treeitem': {tree_a11y['allHaveTreeItem']}")
        print(f"All rows have aria-level: {tree_a11y['allHaveAriaLevel']}")
        print(f"Expandable rows have aria-expanded: {tree_a11y['expandableHaveExpanded']}")

        assert tree_a11y['hasRoleTree'], "Container missing role='tree'"
        assert tree_a11y['allHaveTreeItem'], "Rows missing role='treeitem'"
        assert tree_a11y['allHaveAriaLevel'], "Rows missing aria-level"
        assert tree_a11y['expandableHaveExpanded'], "Expandable rows missing aria-expanded"

        # Test Keyboard Navigation: ArrowDown, ArrowUp, Home, End
        nav_test = client.evaluate("""(() => {
            const rows = Array.from(document.querySelectorAll('.tree-row:not([style*="display: none"])'));
            activateTreeRow(rows[0]);
            const startId = document.querySelector('.tree-row.selected')?.getAttribute('data-id');
            
            // Dispatch ArrowDown
            handleTreeKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
            const downId = document.querySelector('.tree-row.selected')?.getAttribute('data-id');

            // Dispatch ArrowUp
            handleTreeKeyDown(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
            const upId = document.querySelector('.tree-row.selected')?.getAttribute('data-id');

            // Dispatch End
            handleTreeKeyDown(new KeyboardEvent('keydown', { key: 'End' }));
            const endId = document.querySelector('.tree-row.selected')?.getAttribute('data-id');

            // Dispatch Home
            handleTreeKeyDown(new KeyboardEvent('keydown', { key: 'Home' }));
            const homeId = document.querySelector('.tree-row.selected')?.getAttribute('data-id');

            return {
                startId,
                downId,
                upId,
                endId,
                homeId,
                downChanged: downId !== startId,
                upReturned: upId === startId,
                endMatchesLast: endId === rows[rows.length - 1].getAttribute('data-id'),
                homeMatchesFirst: homeId === rows[0].getAttribute('data-id')
            };
        })()""")
        print(f"Tree keynav: Down moves row: {nav_test['downChanged']}, Up returns: {nav_test['upReturned']}, End/Home work: {nav_test['endMatchesLast']} & {nav_test['homeMatchesFirst']}")
        assert nav_test['downChanged'], "ArrowDown did not change active row"
        assert nav_test['upReturned'], "ArrowUp did not return to previous row"
        assert nav_test['endMatchesLast'], "End did not jump to last row"
        assert nav_test['homeMatchesFirst'], "Home did not jump to first row"

        print("\n" + "="*70)
        print("PERFORMANCE BENCHMARKS: FIRST RENDER & CATEGORY 8 EXPAND ALL")
        print("="*70)

        first_render_time = client.evaluate("state._firstRenderTimeMs")
        print(f"Time to First Render: {first_render_time} ms")

        # Measure Expand All on Category 8 (321 elements)
        cat8_perf = client.evaluate("""(() => {
            state.selectedCategoryId = '8';
            const explorerCatSelect = document.getElementById("explorer-cat-filter");
            if (explorerCatSelect) explorerCatSelect.value = '8';
            document.querySelectorAll(".category-nav-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-cat-id") === '8');
            });
            renderCategoryHero();
            collapseAllNodes();

            const t0 = performance.now();
            expandAllNodes();
            const t1 = performance.now();
            const elapsed = Math.round((t1 - t0) * 100) / 100;
            const renderedCount = document.querySelectorAll('#process-nodes-container .tree-row').length;
            return { elapsed, renderedCount };
        })()""")
        print(f"Category 8 'Expand all' timing: {cat8_perf['elapsed']} ms for {cat8_perf['renderedCount']} outline rows")
        assert cat8_perf['renderedCount'] == 321, f"Expected 321 elements rendered for Cat 8, got {cat8_perf['renderedCount']}"

        print("\n" + "="*70)
        print("REGRESSION CHECKS: GLOBAL SEARCH, FILTERS, HASH ROUTING")
        print("="*70)

        # Global search "patient" -> 75-78 matches across all categories
        patient_matches = client.evaluate("""(() => {
            const input = document.getElementById('global-search');
            input.value = 'patient';
            input.dispatchEvent(new Event('input'));
            return parseInt(document.getElementById('visible-count').textContent, 10);
        })()""")
        print(f"Global search 'patient' matches: {patient_matches} (expected: 75–78)")
        assert patient_matches in (75, 78), f"Expected 75-78 matches for 'patient', got {patient_matches}"

        # Global search "denial" -> 4 matches
        denial_matches = client.evaluate("""(() => {
            const input = document.getElementById('global-search');
            input.value = 'denial';
            input.dispatchEvent(new Event('input'));
            return parseInt(document.getElementById('visible-count').textContent, 10);
        })()""")
        print(f"Global search 'denial' matches: {denial_matches} (expected: 4)")
        assert denial_matches == 4, f"Expected 4 matches for 'denial', got {denial_matches}"

        # Clear search
        client.evaluate("document.getElementById('clear-search-btn').click()")
        time.sleep(0.2)

        # Reset category to all before testing global filter pill
        client.evaluate("""(() => {
            state.selectedCategoryId = 'all';
            const explorerCatSelect = document.getElementById("explorer-cat-filter");
            if (explorerCatSelect) explorerCatSelect.value = 'all';
            document.querySelectorAll(".category-nav-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-cat-id") === 'all');
            });
            renderCategoryHero();
            renderExplorerNodes();
        })()""")

        # Filter pill 'new' -> 960 elements
        new_pill_count = client.evaluate("""(() => {
            document.querySelector('.filter-pill[data-filter="new"]').click();
            return parseInt(document.getElementById('visible-count').textContent, 10);
        })()""")
        print(f"Filter pill '⭐ New' matches: {new_pill_count} (expected: 960)")
        assert new_pill_count == 960, f"Expected 960 new elements, got {new_pill_count}"
        client.evaluate("document.getElementById('reset-filters-btn').click()")
        time.sleep(0.2)

        # Hash routing
        for hash_view in ["#matrix", "#analytics", "#glossary", "#explorer"]:
            client.evaluate(f"window.location.hash = '{hash_view}'")
            time.sleep(0.2)
            active_view = client.evaluate("state.activeView")
            print(f"Hash {hash_view} -> activeView: {active_view}")
            assert active_view == hash_view.replace("#", ""), f"Hash routing failed for {hash_view}"

        print("\n" + "="*70)
        print("CAPTURING SCREENSHOTS (DESKTOP 1440w & TABLET 820w)")
        print("="*70)

        # 1. Explorer with Category 7 expanded and 7.1.1 selected
        client.set_viewport(1440, 900)
        client.evaluate("""(() => {
            switchView('explorer', false);
            jumpToElement('20958'); // 7.1.1 Develop human resources strategy
        })()""")
        time.sleep(0.5)
        client.capture_screenshot("01_explorer_cat7_desktop.png")

        # 2. Explorer with rail collapsed
        client.evaluate("""(() => {
            const sidebar = document.getElementById('app-sidebar');
            if (!sidebar.classList.contains('collapsed')) {
                toggleSidebar(true);
            }
        })()""")
        time.sleep(0.4)
        client.capture_screenshot("02_explorer_rail_collapsed.png")

        # Restore rail expanded
        client.evaluate("toggleSidebar(false)")
        time.sleep(0.3)

        # 3. Change matrix view
        client.evaluate("switchView('matrix', true)")
        time.sleep(0.4)
        client.capture_screenshot("03_change_matrix.png")

        # 4. Analytics dashboard view (sorted bars and direct-labeled donut)
        client.evaluate("switchView('analytics', true)")
        time.sleep(0.4)
        client.capture_screenshot("04_analytics_dashboard.png")

        # 5. Glossary view with serif definitions
        client.evaluate("switchView('glossary', true)")
        time.sleep(0.4)
        client.capture_screenshot("05_glossary_view.png")

        # 6. Upload dialog with validation error message
        client.evaluate("""(() => {
            switchView('explorer', false);
            showUploadModalError("Sheet 'Glossary terms' wasn't found. Use a 'vX vs vY' workbook from apqc.org/pcf.");
        })()""")
        time.sleep(0.4)
        client.capture_screenshot("06_upload_dialog_error.png")
        client.evaluate("closeUploadModal()")
        time.sleep(0.2)

        # 7. Light theme active
        client.evaluate("""(() => {
            applyTheme('light');
            switchView('explorer', false);
            jumpToElement('20958');
        })()""")
        time.sleep(0.4)
        client.capture_screenshot("07_light_theme.png")

        # Restore dark theme
        client.evaluate("applyTheme('dark')")
        time.sleep(0.2)

        # 8. Tablet viewport 820x1024
        client.set_viewport(820, 1024)
        client.evaluate("""(() => {
            switchView('explorer', false);
            jumpToElement('20958');
        })()""")
        time.sleep(0.5)
        client.capture_screenshot("08_tablet_view.png")

        # Restore desktop viewport
        client.set_viewport(1440, 900)

        print("\n" + "="*70)
        print("PHASE 1D: IN-BROWSER WORKBOOK UPLOAD & RECOVERY (RETAIL PCF)")
        print("="*70)

        retail_path = os.path.join(PROJECT_DIR, "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx")
        with open(retail_path, "rb") as f:
            retail_b64 = base64.b64encode(f.read()).decode("ascii")

        client.evaluate(f"""(() => {{
            const binary = atob("{retail_b64}");
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {{
                bytes[i] = binary.charCodeAt(i);
            }}
            pendingWorkbookBuffer = bytes;
            pendingFileName = "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx";
            openUploadModal(bytes, pendingFileName);
        }})()""")
        time.sleep(0.4)

        modal_visible = client.evaluate("document.getElementById('upload-modal-container').style.display !== 'none'")
        modal_summary = client.evaluate("document.getElementById('modal-detected-summary').textContent.trim()")
        print(f"Upload modal visible: {modal_visible}")
        print(f"Modal Summary: '{modal_summary}'")
        assert modal_visible, "Upload modal did not appear"
        assert "1,708 elements" in modal_summary or "1708 elements" in modal_summary, f"Modal summary incorrect: {modal_summary}"

        # Confirm upload
        client.evaluate("document.getElementById('confirm-upload-btn').click()")
        time.sleep(0.5)

        retail_state = client.evaluate("""({
            framework: state.data.metadata.framework,
            version: state.data.metadata.version,
            elements: state.data.elements.length,
            newCount: state.data.metadata.total_new,
            renamedCount: state.data.metadata.total_renamed,
            metricsCount: state.data.metadata.total_with_metrics,
            defsCount: state.data.metadata.definitions_count,
            cat4Def: state.data.elements.find(e => e.hierarchy_id === '4.0')?.definition || '',
            opCats: Array.from(document.querySelectorAll('.process-type-section:first-child .category-nav-item')).length,
            supCats: Array.from(document.querySelectorAll('.process-type-section:last-child .category-nav-item')).length,
            isCustomLoaded: state.isCustomLoaded,
            resetBtnVisible: window.getComputedStyle(document.getElementById('reset-default-pcf-btn')).display !== 'none'
        })""")
        print("\nRetail Framework Verification in UI:")
        print(f"  • Framework Title: {retail_state['framework']}")
        print(f"  • Total Elements: {retail_state['elements']} (Expected: 1,708)")
        print(f"  • New Elements: {retail_state['newCount']} (Expected: 608)")
        print(f"  • Renamed Elements: {retail_state['renamedCount']} (Expected: 74)")
        print(f"  • Metrics Available: {retail_state['metricsCount']} (Expected: 180)")
        print(f"  • Definitions Count: {retail_state['defsCount']} (Expected: 1,462)")
        print(f"  • Category 4.0 Definition: '{retail_state['cat4Def']}' (Expected empty)")
        print(f"  • Operating Categories count: {retail_state['opCats']} (Expected: 6)")
        print(f"  • Support Categories count: {retail_state['supCats']} (Expected: 7)")
        print(f"  • Reset Button Visible: {retail_state['resetBtnVisible']} (Expected: True)")

        assert retail_state['elements'] == 1708, f"Expected 1708 elements, got {retail_state['elements']}"
        assert retail_state['newCount'] == 608, f"Expected 608 new, got {retail_state['newCount']}"
        assert retail_state['renamedCount'] == 74, f"Expected 74 renamed, got {retail_state['renamedCount']}"
        assert retail_state['metricsCount'] == 180, f"Expected 180 metrics, got {retail_state['metricsCount']}"
        assert retail_state['defsCount'] == 1462, f"Expected 1462 definitions, got {retail_state['defsCount']}"
        assert retail_state['cat4Def'] == "", "Retail 4.0 should have empty definition"
        assert retail_state['opCats'] == 6, f"Expected 6 operating categories for Retail, got {retail_state['opCats']}"
        assert retail_state['supCats'] == 7, f"Expected 7 support categories for Retail, got {retail_state['supCats']}"
        assert retail_state['resetBtnVisible'], "Reset to default button should be visible when custom workbook loaded"

        # Test Reset to Default
        client.evaluate("document.getElementById('reset-default-pcf-btn').click()")
        time.sleep(0.3)
        restored_elements = client.evaluate("state.data.elements.length")
        is_custom = client.evaluate("state.isCustomLoaded")
        print(f"After Reset: elements={restored_elements} (Expected: 1985), isCustomLoaded={is_custom} (Expected: False)")
        assert restored_elements == 1985, "Reset failed to restore Healthcare dataset"
        assert not is_custom, "isCustomLoaded should be false after reset"

        # Test Invalid File Upload Handling
        invalid_result = client.evaluate("""(() => {
            try {
                const junk = new Uint8Array([1, 2, 3, 4, 5]);
                openUploadModal(junk, "corrupt.xlsx");
                return { 
                    modalOpened: document.getElementById('upload-modal-container').style.display !== 'none',
                    errorVisible: document.getElementById('upload-dialog-error').style.display !== 'none',
                    errorText: document.getElementById('upload-dialog-error').textContent.trim()
                };
            } catch (e) {
                return { error: e.message };
            }
        })()""")
        print(f"Corrupt file handling: {invalid_result}")
        assert invalid_result.get('modalOpened'), "Upload modal should display on error"
        assert invalid_result.get('errorVisible'), "Error message box should be visible on corrupt file"
        client.evaluate("closeUploadModal()")

        elements_after_corrupt = client.evaluate("state.data.elements.length")
        assert elements_after_corrupt == 1985, "Corrupt file corrupts current state"

        print("\n" + "="*70)
        print("TEXT SIZE CONTROL: STEPPING, SHORTCUTS, LOCALSTORAGE, LAYOUT & SCREENSHOTS")
        print("="*70)

        # 1. Verify initial scale
        init_scale = client.evaluate("""({
            textScale: state.textScale,
            label: document.getElementById('text-size-label').textContent.trim(),
            rootVar: document.documentElement.style.getPropertyValue('--text-scale') || '1'
        })""")
        print(f"Initial text scale: {init_scale}")
        assert init_scale['textScale'] == 1.0, f"Expected initial scale 1.0, got {init_scale['textScale']}"
        assert init_scale['label'] == '100%', f"Expected initial label 100%, got {init_scale['label']}"

        # 2. Step up using A+ button
        inc_btn = "document.getElementById('text-size-inc-btn').click()"
        dec_btn = "document.getElementById('text-size-dec-btn').click()"
        reset_btn = "document.getElementById('text-size-reset-btn').click()"

        client.evaluate(inc_btn)
        s1 = client.evaluate("({ scale: state.textScale, label: document.getElementById('text-size-label').textContent.trim() })")
        assert s1['scale'] == 1.15 and s1['label'] == '115%', f"Expected 1.15, got {s1}"

        client.evaluate(inc_btn)
        s2 = client.evaluate("({ scale: state.textScale, label: document.getElementById('text-size-label').textContent.trim() })")
        assert s2['scale'] == 1.30 and s2['label'] == '130%', f"Expected 1.30, got {s2}"

        client.evaluate(inc_btn)
        s3 = client.evaluate("({ scale: state.textScale, label: document.getElementById('text-size-label').textContent.trim() })")
        assert s3['scale'] == 1.50 and s3['label'] == '150%', f"Expected 1.50, got {s3}"

        # Max clamp check
        client.evaluate(inc_btn)
        s_max = client.evaluate("state.textScale")
        assert s_max == 1.50, f"Scale should clamp at 1.50, got {s_max}"

        # Reset button test (clicking label)
        client.evaluate(reset_btn)
        s_reset = client.evaluate("({ scale: state.textScale, label: document.getElementById('text-size-label').textContent.trim() })")
        assert s_reset['scale'] == 1.0 and s_reset['label'] == '100%', f"Expected reset to 1.0, got {s_reset}"

        # Step down to 85%
        client.evaluate(dec_btn)
        s_min = client.evaluate("({ scale: state.textScale, label: document.getElementById('text-size-label').textContent.trim() })")
        assert s_min['scale'] == 0.85 and s_min['label'] == '85%', f"Expected 0.85, got {s_min}"

        # Min clamp check
        client.evaluate(dec_btn)
        assert client.evaluate("state.textScale") == 0.85, "Scale should clamp at 0.85"

        # 3. Keyboard shortcuts: Ctrl + =, Ctrl + -, Ctrl + 0
        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: '=', ctrlKey: true }))")
        assert client.evaluate("state.textScale") == 1.0, "Ctrl+= failed to step up"

        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: '+', ctrlKey: true }))")
        assert client.evaluate("state.textScale") == 1.15, "Ctrl++ failed to step up"

        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: '-', ctrlKey: true }))")
        assert client.evaluate("state.textScale") == 1.0, "Ctrl+- failed to step down"

        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: '=', ctrlKey: true }))")
        client.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', { key: '0', ctrlKey: true }))")
        assert client.evaluate("state.textScale") == 1.0, "Ctrl+0 failed to reset scale"

        # Shortcut input guard: typing in search does not change scale
        guard_shortcut = client.evaluate("""(() => {
            const search = document.getElementById('global-search');
            search.focus();
            window.dispatchEvent(new KeyboardEvent('keydown', { key: '=', ctrlKey: true }));
            const scale = state.textScale;
            search.blur();
            return scale;
        })()""")
        assert guard_shortcut == 1.0, f"Ctrl+= fired while search input had focus! Got {guard_shortcut}"

        # 4. Proportional scaling measurements at 85%, 100%, 150%
        client.evaluate("setTextScale(1.0); jumpToElement('20958');")
        time.sleep(0.3)

        measurements_100 = client.evaluate("""(() => {
            const row = document.querySelector('.tree-row[data-id="20958"]');
            const rowHeight = row.getBoundingClientRect().height;
            const indent = parseFloat(window.getComputedStyle(row).paddingLeft);
            const diffBar = row.querySelector('.diff-bar-fill');
            const barWidth = diffBar ? parseFloat(window.getComputedStyle(diffBar).width) : 0;
            return { rowHeight, indent, barWidth };
        })()""")

        client.evaluate("setTextScale(0.85)")
        time.sleep(0.3)
        measurements_85 = client.evaluate("""(() => {
            const row = document.querySelector('.tree-row[data-id="20958"]');
            const rowHeight = row.getBoundingClientRect().height;
            const indent = parseFloat(window.getComputedStyle(row).paddingLeft);
            const diffBar = row.querySelector('.diff-bar-fill');
            const barWidth = diffBar ? parseFloat(window.getComputedStyle(diffBar).width) : 0;
            return { rowHeight, indent, barWidth };
        })()""")

        client.evaluate("setTextScale(1.50)")
        time.sleep(0.3)
        measurements_150 = client.evaluate("""(() => {
            const row = document.querySelector('.tree-row[data-id="20958"]');
            const rowHeight = row.getBoundingClientRect().height;
            const indent = parseFloat(window.getComputedStyle(row).paddingLeft);
            const diffBar = row.querySelector('.diff-bar-fill');
            const barWidth = diffBar ? parseFloat(window.getComputedStyle(diffBar).width) : 0;
            return { rowHeight, indent, barWidth };
        })()""")

        print(f"Measurements at 100%: {measurements_100}")
        print(f"Measurements at 85%:  {measurements_85}")
        print(f"Measurements at 150%: {measurements_150}")

        # Assert proportional scaling ratios
        ratio_85 = measurements_85['rowHeight'] / measurements_100['rowHeight']
        ratio_150 = measurements_150['rowHeight'] / measurements_100['rowHeight']
        print(f"  • Row height ratio 85%/100%: {ratio_85:.3f} (target ~0.85)")
        print(f"  • Row height ratio 150%/100%: {ratio_150:.3f} (target ~1.50)")
        assert 0.80 <= ratio_85 <= 0.90, f"Row height ratio at 85% out of range: {ratio_85}"
        assert 1.40 <= ratio_150 <= 1.60, f"Row height ratio at 150% out of range: {ratio_150}"

        indent_ratio_85 = measurements_85['indent'] / measurements_100['indent']
        indent_ratio_150 = measurements_150['indent'] / measurements_100['indent']
        print(f"  • Indent ratio 85%/100%: {indent_ratio_85:.3f} (target ~0.85)")
        print(f"  • Indent ratio 150%/100%: {indent_ratio_150:.3f} (target ~1.50)")
        assert 0.80 <= indent_ratio_85 <= 0.90
        assert 1.40 <= indent_ratio_150 <= 1.60

        bar_ratio_85 = measurements_85['barWidth'] / measurements_100['barWidth']
        bar_ratio_150 = measurements_150['barWidth'] / measurements_100['barWidth']
        print(f"  • Diff bar ratio 85%/100%: {bar_ratio_85:.3f} (target ~0.85)")
        print(f"  • Diff bar ratio 150%/100%: {bar_ratio_150:.3f} (target ~1.50)")
        assert 0.80 <= bar_ratio_85 <= 0.90
        assert 1.40 <= bar_ratio_150 <= 1.60

        # 5. Layout check at 150% - no horizontal page scrolling
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.50)")
        time.sleep(0.4)
        no_horiz_scroll = client.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        print(f"No horizontal page scroll at 150% scale: {no_horiz_scroll}")
        assert no_horiz_scroll, "Page has horizontal scroll at 150% scale"

        # 6. Capture Screenshots at 85% and 150%
        # ---- AT 85% SCALE ----
        client.evaluate("setTextScale(0.85)")
        time.sleep(0.3)

        # 85% - Explorer Cat 7 & 7.1.1
        client.evaluate("""(() => {
            switchView('explorer', false);
            jumpToElement('20958');
        })()""")
        time.sleep(0.5)
        client.capture_screenshot("scale_85_explorer_cat7.png")

        # 85% - Inspector view
        client.capture_screenshot("scale_85_inspector.png")

        # 85% - Change table (#matrix)
        client.evaluate("switchView('matrix', true)")
        time.sleep(0.5)
        client.capture_screenshot("scale_85_change_table.png")

        # 85% - Upload dialog
        client.evaluate("""(() => {
            switchView('explorer', false);
            showUploadModalError("Sample validation dialog preview at 85% text scale.");
        })()""")
        time.sleep(0.4)
        client.capture_screenshot("scale_85_upload_dialog.png")
        client.evaluate("closeUploadModal()")
        time.sleep(0.2)

        # ---- AT 150% SCALE ----
        client.evaluate("setTextScale(1.50)")
        time.sleep(0.3)

        # 150% - Explorer Cat 7 & 7.1.1
        client.evaluate("""(() => {
            switchView('explorer', false);
            jumpToElement('20958');
        })()""")
        time.sleep(0.5)
        client.capture_screenshot("scale_150_explorer_cat7.png")

        # 150% - Inspector view
        client.capture_screenshot("scale_150_inspector.png")

        # 150% - Change table (#matrix)
        client.evaluate("switchView('matrix', true)")
        time.sleep(0.5)
        client.capture_screenshot("scale_150_change_table.png")

        # 150% - Upload dialog
        client.evaluate("""(() => {
            switchView('explorer', false);
            showUploadModalError("Sample validation dialog preview at 150% text scale.");
        })()""")
        time.sleep(0.4)
        client.capture_screenshot("scale_150_upload_dialog.png")
        client.evaluate("closeUploadModal()")
        time.sleep(0.2)

        # 7. LocalStorage Persistence & Anti-flash check
        client.evaluate("setTextScale(1.30)")
        stored = client.evaluate("localStorage.getItem('pcf_text_scale')")
        print(f"LocalStorage persisted scale: {stored}")
        assert stored == "1.3", f"Expected localStorage '1.3', got {stored}"

        # Reset back to 100%
        client.evaluate("setTextScale(1.0)")
        assert client.evaluate("localStorage.getItem('pcf_text_scale')") == "1"

        # 8. Print stylesheet check
        print_style_check = client.evaluate("""(() => {
            let matched = false;
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        if (rule.media && rule.media.mediaText.includes('print')) {
                            if (rule.cssText.includes('--text-scale: 1') || rule.cssText.includes('--text-scale:1')) {
                                matched = true;
                            }
                        }
                    }
                } catch(e) {}
            }
            return matched;
        })()""")
        print(f"Print stylesheet forces --text-scale: 1: {print_style_check}")
        assert print_style_check, "Print media query rule for --text-scale: 1 missing"

        print("\n" + "="*70)
        print("ITEM 1: INSPECTOR SQUASHED SECTIONS & LAYOUT FIX VERIFICATION")
        print("="*70)

        # Select Healthcare 2.3.1.1 (ID 10083, long definition, 12 siblings)
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.0); switchView('explorer', false); jumpToElement('10083');")
        time.sleep(0.5)

        inspector_checks = client.evaluate("""(() => {
            const sections = Array.from(document.querySelectorAll('#inspector-content details.ref-section'));
            const sectionHeights = sections.map(s => {
                const sRect = s.getBoundingClientRect();
                const summaryRect = s.querySelector('summary').getBoundingClientRect();
                return {
                    text: s.querySelector('summary span').textContent.trim(),
                    height: sRect.height,
                    summaryHeight: summaryRect.height,
                    isSquashed: sRect.height < summaryRect.height || sRect.height < 20
                };
            });

            // Breadcrumb single line check
            const bc = document.querySelector('.ref-breadcrumb');
            const bcSingleLine = bc ? bc.scrollHeight <= bc.clientHeight + 4 : false;
            const bcTitle = bc ? (bc.getAttribute('title') || '') : '';

            // Copy button placement: must be below ref-subline (no overlap)
            const subline = document.querySelector('.ref-subline');
            const copyBtn = document.querySelector('.ref-copy-btn');
            let copyBtnNoOverlap = false;
            if (subline && copyBtn) {
                const sublineBottom = subline.getBoundingClientRect().bottom;
                const copyBtnTop = copyBtn.getBoundingClientRect().top;
                copyBtnNoOverlap = copyBtnTop >= sublineBottom - 2;
            }

            // Related top 5 and toggle
            const topRelatedVisible = Array.from(document.querySelectorAll('#inspector-content details.ref-section:nth-of-type(2) .ref-item-row'))
                .filter(r => window.getComputedStyle(r).display !== 'none').length;
            const hasToggleBtn = Boolean(document.getElementById('toggle-related-all-btn'));

            return {
                sectionHeights,
                allSectionsHealthy: sectionHeights.every(s => !s.isSquashed),
                bcSingleLine,
                bcTitle,
                copyBtnNoOverlap,
                topRelatedVisible,
                hasToggleBtn
            };
        })()""")

        print(f"Inspector section heights: {inspector_checks['sectionHeights']}")
        print(f"All sections healthy (height >= summary): {inspector_checks['allSectionsHealthy']}")
        print(f"Breadcrumb single-line: {inspector_checks['bcSingleLine']} (Title: '{inspector_checks['bcTitle']}')")
        print(f"Copy button below subline (no overlap): {inspector_checks['copyBtnNoOverlap']}")
        print(f"Top related visible count: {inspector_checks['topRelatedVisible']} (Has toggle: {inspector_checks['hasToggleBtn']})")

        assert inspector_checks['allSectionsHealthy'], "Inspector sections are squashed!"
        assert inspector_checks['bcSingleLine'], "Breadcrumb wrapped onto multiple lines!"
        assert "2.3" in inspector_checks['bcTitle'] and "2.3.1.1" in inspector_checks['bcTitle'], "Breadcrumb title missing full path"
        assert inspector_checks['copyBtnNoOverlap'], "Copy button overlaps .ref-subline!"
        assert inspector_checks['topRelatedVisible'] == 5, f"Expected 5 related items initially, got {inspector_checks['topRelatedVisible']}"

        # Test toggle related items
        client.evaluate("document.getElementById('toggle-related-all-btn').click()")
        toggle_state_1 = client.evaluate("""(() => {
            const btn = document.getElementById('toggle-related-all-btn');
            const rows = Array.from(document.querySelectorAll('#inspector-content details.ref-section:nth-of-type(2) .ref-item-row'))
                .filter(r => window.getComputedStyle(r).display !== 'none').length;
            return { text: btn.textContent.trim(), count: rows };
        })()""")
        print(f"After expanding related: count={toggle_state_1['count']}, btnText='{toggle_state_1['text']}'")
        assert toggle_state_1['count'] == 10, f"Expected 10 related items expanded, got {toggle_state_1['count']}"
        assert toggle_state_1['text'] == "Show top 5"

        client.evaluate("document.getElementById('toggle-related-all-btn').click()")
        toggle_state_2 = client.evaluate("""(() => {
            const btn = document.getElementById('toggle-related-all-btn');
            const rows = Array.from(document.querySelectorAll('#inspector-content details.ref-section:nth-of-type(2) .ref-item-row'))
                .filter(r => window.getComputedStyle(r).display !== 'none').length;
            return { text: btn.textContent.trim(), count: rows };
        })()""")
        print(f"After collapsing related: count={toggle_state_2['count']}, btnText='{toggle_state_2['text']}'")
        assert toggle_state_2['count'] == 5
        assert "Show all" in toggle_state_2['text']

        # Capture Item 1 screenshots: 2.3.1.1 & 8.1.1 at 100%, 85%, 150% in Desktop (1440x900) and Tablet (820x1100)
        print("\nCapturing Item 1 screenshots under docs/screenshots/fix_inspector_*.png:")

        # --- 2.3.1.1 Desktop (1440x900) ---
        client.set_viewport(1440, 900)
        for scale, sname in [(1.0, "100"), (0.85, "85"), (1.50, "150")]:
            client.evaluate(f"setTextScale({scale}); jumpToElement('10083');")
            time.sleep(0.4)
            client.capture_screenshot(f"fix_inspector_2_3_1_1_{sname}_desktop.png")

        # --- 2.3.1.1 Tablet (820x1100) ---
        client.set_viewport(820, 1100)
        for scale, sname in [(1.0, "100"), (0.85, "85"), (1.50, "150")]:
            client.evaluate(f"setTextScale({scale}); jumpToElement('10083');")
            time.sleep(0.4)
            client.capture_screenshot(f"fix_inspector_2_3_1_1_{sname}_tablet.png")

        # --- 8.1.1 Desktop (1440x900) at 100% and 150% ---
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.0); jumpToElement('20609');")
        time.sleep(0.4)
        client.capture_screenshot("fix_inspector_8_1_1_100_desktop.png")

        client.evaluate("setTextScale(1.50); jumpToElement('20609');")
        time.sleep(0.4)
        client.capture_screenshot("fix_inspector_8_1_1_150_desktop.png")

        # Reset viewport & scale
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.0)")

        print("\n" + "="*70)
        print("ITEM 4: STORAGE SAFETY (BLOCKED STORAGE TEST)")
        print("="*70)

        storage_safety = client.evaluate("""(() => {
            const origGet = Storage.prototype.getItem;
            const origSet = Storage.prototype.setItem;
            Storage.prototype.getItem = function() { throw new DOMException("The operation is insecure.", "SecurityError"); };
            Storage.prototype.setItem = function() { throw new DOMException("The operation is insecure.", "SecurityError"); };
            let success = false;
            try {
                toggleTheme();
                stepTextScale(1);
                toggleSidebar();
                toggleInspector();
                success = true;
            } catch (e) {
                success = false;
            } finally {
                Storage.prototype.getItem = origGet;
                Storage.prototype.setItem = origSet;
            }
            return { success };
        })()""")
        print(f"App operates smoothly with storage blocked: {storage_safety['success']}")
        assert storage_safety['success'], "Storage safety failure when localStorage throws"

        print("\n" + "="*70)
        print("ITEM 3: WORKBOOK ESCAPING & INLINE HANDLER REMOVAL TEST")
        print("="*70)

        # Generate /tmp/malicious_pcf.xlsx
        import openpyxl
        import shutil
        malicious_xlsx = "/tmp/malicious_pcf.xlsx"
        src_xlsx = os.path.join(PROJECT_DIR, "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx")
        shutil.copyfile(src_xlsx, malicious_xlsx)
        wb = openpyxl.load_workbook(malicious_xlsx)
        ws = wb['Combined']
        mal_id = '99999\'"><script>window.__xss_executed=true;</script>\\\\test'
        mal_name = 'XSS \'single\' "double" <script>window.__xss_executed=true;</script> \\\\backslash'
        ws.cell(row=2, column=1, value=mal_id)
        ws.cell(row=2, column=3, value=mal_name)
        wb.save(malicious_xlsx)

        with open(malicious_xlsx, "rb") as mf:
            m_b64 = base64.b64encode(mf.read()).decode("ascii")

        client.evaluate(f"""(() => {{
            const b64 = "{m_b64}";
            const bin = atob(b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            pendingWorkbookBuffer = bytes;
            pendingFileName = "malicious_pcf.xlsx";
            openUploadModal(bytes, "malicious_pcf.xlsx");
            document.getElementById("confirm-upload-btn").click();
        }})()""")
        time.sleep(0.5)

        xss_executed = client.evaluate("Boolean(window.__xss_executed)")
        print(f"XSS executed after uploading workbook with quotes and script tags: {xss_executed}")
        assert not xss_executed, "XSS vulnerability detected! Script executed from workbook data."

        # Verify element links and text rendering
        raw_id_json = json.dumps(mal_id)
        jump_test = client.evaluate(f"""(() => {{
            const rawId = {raw_id_json};
            jumpToElement(rawId);
            const titleEl = document.querySelector('.ref-title');
            const breadcrumbEl = document.querySelector('.ref-breadcrumb');
            return {{
                titleText: titleEl ? titleEl.textContent : '',
                breadcrumbText: breadcrumbEl ? breadcrumbEl.textContent : '',
                xssFired: Boolean(window.__xss_executed)
            }};
        }})()""")
        print(f"Escaped title rendered safely: '{jump_test['titleText'][:50]}...'")
        print(f"XSS fired after jumping: {jump_test['xssFired']}")
        assert not jump_test['xssFired'], "XSS script executed during jumpToElement!"
        assert "XSS" in jump_test['titleText'], "Malicious element title failed to render"

        # Restore default PCF
        client.evaluate("document.getElementById('reset-default-pcf-btn').click()")
        time.sleep(0.3)
        assert client.evaluate("state.data.elements.length") == 1985

        print("\n" + "="*70)
        print("ITEM 7: CATEGORY 8 'EXPAND ALL' TIMING AT 100% AND 150% SCALE")
        print("="*70)

        # 100% Scale timing for Category 8 Expand All
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.0); selectCategory('8', false);")
        time.sleep(0.3)
        cat8_timing_100 = client.evaluate("""(() => {
            collapseAllNodes();
            const t0 = performance.now();
            expandAllNodes();
            const t1 = performance.now();
            return {
                timeMs: +(t1 - t0).toFixed(2),
                rowsRendered: document.querySelectorAll('.tree-row').length
            };
        })()""")
        print(f"Category 8 Expand All at 100% scale (1440x900): {cat8_timing_100['timeMs']} ms ({cat8_timing_100['rowsRendered']} rows)")

        # 150% Scale timing for Category 8 Expand All
        client.evaluate("setTextScale(1.50); selectCategory('8', false);")
        time.sleep(0.3)
        cat8_timing_150 = client.evaluate("""(() => {
            collapseAllNodes();
            const t0 = performance.now();
            expandAllNodes();
            const t1 = performance.now();
            return {
                timeMs: +(t1 - t0).toFixed(2),
                rowsRendered: document.querySelectorAll('.tree-row').length
            };
        })()""")
        print(f"Category 8 Expand All at 150% scale (1440x900): {cat8_timing_150['timeMs']} ms ({cat8_timing_150['rowsRendered']} rows)")

        # Reset scale back to 100%
        client.evaluate("setTextScale(1.0); selectCategory('1', false);")
        time.sleep(0.2)

        print("\n" + "="*70)
        print("VERIFICATION: GLOSSARY & ANALYTICS SCROLLABILITY AND FLEX FIX")
        print("="*70)

        # 1. Four Views Scrollability Check (1440x900)
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.0);")
        time.sleep(0.3)

        views_to_test = [
            ("explorer", "#view-explorer", ".tree-scroll-container"),
            ("matrix", "#view-matrix", ".table-scroll-wrapper"),
            ("analytics", "#view-analytics", ".dashboard-view-container"),
            ("glossary", "#view-glossary", "#glossary-cards-container")
        ]

        # Expand category 8 in explorer first so it has enough rows to scroll
        client.evaluate("selectCategory('8', false); expandAllNodes();")
        time.sleep(0.2)

        for vname, vsel, scrl_sel in views_to_test:
            if vname == "analytics":
                client.set_viewport(1280, 600)
            else:
                client.set_viewport(1440, 900)
            time.sleep(0.2)

            res = client.evaluate(f"""(() => {{
                switchView('{vname}', false);
                const view = document.querySelector('{vsel}');
                const scroller = document.querySelector('{scrl_sel}');
                const main = document.querySelector('main.main-content');
                const footer = document.querySelector('footer.app-footer');
                if (!view || !scroller || !main) return {{ error: 'Elements not found' }};

                const mainHeight = main.clientHeight;
                const footerHeight = footer ? footer.offsetHeight : 0;
                const availableHeight = mainHeight - footerHeight;
                const viewHeight = view.clientHeight;
                const isHeightBounded = Math.abs(viewHeight - availableHeight) <= 3;

                const scrollHeight = scroller.scrollHeight;
                const clientHeight = scroller.clientHeight;
                const canScroll = scrollHeight > clientHeight;

                scroller.scrollTop = scrollHeight;
                const finalScrollTop = scroller.scrollTop;
                const reachedEnd = (finalScrollTop + clientHeight) >= (scrollHeight - 2);

                scroller.scrollTop = 0;

                return {{
                    vname: '{vname}',
                    mainHeight,
                    availableHeight,
                    viewHeight,
                    isHeightBounded,
                    scrollHeight,
                    clientHeight,
                    canScroll,
                    finalScrollTop,
                    reachedEnd
                }};
            }})()""")
            print(f"View '{res['vname']}': viewHeight={res['viewHeight']}px (available={res['availableHeight']}px, bounded={res['isHeightBounded']}), scroller scrollHeight={res['scrollHeight']}px vs clientHeight={res['clientHeight']}px (canScroll={res['canScroll']}, reachedEnd={res['reachedEnd']})")
            assert res['isHeightBounded'], f"View '{vname}' height ({res['viewHeight']}px) is not bounded by available space ({res['availableHeight']}px)!"
            assert res['canScroll'], f"View '{vname}' does not have scrollable content ({res['scrollHeight']} <= {res['clientHeight']})"
            assert res['reachedEnd'], f"View '{vname}' could not scroll to the end (finalScrollTop={res['finalScrollTop']}, clientHeight={res['clientHeight']}, scrollHeight={res['scrollHeight']})"

        # 2. Detailed Glossary Checks
        print("\n--- Detailed Glossary Verification ---")
        # 1440x900
        client.set_viewport(1440, 900)
        client.evaluate("switchView('glossary', false); renderGlossaryView('');")
        time.sleep(0.3)

        glossary_measurements_1440 = client.evaluate("""(() => {
            const scroller = document.getElementById('glossary-cards-container');
            const view = document.getElementById('view-glossary');
            const card = document.querySelector('.glossary-card');
            const pagBar = document.getElementById('glossary-pagination-bar');
            
            const scrollerRect = scroller.getBoundingClientRect();
            const viewRect = view.getBoundingClientRect();
            const cardRect = card ? card.getBoundingClientRect() : null;

            // Scrollbar at right edge check: scroller right should equal view right
            const scrollbarAtRight = Math.abs(scrollerRect.right - viewRect.right) <= 2;
            const cardCentered = cardRect ? (cardRect.width <= 762 && Math.abs((cardRect.left - scrollerRect.left) - (scrollerRect.right - cardRect.right)) <= 40) : false;

            scroller.scrollTop = scroller.scrollHeight;
            const lastCard = document.querySelector('.glossary-card:last-child');
            const lastCardRect = lastCard ? lastCard.getBoundingClientRect() : null;
            const pagBarRect = pagBar.getBoundingClientRect();

            const isLastCardVisible = lastCardRect ? (lastCardRect.bottom <= pagBarRect.top + 5 && lastCardRect.top >= scrollerRect.top) : false;
            const isPagBarVisible = window.getComputedStyle(pagBar).display !== 'none' && pagBarRect.height > 20;

            return {
                scrollHeight: scroller.scrollHeight,
                clientHeight: scroller.clientHeight,
                scrollbarAtRight,
                cardCentered,
                cardWidth: cardRect ? cardRect.width : 0,
                isLastCardVisible,
                isPagBarVisible
            };
        })()""")
        print(f"Glossary at 1440x900: scrollHeight={glossary_measurements_1440['scrollHeight']} vs clientHeight={glossary_measurements_1440['clientHeight']}")
        print(f"  • Scrollbar at right edge of view: {glossary_measurements_1440['scrollbarAtRight']}")
        print(f"  • Card max reading width (760px) centred: {glossary_measurements_1440['cardCentered']} (width={glossary_measurements_1440['cardWidth']}px)")
        print(f"  • Last card visible at bottom: {glossary_measurements_1440['isLastCardVisible']}")
        print(f"  • Pagination bar visible simultaneously: {glossary_measurements_1440['isPagBarVisible']}")
        assert glossary_measurements_1440['scrollbarAtRight'], "Glossary scrollbar is not at the right edge of view"
        assert glossary_measurements_1440['isLastCardVisible'], "Last card is not visible when scrolled to bottom"
        assert glossary_measurements_1440['isPagBarVisible'], "Pagination bar is not visible at bottom"

        # Capture screenshot of glossary scrolled to bottom
        client.capture_screenshot("fix_scroll_glossary_bottom.png")

        # 820x1100 (Tablet)
        client.set_viewport(820, 1100)
        time.sleep(0.3)
        tablet_glossary = client.evaluate("""(() => {
            const scroller = document.getElementById('glossary-cards-container');
            scroller.scrollTop = scroller.scrollHeight;
            return {
                scrollHeight: scroller.scrollHeight,
                clientHeight: scroller.clientHeight,
                reachedEnd: (scroller.scrollTop + scroller.clientHeight) >= (scroller.scrollHeight - 2)
            };
        })()""")
        print(f"Glossary at 820x1100 (Tablet): scrollHeight={tablet_glossary['scrollHeight']} vs clientHeight={tablet_glossary['clientHeight']}, reachedEnd={tablet_glossary['reachedEnd']}")
        assert tablet_glossary['reachedEnd'], "Glossary did not scroll to end on tablet"

        # 390x844 (Narrow Mobile/Touch)
        client.set_viewport(390, 844, mobile=True)
        time.sleep(0.3)
        mobile_glossary = client.evaluate("""(() => {
            const scroller = document.getElementById('glossary-cards-container');
            scroller.scrollTop = scroller.scrollHeight;
            return {
                scrollHeight: scroller.scrollHeight,
                clientHeight: scroller.clientHeight,
                reachedEnd: (scroller.scrollTop + scroller.clientHeight) >= (scroller.scrollHeight - 2)
            };
        })()""")
        print(f"Glossary at 390x844 (Mobile): scrollHeight={mobile_glossary['scrollHeight']} vs clientHeight={mobile_glossary['clientHeight']}, reachedEnd={mobile_glossary['reachedEnd']}")
        assert mobile_glossary['reachedEnd'], "Glossary did not scroll to end on mobile"

        # Reset viewport to 1440x900
        client.set_viewport(1440, 900)
        time.sleep(0.3)

        # Keyboard Navigation for Glossary Scrolling
        kb_scroll = client.evaluate("""(() => {
            const scroller = document.getElementById('glossary-cards-container');
            scroller.scrollTop = 0;
            scroller.focus();
            const isFocused = document.activeElement === scroller;
            const hasTabindex = scroller.getAttribute('tabindex') === '0';
            const hasRole = scroller.getAttribute('role') === 'region';

            // Simulate keyboard PageDown scroll
            scroller.scrollBy({ top: 300, behavior: 'instant' });
            const scrolledDown = scroller.scrollTop >= 250;

            // Simulate keyboard Home
            scroller.scrollTop = 0;
            const scrolledHome = scroller.scrollTop === 0;

            return { isFocused, hasTabindex, hasRole, scrolledDown, scrolledHome };
        })()""")
        print(f"Glossary Keyboard Navigation: focusable={kb_scroll['isFocused']} (tabindex={kb_scroll['hasTabindex']}, role={kb_scroll['hasRole']}), scrolls={kb_scroll['scrolledDown']}, returns home={kb_scroll['scrolledHome']}")
        assert kb_scroll['isFocused'], "Glossary container not focusable"
        assert kb_scroll['scrolledDown'], "Glossary container failed to scroll"

        # Glossary Filter box check ("patient" & clear)
        filter_check = client.evaluate("""(() => {
            const searchInput = document.getElementById('glossary-search');
            const scroller = document.getElementById('glossary-cards-container');

            // Type "patient"
            searchInput.value = 'patient';
            renderGlossaryView('patient');
            const matchCount = state.data.elements.filter(e => e.definition && e.definition.trim().length > 0)
                .filter(e => (e.name && e.name.toLowerCase().includes('patient')) || (e.definition && e.definition.toLowerCase().includes('patient')) || (e.hierarchy_id && e.hierarchy_id.includes('patient')) || (e.pcf_id && e.pcf_id.includes('patient'))).length;
            const cardsCount1 = document.querySelectorAll('#glossary-cards-container .glossary-card').length;
            scroller.scrollTop = 200;
            const scrolledWithFilter = scroller.scrollTop > 0;

            // Clear filter
            searchInput.value = '';
            renderGlossaryView('');
            const resetScrollTop = scroller.scrollTop;
            const cardsCount2 = document.querySelectorAll('#glossary-cards-container .glossary-card').length;

            return { matchCount, cardsCount1, scrolledWithFilter, resetScrollTop, cardsCount2 };
        })()""")
        print(f"Glossary Filter 'patient': matches={filter_check['matchCount']}, rendered={filter_check['cardsCount1']}, scrolled={filter_check['scrolledWithFilter']}; After clear: cards={filter_check['cardsCount2']}, scrollTop={filter_check['resetScrollTop']}")
        assert filter_check['matchCount'] > 0, "No matches for 'patient' in glossary"
        assert filter_check['scrolledWithFilter'], "Glossary failed to scroll with filtered results"
        assert filter_check['resetScrollTop'] == 0, "Clearing filter did not reset scroll position to 0"

        # "Show more" behaviour check (must NOT reset scroll position)
        show_more_check = client.evaluate("""(() => {
            const scroller = document.getElementById('glossary-cards-container');
            const pagBar = document.getElementById('glossary-pagination-bar');
            const moreBtn = pagBar.querySelector('button:first-child');

            const countBefore = document.querySelectorAll('#glossary-cards-container .glossary-card').length;
            scroller.scrollTop = 320;
            const scrollPosBefore = scroller.scrollTop;

            moreBtn.click();
            const countAfter = document.querySelectorAll('#glossary-cards-container .glossary-card').length;
            const scrollPosAfter = scroller.scrollTop;

            return {
                countBefore,
                countAfter,
                scrollPosBefore,
                scrollPosAfter,
                preservedScroll: Math.abs(scrollPosAfter - scrollPosBefore) <= 2
            };
        })()""")
        print(f"Glossary 'Show more': count {show_more_check['countBefore']} -> {show_more_check['countAfter']}, scrollTop before={show_more_check['scrollPosBefore']} vs after={show_more_check['scrollPosAfter']} (preserved={show_more_check['preservedScroll']})")
        assert show_more_check['countAfter'] == show_more_check['countBefore'] + 80, f"Expected {show_more_check['countBefore'] + 80} cards after show more, got {show_more_check['countAfter']}"
        assert show_more_check['preservedScroll'], f"Show more reset scroll position from {show_more_check['scrollPosBefore']} to {show_more_check['scrollPosAfter']}!"

        # "Show all (1,931)" behaviour check (smoothness & timing < 300ms)
        show_all_check = client.evaluate("""(() => {
            const pagBar = document.getElementById('glossary-pagination-bar');
            const allBtn = pagBar.querySelector('button:last-child');
            allBtn.click();

            const countAll = document.querySelectorAll('#glossary-cards-container .glossary-card').length;
            const pagBarDisplay = window.getComputedStyle(pagBar).display;
            const renderTime = state._glossaryRenderAllTimeMs || 0;

            return {
                countAll,
                pagBarDisplay,
                renderTime
            };
        })()""")
        print(f"Glossary 'Show all': rendered {show_all_check['countAll']} cards in {show_all_check['renderTime']} ms (target < 300ms), pagBar hidden: {show_all_check['pagBarDisplay'] == 'none'}")
        assert show_all_check['countAll'] == 1931, f"Expected 1931 cards, got {show_all_check['countAll']}"
        assert show_all_check['renderTime'] < 300, f"Show all took {show_all_check['renderTime']} ms (exceeded 300 ms)"
        assert show_all_check['pagBarDisplay'] == 'none', "Pagination bar should be hidden when all cards are shown"

        # 3. Detailed Analytics Checks in Short Window (1280x600)
        print("\n--- Detailed Analytics Dashboard Verification (1280x600) ---")
        for scale, sname, vh in [(1.0, "100", 600), (1.50, "150", 600), (0.85, "85", 480)]:
            client.set_viewport(1280, vh)
            client.evaluate(f"setTextScale({scale}); switchView('analytics', false);")
            time.sleep(0.3)
            analytics_res = client.evaluate("""(() => {
                const scroller = document.querySelector('.dashboard-view-container');
                const view = document.getElementById('view-analytics');
                const donut = document.getElementById('donut-chart-container');
                const chartsGrid = document.querySelector('.dash-charts-grid');

                const scrollHeight = scroller.scrollHeight;
                const clientHeight = scroller.clientHeight;
                const canScroll = scrollHeight > clientHeight;

                scroller.scrollTop = scrollHeight;
                const reachedBottom = (scroller.scrollTop + scroller.clientHeight) >= (scrollHeight - 2);

                const sRect = scroller.getBoundingClientRect();
                const chartsRect = chartsGrid.getBoundingClientRect();
                const chartsAtBottom = Math.abs(chartsRect.bottom - sRect.bottom) <= 60;

                // Donut chart is visible when scrolled to bottom / charts section
                const donutRect = donut.getBoundingClientRect();
                const donutVisibleInScroll = (donutRect.bottom > sRect.top) && (donutRect.top < sRect.bottom);

                return {
                    scrollHeight,
                    clientHeight,
                    canScroll,
                    scrollTop: scroller.scrollTop,
                    reachedBottom,
                    chartsAtBottom,
                    donutVisibleInScroll
                };
            })()""")
            print(f"Analytics at {sname}% scale (1280x{vh}): scrollHeight={analytics_res['scrollHeight']}px vs clientHeight={analytics_res['clientHeight']}px (canScroll={analytics_res['canScroll']}, reachedBottom={analytics_res['reachedBottom']}, chartsAtBottom={analytics_res['chartsAtBottom']}, donutVisible={analytics_res['donutVisibleInScroll']})")
            assert analytics_res['canScroll'], f"Analytics at {sname}% scale did not scroll ({analytics_res['scrollHeight']} <= {analytics_res['clientHeight']})"
            assert analytics_res['reachedBottom'], f"Analytics at {sname}% scale could not scroll to the bottom"
            assert analytics_res['chartsAtBottom'], f"Analytics at {sname}% scale charts grid did not reach the bottom"
            assert analytics_res['donutVisibleInScroll'], f"Analytics at {sname}% scale donut chart is not visible when scrolled"

            if sname == "150":
                client.capture_screenshot("fix_scroll_analytics_150.png")

        # 4. Check Inspector Scrolling
        print("\n--- Inspector Drawer Scrolling Check ---")
        client.set_viewport(1440, 900)
        client.evaluate("setTextScale(1.0); switchView('explorer', false); jumpToElement('10083');")
        time.sleep(0.4)
        inspector_scroll = client.evaluate("""(() => {
            const body = document.getElementById('inspector-content');
            const canScroll = body.scrollHeight > body.clientHeight;
            body.scrollTop = body.scrollHeight;
            const reachedEnd = (body.scrollTop + body.clientHeight) >= (body.scrollHeight - 2);
            body.scrollTop = 0;
            return { canScroll, reachedEnd, scrollHeight: body.scrollHeight, clientHeight: body.clientHeight };
        })()""")
        print(f"Inspector drawer: scrollHeight={inspector_scroll['scrollHeight']}px vs clientHeight={inspector_scroll['clientHeight']}px (canScroll={inspector_scroll['canScroll']}, reachedEnd={inspector_scroll['reachedEnd']})")
        assert inspector_scroll['canScroll'], "Inspector drawer content does not overflow to scroll"

        # 5. Check Print Stylesheet Rules
        print("\n--- Print Stylesheet Rules Check ---")
        print_rules = client.evaluate("""(() => {
            let foundPrint = false;
            let overflowVisible = false;
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        if (rule.media && rule.media.mediaText.includes('print')) {
                            foundPrint = true;
                            for (const inner of rule.cssRules) {
                                if (inner.selectorText && (inner.selectorText.includes('view-panel') || inner.selectorText.includes('glossary-view-container'))) {
                                    if (inner.style.overflow === 'visible') overflowVisible = true;
                                }
                            }
                        }
                    }
                } catch (e) {}
            }
            return { foundPrint, overflowVisible };
        })()""")
        print(f"Print stylesheet: found print media={print_rules['foundPrint']}, view-panel/glossary overflow:visible={print_rules['overflowVisible']}")
        assert print_rules['overflowVisible'], "Print stylesheet missing overflow: visible for view containers"

        # ======================================================================
        # PHASE 3 THEMES EXTENSION: INDIGO ROSE & ELECTRIC CANARY VERIFICATION
        # ======================================================================
        print("\n" + "="*70)
        print("THEME VERIFICATION: INDIGO ROSE, ELECTRIC CANARY, OBSIDIAN DARK & LIGHT")
        print("="*70)

        # 1. Theme Menu UI & Keyboard Navigation
        print("\n--- Theme Menu UI & Keyboard Navigation ---")
        menu_test = client.evaluate("""(() => {
            const trigger = document.getElementById('theme-toggle-btn');
            const dropdown = document.getElementById('theme-menu-dropdown');
            const items = Array.from(dropdown.querySelectorAll('.theme-menu-item'));
            
            // Initial state: closed
            const initiallyHidden = dropdown.hasAttribute('hidden');
            
            // Open via click
            trigger.click();
            const openedOnClick = !dropdown.hasAttribute('hidden') && trigger.getAttribute('aria-expanded') === 'true';
            
            // Check active item is focused
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const activeItem = dropdown.querySelector('.theme-menu-item.active');
            const activeItemFocused = (document.activeElement === activeItem);
            
            // Keyboard ArrowDown
            dropdown.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
            const itemAfterDown = document.activeElement ? document.activeElement.getAttribute('data-theme') : null;
            
            // Keyboard ArrowUp
            dropdown.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
            const itemAfterUp = document.activeElement ? document.activeElement.getAttribute('data-theme') : null;
            
            // Keyboard End (jumps to last item)
            dropdown.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
            const lastItem = document.activeElement ? document.activeElement.getAttribute('data-theme') : null;
            
            // Keyboard Home (jumps to first item)
            dropdown.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
            const firstItem = document.activeElement ? document.activeElement.getAttribute('data-theme') : null;
            
            // Keyboard Escape (closes menu and returns focus to trigger)
            dropdown.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            const closedOnEsc = dropdown.hasAttribute('hidden') && trigger.getAttribute('aria-expanded') === 'false';
            const focusReturnedToTrigger = (document.activeElement === trigger);
            
            // Test selection with Enter
            trigger.click();
            const secondItem = items[1]; // 'light'
            secondItem.focus();
            dropdown.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
            const closedOnSelect = dropdown.hasAttribute('hidden');
            const themeAfterEnter = document.documentElement.getAttribute('data-theme');
            
            // Test outside click closes menu
            trigger.click();
            document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            const closedOnOutsideClick = dropdown.hasAttribute('hidden');
            
            // Restore dark
            applyTheme('dark');

            return {
                initiallyHidden,
                openedOnClick,
                activeItemFocused,
                itemAfterDown,
                itemAfterUp,
                firstItem,
                lastItem,
                closedOnEsc,
                focusReturnedToTrigger,
                closedOnSelect,
                themeAfterEnter,
                closedOnOutsideClick
            };
        })()""")
        print(f"Theme Menu UI checks: opened={menu_test['openedOnClick']}, focusIn={menu_test['activeItemFocused']}, ArrowDown={menu_test['itemAfterDown']}, Home={menu_test['firstItem']}, End={menu_test['lastItem']}, EscClose={menu_test['closedOnEsc']}, FocusReturn={menu_test['focusReturnedToTrigger']}, SelectEnter={menu_test['themeAfterEnter']}, OutsideClickClose={menu_test['closedOnOutsideClick']}")
        assert menu_test['openedOnClick'], "Theme menu failed to open on click"
        assert menu_test['closedOnEsc'], "Theme menu failed to close on Escape"
        assert menu_test['focusReturnedToTrigger'], "Focus failed to return to trigger button after Escape"
        assert menu_test['themeAfterEnter'] == 'light', "Enter key on menu item failed to select theme"
        assert menu_test['closedOnOutsideClick'], "Theme menu failed to close on outside click"

        # 2. Cycle all four themes and verify attributes
        print("\n--- Four Themes Cycling & Attributes ---")
        theme_cycles = [
            ("dark", "dark", "Obsidian dark"),
            ("light", "light", "Light"),
            ("indigo-rose", "light", "Indigo Rose"),
            ("electric-canary", "light", "Electric Canary")
        ]
        for theme_name, exp_color_scheme, label in theme_cycles:
            client.evaluate(f"applyTheme('{theme_name}')")
            time.sleep(0.15)
            t_check = client.evaluate(f"""(() => {{
                const htmlTheme = document.documentElement.getAttribute('data-theme');
                const compScheme = window.getComputedStyle(document.documentElement).colorScheme;
                const dropdown = document.getElementById('theme-menu-dropdown');
                const activeItem = dropdown.querySelector('.theme-menu-item[data-theme="{theme_name}"]');
                const isChecked = activeItem ? activeItem.getAttribute('aria-checked') : null;
                const bodyBg = window.getComputedStyle(document.body).backgroundColor;
                const bodyColor = window.getComputedStyle(document.body).color;
                return {{
                    htmlTheme,
                    compScheme,
                    isChecked,
                    bodyBg,
                    bodyColor
                }};
            }})()""")
            print(f"Theme '{theme_name}' ({label}): data-theme={t_check['htmlTheme']}, color-scheme={t_check['compScheme']}, aria-checked={t_check['isChecked']}, bodyBg={t_check['bodyBg']}")
            assert t_check['htmlTheme'] == theme_name, f"Theme {theme_name} data-theme mismatch"
            assert t_check['compScheme'] == exp_color_scheme, f"Theme {theme_name} color-scheme mismatch: expected {exp_color_scheme}, got {t_check['compScheme']}"
            assert t_check['isChecked'] == 'true', f"Theme {theme_name} aria-checked not set to true"

        # 3. Automated WCAG Contrast Ratio Verification
        print("\n--- Programmatic WCAG AA Contrast Verification (All 4 Themes) ---")
        contrast_results = client.evaluate("""(() => {
            function lum(rgbStr) {
                let r, g, b;
                if (rgbStr.startsWith('#')) {
                    let hex = rgbStr.slice(1);
                    if (hex.length === 3) hex = hex.split('').map(x => x + x).join('');
                    r = parseInt(hex.slice(0, 2), 16);
                    g = parseInt(hex.slice(2, 4), 16);
                    b = parseInt(hex.slice(4, 6), 16);
                } else {
                    const m = rgbStr.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (!m) return 0;
                    r = parseInt(m[1]);
                    g = parseInt(m[2]);
                    b = parseInt(m[3]);
                }
                const [rs, gs, bs] = [r, g, b].map(c => {
                    const v = c / 255;
                    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                });
                return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
            }
            function cr(c1, c2) {
                const l1 = lum(c1);
                const l2 = lum(c2);
                return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
            }
            function getVar(name) {
                return window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
            }

            const results = {};
            const themes = ['dark', 'light', 'indigo-rose', 'electric-canary'];
            
            for (const t of themes) {
                applyTheme(t);
                const bgApp = getVar('--bg-app');
                const bgPanel = getVar('--bg-panel');
                const bgInspector = getVar('--bg-inspector');
                const bgSelected = getVar('--bg-selected');
                
                const text = getVar('--text');
                const textMuted = getVar('--text-muted');
                const accentText = getVar('--accent-text');
                const actionFill = getVar('--action-fill');
                const actionText = getVar('--action-text');
                const statusNew = getVar('--status-new');
                const statusRemoved = getVar('--status-removed');
                const statusRenamed = getVar('--status-renamed');
                const edgeSelected = getVar('--edge-selected');
                const focusRing = getVar('--focus-ring');
                const borderInput = getVar('--border-input');

                results[t] = {
                    text_on_app: cr(text, bgApp),
                    text_on_panel: cr(text, bgPanel),
                    text_on_inspector: cr(text, bgInspector),
                    text_on_selected: cr(text, bgSelected),
                    muted_on_app: cr(textMuted, bgApp),
                    muted_on_panel: cr(textMuted, bgPanel),
                    accent_on_app: cr(accentText, bgApp),
                    accent_on_panel: cr(accentText, bgPanel),
                    action_text_on_fill: cr(actionText, actionFill),
                    status_new_on_app: cr(statusNew, bgApp),
                    status_new_on_panel: cr(statusNew, bgPanel),
                    status_removed_on_app: cr(statusRemoved, bgApp),
                    status_removed_on_panel: cr(statusRemoved, bgPanel),
                    status_renamed_on_app: cr(statusRenamed, bgApp),
                    status_renamed_on_panel: cr(statusRenamed, bgPanel),
                    edge_on_app: cr(edgeSelected, bgApp),
                    edge_on_panel: cr(edgeSelected, bgPanel),
                    focus_ring_on_app: cr(focusRing, bgApp),
                    border_input_on_panel: cr(borderInput, bgPanel)
                };
            }
            return results;
        })()""")

        for tname, res in contrast_results.items():
            print(f"\nContrast Measurements for '{tname}':")
            print(f"  • --text on --bg-app: {res['text_on_app']:.2f}:1, on --bg-panel: {res['text_on_panel']:.2f}:1")
            print(f"  • --text-muted on --bg-app: {res['muted_on_app']:.2f}:1, on --bg-panel: {res['muted_on_panel']:.2f}:1")
            print(f"  • --accent-text on --bg-app: {res['accent_on_app']:.2f}:1, on --bg-panel: {res['accent_on_panel']:.2f}:1")
            print(f"  • --action-text on --action-fill: {res['action_text_on_fill']:.2f}:1")
            print(f"  • --status-new on --bg-app: {res['status_new_on_app']:.2f}:1, on --bg-panel: {res['status_new_on_panel']:.2f}:1")
            print(f"  • --status-removed on --bg-app: {res['status_removed_on_app']:.2f}:1, on --bg-panel: {res['status_removed_on_panel']:.2f}:1")
            print(f"  • --status-renamed on --bg-app: {res['status_renamed_on_app']:.2f}:1, on --bg-panel: {res['status_renamed_on_panel']:.2f}:1")
            print(f"  • --edge-selected on --bg-app: {res['edge_on_app']:.2f}:1, UI component: {res['edge_on_panel']:.2f}:1")
            print(f"  • --focus-ring on --bg-app: {res['focus_ring_on_app']:.2f}:1")
            print(f"  • --border-input on --bg-panel: {res['border_input_on_panel']:.2f}:1")
            
            # Assert text >= 4.5:1
            assert res['text_on_app'] >= 4.5, f"{tname}: text_on_app failed 4.5:1"
            assert res['text_on_panel'] >= 4.5, f"{tname}: text_on_panel failed 4.5:1"
            assert res['muted_on_app'] >= 4.5, f"{tname}: muted_on_app failed 4.5:1"
            assert res['muted_on_panel'] >= 4.5, f"{tname}: muted_on_panel failed 4.5:1"
            assert res['accent_on_app'] >= 4.5, f"{tname}: accent_on_app failed 4.5:1"
            assert res['accent_on_panel'] >= 4.5, f"{tname}: accent_on_panel failed 4.5:1"
            assert res['action_text_on_fill'] >= 4.5, f"{tname}: action_text_on_fill failed 4.5:1"
            assert res['status_new_on_app'] >= 4.5, f"{tname}: status_new_on_app failed 4.5:1"
            assert res['status_new_on_panel'] >= 4.5, f"{tname}: status_new_on_panel failed 4.5:1"
            assert res['status_removed_on_app'] >= 4.5, f"{tname}: status_removed_on_app failed 4.5:1"
            assert res['status_removed_on_panel'] >= 4.5, f"{tname}: status_removed_on_panel failed 4.5:1"
            assert res['status_renamed_on_app'] >= 4.5, f"{tname}: status_renamed_on_app failed 4.5:1"
            assert res['status_renamed_on_panel'] >= 4.5, f"{tname}: status_renamed_on_panel failed 4.5:1"
            # Assert UI components >= 3.0:1
            assert res['edge_on_app'] >= 3.0, f"{tname}: edge_on_app failed 3.0:1"
            assert res['focus_ring_on_app'] >= 3.0, f"{tname}: focus_ring_on_app failed 3.0:1"
            assert res['border_input_on_panel'] >= 3.0, f"{tname}: border_input_on_panel failed 3.0:1"

        # 4. Storage Safety & Fallback Verification
        print("\n--- Theme Storage Fallback Verification ---")
        persist_test = client.evaluate("""(() => {
            applyTheme('indigo-rose');
            const saved = storeGet('pcf_theme', 'dark');
            return { saved };
        })()""")
        print(f"Persisted theme in storage: {persist_test['saved']} (expected 'indigo-rose')")
        assert persist_test['saved'] == 'indigo-rose', "Failed to persist theme in storage"

        # 5. Capture 10 Screenshots for Indigo Rose & Electric Canary
        print("\n--- Capturing 10 Theme Screenshots under docs/screenshots/ ---")
        client.set_viewport(1440, 900)
        
        for theme_key in ["indigo_rose", "electric_canary"]:
            theme_val = "indigo-rose" if theme_key == "indigo_rose" else "electric-canary"
            print(f"\nGenerating screenshots for theme '{theme_val}'...")
            client.evaluate(f"applyTheme('{theme_val}')")
            time.sleep(0.2)
            
            # 1. Explorer with Category 7 expanded, 7.1.1 selected, inspector open
            client.evaluate("""(() => {
                toggleSidebar(false);
                toggleInspector(true);
                switchView('explorer', false);
                jumpToElement('20958');
            })()""")
            time.sleep(0.5)
            client.capture_screenshot(f"theme_{theme_key}_explorer.png")
            
            # 2. Change Table View
            client.evaluate("switchView('matrix', false)")
            time.sleep(0.4)
            client.capture_screenshot(f"theme_{theme_key}_change_table.png")
            
            # 3. Analytics View (with donut)
            client.evaluate("switchView('analytics', false)")
            time.sleep(0.4)
            client.capture_screenshot(f"theme_{theme_key}_analytics.png")
            
            # 4. Glossary View (scrolled)
            client.evaluate("""(() => {
                switchView('glossary', false);
                const scroller = document.getElementById('glossary-cards-container');
                if (scroller) scroller.scrollTop = 300;
            })()""")
            time.sleep(0.4)
            client.capture_screenshot(f"theme_{theme_key}_glossary.png")
            
            # 5. Upload Error Dialog
            client.evaluate("""(() => {
                switchView('explorer', false);
                openUploadModal();
                showUploadModalError("Sheet 'Glossary terms' wasn't found. Use a 'vX vs vY' workbook from apqc.org/pcf.");
            })()""")
            time.sleep(0.4)
            client.capture_screenshot(f"theme_{theme_key}_upload_error.png")
            client.evaluate("closeUploadModal()")
            time.sleep(0.2)

        # 6. Retail Workbook Upload in both themes
        print("\n--- Retail Workbook Upload in New Themes ---")
        with open(retail_path, "rb") as f:
            retail_b64 = base64.b64encode(f.read()).decode("ascii")

        # In indigo-rose:
        client.evaluate(f"""(() => {{
            applyTheme('indigo-rose');
            const binary = atob("{retail_b64}");
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {{
                bytes[i] = binary.charCodeAt(i);
            }}
            pendingWorkbookBuffer = bytes;
            pendingFileName = "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx";
            openUploadModal(bytes, pendingFileName);
            document.getElementById('confirm-upload-btn').click();
        }})()""")
        time.sleep(0.5)
        retail_ir_check = client.evaluate("""({
            elements: state.data.elements.length,
            theme: document.documentElement.getAttribute('data-theme'),
            isCustom: state.isCustomLoaded
        })""")
        print(f"Retail loaded in Indigo Rose: elements={retail_ir_check['elements']}, theme={retail_ir_check['theme']}, isCustom={retail_ir_check['isCustom']}")
        assert retail_ir_check['elements'] == 1708, "Retail load in Indigo Rose failed"
        assert retail_ir_check['theme'] == 'indigo-rose', "Theme unexpectedly changed during upload"

        # Switch to electric-canary:
        client.evaluate("applyTheme('electric-canary')")
        time.sleep(0.2)
        retail_ec_check = client.evaluate("""({
            elements: state.data.elements.length,
            theme: document.documentElement.getAttribute('data-theme'),
            isCustom: state.isCustomLoaded
        })""")
        print(f"Retail in Electric Canary: elements={retail_ec_check['elements']}, theme={retail_ec_check['theme']}, isCustom={retail_ec_check['isCustom']}")
        assert retail_ec_check['elements'] == 1708, "Retail elements lost when switching theme"

        # Reset back to default Healthcare
        client.evaluate("document.getElementById('reset-default-pcf-btn').click()")
        time.sleep(0.3)
        restored = client.evaluate("state.data.elements.length")
        print(f"Restored dataset to default: elements={restored}")
        assert restored == 1985, "Failed to restore Healthcare default dataset"

        # 7. Scrolling intact across themes
        print("\n--- Scrolling Intact Across Themes ---")
        client.evaluate("applyTheme('light'); switchView('glossary', false);")
        time.sleep(0.2)
        light_scroll = client.evaluate("document.getElementById('glossary-cards-container').scrollHeight > document.getElementById('glossary-cards-container').clientHeight")
        client.evaluate("applyTheme('dark');")
        time.sleep(0.2)
        dark_scroll = client.evaluate("document.getElementById('glossary-cards-container').scrollHeight > document.getElementById('glossary-cards-container').clientHeight")
        print(f"Scrolling intact in Light theme: {light_scroll}, Dark theme: {dark_scroll}")
        assert light_scroll and dark_scroll, "Theme toggle broke scrolling"

        # Reset to Explorer View & Dark Theme
        client.evaluate("applyTheme('dark'); switchView('explorer', false);")
        time.sleep(0.2)

        # Check for any console errors
        print(f"\nConsole Errors Count: {len(client.console_errors)}")
        if client.console_errors:
            for err in client.console_errors:
                print("  Console Error:", err)
        assert len(client.console_errors) == 0, f"Encountered {len(client.console_errors)} console errors"

        client.close()
        print("\n" + "="*70)
        print("ALL BROWSER E2E TESTS AND SCREENSHOT CAPTURES PASSED 100%!")
        print("="*70)

    finally:
        chrome_proc.send_signal(signal.SIGTERM)
        server_proc.send_signal(signal.SIGTERM)
        time.sleep(0.5)

if __name__ == "__main__":
    run_tests()
