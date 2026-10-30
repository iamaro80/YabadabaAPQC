#!/usr/bin/env bash
# One-command test runner for YabadabaAPQC test suites:
# 1. verify_pcf.py (Python data integrity)
# 2. test_shared_cases.py (Python edge cases & parser parity)
# 3. test_shared_cases.js (Node.js edge cases & parser parity)
# 4. verify_browser.py (CDP Browser E2E suite, if Chrome is available)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

echo "======================================================================"
echo "RUNNING SUITE 1: verify_pcf.py"
echo "======================================================================"
python3 scripts/verify_pcf.py

echo ""
echo "======================================================================"
echo "RUNNING SUITE 2: test_shared_cases.py"
echo "======================================================================"
python3 scripts/test_shared_cases.py

echo ""
echo "======================================================================"
echo "RUNNING SUITE 3: test_shared_cases.js"
echo "======================================================================"
node scripts/test_shared_cases.js

echo ""
echo "======================================================================"
echo "CHECKING BROWSER PREREQUISITES FOR SUITE 4"
echo "======================================================================"

CHROME_BIN=""
for candidate in google-chrome google-chrome-stable chromium chromium-browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    if command -v "$candidate" >/dev/null 2>&1; then
        CHROME_BIN="$(command -v "$candidate")"
        break
    elif [ -x "$candidate" ]; then
        CHROME_BIN="$candidate"
        break
    fi
done

if [ -z "$CHROME_BIN" ]; then
    echo "⚠️  WARNING: Google Chrome / Chromium executable not found on PATH."
    echo "Skipping browser E2E test suite (verify_browser.py)."
    echo "To run browser tests, install Google Chrome or Chromium, and websocket-client (pip install websocket-client)."
    echo ""
    echo "✅ Core test suites (verify_pcf.py, test_shared_cases.py, test_shared_cases.js) PASSED!"
    exit 0
fi

echo "Found Chrome binary: ${CHROME_BIN}"
echo "Running SUITE 4: verify_browser.py..."
python3 scripts/verify_browser.py

echo ""
echo "======================================================================"
echo "🎉 ALL TEST SUITES PASSED SUCCESSFULLY!"
echo "======================================================================"
