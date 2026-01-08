"""
Tests unitaires pour HistoryService.

Ce module teste le service de gestion d'historique undo/redo
sans dépendances QGIS.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.services.history_service import (
    HistoryService,
    HistoryEntry,
    HistoryState
)


# ============================================================================
# HistoryEntry Tests
# ============================================================================

class TestHistoryEntry:
    """Tests pour HistoryEntry."""
    
    def test_create_factory(self):
        """create() devrait créer une entrée valide."""
        entry = HistoryEntry.create(
            expression='"field" = 1',
            layer_ids=["layer_123", "layer_456"],
            previous_filters=[("layer_123", ""), ("layer_456", '"old" = 2')]
        )
        
        assert entry.expression == '"field" = 1'
        assert "layer_123" in entry.layer_ids
        assert "layer_456" in entry.layer_ids
        assert entry.entry_id.startswith("hist_")
    
    def test_create_with_description(self):
        """create() devrait accepter une description personnalisée."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[],
            description="Custom description"
        )
        
        assert entry.description == "Custom description"
    
    def test_create_auto_description(self):
        """create() devrait générer une description automatique."""
        entry = HistoryEntry.create(
            expression='"name" = \'test\'',
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        
        assert "Filter:" in entry.description
    
    def test_create_with_metadata(self):
        """create() devrait accepter des métadonnées."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[],
            metadata={"source": "ui", "version": 1}
        )
        
        assert entry.get_metadata_value("source") == "ui"
        assert entry.get_metadata_value("version") == 1
    
    def test_layer_count(self):
        """layer_count devrait retourner le nombre de couches."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["a", "b", "c"],
            previous_filters=[]
        )
        
        assert entry.layer_count == 3
    
    def test_has_previous_filters_true(self):
        """has_previous_filters devrait être True si des filtres existent."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[("layer_1", "old_filter")]
        )
        
        assert entry.has_previous_filters
    
    def test_has_previous_filters_false(self):
        """has_previous_filters devrait être False si pas de filtres."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        
        assert not entry.has_previous_filters
    
    def test_get_previous_filter_found(self):
        """get_previous_filter devrait retourner le filtre précédent."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1", "layer_2"],
            previous_filters=[("layer_1", "filter_a"), ("layer_2", "filter_b")]
        )
        
        assert entry.get_previous_filter("layer_1") == "filter_a"
        assert entry.get_previous_filter("layer_2") == "filter_b"
    
    def test_get_previous_filter_not_found(self):
        """get_previous_filter devrait retourner None si non trouvé."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[("layer_1", "filter")]
        )
        
        assert entry.get_previous_filter("unknown_layer") is None
    
    def test_entry_is_immutable(self):
        """HistoryEntry devrait être immuable."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.expression = "modified"
    
    def test_str_representation(self):
        """__str__ devrait retourner une représentation lisible."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[],
            description="Test filter"
        )
        
        str_repr = str(entry)
        
        assert "HistoryEntry" in str_repr
        assert entry.entry_id in str_repr
    
    def test_get_metadata_value_not_found(self):
        """get_metadata_value devrait retourner None si clé non trouvée."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        
        assert entry.get_metadata_value("unknown_key") is None


# ============================================================================
# HistoryState Tests
# ============================================================================

class TestHistoryState:
    """Tests pour HistoryState."""
    
    def test_state_attributes(self):
        """HistoryState devrait avoir tous les attributs."""
        state = HistoryState(
            can_undo=True,
            can_redo=False,
            undo_description="Undo filter",
            redo_description="",
            undo_count=5,
            redo_count=0
        )
        
        assert state.can_undo is True
        assert state.can_redo is False
        assert state.undo_description == "Undo filter"
        assert state.redo_description == ""
        assert state.undo_count == 5
        assert state.redo_count == 0


# ============================================================================
# HistoryService Basic Tests
# ============================================================================

class TestHistoryServiceBasic:
    """Tests de base pour HistoryService."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    @pytest.fixture
    def sample_entry(self):
        """Créer une entrée exemple."""
        return HistoryEntry.create(
            expression='"field" = 1',
            layer_ids=["layer_123"],
            previous_filters=[("layer_123", "")]
        )
    
    def test_initial_state_empty(self, service):
        """L'état initial devrait être vide."""
        assert not service.can_undo
        assert not service.can_redo
        assert service.undo_count == 0
        assert service.redo_count == 0
    
    def test_push_entry(self, service, sample_entry):
        """push devrait ajouter une entrée."""
        service.push(sample_entry)
        
        assert service.can_undo
        assert not service.can_redo
        assert service.undo_count == 1
    
    def test_push_multiple_entries(self, service):
        """push devrait ajouter plusieurs entrées."""
        for i in range(5):
            entry = HistoryEntry.create(
                expression=f"expr_{i}",
                layer_ids=["layer"],
                previous_filters=[]
            )
            service.push(entry)
        
        assert service.undo_count == 5
    
    def test_total_entries(self, service, sample_entry):
        """total_entries devrait compter toutes les entrées."""
        service.push(sample_entry)
        
        assert service.total_entries == 1


