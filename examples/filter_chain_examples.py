"""
FilterChain Usage Examples

Demonstrates how to use the new FilterChain system to combine filters clearly.

Author: FilterMate Team
Date: 2026-01-21
"""

import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import directement le module sans passer par core/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "filter_chain",
    os.path.join(parent_dir, "core", "filter", "filter_chain.py")
)
filter_chain_module = importlib.util.module_from_spec(spec)

# Mock QGIS before loading
class MockQgsVectorLayer:
    def __init__(self, name="mock"):
        self._name = name
    def name(self):
        return self._name

# Mock infrastructure.logging
class MockLogger:
    @staticmethod
    def info(msg): pass
    @staticmethod
    def warning(msg): pass
    @staticmethod
    def debug(msg): pass
    @staticmethod
    def error(msg): pass

sys.modules['qgis'] = type(sys)('qgis')
sys.modules['qgis.core'] = type(sys)('qgis.core')
sys.modules['qgis.core'].QgsVectorLayer = MockQgsVectorLayer
sys.modules['infrastructure'] = type(sys)('infrastructure')
sys.modules['infrastructure.logging'] = type(sys)('infrastructure.logging')
sys.modules['infrastructure.logging.logger'] = type(sys)('infrastructure.logging.logger')
sys.modules['infrastructure.logging.logger'].get_logger = lambda name: MockLogger()

# Now load the module
spec.loader.exec_module(filter_chain_module)

from datetime import datetime

# Extract classes from the module
Filter = filter_chain_module.Filter
FilterType = filter_chain_module.FilterType
FilterChain = filter_chain_module.FilterChain
CombinationStrategy = filter_chain_module.CombinationStrategy


