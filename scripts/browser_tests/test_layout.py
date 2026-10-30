"""
Layout, collapsing panels, inspector, navigation, scrolling, and print stylesheet tests.
"""

import time

def run_layout_tests(client, project_dir):
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

    # Item 1 Squashed Sections verification
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

    # Detailed Glossary & Analytics Scrollability
    print("\n" + "="*70)
    print("VERIFICATION: GLOSSARY & ANALYTICS SCROLLABILITY AND FLEX FIX")
    print("="*70)

    client.set_viewport(1440, 900)
    client.evaluate("setTextScale(1.0);")
    time.sleep(0.3)

    views_to_test = [
        ("explorer", "#view-explorer", ".tree-scroll-container"),
        ("matrix", "#view-matrix", ".table-scroll-wrapper"),
        ("analytics", "#view-analytics", ".dashboard-view-container"),
        ("glossary", "#view-glossary", "#glossary-cards-container")
    ]

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

    # Detailed Glossary Checks
    print("\n--- Detailed Glossary Verification ---")
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

        scroller.scrollBy({ top: 300, behavior: 'instant' });
        const scrolledDown = scroller.scrollTop >= 250;

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

        searchInput.value = 'patient';
        renderGlossaryView('patient');
        const matchCount = state.data.elements.filter(e => e.definition && e.definition.trim().length > 0)
            .filter(e => (e.name && e.name.toLowerCase().includes('patient')) || (e.definition && e.definition.toLowerCase().includes('patient')) || (e.hierarchy_id && e.hierarchy_id.includes('patient')) || (e.pcf_id && e.pcf_id.includes('patient'))).length;
        const cardsCount1 = document.querySelectorAll('#glossary-cards-container .glossary-card').length;
        scroller.scrollTop = 200;
        const scrolledWithFilter = scroller.scrollTop > 0;

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

    # Detailed Analytics Checks in Short Window (1280x600)
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

    # Check Inspector Scrolling
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

    # Check Print Stylesheet Rules
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
