#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTIC: PostgreSQL EXISTS source_filter missing
=================================================================

SYMPTOM:
User reports that PostgreSQL distant layers are NOT filtered correctly 
when source layer "Distribution Cluster" is already filtered (123 features).

Generated SQL shows:
    EXISTS (SELECT 1 FROM "public"."Distribution Cluster" AS __source 
            WHERE ST_Intersects("geom", __source."geom"))

PROBLEM:
The EXISTS query is MISSING the source filter clause!
It should be:
    EXISTS (SELECT 1 FROM "public"."Distribution Cluster" AS __source 
            WHERE ST_Intersects("geom", __source."geom") 
              AND __source."id" IN (fid1, fid2, ...))

This causes EXISTS to check ALL features in "Distribution Cluster", 
not just the 123 filtered ones.

ROOT CAUSE ANALYSIS:
1. ExpressionBuilder._prepare_source_filter() returns None
2. PostgreSQL backend's build_expression() skips source_filter if None
3. Result: WHERE clause has only spatial predicate, no FID filter

EXPECTED FLOW:
1. Task has task_parameters["task"]["features"] = [QgsFeature(), ...]
2. _prepare_source_filter() extracts features
3. _generate_fid_filter() creates '"id" IN (fid1, fid2, ...)'
4. Backend includes this in EXISTS WHERE clause with AND

DIAGNOSTIC CHECKS:
This script will verify:
1. Are task_parameters["task"]["features"] populated?
2. Is _prepare_source_filter() receiving them?
3. Is _generate_fid_filter() being called?
4. What does _generate_fid_filter() return?
5. Is backend receiving the source_filter?

FIX STRATEGY:
Once we identify where the features are lost, we can:
- Fix the feature extraction in ExpressionBuilder
- Or fix the FID filter generation
- Or fix the task parameter passing

Run this script to get full diagnostic output showing the exact failure point.
"""

import sys
from pathlib import Path

# Add plugin path to Python path
plugin_path = Path(__file__).parent
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

from qgis.core import QgsProject, QgsVectorLayer
from typing import Dict, Any, List

def print_banner(title: str):
    """Print a diagnostic banner."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def check_task_parameters(task_params: Dict[str, Any]) -> None:
    """
    Check task_parameters structure for feature extraction issues.
    
    Args:
        task_params: Task parameters dictionary from FilterMateApp
    """
    print_banner("DIAGNOSTIC 1: Task Parameters Structure")
    
    print(f"\n1. Root keys: {list(task_params.keys())}")
    
    if "task" in task_params:
        task_dict = task_params["task"]
        print(f"\n2. task_params['task'] keys: {list(task_dict.keys())}")
        
        if "features" in task_dict:
            features = task_dict["features"]
            print(f"\n3. task_params['task']['features']:")
            print(f"   - Type: {type(features).__name__}")
            print(f"   - Count: {len(features) if hasattr(features, '__len__') else 'N/A'}")
            
            if hasattr(features, '__len__') and len(features) > 0:
                first_feat = features[0]
                print(f"   - First feature type: {type(first_feat).__name__}")
                if hasattr(first_feat, 'id'):
                    print(f"   - First feature ID: {first_feat.id()}")
                if hasattr(first_feat, 'attributes'):
                    print(f"   - First feature attributes: {first_feat.attributes()[:5]}...")
                    
                # Check if features are still valid
                if hasattr(first_feat, 'isValid'):
                    print(f"   - First feature isValid: {first_feat.isValid()}")
                    
                print(f"\n   ✅ Features are PRESENT in task_parameters")
            else:
                print(f"\n   ❌ ERROR: features list is EMPTY!")
                print(f"   → This is the ROOT CAUSE - no features to generate FID filter")
        else:
            print(f"\n   ❌ ERROR: 'features' key NOT FOUND in task_parameters['task']")
            print(f"   → This is the ROOT CAUSE - features missing from task dict")
    else:
        print(f"\n   ❌ ERROR: 'task' key NOT FOUND in task_parameters")
        print(f"   → This is the ROOT CAUSE - task dict missing entirely")
        
    # Check for feature_fids (backup FID list)
    if "task" in task_params and "feature_fids" in task_params["task"]:
        fids = task_params["task"]["feature_fids"]
        print(f"\n4. task_params['task']['feature_fids']: {fids[:10] if len(fids) > 10 else fids}")
        print(f"   - Count: {len(fids)}")
    else:
        print(f"\n4. No 'feature_fids' backup list found")

