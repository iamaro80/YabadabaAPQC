"""
Storage safety browser tests (blocked storage, quota errors, private browsing modes).
"""

def run_storage_tests(client):
    print("\n" + "="*70)
    print("STORAGE SAFETY (BLOCKED STORAGE TEST)")
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