def example_1_ducts_with_zone_pop_and_custom():
    """
    Example 1: Couche ducts avec filtre zone_pop + custom expression
    
    Contexte:
    - Layer: ducts
    - Filtre spatial: zone_pop (5 UUIDs sélectionnés)
    - Expression custom: status = 'active' (exploration utilisateur)
    
    Résultat attendu:
    Les deux filtres sont combinés avec AND, zone_pop en priorité.
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Ducts avec zone_pop + custom expression")
    print("="*80)
    
    # Simuler layer (normalement QgsVectorLayer)
    class MockLayer:
        def name(self):
            return "ducts"
    
    ducts_layer = MockLayer()
    
    # Créer FilterChain
    chain = FilterChain(ducts_layer)
    
    # 1. Filtre spatial zone_pop (priorité 80)
    zone_pop_filter = Filter(
        filter_type=FilterType.SPATIAL_SELECTION,
        expression="pk IN (SELECT pk FROM infra.zone_pop WHERE uuid IN ('a1', 'a2', 'a3', 'a4', 'a5'))",
        layer_name="zone_pop",
        priority=80,  # Auto-assigné par défaut, mais explicite ici
        combine_operator="AND",
        metadata={
            'source': 'zone_pop',
            'uuid_count': 5,
            'description': 'Filtre spatial par zones de population'
        }
    )
    
    # 2. Custom expression pour exploration (priorité 30)
    custom_filter = Filter(
        filter_type=FilterType.CUSTOM_EXPRESSION,
        expression="status = 'active' AND type IN ('fiber', 'copper')",
        layer_name="ducts",
        priority=30,  # Priorité basse - ne doit pas écraser zone_pop
        combine_operator="AND",
        metadata={
            'user_defined': True,
            'purpose': 'exploration',
            'description': 'Filtre utilisateur pour explorer certains types'
        }
    )
    
    # Ajouter les filtres à la chaîne
    print("\n📋 Adding filters to chain...")
    chain.add_filter(zone_pop_filter)
    chain.add_filter(custom_filter)
    
    # Afficher la chaîne
    print("\n" + str(chain))
    
    # Construire l'expression finale
    final_expr = chain.build_expression('postgresql')
    
    print(f"\n✅ Final expression ({len(final_expr)} chars):")
    print(f"   {final_expr}")
    
    # Vérifications
    assert "zone_pop" in final_expr, "zone_pop filter missing"
    assert "status = 'active'" in final_expr, "custom expression missing"
    assert "AND" in final_expr, "Filters not combined with AND"
    
    # Position: zone_pop doit apparaître avant custom (priorité)
    pos_zone = final_expr.find("zone_pop")
    pos_custom = final_expr.find("status")
    assert pos_zone < pos_custom, f"Wrong order: zone_pop at {pos_zone}, custom at {pos_custom}"
    
    print("\n✅ All assertions passed!")
    
    # Serialization pour debugging/logging
    print("\n📦 Serialized chain (JSON):")
    import json
    print(json.dumps(chain.to_dict(), indent=2))
    
    return chain


def example_2_structures_with_buffer_intersect():
    """
    Example 2: Couche structures filtrée par ducts avec buffer
    
    Contexte:
    - Layer: structures
    - Filtre hérité: zone_pop (même UUIDs que ducts)
    - Filtre spatial: buffer intersect avec ducts (50m)
    
    Résultat attendu:
    Les structures doivent respecter BOTH:
    - zone_pop constraint (hérité)
    - buffer intersect avec ducts (qui est lui-même pré-filtré par zone_pop)
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Structures avec zone_pop + buffer intersect ducts")
    print("="*80)
    
    class MockLayer:
        def name(self):
            return "structures"
    
    structures_layer = MockLayer()
    
    # Créer FilterChain
    chain = FilterChain(structures_layer)
    
    # 1. Filtre spatial hérité - zone_pop (priorité 80)
    zone_pop_filter = Filter(
        filter_type=FilterType.SPATIAL_SELECTION,
        expression="pk IN (SELECT pk FROM infra.zone_pop WHERE uuid IN ('a1', 'a2', 'a3', 'a4', 'a5'))",
        layer_name="zone_pop",
        priority=80,
        metadata={
            'source': 'zone_pop',
            'inherited_from': 'ducts',
            'description': 'Filtre spatial hérité de la couche source'
        }
    )
    
    # 2. Buffer intersect avec ducts (priorité 60)
    # IMPORTANT: Le filtre EXISTS doit AUSSI référencer zone_pop dans la sous-requête
    buffer_filter = Filter(
        filter_type=FilterType.BUFFER_INTERSECT,
        expression="""EXISTS (
            SELECT 1 FROM infra.ducts AS __source
            WHERE ST_Intersects(structures.geom, ST_Buffer(__source.geom, 50))
            AND __source.pk IN (
                SELECT pk FROM infra.zone_pop WHERE uuid IN ('a1', 'a2', 'a3', 'a4', 'a5')
            )
        )""",
        layer_name="ducts",
        priority=60,
        combine_operator="AND",
        metadata={
            'buffer_distance': 50,
            'buffer_unit': 'meters',
            'source_layer': 'ducts',
            'source_filter': 'zone_pop',
            'description': 'Intersection avec buffer de ducts pré-filtrés'
        }
    )
    
    # Ajouter les filtres
    print("\n📋 Adding filters to chain...")
    chain.add_filter(zone_pop_filter)
    chain.add_filter(buffer_filter)
    
    # Afficher la chaîne
    print("\n" + str(chain))
    
    # Construire l'expression
    final_expr = chain.build_expression('postgresql')
    
    print(f"\n✅ Final expression ({len(final_expr)} chars):")
    # Pretty print avec indentation
    import re
    formatted = re.sub(r'(AND|OR|WHERE|SELECT)', r'\n    \1', final_expr)
    print(f"   {formatted}")
    
    # Vérifications
    assert "zone_pop" in final_expr, "zone_pop filter missing"
    assert "ST_Buffer" in final_expr, "Buffer operation missing"
    assert "ST_Intersects" in final_expr, "Spatial intersect missing"
    assert final_expr.count("zone_pop") >= 2, "zone_pop should appear in both filters"
    
    print("\n✅ All assertions passed!")
    
    return chain


