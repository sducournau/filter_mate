"""
Diagnostic script to check primary key detection for all layers in FilterMate project.

Usage from QGIS Python console:
    exec(open(r'C:\Users\Simon\AppData\Roaming\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate\tools\diagnostic\check_primary_keys.py').read())
"""

from qgis.core import QgsProject

def check_layer_primary_keys():
    """Check primary key detection for all layers."""
    project = QgsProject.instance()
    layers = project.mapLayers()
    
    print("\n" + "="*80)
    print("PRIMARY KEY DETECTION DIAGNOSTIC")
    print("="*80 + "\n")
    
    for layer_id, layer in layers.items():
        if not hasattr(layer, 'fields'):
            continue
            
        print(f"Layer: {layer.name()}")
        print(f"  Provider: {layer.providerType()}")
        print(f"  Feature count: {layer.featureCount()}")
        
        # Check declared primary key
        pk_attributes = layer.primaryKeyAttributes()
        if pk_attributes:
            print(f"  ✓ Declared PRIMARY KEY: {[layer.fields()[idx].name() for idx in pk_attributes]}")
        else:
            print(f"  ✗ No declared PRIMARY KEY")
        
        # List all fields
        fields = layer.fields()
        print(f"  Fields ({fields.count()}):")
        for idx, field in enumerate(fields):
            is_numeric = field.isNumeric()
            type_name = field.typeName()
            field_name = field.name()
            has_id = 'id' in field_name.lower()
            print(f"    [{idx}] {field_name:20} | Type: {type_name:15} | Numeric: {is_numeric} | Has 'id': {has_id}")
        
        # Check FilterMate variables
        from qgis.core import QgsExpressionContextUtils
        fm_pk = QgsExpressionContextUtils.layerScope(layer).variable('filterMate_infos_primary_key_name')
        if fm_pk:
            print(f"  FilterMate stored primary key: '{fm_pk}'")
            if fm_pk == 'ctid':
                print(f"    ⚠️  WARNING: Using ctid (PostgreSQL internal ID)")
        else:
            print(f"  FilterMate: Not tracked")
        
        print()
    
    print("="*80)
    print("RECOMMENDATIONS:")
    print("  - If a layer shows 'ctid' but has an 'id' field:")
    print("    1. Remove the layer from FilterMate")
    print("    2. Re-add the layer to FilterMate")
    print("    3. The new detection logic should find the 'id' field")
    print("="*80)

# Run the diagnostic
check_layer_primary_keys()
