"""
Quick diagnostic: Check if AppInitializer is properly imported.
Paste this in QGIS Python console BEFORE clicking the FilterMate button.
"""


def check_imports():

    try:
        from filter_mate.filter_mate_app import HEXAGONAL_AVAILABLE

        from filter_mate.filter_mate_app import AppInitializer

        if HEXAGONAL_AVAILABLE and AppInitializer is not None:
            pass  # block was empty
        else:
            pass  # block was empty

        # Check other dependencies
        from filter_mate.filter_mate_app import (  # noqa: F401
            TaskOrchestrator, OptimizationManager, FilterResultHandler,
            DatasourceManager, LayerRefreshManager
        )

    except Exception:
        import traceback
        traceback.print_exc()


check_imports()
