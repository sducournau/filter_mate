"""
Script to check which version of setup_filtering_tab_widgets is loaded.

Run in QGIS Python console after plugin reload:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/check_code_version.py').read())
"""

import inspect
from qgis.utils import plugins

print("=" * 70)
print("CODE VERSION CHECK")
print("=" * 70)

if 'filter_mate' in plugins:
    fm = plugins['filter_mate']
    
    # Check if dockwidget has the configuration manager
    if hasattr(fm, 'dockwidget') and fm.dockwidget:
        d = fm.dockwidget
        
        if hasattr(d, '_configuration_manager') and d._configuration_manager:
            cm = d._configuration_manager
            
            # Get the source code of setup_filtering_tab_widgets
            try:
                source = inspect.getsource(cm.setup_filtering_tab_widgets)
                
                # Check for version markers
                if "FIX 2026-02-02 v8" in source:
                    print("✅ VERSION: v8 (latest fix with complete cleanup)")
                elif "FIX 2026-02-02 v7" in source:
                    print("⚠️ VERSION: v7 (old fix)")
                elif "FIX 2026-02-02 v6" in source:
                    print("❌ VERSION: v6 (old fix)")
                else:
                    print("❓ VERSION: Unknown")
                
                # Show key parts of the code
                print()
                print("Key code sections found:")
                
                if "Remove old layout from vl AND cleanup reference" in source:
                    print("  ✓ Has 'Remove old layout from vl' step")
                else:
                    print("  ❌ Missing 'Remove old layout from vl' step")
                
                if "vl.takeAt(i)" in source:
                    print("  ✓ Has vl.takeAt(i) call")
                else:
                    print("  ❌ Missing vl.takeAt(i) call")
                
                if "h_layout parentWidget BEFORE insert" in source:
                    print("  ✓ Has BEFORE/AFTER parentWidget logging")
                else:
                    print("  ❌ Missing BEFORE/AFTER parentWidget logging")
                    
                print()
                print("First 100 lines of setup_filtering_tab_widgets:")
                print("-" * 70)
                lines = source.split('\n')
                for i, line in enumerate(lines[:100]):
                    print(f"{i+1:3d}: {line}")
                    
            except Exception as e:
                print(f"❌ Error getting source: {e}")
        else:
            print("❌ _configuration_manager not found")
    else:
        print("❌ dockwidget not found")
else:
    print("❌ filter_mate plugin not loaded")

print()
print("=" * 70)
