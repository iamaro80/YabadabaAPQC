#!/usr/bin/env python3
"""
Thin test runner for YabadabaAPQC end-to-end browser verification suite.
Runs modular test suites under scripts/browser_tests/:
- test_data: integrity, brand, attribution, retail upload & recovery
- test_layout: panel toggles, shortcuts, inspector, glossary, analytics, a11y, print
- test_scaling: text scaling, shortcuts, localStorage, ratios, timing
- test_storage: storage safety with blocked localStorage
- test_escaping: workbook escaping & category ID injection prevention
- test_themes: theme switching, contrast verification, brand screenshots
"""

import os
import sys
import time
import signal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from browser_tests.cdp_client import (
    PORT,
    CHROME_PORT,
    start_server,
    start_chrome,
    get_websocket_url,
    CDPClient
)
from browser_tests.test_data import run_data_tests
from browser_tests.test_layout import run_layout_tests
from browser_tests.test_scaling import run_scaling_tests
from browser_tests.test_storage import run_storage_tests
from browser_tests.test_escaping import run_escaping_tests
from browser_tests.test_themes import run_theme_tests

SCREENSHOTS_DIR = os.path.join(PROJECT_DIR, "docs", "screenshots")

def run_all():
    server_proc = None
    chrome_proc = None
    client = None

    try:
        server_proc = start_server(PROJECT_DIR, port=PORT)
        url = f"http://localhost:{PORT}/index.html"
        chrome_proc = start_chrome(url, port=CHROME_PORT)

        ws_url = get_websocket_url(port=CHROME_PORT)
        client = CDPClient(ws_url, SCREENSHOTS_DIR)

        print("Waiting for page load and initialization...")
        client.wait_for_load()
        client.set_viewport(1440, 900)
        client.evaluate("localStorage.clear(); toggleSidebar(true); toggleInspector(true); applyTheme('dark'); setTextScale(1.0);")
        time.sleep(0.3)

        # Run test suites in sequence
        run_data_tests(client, PROJECT_DIR)
        run_layout_tests(client, PROJECT_DIR)
        run_scaling_tests(client)
        run_storage_tests(client)
        run_escaping_tests(client, PROJECT_DIR)
        run_theme_tests(client, PROJECT_DIR)

        # Check for console errors
        print(f"\nConsole Errors Count: {len(client.console_errors)}")
        if client.console_errors:
            for err in client.console_errors:
                print("  Console Error:", err)
        assert len(client.console_errors) == 0, f"Encountered {len(client.console_errors)} console errors"

        print("\n" + "="*70)
        print("ALL BROWSER E2E TESTS AND SCREENSHOT CAPTURES PASSED 100%!")
        print("="*70)

    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass
        if chrome_proc:
            try:
                chrome_proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
        if server_proc:
            try:
                server_proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
        time.sleep(0.5)

if __name__ == "__main__":
    run_all()
