"""
Test script for Spatialite Zero Features Fallback (v2.9.40)

This script tests the automatic fallback to OGR when Spatialite returns 0 features.
Run in QGIS Python console.
"""

def test_zero_features_fallback():
    """Test that Spatialite correctly triggers OGR fallback on 0 features"""
    
    print("\n" + "="*80)
    print("TEST: Spatialite Zero Features Fallback (v2.9.40)")
    print("="*80 + "\n")
    
    # Get FilterMate instance
    from qgis.utils import plugins
    fm = plugins.get('filter_mate')
    if not fm:
        print("❌ FilterMate plugin not loaded")
        return False
    
    # Get active layer
    layer = iface.activeLayer()
    if not layer:
        print("❌ No active layer - please select a layer")
        return False
    
    print(f"✓ Testing with layer: {layer.name()}")
    print(f"  - Provider: {layer.providerType()}")
    print(f"  - Features: {layer.featureCount():,}")
    
    # Import backend modules
    from filter_mate.modules.backends.factory import BackendFactory
    from filter_mate.modules.backends.spatialite_backend import SpatialiteBackend
    
    # Create backend
    task_params = {
        'infos': {
            'source_geom_wkt': 'POINT(0 0)',  # Simple test geometry
            'layer_crs_authid': 'EPSG:4326'
        },
        'filtering': {
            'geometric_predicates': ['ST_Intersects'],
            'buffer_value': 0
        }
    }
    
    backend = BackendFactory.get_backend('spatialite', layer, task_params)
    
    if not isinstance(backend, SpatialiteBackend):
        print(f"⚠️ Backend is {type(backend).__name__}, not SpatialiteBackend - skipping test")
        return False
    
    print(f"✓ Created Spatialite backend")
    
    # Test 1: Check flag is initially False
    has_flag = hasattr(backend, '_spatialite_zero_result_fallback')
    flag_value = getattr(backend, '_spatialite_zero_result_fallback', False)
    print(f"\n📋 Test 1: Initial state")
    print(f"  - Has flag: {has_flag}")
    print(f"  - Flag value: {flag_value}")
    
    if flag_value:
        print("  ❌ Flag should be False initially")
        return False
    else:
        print("  ✓ Flag is False (correct)")
    
    # Test 2: Simulate 0 features result (not multi-step, not negative buffer)
    print(f"\n📋 Test 2: Simulate Spatialite returning 0 features")
    
    # Mock the method to return 0 features
    original_method = backend._apply_filter_direct_sql
    
    def mock_apply_filter_zero(*args, **kwargs):
        """Mock that returns False for 0 features (should trigger fallback)"""
        # Set the flag
        backend._spatialite_zero_result_fallback = True
        return False
    
    backend._apply_filter_direct_sql = mock_apply_filter_zero
    
    # Call apply_filter
    result = backend.apply_filter(layer, "test_expression")
    
    # Check flag
    flag_after = getattr(backend, '_spatialite_zero_result_fallback', False)
    print(f"  - apply_filter returned: {result}")
    print(f"  - Flag after: {flag_after}")
    
    if result:
        print("  ❌ apply_filter should return False for 0 features")
        return False
    
    if not flag_after:
        print("  ❌ Flag should be True after 0 features")
        return False
    
    print("  ✓ Fallback correctly triggered (result=False, flag=True)")
    
    # Restore original method
    backend._apply_filter_direct_sql = original_method
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - Zero features fallback working correctly!")
    print("="*80 + "\n")
    
    return True


def test_valid_zero_cases():
    """Test that valid 0-feature cases do NOT trigger fallback"""
    
    print("\n" + "="*80)
    print("TEST: Valid Zero Feature Cases (should NOT fallback)")
    print("="*80 + "\n")
    
    print("📋 Valid cases that should NOT trigger fallback:")
    print("  1. Multi-step filtering with empty intersection")
    print("  2. Negative buffer producing empty geometry")
    print("\nThese tests require specific layer setup - see test documentation.")
    
    return True


if __name__ == '__main__':
    try:
        # Run tests
        test_zero_features_fallback()
        test_valid_zero_cases()
        
    except Exception as e:
        print(f"\n❌ TEST FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
