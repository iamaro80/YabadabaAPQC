"""
Text size control, stepping, shortcuts, layout ratios, and scaling browser tests.
"""

import time

def run_scaling_tests(client):
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

    client.evaluate("""(() => {
        switchView('explorer', false);
        jumpToElement('20958');
    })()""")
    time.sleep(0.5)
    client.capture_screenshot("scale_85_explorer_cat7.png")

    client.capture_screenshot("scale_85_inspector.png")

    client.evaluate("switchView('matrix', true)")
    time.sleep(0.5)
    client.capture_screenshot("scale_85_change_table.png")

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

    client.evaluate("""(() => {
        switchView('explorer', false);
        jumpToElement('20958');
    })()""")
    time.sleep(0.5)
    client.capture_screenshot("scale_150_explorer_cat7.png")

    client.capture_screenshot("scale_150_inspector.png")

    client.evaluate("switchView('matrix', true)")
    time.sleep(0.5)
    client.capture_screenshot("scale_150_change_table.png")

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

    # 9. Category 8 Expand All Timing at 100% and 150%
    print("\n" + "="*70)
    print("CATEGORY 8 'EXPAND ALL' TIMING AT 100% AND 150% SCALE")
    print("="*70)

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

    # Reset scale back to 100% and category 1
    client.evaluate("setTextScale(1.0); selectCategory('1', false);")
    time.sleep(0.2)
