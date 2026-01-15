"""
Test d'intégration pour vérifier que le fix de compatibilité HistoryService fonctionne.

Ce test simule ce qui se passe dans filter_mate_app.py et undo_redo_handler.py.
"""

def test_history_service_compatibility():
    """Test that HistoryService provides backward compatible API."""
    from core.services.history_service import HistoryService
    
    # Simule ce qui se passe dans filter_mate_app.py ligne 347
    history_manager = HistoryService(max_depth=50)
    
    # Simule ce qui se passe dans undo_redo_handler.py ligne 620
    # C'est cette ligne qui causait l'erreur avant le fix
    layer_id = "test_layer_123"
    history = history_manager.get_or_create_history(layer_id)
    
    # Vérifications
    assert hasattr(history_manager, 'get_or_create_history'), \
        "HistoryService should have get_or_create_history method"
    
    assert history is not None, \
        "get_or_create_history should return a LayerHistory instance"
    
    assert hasattr(history, 'push_state'), \
        "LayerHistory should have push_state method"
    
    assert hasattr(history, '_states'), \
        "LayerHistory should have _states attribute"
    
    assert history.layer_id == layer_id, \
        f"LayerHistory should store layer_id, got {history.layer_id}"
    
    # Test push_state (ligne 620-625 dans undo_redo_handler.py)
    history.push_state(
        expression="test_field = 'value'",
        feature_count=42,
        description="Test filter"
    )
    
    assert len(history._states) == 1, \
        "push_state should add a state"
    
    # Test que le même layer_id retourne la même instance
    history2 = history_manager.get_or_create_history(layer_id)
    assert history is history2, \
        "get_or_create_history should return same instance for same layer_id"
    
    # Test avec un autre layer_id
    history3 = history_manager.get_or_create_history("another_layer")
    assert history is not history3, \
        "get_or_create_history should return different instance for different layer_id"
    
    print("✅ Tous les tests de compatibilité ont réussi!")
    return True


if __name__ == "__main__":
    try:
        test_history_service_compatibility()
        print("\n" + "="*60)
        print("SUCCESS: Le fix de compatibilité fonctionne correctement")
        print("="*60)
        print("\nCe qui a été testé:")
        print("- ✓ HistoryService.get_or_create_history() existe")
        print("- ✓ Retourne une instance de LayerHistory")
        print("- ✓ LayerHistory.push_state() fonctionne")
        print("- ✓ Cache des instances fonctionne")
        print("\nLe plugin devrait maintenant se charger sans l'erreur:")
        print("  AttributeError: 'HistoryService' object has no attribute 'get_or_create_history'")
    except Exception as e:
        print(f"\n❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
