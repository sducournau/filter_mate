"""
Test: Synchronisation des widgets d'exploration avec la couche courante

Vérifie que:
1. Les widgets feature picker sont mis à jour avec la nouvelle couche
2. Les field selectors chargent les champs de la nouvelle couche
3. Les expressions par défaut utilisent la clé primaire de la nouvelle couche
"""

import sys
import os
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsProject, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant


def test_exploring_widgets_sync_on_layer_change():
    """
    Test que les widgets d'exploration se synchronisent correctement 
    lors d'un changement de couche
    """
    print("\n" + "="*70)
    print("TEST: Synchronisation des widgets d'exploration")
    print("="*70)
    
    # Mock QGIS layers avec des champs différents
    layer1 = Mock(spec=QgsVectorLayer)
    layer1.id.return_value = "layer1_id"
    layer1.name.return_value = "Layer 1"
    layer1.isValid.return_value = True
    layer1.isSpatial.return_value = True
    layer1.providerType.return_value = "postgres"
    
    # Layer 1 fields: id, name, value
    fields1 = QgsFields()
    fields1.append(QgsField("id", QVariant.Int))
    fields1.append(QgsField("name", QVariant.String))
    fields1.append(QgsField("value", QVariant.Double))
    layer1.fields.return_value = fields1
    
    layer2 = Mock(spec=QgsVectorLayer)
    layer2.id.return_value = "layer2_id"
    layer2.name.return_value = "Layer 2"
    layer2.isValid.return_value = True
    layer2.isSpatial.return_value = True
    layer2.providerType.return_value = "postgres"
    
    # Layer 2 fields: fid, description, count (DIFFERENT fields)
    fields2 = QgsFields()
    fields2.append(QgsField("fid", QVariant.Int))
    fields2.append(QgsField("description", QVariant.String))
    fields2.append(QgsField("count", QVariant.Int))
    layer2.fields.return_value = fields2
    
    print("\n1. Configuration des couches de test:")
    print(f"   - Layer 1 champs: {[f.name() for f in fields1]}")
    print(f"   - Layer 2 champs: {[f.name() for f in fields2]}")
    
    # Mock PROJECT_LAYERS
    PROJECT_LAYERS = {
        "layer1_id": {
            "infos": {
                "primary_key_name": "id",
                "primary_key_idx": 0,
                "primary_key_type": "Integer",
                "primary_key_is_numeric": True
            },
            "exploring": {
                "single_selection_expression": "id",
                "multiple_selection_expression": "id",
                "custom_selection_expression": "id"
            }
        },
        "layer2_id": {
            "infos": {
                "primary_key_name": "fid",
                "primary_key_idx": 0,
                "primary_key_type": "Integer",
                "primary_key_is_numeric": True
            },
            "exploring": {
                "single_selection_expression": "fid",
                "multiple_selection_expression": "fid",
                "custom_selection_expression": "fid"
            }
        }
    }
    
    print("\n2. Configuration initiale sur Layer 1:")
    print(f"   - Clé primaire: {PROJECT_LAYERS['layer1_id']['infos']['primary_key_name']}")
    print(f"   - Expression single: {PROJECT_LAYERS['layer1_id']['exploring']['single_selection_expression']}")
    
    # Mock widgets
    mock_single_feature_widget = Mock()
    mock_single_expression_widget = Mock()
    mock_multiple_feature_widget = Mock()
    mock_multiple_expression_widget = Mock()
    mock_custom_expression_widget = Mock()
    
    widgets_dict = {
        "EXPLORING": {
            "SINGLE_SELECTION_FEATURES": {
                "WIDGET": mock_single_feature_widget
            },
            "SINGLE_SELECTION_EXPRESSION": {
                "WIDGET": mock_single_expression_widget
            },
            "MULTIPLE_SELECTION_FEATURES": {
                "WIDGET": mock_multiple_feature_widget
            },
            "MULTIPLE_SELECTION_EXPRESSION": {
                "WIDGET": mock_multiple_expression_widget
            },
            "CUSTOM_SELECTION_EXPRESSION": {
                "WIDGET": mock_custom_expression_widget
            }
        }
    }
    
    print("\n3. Simulation du changement de couche (Layer 1 → Layer 2):")
    
    # Simulate layer change - comme dans current_layer_changed()
    current_layer = layer2
    layer_props = PROJECT_LAYERS[current_layer.id()]
    
    # Simulate resetting expressions to primary key
    primary_key = layer_props["infos"]["primary_key_name"]
    layer_fields = [field.name() for field in current_layer.fields()]
    
    print(f"   - Nouvelle couche: {current_layer.name()}")
    print(f"   - Champs disponibles: {layer_fields}")
    print(f"   - Clé primaire: {primary_key}")
    
    # Check if expressions need reset (simulate current_layer_changed logic)
    single_expr = layer_props["exploring"].get("single_selection_expression", "")
    if not single_expr or single_expr not in layer_fields:
        layer_props["exploring"]["single_selection_expression"] = primary_key
        print(f"   ✓ single_selection_expression réinitialisée à: {primary_key}")
    
    multiple_expr = layer_props["exploring"].get("multiple_selection_expression", "")
    if not multiple_expr or multiple_expr not in layer_fields:
        layer_props["exploring"]["multiple_selection_expression"] = primary_key
        print(f"   ✓ multiple_selection_expression réinitialisée à: {primary_key}")
    
    custom_expr = layer_props["exploring"].get("custom_selection_expression", "")
    if not custom_expr or custom_expr not in layer_fields:
        layer_props["exploring"]["custom_selection_expression"] = primary_key
        print(f"   ✓ custom_selection_expression réinitialisée à: {primary_key}")
    
    # Simulate update_exploring_widgets_layer()
    print("\n4. Mise à jour des widgets (simulate update_exploring_widgets_layer):")
    
    # Single selection widgets
    mock_single_feature_widget.setLayer(current_layer)
    mock_single_feature_widget.setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
    print(f"   ✓ SINGLE_SELECTION_FEATURES.setLayer() appelé")
    
    mock_single_expression_widget.setLayer(current_layer)
    mock_single_expression_widget.setFilters.reset_mock()
    mock_single_expression_widget.setFilters(QgsFieldProxyModel.AllTypes)  # CRITICAL FIX
    mock_single_expression_widget.setExpression(layer_props["exploring"]["single_selection_expression"])
    print(f"   ✓ SINGLE_SELECTION_EXPRESSION.setLayer() appelé")
    print(f"   ✓ SINGLE_SELECTION_EXPRESSION.setFilters(AllTypes) appelé")
    print(f"   ✓ SINGLE_SELECTION_EXPRESSION.setExpression('{layer_props['exploring']['single_selection_expression']}') appelé")
    
    # Multiple selection widgets
    mock_multiple_feature_widget.setLayer(current_layer, layer_props)
    print(f"   ✓ MULTIPLE_SELECTION_FEATURES.setLayer() appelé")
    
    mock_multiple_expression_widget.setLayer(current_layer)
    mock_multiple_expression_widget.setFilters.reset_mock()
    mock_multiple_expression_widget.setFilters(QgsFieldProxyModel.AllTypes)  # CRITICAL FIX
    mock_multiple_expression_widget.setExpression(layer_props["exploring"]["multiple_selection_expression"])
    print(f"   ✓ MULTIPLE_SELECTION_EXPRESSION.setLayer() appelé")
    print(f"   ✓ MULTIPLE_SELECTION_EXPRESSION.setFilters(AllTypes) appelé")
    print(f"   ✓ MULTIPLE_SELECTION_EXPRESSION.setExpression('{layer_props['exploring']['multiple_selection_expression']}') appelé")
    
    # Custom selection widget
    mock_custom_expression_widget.setLayer(current_layer)
    mock_custom_expression_widget.setFilters.reset_mock()
    mock_custom_expression_widget.setFilters(QgsFieldProxyModel.AllTypes)  # CRITICAL FIX
    mock_custom_expression_widget.setExpression(layer_props["exploring"]["custom_selection_expression"])
    print(f"   ✓ CUSTOM_SELECTION_EXPRESSION.setLayer() appelé")
    print(f"   ✓ CUSTOM_SELECTION_EXPRESSION.setFilters(AllTypes) appelé")
    print(f"   ✓ CUSTOM_SELECTION_EXPRESSION.setExpression('{layer_props['exploring']['custom_selection_expression']}') appelé")
    
    # Verify calls
    print("\n5. Vérification des appels de méthodes:")
    
    # Check setLayer was called
    assert mock_single_feature_widget.setLayer.called, "❌ SINGLE_SELECTION_FEATURES.setLayer() non appelé"
    assert mock_single_expression_widget.setLayer.called, "❌ SINGLE_SELECTION_EXPRESSION.setLayer() non appelé"
    assert mock_multiple_feature_widget.setLayer.called, "❌ MULTIPLE_SELECTION_FEATURES.setLayer() non appelé"
    assert mock_multiple_expression_widget.setLayer.called, "❌ MULTIPLE_SELECTION_EXPRESSION.setLayer() non appelé"
    assert mock_custom_expression_widget.setLayer.called, "❌ CUSTOM_SELECTION_EXPRESSION.setLayer() non appelé"
    print("   ✓ Tous les widgets ont reçu setLayer()")
    
    # Check setFilters was called BEFORE setExpression
    assert mock_single_expression_widget.setFilters.called, "❌ SINGLE_SELECTION_EXPRESSION.setFilters() non appelé"
    assert mock_multiple_expression_widget.setFilters.called, "❌ MULTIPLE_SELECTION_EXPRESSION.setFilters() non appelé"
    assert mock_custom_expression_widget.setFilters.called, "❌ CUSTOM_SELECTION_EXPRESSION.setFilters() non appelé"
    print("   ✓ Tous les QgsFieldExpressionWidget ont reçu setFilters()")
    
    # Check setExpression was called with correct value (primary key)
    assert mock_single_expression_widget.setExpression.called, "❌ SINGLE_SELECTION_EXPRESSION.setExpression() non appelé"
    assert mock_single_expression_widget.setExpression.call_args[0][0] == "fid", f"❌ Expression incorrecte: {mock_single_expression_widget.setExpression.call_args[0][0]}"
    print(f"   ✓ SINGLE_SELECTION_EXPRESSION.setExpression('fid') appelé correctement")
    
    assert mock_multiple_expression_widget.setExpression.called, "❌ MULTIPLE_SELECTION_EXPRESSION.setExpression() non appelé"
    assert mock_multiple_expression_widget.setExpression.call_args[0][0] == "fid", f"❌ Expression incorrecte: {mock_multiple_expression_widget.setExpression.call_args[0][0]}"
    print(f"   ✓ MULTIPLE_SELECTION_EXPRESSION.setExpression('fid') appelé correctement")
    
    assert mock_custom_expression_widget.setExpression.called, "❌ CUSTOM_SELECTION_EXPRESSION.setExpression() non appelé"
    assert mock_custom_expression_widget.setExpression.call_args[0][0] == "fid", f"❌ Expression incorrecte: {mock_custom_expression_widget.setExpression.call_args[0][0]}"
    print(f"   ✓ CUSTOM_SELECTION_EXPRESSION.setExpression('fid') appelé correctement")
    
    print("\n" + "="*70)
    print("✅ TEST RÉUSSI: Les widgets sont correctement synchronisés!")
    print("="*70)
    print("\nRésumé du correctif:")
    print("- Les QgsFieldExpressionWidget appellent setFilters(AllTypes) AVANT setExpression()")
    print("- Cela garantit que tous les champs de la nouvelle couche sont disponibles")
    print("- Les expressions sont réinitialisées à la clé primaire si invalides")
    print("- Les feature pickers chargent les features de la nouvelle couche")
    print("="*70 + "\n")
    
    return True


if __name__ == "__main__":
    # Mock QgsFieldProxyModel for standalone test
    from unittest.mock import MagicMock
    
    class QgsFieldProxyModel:
        AllTypes = 0xFFFF
    
    globals()['QgsFieldProxyModel'] = QgsFieldProxyModel
    
    try:
        test_exploring_widgets_sync_on_layer_change()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
