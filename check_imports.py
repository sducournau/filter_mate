"""
Quick diagnostic: Check if AppInitializer is properly imported.
Paste this in QGIS Python console BEFORE clicking the FilterMate button.
"""

def check_imports():
    # print("\n=== Import Diagnostic ===\n")  # DEBUG REMOVED
    
    try:
        from filter_mate.filter_mate_app import HEXAGONAL_AVAILABLE
        # print(f"HEXAGONAL_AVAILABLE = {HEXAGONAL_AVAILABLE}")  # DEBUG REMOVED
        
        from filter_mate.filter_mate_app import AppInitializer
        # print(f"AppInitializer = {AppInitializer}")  # DEBUG REMOVED
        
        if HEXAGONAL_AVAILABLE and AppInitializer is not None:
            pass  # block was empty
            # print("✅ AppInitializer should initialize correctly")  # DEBUG REMOVED
        else:
            pass  # block was empty
            # print("❌ AppInitializer won't initialize - HEXAGONAL_AVAILABLE=False or AppInitializer=None")  # DEBUG REMOVED
            
        # Check other dependencies
        from filter_mate.filter_mate_app import (
            TaskOrchestrator, OptimizationManager, FilterResultHandler,
            DatasourceManager, LayerRefreshManager
        )
        # print(f"\nOther managers:")  # DEBUG REMOVED
        # print(f"  TaskOrchestrator = {TaskOrchestrator}")  # DEBUG REMOVED
        # print(f"  OptimizationManager = {OptimizationManager}")  # DEBUG REMOVED
        # print(f"  FilterResultHandler = {FilterResultHandler}")  # DEBUG REMOVED
        # print(f"  DatasourceManager = {DatasourceManager}")  # DEBUG REMOVED
        # print(f"  LayerRefreshManager = {LayerRefreshManager}")  # DEBUG REMOVED
        
    except Exception as e:
        # print(f"❌ Error: {e}")  # DEBUG REMOVED
        import traceback
        traceback.print_exc()
    
    # print("\n=== End Diagnostic ===\n")  # DEBUG REMOVED

check_imports()
