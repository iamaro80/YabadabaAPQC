"""
CDPClient and process management for browser verification suite.
"""

import os
import sys
import time
import json
import base64
import shutil
import urllib.request
import subprocess

PORT = 8765
CHROME_PORT = 9222

def find_chrome_executable():
    """Locates a local Google Chrome or Chromium binary."""
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if os.path.isabs(c):
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        else:
            path = shutil.which(c)
            if path:
                return path
    return None

def start_server(project_dir, port=PORT):
    print(f"Starting HTTP server on port {port}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1)
    return proc

def start_chrome(http_url, port=CHROME_PORT):
    chrome_bin = find_chrome_executable()
    if not chrome_bin:
        print("ERROR: Google Chrome or Chromium executable not found on PATH.", file=sys.stderr)
        print("verify_browser.py requires a local Chrome or Chromium installation and 'websocket-client'.", file=sys.stderr)
        sys.exit(2)

    print(f"Starting headless Chrome on debug port {port}...")
    user_data = "/tmp/pcf_chrome_test_profile"
    if os.path.exists(user_data):
        shutil.rmtree(user_data, ignore_errors=True)
    chrome_cmd = [
        chrome_bin,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data}",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        http_url
    ]
    proc = subprocess.Popen(
        chrome_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    return proc

def get_websocket_url(port=CHROME_PORT):
    url = f"http://127.0.0.1:{port}/json"
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
    def __init__(self, ws_url, screenshots_dir):
        try:
            import websocket
        except (ImportError, ModuleNotFoundError):
            print("ERROR: Python package 'websocket-client' is not installed.", file=sys.stderr)
            print("Install it with: pip install websocket-client", file=sys.stderr)
            sys.exit(3)

        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.msg_id = 0
        self.console_errors = []
        self.screenshots_dir = screenshots_dir

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

    def capture_screenshot(self, filename, clip=None):
        filepath = os.path.join(self.screenshots_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        params = {"format": "png"}
        if clip:
            params["clip"] = clip
        res = self.send("Page.captureScreenshot", params)
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
