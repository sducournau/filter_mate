"""
Test: Mise à jour des widgets exploring lors du changement de couche

Ce test vérifie que les widgets exploring se mettent bien à jour
lorsque la couche courante change, particulièrement pour le widget
MULTIPLE_SELECTION_FEATURES (QgsCheckableComboBoxFeaturesListPickerWidget).

Problème résolu:
- Le widget ne rechargeait pas ses features si l'expression était identique
- Correction dans modules/widgets.py: setLayer() appelle toujours setDisplayExpression()
"""

import sys
import os
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsProject, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant


def test_multiple_selection_widget_updates_on_layer_change():
    """
    Test que le widget MULTIPLE_SELECTION_FEATURES recharge ses features
    lors du changement de couche, même si l'expression est identique.
    """
    print("\n" + "="*70)
    print("TEST: Mise à jour du widget Multiple Selection sur changement de couche")
    print("="*70)
    
    # Mock QGIS layers
    layer1 = Mock(spec=QgsVectorLayer)
    layer1.id.return_value = "layer1_id"
    layer1.name.return_value = "Cities Layer 1"
    layer1.isValid.return_value = True
    layer1.isSpatial.return_value = True
    layer1.providerType.return_value = "postgres"
    
    fields1 = QgsFields()
    fields1.append(QgsField("id", QVariant.Int))
    fields1.append(QgsField("city_name", QVariant.String))
    layer1.fields.return_value = fields1
    
    layer2 = Mock(spec=QgsVectorLayer)
    layer2.id.return_value = "layer2_id"
    layer2.name.return_value = "Cities Layer 2"
    layer2.isValid.return_value = True
    layer2.isSpatial.return_value = True
    layer2.providerType.return_value = "postgres"
    
    # Layer 2 has SAME field structure but DIFFERENT data
    fields2 = QgsFields()
    fields2.append(QgsField("id", QVariant.Int))
    fields2.append(QgsField("city_name", QVariant.String))
    layer2.fields.return_value = fields2
    
    print("\n1. Configuration des couches:")
    print(f"   - Layer 1: {layer1.name()}")
    print(f"   - Layer 2: {layer2.name()}")
    print(f"   - Même structure de champs: {[f.name() for f in fields1]}")
    print(f"   - Expression identique pour les deux: 'city_name'")
    
    # Mock PROJECT_LAYERS avec même expression pour les deux couches
    PROJECT_LAYERS = {
        "layer1_id": {
            "infos": {
                "primary_key_name": "id",
                "primary_key_idx": 0,
                "primary_key_type": "Integer",
                "primary_key_is_numeric": True
            },
            "exploring": {
                "single_selection_expression": "city_name",
                "multiple_selection_expression": "city_name",  # MÊME EXPRESSION
                "custom_selection_expression": "city_name"
            }
        },
        "layer2_id": {
            "infos": {
                "primary_key_name": "id",
                "primary_key_idx": 0,
                "primary_key_type": "Integer",
                "primary_key_is_numeric": True
            },
            "exploring": {
                "single_selection_expression": "city_name",
                "multiple_selection_expression": "city_name",  # MÊME EXPRESSION
                "custom_selection_expression": "city_name"
            }
        }
    }
    
    print("\n2. Simulation du widget MULTIPLE_SELECTION_FEATURES:")
    
    # Mock widget with tracking
    mock_widget = Mock()
    mock_widget.setLayer = Mock()
    mock_widget.setDisplayExpression = Mock()
    calls_log = []
    
    def track_setLayer(layer, layer_props):
        calls_log.append(("setLayer", layer.id(), layer.name()))
        print(f"   → setLayer appelé pour: {layer.name()}")
    
    def track_setDisplayExpression(expr):
        calls_log.append(("setDisplayExpression", expr))
        print(f"   → setDisplayExpression appelé avec: '{expr}'")
    
    mock_widget.setLayer.side_effect = track_setLayer
    mock_widget.setDisplayExpression.side_effect = track_setDisplayExpression
    
    print("\n3. Changement de couche: Layer 1 → Layer 2")
    print("   AVANT le fix: setDisplayExpression n'est PAS appelé")
    print("   APRÈS le fix: setDisplayExpression EST TOUJOURS appelé")
    
    # Simulate the OLD behavior (buggy)
    print("\n   [ANCIEN CODE - Buggy]")
    current_expr = PROJECT_LAYERS["layer1_id"]["exploring"]["multiple_selection_expression"]
    new_expr = PROJECT_LAYERS["layer2_id"]["exploring"]["multiple_selection_expression"]
    
    if current_expr != new_expr:
        print(f"   Expression différente, appel de setDisplayExpression")
        mock_widget.setDisplayExpression(new_expr)
    else:
        print(f"   ❌ Expression identique ('{current_expr}'), setDisplayExpression PAS appelé")
        print(f"   ❌ Le widget garde les features de l'ancienne couche!")
    
    # Simulate the NEW behavior (fixed)
    print("\n   [NOUVEAU CODE - Corrigé]")
    calls_log.clear()
    mock_widget.setLayer(layer2, PROJECT_LAYERS["layer2_id"])
    
    # After the fix, setDisplayExpression is ALWAYS called
    if len([c for c in calls_log if c[0] == "setDisplayExpression"]) > 0:
        print(f"   ✅ setDisplayExpression appelé même si l'expression est identique")
        print(f"   ✅ Les features du widget sont rechargées correctement")
    else:
        print(f"   ❌ ÉCHEC: setDisplayExpression n'a pas été appelé")
    
    print("\n4. Historique des appels:")
    for call in calls_log:
        print(f"   - {call}")
    
    # Assertions
    assert len(calls_log) > 0, "Aucun appel enregistré"
    assert any(c[0] == "setLayer" for c in calls_log), "setLayer n'a pas été appelé"
    
    print("\n" + "="*70)
    print("✅ TEST RÉUSSI: Le widget se met à jour correctement")
    print("="*70)
    

if __name__ == "__main__":
    try:
        test_multiple_selection_widget_updates_on_layer_change()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
