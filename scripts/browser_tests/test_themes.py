"""
Theme system, WCAG AA contrast, keyboard navigation, and theme screenshots browser tests.
"""

import os
import time
import base64
from browser_tests.cdp_client import load_workbook

def run_theme_tests(client, project_dir):
    print("\n" + "="*70)
    print("THEME VERIFICATION: INDIGO ROSE, ELECTRIC CANARY, DARK & LIGHT")
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
        ("dark", "dark", "Dark"),
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
            const logoBg = getVar('--logo-bg');

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
                border_input_on_panel: cr(borderInput, bgPanel),
                logo_white_on_bg: cr('#ffffff', logoBg),
                footer_disclaimer_on_panel: cr(textMuted, bgPanel)
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
        print(f"  • Logo white on --logo-bg: {res['logo_white_on_bg']:.2f}:1")
        print(f"  • Footer disclaimer on --bg-panel: {res['footer_disclaimer_on_panel']:.2f}:1")
        
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
        assert res['logo_white_on_bg'] >= 4.5, f"{tname}: logo_white_on_bg failed 4.5:1"
        assert res['footer_disclaimer_on_panel'] >= 4.5, f"{tname}: footer_disclaimer_on_panel failed 4.5:1"
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

    # Capture Brand Screenshots: brand_header_dark.png, brand_header_light.png, brand_tab_zoom.png
    print("\n--- Capturing Brand Header & Tab Zoom Screenshots ---")
    client.set_viewport(1440, 900)

    # 1. brand_header_dark.png
    client.evaluate("applyTheme('dark'); switchView('explorer', false);")
    time.sleep(0.3)
    header_clip_dark = client.evaluate("""(() => {
        const h = document.querySelector('header.app-header');
        const r = h.getBoundingClientRect();
        return { x: Math.floor(r.x), y: Math.floor(r.y), width: Math.ceil(r.width), height: Math.ceil(r.height), scale: 1 };
    })()""")
    client.capture_screenshot("brand_header_dark.png", clip=header_clip_dark)

    # 2. brand_header_light.png
    client.evaluate("applyTheme('light');")
    time.sleep(0.3)
    header_clip_light = client.evaluate("""(() => {
        const h = document.querySelector('header.app-header');
        const r = h.getBoundingClientRect();
        return { x: Math.floor(r.x), y: Math.floor(r.y), width: Math.ceil(r.width), height: Math.ceil(r.height), scale: 1 };
    })()""")
    client.capture_screenshot("brand_header_light.png", clip=header_clip_light)

    # 3. brand_tab_zoom.png
    client.evaluate("applyTheme('dark');")
    tab_clip = client.evaluate("""(() => {
        let el = document.getElementById('tab-zoom-showcase');
        if (el) el.remove();
        el = document.createElement('div');
        el.id = 'tab-zoom-showcase';
        el.style.position = 'fixed';
        el.style.top = '60px';
        el.style.left = '60px';
        el.style.zIndex = '999999';
        el.style.padding = '24px 28px';
        el.style.background = '#1a1a1a';
        el.style.border = '1px solid #3a3a3a';
        el.style.borderRadius = '12px';
        el.style.boxShadow = '0 24px 48px rgba(0,0,0,0.5)';
        el.style.fontFamily = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        el.style.color = '#fff';
        el.style.display = 'flex';
        el.style.flexDirection = 'column';
        el.style.gap = '20px';
        el.style.width = '520px';

        const faviconHref = document.querySelector('link[rel="icon"]').href;
        const pageTitle = document.title;

        el.innerHTML = `
            <div style="font-size: 13px; font-weight: 600; color: #999; text-transform: uppercase; letter-spacing: 0.06em;">Browser Tab & Favicon Inspection</div>
            <!-- Simulated Desktop Browser Tab -->
            <div style="display: flex; align-items: center; background: #2b2b2b; border-radius: 8px 8px 0 0; padding: 10px 14px; border-top: 2px solid #6b57d6; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                <img src="${faviconHref}" width="16" height="16" style="margin-right: 10px; display: block; flex-shrink: 0;" alt="Tab Icon" />
                <span style="font-size: 13px; font-weight: 500; color: #ececec; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1;">${pageTitle}</span>
                <span style="font-size: 14px; color: #777; margin-left: 10px; line-height: 1;">✕</span>
            </div>
            <!-- Crisp Pixel Scale Grids -->
            <div style="display: flex; gap: 20px; align-items: flex-end; padding-top: 14px; border-top: 1px solid #2e2e2e;">
                <div style="text-align: center;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 6px;">16×16 (1x)</div>
                    <div style="padding: 12px; background: #262626; border: 1px solid #333; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px;">
                        <img src="${faviconHref}" width="16" height="16" style="display: block;" />
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 6px;">32×32 (2x)</div>
                    <div style="padding: 12px; background: #262626; border: 1px solid #333; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; width: 60px; height: 60px;">
                        <img src="${faviconHref}" width="32" height="32" style="display: block;" />
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 6px;">64×64 (4x)</div>
                    <div style="padding: 12px; background: #262626; border: 1px solid #333; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; width: 92px; height: 92px;">
                        <img src="${faviconHref}" width="64" height="64" style="display: block;" />
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 6px;">128×128 (8x Zoom)</div>
                    <div style="padding: 12px; background: #262626; border: 1px solid #333; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; width: 156px; height: 156px;">
                        <img src="${faviconHref}" width="128" height="128" style="display: block;" />
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(el);
        const r = el.getBoundingClientRect();
        return { x: Math.floor(r.x), y: Math.floor(r.y), width: Math.ceil(r.width), height: Math.ceil(r.height), scale: 1 };
    })()""")
    time.sleep(0.3)
    client.capture_screenshot("brand_tab_zoom.png", clip=tab_clip)
    client.evaluate("document.getElementById('tab-zoom-showcase')?.remove()")
    client.evaluate("applyTheme('dark');")

    # 6. Retail Workbook Upload in both themes
    print("\n--- Retail Workbook Upload in New Themes ---")
    retail_path = os.path.join(project_dir, "K09276_Retail_v721_vs_Retail_v611_April 2023.xlsx")
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
        appState: state.appState
    })""")
    print(f"Retail loaded in Indigo Rose: elements={retail_ir_check['elements']}, theme={retail_ir_check['theme']}, appState={retail_ir_check['appState']}")
    assert retail_ir_check['elements'] == 1708, "Retail load in Indigo Rose failed"
    assert retail_ir_check['theme'] == 'indigo-rose', "Theme unexpectedly changed during upload"

    # Switch to electric-canary:
    client.evaluate("applyTheme('electric-canary')")
    time.sleep(0.2)
    retail_ec_check = client.evaluate("""({
        elements: state.data.elements.length,
        theme: document.documentElement.getAttribute('data-theme'),
        appState: state.appState
    })""")
    print(f"Retail in Electric Canary: elements={retail_ec_check['elements']}, theme={retail_ec_check['theme']}, appState={retail_ec_check['appState']}")
    assert retail_ec_check['elements'] == 1708, "Retail elements lost when switching theme"

    # Restore Healthcare PCF
    healthcare_path = os.path.join(project_dir, "K07128_Healthcare Provider_v721_vs_Healthcare Provider_v611_April 2023.xlsx")
    load_workbook(client, healthcare_path)
    restored = client.evaluate("state.data.elements.length")
    print(f"Restored dataset: elements={restored}")
    assert restored == 1985, "Failed to restore Healthcare PCF"

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

    # Reset to Explorer View & Dark Theme, ensuring sidebar is open
    client.evaluate("applyTheme('dark'); toggleSidebar(true); switchView('explorer', false);")
    time.sleep(0.2)
