fix(signals): Consolidate signal management and eliminate duplicate connections

## 🎯 Summary
Major signal management overhaul to prevent duplicate connections, crashes,
and memory leaks. All critical signals now use safe_connect() from signal_utils.

## 🔧 Changes Made

### Critical Fixes
1. **filter_mate.py** - Eliminated duplicate closingPlugin connection
   - Before: Direct connect() could create multiple connections
   - After: safe_connect() ensures single connection on plugin reload
   - Impact: Prevents crashes when closing dockwidget

2. **filter_mate_app.py** - Secured QGIS signals
   - Before: projectRead, newProjectCreated, layersAdded used direct connect()
   - After: All QGIS signals use safe_connect()
   - Impact: No more duplicate handlers on plugin reload

3. **filter_mate_dockwidget.py** - Secured selectionChanged signal
   - Before: current_layer.selectionChanged.connect() could duplicate
   - After: Uses safe_connect() for layer selection tracking
   - Impact: Clean connections when switching layers

### Code Cleanup
4. **filter_mate_app.py** - Removed obsolete commented code
   - Lines 280-281: Removed qtree_signal connection comments
   - Line 413: Removed taskCompleted connection comment
   - Impact: Cleaner, more maintainable code

## 📊 Metrics
- **Files changed**: 3 (filter_mate.py, filter_mate_app.py, filter_mate_dockwidget.py)
- **Critical issues fixed**: 5
- **Lines removed**: 7 (obsolete comments)
- **Lines modified**: 12 (safe_connect migrations)

## ✅ Testing
- [x] No Python errors after changes
- [x] Plugin loads correctly
- [ ] Manual test: Reload plugin 10x (to be done)
- [ ] Manual test: Open/close dockwidget 10x (to be done)
- [ ] Manual test: Switch layers 20x (to be done)

## 📚 Documentation
- Created: docs/AUDIT_SIGNAL_CONSOLIDATION_2025-12-10.md
- Updated: All changes follow patterns from docs/SIGNAL_UTILS_GUIDE.md

## 🚀 Follow-up Tasks
- [ ] Complete manual regression tests
- [ ] Consider migrating remaining connect() to safe_connect()
- [ ] Add unit tests for signal connection edge cases

## 🔗 Related
- Related to: docs/AUDIT_REPORT_2025-12-10.md (previous audit)
- Implements: signal_utils.py safe_connect/safe_disconnect pattern
- Prevents: #XXX (crashes on plugin reload)

---

Co-authored-by: GitHub Copilot <copilot@github.com>
