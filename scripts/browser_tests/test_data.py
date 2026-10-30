"""
Data integrity, attribution, and workbook upload/reset browser tests.
"""

import os
import time
import base64

def run_data_tests(client, project_dir):
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

    # Brand & Rebrand Assertions
    brand_info = client.evaluate("""({
        brandTitle: document.querySelector('.brand-title')?.textContent.trim(),
        headerTitle: document.getElementById('header-framework-title')?.textContent.trim(),
        headerVersion: document.getElementById('header-version-badge')?.textContent.trim(),
        pageTitle: document.title,
        footerDisclaimer: document.getElementById('footer-disclaimer')?.textContent.trim(),
        resetBtnLabel: document.getElementById('reset-default-pcf-btn')?.textContent.trim(),
        logoUseHref: document.querySelector('.header-logo use')?.getAttribute('href')
    })""")
    print(f"Brand Title: {brand_info['brandTitle']} (expected: YabadabaAPQC)")
    print(f"Header Subtitle: {brand_info['headerTitle']} (expected: Sample data: Healthcare Provider)")
    print(f"Header Version Badge: '{brand_info['headerVersion']}' (expected empty for sample data)")
    print(f"Page Title: {brand_info['pageTitle']} (expected: YabadabaAPQC · APQC Healthcare Provider PCF v7.2.1)")
    print(f"Footer Disclaimer: {brand_info['footerDisclaimer']}")
    print(f"Reset Button Label: {brand_info['resetBtnLabel']} (expected: Back to sample data)")
    print(f"Logo Mark: {brand_info['logoUseHref']} (expected: #logo-mark)")

    assert brand_info['brandTitle'] == "YabadabaAPQC", "Brand title must be YabadabaAPQC"
    assert brand_info['headerTitle'] == "Sample data: Healthcare Provider", "Initial subtitle must be 'Sample data: Healthcare Provider'"
    assert brand_info['headerVersion'] == "", "Initial version badge should be empty for sample data"
    assert brand_info['pageTitle'] == "YabadabaAPQC · APQC Healthcare Provider PCF v7.2.1", "Page title mismatch"
    assert brand_info['footerDisclaimer'] == "YabadabaAPQC is an independent tool. It is not affiliated with or endorsed by APQC.", "Footer disclaimer mismatch"
    assert brand_info['resetBtnLabel'] == "Back to sample data", "Reset button text mismatch"
    assert brand_info['logoUseHref'] == "#logo-mark", "Logo use href mismatch"

    # Upload & Custom Workbook Recovery (Phase 1D)
    print("\n" + "="*70)
    print("PHASE 1D: IN-BROWSER WORKBOOK UPLOAD & RECOVERY (RETAIL PCF)")
    print("="*70)

    retail_path = os.path.join(project_dir, "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx")
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

    # Check Dynamic Header & Title for Custom Workbook
    custom_titles = client.evaluate("""({
        headerTitle: document.getElementById('header-framework-title')?.textContent.trim(),
        headerVersion: document.getElementById('header-version-badge')?.textContent.trim(),
        pageTitle: document.title,
        csvFilename: (() => {
            let rawFw = (state.data?.metadata?.framework || "pcf").toLowerCase();
            rawFw = rawFw.replace(/\\b(apqc|pcf|process\\s+classification\\s+framework)\\b/gi, "");
            let shortName = rawFw.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
            if (!shortName) shortName = "pcf";
            return `yabadabaapqc_${shortName}_${state.activeView}.csv`;
        })()
    })""")
    print(f"Retail Header Title: {custom_titles['headerTitle']} (expected: APQC Retail PCF)")
    print(f"Retail Version: {custom_titles['headerVersion']} (expected: v7.2.1)")
    print(f"Retail Page Title: {custom_titles['pageTitle']} (expected: YabadabaAPQC · APQC Retail PCF v7.2.1)")
    print(f"Retail CSV Filename: {custom_titles['csvFilename']} (expected: yabadabaapqc_retail_explorer.csv)")

    assert custom_titles['headerTitle'] == "APQC Retail PCF", "Custom header title mismatch"
    assert custom_titles['pageTitle'] == "YabadabaAPQC · APQC Retail PCF v7.2.1", "Custom page title mismatch"
    assert custom_titles['csvFilename'] == "yabadabaapqc_retail_explorer.csv", "CSV export filename pattern mismatch"

    # Test Reset to Default
    client.evaluate("document.getElementById('reset-default-pcf-btn').click()")
    time.sleep(0.3)
    restored_elements = client.evaluate("state.data.elements.length")
    is_custom = client.evaluate("state.isCustomLoaded")
    reset_titles = client.evaluate("""({
        headerTitle: document.getElementById('header-framework-title')?.textContent.trim(),
        pageTitle: document.title
    })""")
    print(f"After Reset: elements={restored_elements} (Expected: 1985), isCustomLoaded={is_custom} (Expected: False)")
    print(f"Restored Header Title: {reset_titles['headerTitle']} (expected: Sample data: Healthcare Provider)")
    print(f"Restored Page Title: {reset_titles['pageTitle']} (expected: YabadabaAPQC · APQC Healthcare Provider PCF v7.2.1)")

    assert restored_elements == 1985, "Reset failed to restore Healthcare dataset"
    assert not is_custom, "isCustomLoaded should be false after reset"
    assert reset_titles['headerTitle'] == "Sample data: Healthcare Provider", "Header title did not reset"
    assert reset_titles['pageTitle'] == "YabadabaAPQC · APQC Healthcare Provider PCF v7.2.1", "Page title did not reset"

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