def example_3_optimization_with_mv():
    """
    Example 3: Optimisation avec Materialized View
    
    Contexte:
    - Large FID selection (2862 UUIDs - comme votre cas réel!)
    - Expression inline: 132KB (trop grande)
    - Solution: Créer MV temporaire et référencer
    
    Résultat attendu:
    L'expression passe de 132KB à ~50 bytes avec MV.
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Optimisation MV pour large FID selection")
    print("="*80)
    
    class MockLayer:
        def name(self):
            return "ducts"
    
    ducts_layer = MockLayer()
    
    # Simuler une grande liste de FIDs (comme vos 2862 UUIDs)
    large_uuid_list = [f"uuid_{i}" for i in range(2862)]
    
    # === AVANT: FID_LIST inline (inefficace) ===
    print("\n❌ BEFORE: Using inline FID_LIST...")
    
    chain_before = FilterChain(ducts_layer)
    
    # Construire la liste de UUIDs pour l'expression
    uuid_list_str = ', '.join(f"'{uid}'" for uid in large_uuid_list)
    
    fid_filter = Filter(
        filter_type=FilterType.FID_LIST,
        expression=f"pk IN ({uuid_list_str})",
        layer_name="ducts",
        priority=70,
        metadata={'fid_count': len(large_uuid_list)}
    )
    
    chain_before.add_filter(fid_filter)
    expr_before = chain_before.build_expression()
    
    print(f"   Expression length: {len(expr_before):,} chars")
    print(f"   Preview: {expr_before[:100]}...")
    
    # === APRÈS: MATERIALIZED_VIEW (optimisé) ===
    print("\n✅ AFTER: Using MATERIALIZED_VIEW...")
    
    chain_after = FilterChain(ducts_layer)
    
    # Créer MV name avec timestamp
    mv_name = f"mv_selection_ducts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    mv_filter = Filter(
        filter_type=FilterType.MATERIALIZED_VIEW,
        expression=f"pk IN (SELECT pk FROM {mv_name})",
        layer_name="ducts",
        priority=100,  # Priorité MAX pour optimisation
        combine_operator="AND",
        metadata={
            'mv_name': mv_name,
            'fid_count': len(large_uuid_list),
            'original_size': len(expr_before),
            'description': 'Temporary MV for large FID selection'
        },
        is_temporary=True  # MV sera nettoyée après utilisation
    )
    
    chain_after.add_filter(mv_filter)
    expr_after = chain_after.build_expression()
    
    print(f"   Expression length: {len(expr_after):,} chars")
    print(f"   Full expression: {expr_after}")
    
    # Comparaison
    reduction = 100 * (1 - len(expr_after) / len(expr_before))
    print(f"\n📊 Size reduction: {reduction:.1f}%")
    print(f"   Before: {len(expr_before):,} chars")
    print(f"   After:  {len(expr_after):,} chars")
    
    print("\n✅ MV optimization successful!")
    
    return chain_before, chain_after


def example_4_complex_chain():
    """
    Example 4: Chaîne complexe avec multiple filtres
    
    Contexte:
    - Multiple types de filtres combinés
    - Démonstration des priorités
    - Cas réel combinant tous les patterns
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Chaîne complexe multi-filtres")
    print("="*80)
    
    class MockLayer:
        def name(self):
            return "complex_layer"
    
    layer = MockLayer()
    
    chain = FilterChain(layer, CombinationStrategy.PRIORITY_AND)
    
    # Filtre 1: BBOX pour optimisation initiale (priorité 90)
    bbox_filter = Filter(
        filter_type=FilterType.BBOX_FILTER,
        expression="geom && ST_MakeEnvelope(2.0, 48.0, 3.0, 49.0, 4326)",
        layer_name="complex_layer",
        priority=90,
        metadata={'description': 'Bounding box pre-filter for performance'}
    )
    
    # Filtre 2: Spatial selection zone_pop (priorité 80)
    spatial_filter = Filter(
        filter_type=FilterType.SPATIAL_SELECTION,
        expression="pk IN (SELECT pk FROM zone_pop WHERE category = 'urban')",
        layer_name="zone_pop",
        priority=80
    )
    
    # Filtre 3: Buffer intersect (priorité 60)
    buffer_filter = Filter(
        filter_type=FilterType.BUFFER_INTERSECT,
        expression="EXISTS (SELECT 1 FROM source WHERE ST_DWithin(geom, source.geom, 100))",
        layer_name="source",
        priority=60
    )
    
    # Filtre 4: Field conditions (priorité 50)
    field_filter = Filter(
        filter_type=FilterType.FIELD_CONDITION,
        expression="status = 'active' AND quality >= 80",
        layer_name="complex_layer",
        priority=50
    )
    
    # Filtre 5: Custom expression exploration (priorité 30)
    custom_filter = Filter(
        filter_type=FilterType.CUSTOM_EXPRESSION,
        expression="type IN ('A', 'B') OR special_flag = true",
        layer_name="complex_layer",
        priority=30
    )
    
    # Ajouter dans un ordre aléatoire (pour montrer que la priorité gère l'ordre)
    print("\n📋 Adding filters in random order...")
    chain.add_filter(field_filter)
    chain.add_filter(custom_filter)
    chain.add_filter(spatial_filter)
    chain.add_filter(bbox_filter)
    chain.add_filter(buffer_filter)
    
    # Afficher la chaîne (devrait être triée par priorité)
    print("\n" + str(chain))
    
    # Construire expression
    final_expr = chain.build_expression()
    
    print(f"\n✅ Final expression ({len(final_expr)} chars):")
    import re
    formatted = re.sub(r'(AND)', r'\n    \1', final_expr)
    print(f"   {formatted}")
    
    # Vérifier l'ordre des filtres (par position dans l'expression)
    positions = {
        'bbox': final_expr.find('ST_MakeEnvelope'),
        'spatial': final_expr.find('zone_pop'),
        'buffer': final_expr.find('ST_DWithin'),
        'field': final_expr.find("status = 'active'"),
        'custom': final_expr.find("type IN")
    }
    
    print("\n📊 Filter positions (should be in priority order):")
    for name, pos in sorted(positions.items(), key=lambda x: x[1]):
        print(f"   {name:10s}: position {pos:4d}")
    
    # Vérifier que l'ordre est correct
    assert positions['bbox'] < positions['spatial'], "BBOX should be first"
    assert positions['spatial'] < positions['buffer'], "Spatial before buffer"
    assert positions['buffer'] < positions['field'], "Buffer before field"
    assert positions['field'] < positions['custom'], "Field before custom"
    
    print("\n✅ All filters in correct priority order!")
    
    return chain


