"""
Quick diagnostic: Check if AppInitializer is properly imported.
Paste this in QGIS Python console BEFORE clicking the FilterMate button.
"""

def check_imports():
    print("\n=== Import Diagnostic ===\n")
    
    try:
        from filter_mate.filter_mate_app import HEXAGONAL_AVAILABLE
        print(f"HEXAGONAL_AVAILABLE = {HEXAGONAL_AVAILABLE}")
        
        from filter_mate.filter_mate_app import AppInitializer
        print(f"AppInitializer = {AppInitializer}")
        
        if HEXAGONAL_AVAILABLE and AppInitializer is not None:
            print("✅ AppInitializer should initialize correctly")
        else:
            print("❌ AppInitializer won't initialize - HEXAGONAL_AVAILABLE=False or AppInitializer=None")
            
        # Check other dependencies
        from filter_mate.filter_mate_app import (
            TaskOrchestrator, OptimizationManager, FilterResultHandler,
            DatasourceManager, LayerRefreshManager
        )
        print(f"\nOther managers:")
        print(f"  TaskOrchestrator = {TaskOrchestrator}")
        print(f"  OptimizationManager = {OptimizationManager}")
        print(f"  FilterResultHandler = {FilterResultHandler}")
        print(f"  DatasourceManager = {DatasourceManager}")
        print(f"  LayerRefreshManager = {LayerRefreshManager}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== End Diagnostic ===\n")

check_imports()
