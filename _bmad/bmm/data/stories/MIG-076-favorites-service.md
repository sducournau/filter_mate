---
storyId: MIG-076
title: Create FavoritesService
epic: 6.4 - Additional Services
phase: 6
sprint: 7
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-012]
blocks: [MIG-072, MIG-081, MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-076: Create FavoritesService

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un service pour les favoris,  
**Afin que** le CRUD favoris soit testable et découplé de l'UI.

---

## 🎯 Objectif

Créer un service pur Python pour gérer les opérations CRUD sur les favoris avec persistance via `FavoritesRepository`.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `core/services/favorites_service.py` créé (< 250 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style
- [ ] **Aucune dépendance QGIS directe**

### Méthodes à Implémenter

- [ ] `add_favorite(name: str, expression: str, layer_id: str) -> Favorite`
- [ ] `apply_favorite(favorite: Favorite) -> bool`
- [ ] `remove_favorite(favorite_id: str) -> bool`
- [ ] `update_favorite(favorite_id: str, **kwargs) -> Favorite`
- [ ] `get_favorites_for_layer(layer_id: str) -> List[Favorite]`
- [ ] `get_all_favorites() -> List[Favorite]`
- [ ] `export_favorites(path: str) -> bool`
- [ ] `import_favorites(path: str) -> int`
- [ ] `search_favorites(query: str) -> List[Favorite]`

### Architecture Hexagonale

- [ ] Utilise `Favorite` entity du domaine
- [ ] Utilise `FavoritesRepository` pour la persistance
- [ ] Tests unitaires sans mocks QGIS

### Tests

- [ ] `tests/unit/core/services/test_favorites_service.py` créé
- [ ] Tests pour CRUD complet
- [ ] Tests pour import/export
- [ ] Couverture > 90%

---

## 📝 Spécifications Techniques

### Structure du Service

```python
"""
Favorites Service for FilterMate.

Pure Python service for favorites management.
No direct QGIS dependencies - uses repositories.
"""

from typing import List, Optional
from datetime import datetime
import json
import logging

from core.domain.entities import Favorite
from core.ports.favorites_repository import FavoritesRepository

logger = logging.getLogger(__name__)


class FavoritesService:
    """
    Service for managing filter favorites.

    This service contains pure business logic for CRUD operations
    on favorites. Persistence is delegated to the repository.

    Features:
    - Add/Remove/Update favorites
    - Layer-specific favorites
    - Import/Export to JSON
    - Search functionality
    """

    def __init__(self, repository: FavoritesRepository) -> None:
        """
        Initialize the favorites service.

        Args:
            repository: Repository for favorites persistence
        """
        self._repository = repository

    def add_favorite(
        self,
        name: str,
        expression: str,
        layer_id: Optional[str] = None,
        description: str = ""
    ) -> Favorite:
        """
        Add a new favorite.

        Args:
            name: Display name for the favorite
            expression: Filter expression
            layer_id: Optional layer ID to associate with
            description: Optional description

        Returns:
            Created Favorite entity

        Raises:
            ValueError: If name is empty or already exists
        """
        if not name or not name.strip():
            raise ValueError("Favorite name cannot be empty")

        # Check for duplicate name
        existing = self._repository.get_by_name(name)
        if existing:
            raise ValueError(f"Favorite '{name}' already exists")

        favorite = Favorite(
            id=self._generate_id(),
            name=name.strip(),
            expression=expression,
            layer_id=layer_id,
            description=description,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self._repository.save(favorite)
        logger.info(f"Favorite '{name}' created")

        return favorite

    def apply_favorite(self, favorite: Favorite) -> bool:
        """
        Mark a favorite as recently used and prepare for application.

        Args:
            favorite: Favorite to apply

        Returns:
            True if successful
        """
        # Update last used timestamp
        favorite = favorite._replace(
            last_used=datetime.now(),
            use_count=favorite.use_count + 1
        )
        self._repository.save(favorite)

        return True

    def remove_favorite(self, favorite_id: str) -> bool:
        """
        Remove a favorite by ID.

        Args:
            favorite_id: ID of favorite to remove

        Returns:
            True if removed, False if not found
        """
        return self._repository.delete(favorite_id)

    def update_favorite(
        self,
        favorite_id: str,
        **kwargs
    ) -> Optional[Favorite]:
        """
        Update favorite properties.

        Args:
            favorite_id: ID of favorite to update
            **kwargs: Properties to update

        Returns:
            Updated Favorite or None if not found
        """
        favorite = self._repository.get_by_id(favorite_id)
        if not favorite:
            return None

        # Update allowed fields
        allowed_fields = {'name', 'expression', 'description', 'layer_id'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        updates['updated_at'] = datetime.now()

        updated = favorite._replace(**updates)
        self._repository.save(updated)

        return updated

    def get_favorites_for_layer(
        self,
        layer_id: str
    ) -> List[Favorite]:
        """
        Get favorites associated with a layer.

        Args:
            layer_id: Layer ID

        Returns:
            List of favorites for the layer
        """
        return self._repository.get_by_layer_id(layer_id)

    def get_all_favorites(self) -> List[Favorite]:
        """Get all favorites."""
        return self._repository.get_all()

    def search_favorites(self, query: str) -> List[Favorite]:
        """
        Search favorites by name or expression.

        Args:
            query: Search query

        Returns:
            Matching favorites
        """
        if not query:
            return self.get_all_favorites()

        query_lower = query.lower()
        all_favorites = self.get_all_favorites()

        return [
            f for f in all_favorites
            if query_lower in f.name.lower()
            or query_lower in f.expression.lower()
        ]

    def export_favorites(self, path: str) -> bool:
        """
        Export all favorites to JSON file.

        Args:
            path: File path to export to

        Returns:
            True if successful
        """
        favorites = self.get_all_favorites()

        data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'favorites': [f.to_dict() for f in favorites]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(favorites)} favorites to {path}")
        return True

    def import_favorites(
        self,
        path: str,
        merge: bool = True
    ) -> int:
        """
        Import favorites from JSON file.

        Args:
            path: File path to import from
            merge: If True, merge with existing; if False, replace

        Returns:
            Number of favorites imported
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not merge:
            # Clear existing favorites
            for fav in self.get_all_favorites():
                self._repository.delete(fav.id)

        imported = 0
        for fav_data in data.get('favorites', []):
            try:
                favorite = Favorite.from_dict(fav_data)
                # Generate new ID to avoid conflicts
                favorite = favorite._replace(id=self._generate_id())
                self._repository.save(favorite)
                imported += 1
            except Exception as e:
                logger.warning(f"Failed to import favorite: {e}")

        logger.info(f"Imported {imported} favorites from {path}")
        return imported

    def _generate_id(self) -> str:
        """Generate a unique favorite ID."""
        import uuid
        return str(uuid.uuid4())
```

---

## 🔗 Dépendances

### Entrée

- MIG-012: FilterService (pattern à suivre)
- `core/domain/entities.py` (Favorite entity)

### Sortie

- MIG-072: FavoritesController (utilise ce service)
- MIG-081: FavoritesManagerDialog (utilise ce service)
- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                | Avant       | Après        |
| ----------------------- | ----------- | ------------ |
| Logique dans dockwidget | ~400 lignes | 0            |
| Nouveau fichier         | -           | < 250 lignes |
| Testabilité             | Faible      | 100%         |

---

## 🧪 Scénarios de Test

### Test 1: Add Favorite

```python
def test_add_favorite():
    """Ajouter un favori doit le sauvegarder."""
    mock_repo = Mock()
    mock_repo.get_by_name.return_value = None
    service = FavoritesService(mock_repo)

    result = service.add_favorite("My Filter", "population > 1000")

    assert result.name == "My Filter"
    assert result.expression == "population > 1000"
    mock_repo.save.assert_called_once()
```

### Test 2: Add Duplicate Name Raises Error

```python
def test_add_duplicate_raises():
    """Ajouter un nom dupliqué doit lever une erreur."""
    mock_repo = Mock()
    mock_repo.get_by_name.return_value = Mock()  # Existing
    service = FavoritesService(mock_repo)

    with pytest.raises(ValueError, match="already exists"):
        service.add_favorite("Existing", "id = 1")
```

### Test 3: Search Favorites

```python
def test_search_favorites():
    """La recherche doit filtrer par nom et expression."""
    mock_repo = Mock()
    mock_repo.get_all.return_value = [
        Favorite(id='1', name='Population Filter', expression='pop > 100'),
        Favorite(id='2', name='Area Check', expression='area > 500'),
    ]
    service = FavoritesService(mock_repo)

    results = service.search_favorites("pop")

    assert len(results) == 1
    assert results[0].name == "Population Filter"
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `core/services/favorites_service.py`
- [ ] Créer/vérifier `core/domain/entities.py` contient `Favorite`
- [ ] Créer/vérifier `core/ports/favorites_repository.py` existe
- [ ] Implémenter `FavoritesService`
- [ ] Ajouter export dans `core/services/__init__.py`
- [ ] Créer fichier de test
- [ ] Vérifier pas de dépendances QGIS directes

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
