# -*- coding: utf-8 -*-
"""
ENABLE DEBUG LOGGING FOR POSTGRESQL v4.0 INVESTIGATION

Execute this script in QGIS Python console to enable detailed debug logging
for PostgreSQL backend v4.0.

Usage in QGIS Python console:
    >>> exec(open('/path/to/filter_mate/ENABLE_DEBUG_LOGGING.py').read())
    
Then reload FilterMate plugin and re-run filters.
"""

import logging

# Enable DEBUG level for PostgreSQL backend
logging.getLogger('FilterMate.Backend.PostgreSQL').setLevel(logging.DEBUG)

# Also enable for main app and tasks
logging.getLogger('FilterMate.App').setLevel(logging.DEBUG)
logging.getLogger('FilterMate.Tasks').setLevel(logging.DEBUG)

# Add console handler with DEBUG level to see logs immediately
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)

# Add to relevant loggers
for logger_name in ['FilterMate.Backend.PostgreSQL', 'FilterMate.App', 'FilterMate.Tasks']:
    logger = logging.getLogger(logger_name)
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)
    logger.addHandler(console)

print("✅ DEBUG logging enabled for FilterMate PostgreSQL backend v4.0")
print("   Loggers configured:")
print("   - FilterMate.Backend.PostgreSQL (DEBUG)")
print("   - FilterMate.App (DEBUG)")
print("   - FilterMate.Tasks (DEBUG)")
print("")
print("⚠️ Reload FilterMate plugin now and re-run filters to see detailed logs")