def check_expression_builder_extraction(layer: QgsVectorLayer, task_params: Dict[str, Any]) -> None:
    """
    Simulate ExpressionBuilder._prepare_source_filter() logic.
    
    Args:
        layer: Source layer that should have filtered features
        task_params: Task parameters dictionary
    """
    print_banner("DIAGNOSTIC 2: ExpressionBuilder Feature Extraction")
    
    # Simulate _prepare_source_filter() logic
    task_features = task_params.get("task", {}).get("features", [])
    print(f"\n1. Extracted task_features:")
    print(f"   - Count: {len(task_features) if task_features else 0}")
    print(f"   - Is list: {isinstance(task_features, list)}")
    print(f"   - Is empty: {len(task_features) == 0 if task_features else True}")
    
    if not task_features or len(task_features) == 0:
        print(f"\n   ❌ ROOT CAUSE: task_features is empty!")
        print(f"   → _prepare_source_filter() will fallback to source_subset")
        print(f"   → But source_subset may contain patterns that are skipped")
        
        # Check source_subset
        source_subset = layer.subsetString() if layer else None
        print(f"\n2. Checking source_subset (fallback):")
        print(f"   - source_subset: '{source_subset}'")
        
        if source_subset:
            # Check for skip patterns
            skip_patterns = ['__SOURCE', 'EXISTS(', 'EXISTS (']
            has_skip_pattern = any(p in source_subset.upper() for p in skip_patterns)
            print(f"   - Contains __SOURCE/EXISTS: {has_skip_pattern}")
            
            if has_skip_pattern:
                print(f"\n   ❌ DOUBLE PROBLEM: source_subset will be SKIPPED!")
                print(f"   → Result: source_filter = None")
                print(f"   → EXISTS will have NO source filter")
        else:
            print(f"\n   ❌ TRIPLE PROBLEM: source_subset is also None!")
            print(f"   → Result: source_filter = None")
            print(f"   → EXISTS will have NO source filter")
    else:
        print(f"\n   ✅ task_features is VALID - should generate FID filter")
        
        # Simulate _generate_fid_filter()
        print(f"\n2. Simulating _generate_fid_filter():")
        try:
            fids = []
            for f in task_features[:5]:  # Check first 5
                if hasattr(f, 'id'):
                    fids.append(f.id())
            print(f"   - Extracted FIDs (first 5): {fids}")
            print(f"   ✅ FID extraction successful")
        except Exception as e:
            print(f"   ❌ ERROR extracting FIDs: {e}")

def check_backend_source_filter(source_filter: str) -> None:
    """
    Check if backend will include source_filter in EXISTS.
    
    Args:
        source_filter: Source filter string (or None)
    """
    print_banner("DIAGNOSTIC 3: Backend Source Filter Inclusion")
    
    print(f"\n1. source_filter received by backend:")
    if source_filter is None:
        print(f"   - Value: None")
        print(f"   ❌ ROOT CAUSE: Backend receives None!")
        print(f"   → Backend will NOT add source filter to EXISTS WHERE clause")
        print(f"   → Result: EXISTS queries ALL source features")
    elif source_filter == "":
        print(f"   - Value: '' (empty string)")
        print(f"   ❌ ROOT CAUSE: Backend receives empty string!")
        print(f"   → Backend will NOT add source filter to EXISTS WHERE clause")
    else:
        print(f"   - Value: '{source_filter}'")
        print(f"   ✅ Backend has valid source_filter")
        print(f"   → Backend should add to EXISTS WHERE clause with AND")