def main():
    """Run all examples."""
    print("\n" + "#"*80)
    print("# FilterChain System - Usage Examples")
    print("# Démonstration du nouveau système de combinaison de filtres")
    print("#"*80)
    
    try:
        # Example 1: Basic combination
        chain1 = example_1_ducts_with_zone_pop_and_custom()
        
        # Example 2: Buffer intersect
        chain2 = example_2_structures_with_buffer_intersect()
        
        # Example 3: MV optimization
        chain_before, chain_after = example_3_optimization_with_mv()
        
        # Example 4: Complex chain
        chain4 = example_4_complex_chain()
        
        print("\n" + "#"*80)
        print("# ✅ ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("#"*80)
        print("\n📚 Key Takeaways:")
        print("   1. Chaque filtre a un TYPE explicite (FilterType)")
        print("   2. Les PRIORITÉS contrôlent l'ordre d'application")
        print("   3. Les filtres se COMBINENT automatiquement (AND/OR)")
        print("   4. Traçabilité complète (to_dict, __repr__)")
        print("   5. Optimisation MV intégrée (MATERIALIZED_VIEW)")
        print("\n🎯 Next Steps:")
        print("   → Migrer ExpressionBuilder pour utiliser FilterChain")
        print("   → Adapter FilterEngineTask pour construire FilterChain")
        print("   → Tester dans QGIS avec vraies données")
        
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
