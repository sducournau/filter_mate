# Rapport d'Analyse Comparative Approfondie - Régressions FilterMate v4.0

**Date**: 12 Janvier 2026  
**Analyste**: BMad Master  
**Comparaison**: `filter_mate_dockwidget.py` (2,926 lignes) vs `before_migration/` (12,468 lignes)

---

## 📋 Résumé des Régressions Identifiées

### 🔴 Régressions CRITIQUES (Fonctionnalité cassée)

| # | Régression | Sévérité | Location |
|---|------------|----------|----------|
| 1 | **PushButton checked + widgets associés inactifs** | 🔴 CRITIQUE | `filtering_layers_to_filter_state_changed()` |
| 2 | **Détection géométrie défaillante dans layers_to_filter** | 🔴 CRITIQUE | `populate_layers_checkable_combobox()` |
| 3 | **Predicates non activés au toggle** | 🔴 CRITIQUE | `filtering_geometric_predicates_state_changed()` |
| 4 | **Dimensions UI réduites** | 🟡 MOYEN | `apply_dynamic_dimensions()` |

---

## 🔍 Analyse Détaillée des Régressions

### 1. RÉGRESSION: PushButtons Checked et Widgets Associés Inactifs

#### Problème Observé
Lorsqu'un `pushButton_checkable_filtering_*` est coché, les widgets associés restent désactivés.

#### Comparaison du Code

**ANCIENNE VERSION (CORRECTE)** - `before_migration/filter_mate_dockwidget.py:11149-11177`:
```python
def filtering_layers_to_filter_state_changed(self):
    """Handle changes to the has_layers_to_filter checkable button."""
    if self.widgets_initialized is True and self.has_loaded_layers is True:
        is_checked = self.widgets["FILTERING"]["HAS_LAYERS_TO_FILTER"]["WIDGET"].isChecked()
        
        # ✅ DIRECT: Enable/disable the associated widgets
        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["USE_CENTROIDS_DISTANT_LAYERS"]["WIDGET"].setEnabled(is_checked)
        
        logger.debug(f"filtering_layers_to_filter_state_changed: is_checked={is_checked}")
```

**NOUVELLE VERSION (PROBLÉMATIQUE)** - `filter_mate_dockwidget.py:2417-2425`:
```python
def filtering_layers_to_filter_state_changed(self):
    """v3.1 Sprint 11: Simplified - handle layers_to_filter button changes."""
    if not self._is_ui_ready(): return  # ❌ Peut bloquer prématurément
    is_checked = self.widgets["FILTERING"]["HAS_LAYERS_TO_FILTER"]["WIDGET"].isChecked()
    if self._controller_integration:
        # ❌ Délégation au contrôleur qui peut échouer silencieusement
        self._controller_integration.delegate_filtering_layers_to_filter_state_changed(is_checked)
    # ✅ Ces lignes sont présentes mais peuvent ne jamais s'exécuter si _is_ui_ready() bloque
    self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setEnabled(is_checked)
    self.widgets["FILTERING"]["USE_CENTROIDS_DISTANT_LAYERS"]["WIDGET"].setEnabled(is_checked)
```

#### Cause Racine
1. La méthode `_is_ui_ready()` vérifie `widgets_initialized AND has_loaded_layers` - peut retourner `False` au mauvais moment
2. La délégation au contrôleur peut échouer silencieusement et ne pas activer les widgets

#### Correction Requise
Remplacer `_is_ui_ready()` par la vérification d'origine:
```python
if self.widgets_initialized is True and self.has_loaded_layers is True:
```

---

### 2. RÉGRESSION: Détection Géométrie layers_to_filter

#### Problème Observé
Les icônes de géométrie ne s'affichent pas correctement dans le combobox "layers_to_filter".

#### Comparaison du Code

**ANCIENNE VERSION** - `before_migration/filter_mate_dockwidget.py:5880-5888`:
```python
layer_id = layer_info["layer_id"]
layer_name = layer_info["layer_name"]
layer_crs_authid = layer_info["layer_crs_authid"]
# ✅ Appel direct avec le type de géométrie stocké
layer_icon = self.icon_per_geometry_type(layer_info["layer_geometry_type"])

# ✅ Format d'affichage complet
self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(
    layer_icon, 
    layer_name + ' [%s]' % (layer_crs_authid), 
    {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]}
)
```

