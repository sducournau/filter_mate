# FilterMate - Coding Standard: Error Handling and Silent Failures

**Version:** 4.0.6  
**Date:** 2026-01-16  
**Status:** ✅ ENFORCED

---

## ❌ PROHIBITED: Silent Exception Swallowing

**NEVER write code that silently catches and ignores exceptions without logging.**

### ❌ BAD Examples (FORBIDDEN)

```python
# ❌ FORBIDDEN - No logging
try:
    manager.apply()
except Exception:
    pass  # SILENT FAILURE - IMPOSSIBLE TO DEBUG!

# ❌ FORBIDDEN - Return without logging
try:
    self.configure_ui()
except Exception:
    return  # SILENT FAILURE - USER UNAWARE!

# ❌ FORBIDDEN - Continue without logging
try:
    layer.reload()
except:
    continue  # SILENT FAILURE - DATA CORRUPTION RISK!
```

**Why this is dangerous:**
- ✗ User never knows something failed
- ✗ Developer cannot debug issues
- ✗ Silent data corruption
- ✗ UI appears normal but is broken
- ✗ Violates "fail fast" principle

---

## ✅ REQUIRED: Proper Error Handling

### ✅ GOOD Example 1: Method Returns Boolean

```python
def apply(self) -> bool:
    """
    Apply configuration.
    
    Returns:
        bool: True if successful, False if any error occurred
    """
    try:
        self._apply_settings()
        self._validate_state()
        logger.info("Configuration applied successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to apply configuration: {e}", exc_info=True)
        return False  # Caller can decide how to handle
```

**Caller handles return value:**

```python
success = manager.apply()
if not success:
    logger.warning("Manager.apply() failed - UI may be incomplete")
    iface.messageBar().pushWarning("FilterMate", "Configuration error - see logs")
```

### ✅ GOOD Example 2: Method Raises Exception

```python
def load_layer(self, layer_id: str) -> QgsVectorLayer:
    """
    Load a QGIS layer.
    
    Returns:
        QgsVectorLayer: The loaded layer
    
    Raises:
        ValueError: If layer_id is invalid
        RuntimeError: If layer cannot be loaded
    """
    if not layer_id:
        raise ValueError("layer_id cannot be empty")
    
    layer = QgsProject.instance().mapLayer(layer_id)
    if not layer:
        raise RuntimeError(f"Layer {layer_id} not found in project")
    
    return layer
```

**Caller handles exception:**

```python
try:
    layer = self.load_layer(layer_id)
except (ValueError, RuntimeError) as e:
    logger.error(f"Failed to load layer: {e}")
    iface.messageBar().pushCritical("FilterMate", f"Layer error: {e}")
    return None
```

### ✅ GOOD Example 3: Expected Errors (Cleanup Operations)

```python
# ✅ GOOD - Cleanup operations where failure is acceptable BUT MUST BE LOGGED
try:
    connexion.close()
except Exception:
    logger.debug("Connection cleanup (connection may already be closed)")
    # Suppress expected errors - not critical for operation
```

**When is silent suppression acceptable?**
- ✓ Cleanup operations (close connections, delete temp files)
- ✓ Signal disconnections (signal may already be disconnected)
- ✓ Widget deletions (widget may already be deleted)
- **BUT:** You MUST add `logger.debug()` explaining why it's acceptable!

---

## 📏 Rules for `.apply()` Methods

**All manager methods named `.apply()` MUST:**

1. **Return `bool`** (not `None`)
2. **Log on failure** with `exc_info=True`
3. **Return `False` on any exception** (don't raise)

### Template

```python
def apply(self) -> bool:
    """
    Apply [describe what is being applied].
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Perform operations
        self._do_something()
        self._do_something_else()
        
        logger.info("[ManagerName]: Applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"[ManagerName]: Error applying: {e}", exc_info=True)
        return False  # Let caller decide how to handle
```

### Caller Pattern

```python
# Pattern 1: Log warning if failed
success = manager.apply()
if not success:
    logger.warning(f"{manager.__class__.__name__}.apply() failed")

# Pattern 2: Show user notification if critical
success = manager.apply()
if not success:
    logger.error(f"Critical: {manager.__class__.__name__}.apply() failed")
    iface.messageBar().pushWarning("FilterMate", "UI configuration error - see logs")

# Pattern 3: Fallback to alternative method
if manager and manager.apply():
    logger.debug("Manager applied successfully")
else:
    logger.warning("Manager apply failed - using fallback")
    self._fallback_method()
```

---

## 🔍 Debugging Guidelines

### When an Error Occurs

1. **Check logs first:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/logs/`
2. **Look for:**
   - `ERROR` entries with stack traces
   - `WARNING` entries about failed operations
3. **Report with:**
   - Full error message
   - Stack trace
   - Steps to reproduce

### For Developers

When adding new code:

```python
# ❌ DON'T
try:
    risky_operation()
except:
    pass

# ✅ DO
try:
    risky_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    return False
```

---

## 📋 Checklist for Code Review

When reviewing code, check:

- [ ] No `except: pass` without `logger.debug()` explaining why
- [ ] No `except Exception: pass` without logging
- [ ] All `.apply()` methods return `bool`
- [ ] All `.apply()` callers check return value
- [ ] Critical errors shown to user via `iface.messageBar()`
- [ ] Exceptions include context (what was being done)
- [ ] Stack traces included (`exc_info=True`)

---

## 🚀 Migration from Old Code

### Before (v4.0.5 and earlier)

```python
# ❌ OLD - Silent failure
try:
    self._dimensions_manager.apply()
except Exception:
    pass  # BUG: Silent failure!
```

### After (v4.0.6+)

```python
# ✅ NEW - Proper error handling
try:
    success = self._dimensions_manager.apply()
    if not success:
        logger.warning("DimensionsManager.apply() returned False")
except Exception as e:
    logger.error(f"DimensionsManager.apply() raised exception: {e}", exc_info=True)
```

---

## 📖 Examples from FilterMate Codebase

### Fixed in v4.0.6

| File | Old Code | New Code |
|------|----------|----------|
| [ui/layout/dimensions_manager.py](ui/layout/dimensions_manager.py#L129) | `apply() -> None` + no return | `apply() -> bool` + returns True/False |
| [ui/layout/spacing_manager.py](ui/layout/spacing_manager.py#L90) | `apply() -> None` + no return | `apply() -> bool` + returns True/False |
| [ui/layout/splitter_manager.py](ui/layout/splitter_manager.py#L173) | `apply() -> None` + early return | `apply() -> bool` + returns False on error |
| [ui/layout/action_bar_manager.py](ui/layout/action_bar_manager.py#L124) | `apply() -> None` + no checks | `apply() -> bool` + exception handling |
| [filter_mate_dockwidget.py](filter_mate_dockwidget.py#L655) | `except: pass` silent | Checks return + logs + shows warning |

---

## ✅ Compliance

**This standard is ENFORCED as of v4.0.6.**

- ✅ All manager `.apply()` methods return `bool`
- ✅ All callers check return values
- ✅ All exceptions are logged with context
- ✅ Critical failures notify the user

**Non-compliant code will be rejected in code review.**

---

**Questions? See:**
- [Architecture Documentation](../docs/ARCHITECTURE.md)
- [Error Handling Best Practices](./.github/copilot-instructions.md)
- [Logging Configuration](../infrastructure/logging/)