# ============================================================================
# HistoryService Undo Tests
# ============================================================================

class TestHistoryServiceUndo:
    """Tests pour la fonctionnalité undo."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    def test_undo_empty_returns_none(self, service):
        """undo sur pile vide devrait retourner None."""
        result = service.undo()
        
        assert result is None
    
    def test_undo_returns_entry(self, service):
        """undo devrait retourner l'entrée annulée."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[("layer_1", "old_filter")]
        )
        service.push(entry)
        
        undone = service.undo()
        
        assert undone is not None
        assert undone.expression == "test"
    
    def test_undo_moves_to_redo(self, service):
        """undo devrait déplacer l'entrée vers redo."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        
        service.undo()
        
        assert not service.can_undo
        assert service.can_redo
        assert service.redo_count == 1
    
    def test_multiple_undo(self, service):
        """Multiple undo devrait fonctionner en séquence."""
        entries = []
        for i in range(3):
            entry = HistoryEntry.create(
                expression=f"expr_{i}",
                layer_ids=["layer"],
                previous_filters=[]
            )
            service.push(entry)
            entries.append(entry)
        
        # Undo should return entries in reverse order (LIFO)
        undone3 = service.undo()
        undone2 = service.undo()
        undone1 = service.undo()
        
        assert undone3.expression == "expr_2"
        assert undone2.expression == "expr_1"
        assert undone1.expression == "expr_0"
        
        assert service.redo_count == 3


# ============================================================================
# HistoryService Redo Tests
# ============================================================================

class TestHistoryServiceRedo:
    """Tests pour la fonctionnalité redo."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    def test_redo_empty_returns_none(self, service):
        """redo sur pile vide devrait retourner None."""
        result = service.redo()
        
        assert result is None
    
    def test_redo_returns_entry(self, service):
        """redo devrait retourner l'entrée refaite."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        service.undo()
        
        redone = service.redo()
        
        assert redone is not None
        assert redone.expression == "test"
    
    def test_redo_moves_to_undo(self, service):
        """redo devrait déplacer l'entrée vers undo."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        service.undo()
        
        service.redo()
        
        assert service.can_undo
        assert not service.can_redo
    
    def test_undo_redo_cycle(self, service):
        """Cycle undo/redo devrait préserver l'entrée."""
        entry = HistoryEntry.create(
            expression="original",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        
        undone = service.undo()
        redone = service.redo()
        
        assert undone.entry_id == redone.entry_id


# ============================================================================
# HistoryService Redo Clearing Tests
# ============================================================================

class TestHistoryServiceRedoClearing:
    """Tests pour l'effacement de redo lors de nouvelles opérations."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    def test_push_clears_redo(self, service):
        """push devrait effacer la pile redo."""
        entry1 = HistoryEntry.create(
            expression="first",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry1)
        service.undo()
        
        assert service.can_redo
        
        entry2 = HistoryEntry.create(
            expression="second",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry2)
        
        assert not service.can_redo
        assert service.redo_count == 0


# ============================================================================
# HistoryService Peek Tests
# ============================================================================

class TestHistoryServicePeek:
    """Tests pour les fonctions peek."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    def test_peek_undo_empty(self, service):
        """peek_undo sur pile vide devrait retourner None."""
        assert service.peek_undo() is None
    
    def test_peek_redo_empty(self, service):
        """peek_redo sur pile vide devrait retourner None."""
        assert service.peek_redo() is None
    
    def test_peek_undo_returns_top(self, service):
        """peek_undo devrait retourner le sommet sans modifier."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        
        peeked = service.peek_undo()
        
        assert peeked.expression == "test"
        assert service.undo_count == 1  # Pas modifié
    
    def test_peek_redo_returns_top(self, service):
        """peek_redo devrait retourner le sommet sans modifier."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        service.undo()
        
        peeked = service.peek_redo()
        
        assert peeked.expression == "test"
        assert service.redo_count == 1  # Pas modifié


# ============================================================================
# HistoryService Max Depth Tests
# ============================================================================

class TestHistoryServiceMaxDepth:
    """Tests pour la limite de profondeur."""
    
    def test_max_depth_enforced(self):
        """La profondeur maximale devrait être respectée."""
        service = HistoryService(max_depth=5)
        
        for i in range(10):
            entry = HistoryEntry.create(
                expression=f"expr_{i}",
                layer_ids=["layer"],
                previous_filters=[]
            )
            service.push(entry)
        
        # Seulement les 5 dernières devraient rester
        assert service.undo_count == 5
        
        # La plus ancienne devrait être expr_5 (pas expr_0)
        entries = []
        while service.can_undo:
            entries.append(service.undo())
        
        # Les entrées sont en ordre LIFO
        assert entries[0].expression == "expr_9"
        assert entries[-1].expression == "expr_5"


# ============================================================================
# HistoryService State Tests
# ============================================================================

class TestHistoryServiceState:
    """Tests pour get_state()."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    def test_get_state_initial(self, service):
        """get_state initial devrait être correct."""
        state = service.get_state()
        
        assert not state.can_undo
        assert not state.can_redo
        assert state.undo_count == 0
        assert state.redo_count == 0
    
    def test_get_state_after_push(self, service):
        """get_state après push devrait refléter le changement."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[],
            description="Test filter"
        )
        service.push(entry)
        
        state = service.get_state()
        
        assert state.can_undo
        assert not state.can_redo
        assert state.undo_count == 1
        assert "Test filter" in state.undo_description
    
    def test_get_state_after_undo(self, service):
        """get_state après undo devrait refléter le changement."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[],
            description="Test filter"
        )
        service.push(entry)
        service.undo()
        
        state = service.get_state()
        
        assert not state.can_undo
        assert state.can_redo
        assert state.redo_count == 1
        assert "Test filter" in state.redo_description


# ============================================================================
# HistoryService Callback Tests
# ============================================================================

class TestHistoryServiceCallbacks:
    """Tests pour les callbacks on_change."""
    
    def test_callback_on_push(self):
        """on_change devrait être appelé lors de push."""
        callback_states = []
        
        def on_change(state):
            callback_states.append(state)
        
        service = HistoryService(max_depth=10, on_change=on_change)
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)
        
        assert len(callback_states) == 1
        assert callback_states[0].can_undo
    
    def test_callback_on_undo(self):
        """on_change devrait être appelé lors de undo."""
        callback_count = [0]
        
        def on_change(state):
            callback_count[0] += 1
        
        service = HistoryService(max_depth=10, on_change=on_change)
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)  # callback 1
        service.undo()  # callback 2
        
        assert callback_count[0] == 2
    
    def test_callback_on_redo(self):
        """on_change devrait être appelé lors de redo."""
        callback_count = [0]
        
        def on_change(state):
            callback_count[0] += 1
        
        service = HistoryService(max_depth=10, on_change=on_change)
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        service.push(entry)  # callback 1
        service.undo()  # callback 2
        service.redo()  # callback 3
        
        assert callback_count[0] == 3


# ============================================================================
# HistoryService Clear Tests
# ============================================================================

class TestHistoryServiceClear:
    """Tests pour la fonction clear."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return HistoryService(max_depth=10)
    
    def test_clear_empties_all(self, service):
        """clear devrait vider toutes les piles."""
        for i in range(5):
            entry = HistoryEntry.create(
                expression=f"expr_{i}",
                layer_ids=["layer"],
                previous_filters=[]
            )
            service.push(entry)
        
        service.undo()
        service.undo()
        
        # Avant clear
        assert service.undo_count == 3
        assert service.redo_count == 2
        
        service.clear()
        
        # Après clear
        assert service.undo_count == 0
        assert service.redo_count == 0
        assert not service.can_undo
        assert not service.can_redo