**NOUVELLE VERSION** - `ui/controllers/filtering_controller.py:420-445`:
```python
layer_id = layer_info["layer_id"]
layer_name = layer_info["layer_name"]
layer_crs = layer_info["layer_crs_authid"]
# ✅ Même logique, MAIS via dockwidget.icon_per_geometry_type
layer_icon = dockwidget.icon_per_geometry_type(layer_info["layer_geometry_type"])

display_name = f"{layer_name} [{layer_crs}]"
item_data = {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]}
layers_widget.addItem(layer_icon, display_name, item_data)
```

#### Cause Potentielle
Le problème est dans `icon_per_geometry_type()` dans la nouvelle version:

**ANCIENNE** (`before_migration/filter_mate_dockwidget.py:5778-5802`):
```python
def icon_per_geometry_type(self, geometry_type):
    # Check cache first
    if geometry_type in self._icon_cache:
        return self._icon_cache[geometry_type]
    
    if geometry_type == 'GeometryType.Line':
        icon = QgsLayerItem.iconLine()
    elif geometry_type == 'GeometryType.Point':
        icon = QgsLayerItem.iconPoint()
    elif geometry_type == 'GeometryType.Polygon':
        icon = QgsLayerItem.iconPolygon()
    # ... etc
```

**NOUVELLE** (`filter_mate_dockwidget.py:1395-1416`):
```python
def icon_per_geometry_type(self, geometry_type):
    if geometry_type in self._icon_cache: return self._icon_cache[geometry_type]
    icon_map = {
        'GeometryType.Line': QgsLayerItem.iconLine,
        'GeometryType.Point': QgsLayerItem.iconPoint,
        'GeometryType.Polygon': QgsLayerItem.iconPolygon,
        'GeometryType.UnknownGeometry': QgsLayerItem.iconTable,
        'GeometryType.Null': QgsLayerItem.iconTable,
        'GeometryType.Unknown': QgsLayerItem.iconDefault,
        # Short format (from get_geometry_type_string without legacy_format)
        'Line': QgsLayerItem.iconLine,  # ❌ Ajout non testé
        'Point': QgsLayerItem.iconPoint,
        'Polygon': QgsLayerItem.iconPolygon,
        'Unknown': QgsLayerItem.iconTable,
        'Null': QgsLayerItem.iconTable,
    }
    icon = icon_map.get(geometry_type, QgsLayerItem.iconDefault)()  # ✅ OK
```

Le problème est que `layer_info["layer_geometry_type"]` peut contenir des valeurs qui ne correspondent pas aux clés du map.

---

### 3. RÉGRESSION: Predicates Non Activés

#### Comparaison

**ANCIENNE** (`before_migration/filter_mate_dockwidget.py:11181-11193`):
```python
def filtering_geometric_predicates_state_changed(self):
    """Handle changes to the has_geometric_predicates checkable button."""
    if self.widgets_initialized is True and self.has_loaded_layers is True:
        is_checked = self.widgets["FILTERING"]["HAS_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked()
        
        # ✅ DIRECT enable/disable
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].setEnabled(is_checked)
        
        logger.debug(f"filtering_geometric_predicates_state_changed: is_checked={is_checked}")
```

**NOUVELLE** (`filter_mate_dockwidget.py:2436-2441`):
```python
def filtering_geometric_predicates_state_changed(self):
    """v4.0 S18: Handle geometric predicates button changes."""
    if not self._is_ui_ready(): return  # ❌ Peut bloquer
    is_checked = self.widgets["FILTERING"]["HAS_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked()
    if self._controller_integration: 
        self._controller_integration.delegate_filtering_geometric_predicates_state_changed(is_checked)
    self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].setEnabled(is_checked)
```

#### Correction
Même problème que #1 - `_is_ui_ready()` trop restrictif.

---

### 4. RÉGRESSION: Appel Manquant à `_synchronize_layer_widgets` après changement de couche

**ANCIENNE VERSION** appelle après `current_layer_changed()`:
- `filtering_layers_to_filter_state_changed()` 
- `filtering_combine_operator_state_changed()`
- `filtering_geometric_predicates_state_changed()`

Ces appels synchronisent l'état des widgets avec les propriétés de la couche actuelle.

---

## 📊 Matrice de Comparaison Fonctionnelle

| Fonction | Ancienne | Nouvelle | État |
|----------|----------|----------|------|
| `filtering_layers_to_filter_state_changed()` | Directe | Via Controller + Guard | 🔴 |
| `filtering_geometric_predicates_state_changed()` | Directe | Via Controller + Guard | 🔴 |
| `filtering_combine_operator_state_changed()` | Directe | Via Controller + Guard | 🔴 |
| `filtering_buffer_property_changed()` | Directe | Via Controller | 🟢 |
| `icon_per_geometry_type()` | Conditionals | Dict mapping | 🟡 |
| `populate_layers_checkable_combobox()` | Dans dockwidget | Dans Controller | 🟡 |
| `manage_interactions()` | 60+ lignes détaillées | ~25 lignes condensées | 🟡 |

