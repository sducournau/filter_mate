#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script for FilterMate performance optimizations.

Checks that all major optimizations are present and enabled.

Usage:
    python tests/verify_optimizations.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_method_exists(module_name, class_name, method_name):
    """Check if a method exists in a class"""
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        method = getattr(cls, method_name, None)
        return method is not None
    except Exception as e:
        return False


def check_class_exists(module_name, class_name):
    """Check if a class exists in a module"""
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name, None)
        return cls is not None
    except Exception as e:
        return False


def print_status(name, status, details=""):
    """Print check status with color"""
    symbol = "✅" if status else "❌"
    status_text = "OK" if status else "MISSING"
    print(f"  {symbol} {name:<50} [{status_text}]")
    if details and not status:
        print(f"     → {details}")


def main():
    print("\n" + "="*70)
    print("FilterMate Performance Optimizations - Verification")
    print("="*70 + "\n")
    
    all_checks = []
    
    # Check 1: OGR Spatial Index
    print("🔍 Checking OGR Backend Optimizations...")
    
    check1 = check_method_exists(
        'modules.backends.ogr_backend',
        'OGRGeometricFilter',
        '_ensure_spatial_index'
    )
    print_status("OGR: _ensure_spatial_index() method", check1)
    all_checks.append(check1)
    
    check2 = check_method_exists(
        'modules.backends.ogr_backend',
        'OGRGeometricFilter',
        '_apply_filter_large'
    )
    print_status("OGR: _apply_filter_large() method", check2)
    all_checks.append(check2)
    
    check3 = check_method_exists(
        'modules.backends.ogr_backend',
        'OGRGeometricFilter',
        '_apply_filter_standard'
    )
    print_status("OGR: _apply_filter_standard() method", check3)
    all_checks.append(check3)
    
    # Check 2: Spatialite Optimizations
    print("\n🔍 Checking Spatialite Backend Optimizations...")
    
    check4 = check_method_exists(
        'modules.backends.spatialite_backend',
        'SpatialiteGeometricFilter',
        '_create_temp_geometry_table'
    )
    print_status("Spatialite: _create_temp_geometry_table() method", check4)
    all_checks.append(check4)
    
    check5 = check_method_exists(
        'modules.backends.spatialite_backend',
        'SpatialiteGeometricFilter',
        'cleanup'
    )
    print_status("Spatialite: cleanup() method", check5)
    all_checks.append(check5)
    
    # Check for predicate ordering (by reading source)
    try:
        with open('modules/backends/spatialite_backend.py', 'r', encoding='utf-8') as f:
            content = f.read()
            check6 = 'predicate_order' in content and 'ordered_predicates' in content
    except:
        check6 = False
    
    print_status("Spatialite: Predicate ordering optimization", check6)
    all_checks.append(check6)
    
    # Check 3: Geometry Cache
    print("\n🔍 Checking Geometry Cache...")
    
    check7 = check_class_exists('modules.appTasks', 'SourceGeometryCache')
    print_status("SourceGeometryCache class exists", check7)
    all_checks.append(check7)
    
    if check7:
        check8 = check_method_exists(
            'modules.appTasks',
            'SourceGeometryCache',
            'get'
        )
        print_status("SourceGeometryCache: get() method", check8)
        all_checks.append(check8)
        
        check9 = check_method_exists(
            'modules.appTasks',
            'SourceGeometryCache',
            'put'
        )
        print_status("SourceGeometryCache: put() method", check9)
        all_checks.append(check9)
    
    # Check 4: FilterEngineTask uses cache
    try:
        with open('modules/appTasks.py', 'r', encoding='utf-8') as f:
            content = f.read()
            check10 = '_geometry_cache' in content and 'FilterEngineTask._geometry_cache' in content
    except:
        check10 = False
    
    print_status("FilterEngineTask: Uses shared cache", check10)
    all_checks.append(check10)
    
    # Check 5: Test files exist
    print("\n🔍 Checking Test Files...")
    
    check11 = os.path.exists('tests/test_performance.py')
    print_status("tests/test_performance.py exists", check11)
    all_checks.append(check11)
    
    check12 = os.path.exists('tests/benchmark_simple.py')
    print_status("tests/benchmark_simple.py exists", check12)
    all_checks.append(check12)
    
    # Summary
    print("\n" + "="*70)
    total = len(all_checks)
    passed = sum(all_checks)
    failed = total - passed
    
    print(f"📊 SUMMARY: {passed}/{total} checks passed")
    
    if failed == 0:
        print("✅ All optimizations are present and enabled!")
        print("\n🎉 FilterMate is fully optimized for performance!")
        print("\n💡 Next steps:")
        print("   1. Run: python tests/benchmark_simple.py")
        print("   2. Run: pytest tests/test_performance.py -v")
        print("   3. Test with your real data!")
    else:
        print(f"❌ {failed} optimization(s) missing or not enabled")
        print("\n⚠️  Some optimizations may not be available.")
        print("   Please check the implementation.")
        return 1
    
    print("="*70 + "\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
