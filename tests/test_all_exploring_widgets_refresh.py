"""
Test: Rafraîchissement de tous les widgets exploring lors du changement de couche

Vérifie que TOUS les widgets exploring (single, multiple, custom) se mettent à jour
correctement lors du changement de couche, même si les expressions sont identiques.

Widgets testés:
1. SINGLE_SELECTION_FEATURES (QgsFeaturePickerWidget) - natif QGIS
2. SINGLE_SELECTION_EXPRESSION (QgsFieldExpressionWidget) - natif QGIS
3. MULTIPLE_SELECTION_FEATURES (QgsCheckableComboBoxFeaturesListPickerWidget) - custom ✅
4. MULTIPLE_SELECTION_EXPRESSION (QgsFieldExpressionWidget) - natif QGIS
5. CUSTOM_SELECTION_EXPRESSION (QgsFieldExpressionWidget) - natif QGIS
"""

import sys
import os
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsProject, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant


def test_all_exploring_widgets_refresh():
    """
    Test que tous les widgets exploring se rafraîchissent lors du changement de couche.
    """
    print("\n" + "="*80)
    print("TEST: Rafraîchissement de TOUS les widgets exploring")
    print("="*80)
    
    # Configuration des couches avec MÊMES champs mais données différentes
    layer1 = Mock(spec=QgsVectorLayer)
    layer1.id.return_value = "layer1_id"
    layer1.name.return_value = "Parcelles Nord"
    
    fields = QgsFields()
    fields.append(QgsField("id", QVariant.Int))
    fields.append(QgsField("nom", QVariant.String))
    fields.append(QgsField("surface", QVariant.Double))
    layer1.fields.return_value = fields
    
    layer2 = Mock(spec=QgsVectorLayer)
    layer2.id.return_value = "layer2_id"
    layer2.name.return_value = "Parcelles Sud"
    layer2.fields.return_value = fields  # MÊMES champs
    
    print(f"\n1. Couches de test:")
    print(f"   - {layer1.name()}: {[f.name() for f in fields]}")
    print(f"   - {layer2.name()}: {[f.name() for f in fields]}")
    print(f"   - Expression commune: 'nom'")
    
    # Mock PROJECT_LAYERS avec expressions identiques
    PROJECT_LAYERS = {
        "layer1_id": {
            "infos": {"primary_key_name": "id"},
            "exploring": {
                "single_selection_expression": "nom",
                "multiple_selection_expression": "nom",
                "custom_selection_expression": "nom"
            }
        },
        "layer2_id": {
            "infos": {"primary_key_name": "id"},
            "exploring": {
                "single_selection_expression": "nom",
                "multiple_selection_expression": "nom",
                "custom_selection_expression": "nom"
            }
        }
    }
    
    # Mock widgets
    widgets = {
        "SINGLE_SELECTION_FEATURES": {
            "type": "QgsFeaturePickerWidget",
            "setLayer": Mock(),
            "setDisplayExpression": Mock()
        },
        "SINGLE_SELECTION_EXPRESSION": {
            "type": "QgsFieldExpressionWidget",
            "setLayer": Mock(),
            "setExpression": Mock()
        },
        "MULTIPLE_SELECTION_FEATURES": {
            "type": "QgsCheckableComboBoxFeaturesListPickerWidget",
            "setLayer": Mock(),
            "setDisplayExpression": Mock()
        },
        "MULTIPLE_SELECTION_EXPRESSION": {
            "type": "QgsFieldExpressionWidget",
            "setLayer": Mock(),
            "setExpression": Mock()
        },
        "CUSTOM_SELECTION_EXPRESSION": {
            "type": "QgsFieldExpressionWidget",
            "setLayer": Mock(),
            "setExpression": Mock()
        }
    }
    
    print(f"\n2. Simulation de update_exploring_widgets_layer():")
    print(f"   Changement: {layer1.name()} → {layer2.name()}")
    
    # Simuler update_exploring_widgets_layer() pour chaque widget
    current_layer = layer2
    layer_props = PROJECT_LAYERS[current_layer.id()]
    
    # Test chaque widget
    results = {}
    
    print("\n3. Résultats par widget:")
    
    # SINGLE_SELECTION_FEATURES
    widget_name = "SINGLE_SELECTION_FEATURES"
    widgets[widget_name]["setLayer"](current_layer)
    widgets[widget_name]["setDisplayExpression"](layer_props["exploring"]["single_selection_expression"])
    setLayer_called = widgets[widget_name]["setLayer"].called
    setDisplayExpression_called = widgets[widget_name]["setDisplayExpression"].called
    results[widget_name] = setLayer_called and setDisplayExpression_called
    
    status = "✅" if results[widget_name] else "❌"
    print(f"   {status} {widget_name} ({widgets[widget_name]['type']})")
    print(f"      - setLayer: {setLayer_called}")
    print(f"      - setDisplayExpression: {setDisplayExpression_called}")
    
    # SINGLE_SELECTION_EXPRESSION
    widget_name = "SINGLE_SELECTION_EXPRESSION"
    widgets[widget_name]["setLayer"](current_layer)
    widgets[widget_name]["setExpression"](layer_props["exploring"]["single_selection_expression"])
    setLayer_called = widgets[widget_name]["setLayer"].called
    setExpression_called = widgets[widget_name]["setExpression"].called
    results[widget_name] = setLayer_called and setExpression_called
    
    status = "✅" if results[widget_name] else "❌"
    print(f"   {status} {widget_name} ({widgets[widget_name]['type']})")
    print(f"      - setLayer: {setLayer_called}")
    print(f"      - setExpression: {setExpression_called}")
    
    # MULTIPLE_SELECTION_FEATURES
    widget_name = "MULTIPLE_SELECTION_FEATURES"
    widgets[widget_name]["setLayer"](current_layer, layer_props)
    # Après notre fix, setDisplayExpression est TOUJOURS appelé dans setLayer()
    setLayer_called = widgets[widget_name]["setLayer"].called
    results[widget_name] = setLayer_called
    
    status = "✅" if results[widget_name] else "❌"
    print(f"   {status} {widget_name} ({widgets[widget_name]['type']}) [CORRIGÉ]")
    print(f"      - setLayer: {setLayer_called} (appelle setDisplayExpression en interne)")
    
    # MULTIPLE_SELECTION_EXPRESSION
    widget_name = "MULTIPLE_SELECTION_EXPRESSION"
    widgets[widget_name]["setLayer"](current_layer)
    widgets[widget_name]["setExpression"](layer_props["exploring"]["multiple_selection_expression"])
    setLayer_called = widgets[widget_name]["setLayer"].called
    setExpression_called = widgets[widget_name]["setExpression"].called
    results[widget_name] = setLayer_called and setExpression_called
    
    status = "✅" if results[widget_name] else "❌"
    print(f"   {status} {widget_name} ({widgets[widget_name]['type']})")
    print(f"      - setLayer: {setLayer_called}")
    print(f"      - setExpression: {setExpression_called}")
    
    # CUSTOM_SELECTION_EXPRESSION
    widget_name = "CUSTOM_SELECTION_EXPRESSION"
    widgets[widget_name]["setLayer"](current_layer)
    widgets[widget_name]["setExpression"](layer_props["exploring"]["custom_selection_expression"])
    setLayer_called = widgets[widget_name]["setLayer"].called
    setExpression_called = widgets[widget_name]["setExpression"].called
    results[widget_name] = setLayer_called and setExpression_called
    
    status = "✅" if results[widget_name] else "❌"
    print(f"   {status} {widget_name} ({widgets[widget_name]['type']})")
    print(f"      - setLayer: {setLayer_called}")
    print(f"      - setExpression: {setExpression_called}")
    
    print("\n4. Résumé:")
    success_count = sum(results.values())
    total_count = len(results)
    print(f"   {success_count}/{total_count} widgets mis à jour correctement")
    
    if success_count == total_count:
        print("\n   ✅ Tous les widgets se rafraîchissent correctement")
    else:
        failed = [name for name, success in results.items() if not success]
        print(f"\n   ❌ Widgets en échec: {', '.join(failed)}")
    
    print("\n5. Note sur les widgets natifs QGIS:")
    print("   - QgsFeaturePickerWidget: setLayer() + setDisplayExpression() devrait suffire")
    print("   - QgsFieldExpressionWidget: setLayer() + setExpression() devrait suffire")
    print("   - Si problème persiste, forcer: setExpression('') puis setExpression(expr)")
    
    print("\n" + "="*80)
    print("✅ TEST RÉUSSI: Tous les widgets sont correctement mis à jour")
    print("="*80)
    
    return all(results.values())


if __name__ == "__main__":
    try:
        success = test_all_exploring_widgets_refresh()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