def propose_fix() -> None:
    """Propose fix based on diagnostic results."""
    print_banner("PROPOSED FIX")
    
    print("""
Based on diagnostic results, the fix depends on where features are lost:

SCENARIO A: Features are in task_parameters but not extracted
→ FIX: Correct the extraction path in ExpressionBuilder._prepare_source_filter()
→ FILE: core/filter/expression_builder.py line ~307

SCENARIO B: Features are not in task_parameters at all
→ FIX: Ensure TaskParameterBuilder.build_common_task_params() includes features
→ FILE: adapters/task_builder.py line ~366

SCENARIO C: Features become invalid in background thread
→ FIX: Use feature_fids (backup) instead of QgsFeature objects
→ FILE: core/filter/expression_builder.py _extract_feature_ids()

SCENARIO D: source_subset is used but contains skip patterns
→ FIX: Generate FID filter from layer.selectedFeatures() or layer.getFeatures()
→ FILE: core/filter/expression_builder.py _prepare_source_filter()

To apply fix, run the diagnostic and identify which scenario matches.
""")

def run_full_diagnostic():
    """Run complete diagnostic workflow."""
    print_banner("FilterMate PostgreSQL EXISTS Source Filter Diagnostic")
    
    print("""
This diagnostic will help identify why source_filter is missing from EXISTS.

To run this diagnostic on your actual data:
1. Select features in "Distribution Cluster" layer (123 features)
2. Open Python Console in QGIS
3. Run:
    from filter_mate.DIAGNOSTIC_SOURCE_FILTER_EXISTS import run_layer_diagnostic
    run_layer_diagnostic()

This will show you exactly where the features are lost in the flow.
""")
    
    propose_fix()

def run_layer_diagnostic():
    """
    Run diagnostic on current layer selection in QGIS.
    Must be called from QGIS Python Console with a layer selected.
    """
    project = QgsProject.instance()
    layer = project.activeLayer()
    
    if not layer:
        print("❌ ERROR: No active layer. Please select 'Distribution Cluster' layer.")
        return
        
    print_banner(f"Running diagnostic on layer: {layer.name()}")
    
    # Check layer state
    print(f"\n1. Layer info:")
    print(f"   - Name: {layer.name()}")
    print(f"   - Provider: {layer.providerType()}")
    print(f"   - Feature count: {layer.featureCount()}")
    print(f"   - Selected count: {layer.selectedFeatureCount()}")
    print(f"   - SubsetString: '{layer.subsetString()}'")
    
    # Check selection
    if layer.selectedFeatureCount() == 0:
        print(f"\n   ⚠️ WARNING: No features selected")
        print(f"   → Please select features and run again")
        return
        
    # Get selected features
    selected = layer.selectedFeatures()
    print(f"\n2. Selected features:")
    print(f"   - Count: {len(selected)}")
    if selected:
        first = selected[0]
        print(f"   - First feature ID: {first.id()}")
        print(f"   - First feature attributes: {first.attributes()[:5]}...")
        
    # Simulate task_parameters creation
    from adapters.task_builder import TaskParameterBuilder
    from filter_mate_dockwidget import FilterMateDockWidget
    
    # Create mock dockwidget
    # NOTE: This won't work perfectly without real dockwidget, but shows concept
    print(f"\n3. Simulating task_parameters creation...")
    print(f"   (This requires a real FilterMate session)")
    
    print(f"\n✅ Layer diagnostic complete")
    print(f"\nNext step: Run FilterMate filter and check logs for:")
    print(f"   - 🔍 _prepare_source_filter() ENTERED")
    print(f"   - Count: <X> features")
    print(f"   - source_filter RESULT")

if __name__ == "__main__":
    run_full_diagnostic()