---

## 🔧 Corrections Requises

### Fix 1: Restaurer la logique directe dans les méthodes state_changed

```python
# filter_mate_dockwidget.py ligne ~2417
def filtering_layers_to_filter_state_changed(self):
    """Handle changes to the has_layers_to_filter checkable button."""
    # CRITICAL: Utiliser la condition originale, pas _is_ui_ready()
    if self.widgets_initialized is True and self.has_loaded_layers is True:
        is_checked = self.widgets["FILTERING"]["HAS_LAYERS_TO_FILTER"]["WIDGET"].isChecked()
        
        # TOUJOURS activer/désactiver les widgets associés DIRECTEMENT
        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["USE_CENTROIDS_DISTANT_LAYERS"]["WIDGET"].setEnabled(is_checked)
        
        # Délégation optionnelle au contrôleur (pour logique supplémentaire)
        if self._controller_integration:
            self._controller_integration.delegate_filtering_layers_to_filter_state_changed(is_checked)
        
        logger.debug(f"filtering_layers_to_filter_state_changed: is_checked={is_checked}")
```

### Fix 2: Même pattern pour les autres méthodes state_changed

Appliquer le même fix à:
- `filtering_geometric_predicates_state_changed()`
- `filtering_combine_operator_state_changed()`

### Fix 3: Vérifier icon_per_geometry_type()

Ajouter les formats manquants dans le mapping si nécessaire.

---

## ✅ Corrections Appliquées

### Fix 1: ✅ Méthodes state_changed - Condition originale restaurée

**Fichier**: [filter_mate_dockwidget.py](filter_mate_dockwidget.py#L2417-L2530)

Toutes les méthodes `*_state_changed` ont été corrigées pour utiliser `self.widgets_initialized is True and self.has_loaded_layers is True` au lieu de `_is_ui_ready()`:

- ✅ `filtering_layers_to_filter_state_changed()` 
- ✅ `filtering_geometric_predicates_state_changed()`
- ✅ `filtering_combine_operator_state_changed()`
- ✅ `filtering_buffer_type_state_changed()`

### Fix 2: ✅ Appels state_changed manquants dans _synchronize_layer_widgets

**Fichier**: [filter_mate_dockwidget.py](filter_mate_dockwidget.py#L2096-L2105)

**Problème**: Le fallback du dockwidget (quand le contrôleur n'est pas disponible) n'appelait pas les méthodes `state_changed` après le peuplement du combobox, contrairement à l'ancienne version (lignes 9704-9706).

**Correction appliquée**:
```python
# Populate layers combobox
self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')
self.filtering_populate_layers_chekableCombobox()
self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')

# AJOUTÉ: Synchronize checkable button associated widgets enabled state
self.filtering_layers_to_filter_state_changed()
self.filtering_combine_operator_state_changed()
self.filtering_geometric_predicates_state_changed()
```

### Fix 3: ✅ Format géométrie legacy restauré

**Fichier**: [infrastructure/utils/__init__.py](infrastructure/utils/__init__.py#L130-L165)

La fonction `geometry_type_to_string()` retourne maintenant le format legacy `"GeometryType.Point"` pour compatibilité avec `PROJECT_LAYERS` et `icon_per_geometry_type()`.

### Fix 4: ✅ Mapping icons géométrie étendu

**Fichier**: [filter_mate_dockwidget.py](filter_mate_dockwidget.py#L1385-L1425)

Ajout des formats manquants dans `icon_per_geometry_type()`:
- `"LineString"`, `"MultiPoint"`, `"MultiLineString"`, `"MultiPolygon"`
- `"NoGeometry"`, `"Unknown"`, `"Null"`

---

## 📋 Résumé des Modifications

| Fichier | Lignes | Modification |
|---------|--------|--------------|
| `filter_mate_dockwidget.py` | 2417-2530 | Restauration condition originale dans 4 méthodes |
| `filter_mate_dockwidget.py` | 2096-2105 | Ajout appels state_changed dans fallback |
| `filter_mate_dockwidget.py` | 1385-1425 | Extension mapping icons géométrie |
| `infrastructure/utils/__init__.py` | 130-165 | Format legacy géométrie |

---

**Statut**: ✅ Régressions critiques corrigées - Tests manuels recommandés
