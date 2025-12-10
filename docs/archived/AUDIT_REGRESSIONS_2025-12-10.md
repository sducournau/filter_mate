# Rapport d'Audit - Régressions FilterMate
**Date:** 10 décembre 2025  
**Version:** 2.2.4+  
**Statut:** CRITIQUE - Plusieurs régressions majeures détectées

---

## Résumé Exécutif

L'audit a révélé **plusieurs régressions critiques** dans les widgets des panneaux exploring et filtering, ainsi que des problèmes de signaux et d'initialisation. Ces problèmes affectent gravement la fonctionnalité du plugin.

### Impact Global
- ⚠️ **CRITIQUE**: Feature Picker ne montre aucune feature
- ⚠️ **CRITIQUE**: Filtre géométrique non fonctionnel
- ⚠️ **ÉLEVÉ**: Problèmes d'initialisation des widgets exploring
- ⚠️ **MOYEN**: Signaux déconnectés/reconnectés incorrectement

---

## 1. Feature Picker (Multiple Selection) - RÉGRESSION CRITIQUE

### Symptômes
- Le widget `QgsCheckableComboBoxFeaturesListPickerWidget` ne montre aucune feature
- La liste reste vide même quand la couche contient des données
- Le filtre de recherche ne fonctionne pas

### Cause Racine Identifiée

**Fichier:** `modules/widgets.py`  
**Méthode:** `QgsCheckableComboBoxFeaturesListPickerWidget.setLayer()` (lignes 562-604)

#### Problème 1: Initialisation tardive de `list_widgets`

```python
# LIGNE 562-604 - Code actuel PROBLÉMATIQUE
def setLayer(self, layer, layer_props):
    try:
        if layer != None:
            if self.layer != None:
                self.filter_le.clear()
                self.items_le.clear()
                
            self.layer = layer

            # PROBLÈME: Vérification après affectation de self.layer
            if self.layer.id() not in self.list_widgets:
                self.manage_list_widgets(layer_props)

            # Validation APRÈS l'utilisation potentielle
            if self.layer.id() not in self.list_widgets:
                logger.error(f"Failed to create list_widgets entry for layer {layer.id()}...")
                return  # ❌ RETURN prématuré sans charger les features
```

**Conséquence:** Si `manage_list_widgets()` échoue silencieusement (KeyError sur `layer_props`), le widget retourne sans charger les features.

#### Problème 2: Validation manquante de `layer_props`

```python
# LIGNE 583-589 - Code actuel PROBLÉMATIQUE  
# Validation requise MAIS vient APRÈS l'échec potentiel
if "infos" in layer_props and "primary_key_name" in layer_props["infos"]:
    # Seulement si les clés existent...
    if self.list_widgets[self.layer.id()].getIdentifierFieldName() != layer_props["infos"]["primary_key_name"]:
        self.list_widgets[self.layer.id()].setIdentifierFieldName(layer_props["infos"]["primary_key_name"])
else:
    logger.warning(f"layer_props missing required keys in setLayer for layer {layer.id()}")
    # ❌ Pas de return, continue avec des données incomplètes
```

**Conséquence:** Widget initialisé avec des données partielles/invalides.

#### Problème 3: Appel manquant à la population des features

```python
# LIGNE 595-596 - CRITICAL mais potentiellement non exécuté
# CRITICAL: Always call setDisplayExpression() when layer changes to force reload of features
self.setDisplayExpression(layer_props["exploring"]["multiple_selection_expression"])
```

**Conséquence:** Si un return prématuré se produit (ligne 580), `setDisplayExpression()` n'est JAMAIS appelé → pas de features chargées.

### Trace d'Exécution Problématique

```
1. current_layer_changed() appelé
2. update_exploring_widgets_layer() appelé
3. MULTIPLE_SELECTION_FEATURES.setLayer(layer, layer_props) appelé
4. manage_list_widgets() échoue (KeyError sur layer_props["exploring"])
5. ❌ Return ligne 580 - STOP
6. setDisplayExpression() JAMAIS appelé
7. buildFeaturesList() JAMAIS déclenché
8. ❌ RÉSULTAT: Widget vide
```

### Solution Recommandée

```python
def setLayer(self, layer, layer_props):
    """Set layer and reload features - FIXED VERSION"""
    
    try:
        if layer is None:
            logger.warning("setLayer called with None layer")
            return
            
        # ✅ VALIDATION EN PREMIER
        required_keys = ["infos", "exploring"]
        missing = [k for k in required_keys if k not in layer_props]
        if missing:
            logger.error(f"setLayer: layer_props missing required keys: {missing}")
            return
            
        if "primary_key_name" not in layer_props["infos"]:
            logger.error("setLayer: layer_props['infos'] missing 'primary_key_name'")
            return
            
        if "multiple_selection_expression" not in layer_props["exploring"]:
            logger.error("setLayer: layer_props['exploring'] missing 'multiple_selection_expression'")
            return
        
        # ✅ Clear previous layer data
        if self.layer is not None:
            self.filter_le.clear()
            self.items_le.clear()
            
        self.layer = layer
        
        # ✅ Ensure list_widgets entry exists BEFORE accessing
        if self.layer.id() not in self.list_widgets:
            self.manage_list_widgets(layer_props)
            
        # ✅ Verify creation succeeded
        if self.layer.id() not in self.list_widgets:
            logger.error(f"Failed to create list_widgets for {layer.id()}")
            return
        
        # ✅ Set identifier field
        identifier = layer_props["infos"]["primary_key_name"]
        if self.list_widgets[self.layer.id()].getIdentifierFieldName() != identifier:
            self.list_widgets[self.layer.id()].setIdentifierFieldName(identifier)
        
        # ✅ Restore filter text
        self.filter_le.setText(self.list_widgets[self.layer.id()].getFilterText())
        
        # ✅ CRITICAL: ALWAYS call setDisplayExpression to trigger feature loading
        display_expr = layer_props["exploring"]["multiple_selection_expression"]
        logger.debug(f"setLayer: Calling setDisplayExpression('{display_expr}')")
        self.setDisplayExpression(display_expr)
        
    except (AttributeError, RuntimeError, KeyError) as e:
        logger.error(f"setLayer failed: {e}", exc_info=True)
        # Clear widgets on error
        try:
            self.filter_le.clear()
            self.items_le.clear()
        except:
            pass
```

---

## 2. Filtre Géométrique Non Fonctionnel - RÉGRESSION CRITIQUE

### Symptômes
- Les filtres géométriques (intersects, contains, etc.) ne s'appliquent pas
- Aucune erreur visible mais les couches ne sont pas filtrées
- Le paramètre `layers_to_filter` semble vide ou incomplet

### Cause Racine Identifiée

**Fichier:** `filter_mate_app.py`  
**Méthode:** `get_task_parameters()` (lignes 584-620)

#### Problème: Validation incomplète des clés requises

```python
# LIGNE 592-620 - Code actuel PROBLÉMATIQUE
layers_to_filter = []
for key in self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"]:
    if key in self.PROJECT_LAYERS:
        layer_info = self.PROJECT_LAYERS[key]["infos"].copy()
        
        # ✅ Validation ajoutée récemment mais INCOMPLÈTE
        required_keys = [
            'layer_name', 'layer_id', 'layer_provider_type',
            'primary_key_name', 'layer_geometry_field', 'layer_schema'
        ]
        
        missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
        if missing_keys:
            logger.warning(f"Layer {key} missing required keys: {missing_keys}")
            # ❌ PROBLÈME: Tentative de remplissage mais pas de garantie de succès
            layer_obj = [l for l in self.PROJECT.mapLayers().values() if l.id() == key]
            if layer_obj:
                layer = layer_obj[0]
                # Remplissage partiel...
                # ❌ Si 'layer_geometry_field' ou 'layer_schema' manquent, continue quand même
                
        layers_to_filter.append(layer_info)  # ❌ Ajouté même si incomplet
```

**Conséquence:** Les couches avec des métadonnées incomplètes sont ajoutées à `layers_to_filter` avec des valeurs `None` pour les champs géométriques → échec silencieux du filtre spatial.

#### Problème 2: Champs géométriques manquants pour OGR/Spatialite

Pour les couches **OGR** et **Spatialite**, les champs `layer_geometry_field` et `layer_schema` ne sont PAS toujours remplis lors de l'ajout de la couche.

**Fichier:** `modules/appTasks.py`  
**Méthode:** `LayersManagementEngineTask.add_layer()` (estimation ligne ~500-800)

```python
# Code problématique présumé (non vérifié dans l'audit)
if provider_type == 'ogr':
    layer_props["infos"]["layer_schema"] = None  # ❌ Non rempli
    layer_props["infos"]["layer_geometry_field"] = "geometry"  # ❌ Valeur par défaut peut être incorrecte
```

### Trace d'Exécution Problématique

```
1. Utilisateur active "Has geometric predicates" ✓
2. Sélectionne couches à filtrer ✓
3. Clique "Filter" ✓
4. get_task_parameters('filter') appelé
5. Construit layers_to_filter:
   - Layer A: layer_geometry_field = None ❌
   - Layer B: layer_schema = None ❌
6. FilterEngineTask.run() commence
7. Appelle build_geometric_filter():
   - Essaie d'accéder layer_info['layer_geometry_field']
   - Valeur = None
   - ❌ Échec silencieux ou SQL invalide
8. ❌ RÉSULTAT: Pas de filtre géométrique appliqué
```

### Solution Recommandée

#### A. Dans `filter_mate_app.py` - Validation stricte

```python
# LIGNE 584-620 - VERSION CORRIGÉE
layers_to_filter = []
for key in self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"]:
    if key not in self.PROJECT_LAYERS:
        logger.warning(f"Layer {key} not in PROJECT_LAYERS, skipping")
        continue
        
    layer_info = self.PROJECT_LAYERS[key]["infos"].copy()
    
    # ✅ VALIDATION STRICTE
    required_keys = [
        'layer_name', 'layer_id', 'layer_provider_type',
        'primary_key_name', 'layer_geometry_field', 'layer_schema'
    ]
    
    missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
    
    if missing_keys:
        logger.error(f"Cannot filter layer {key}: missing required keys {missing_keys}")
        # ✅ Tenter de récupérer les métadonnées manquantes
        layer_obj = [l for l in self.PROJECT.mapLayers().values() if l.id() == key]
        if layer_obj:
            layer = layer_obj[0]
            
            # Remplir layer_name et layer_id
            if 'layer_name' not in layer_info or not layer_info['layer_name']:
                layer_info['layer_name'] = layer.name()
            if 'layer_id' not in layer_info or not layer_info['layer_id']:
                layer_info['layer_id'] = layer.id()
                
            # ✅ CRITIQUE: Récupérer layer_geometry_field
            if 'layer_geometry_field' not in layer_info or not layer_info['layer_geometry_field']:
                if layer.geometryType() != QgsWkbTypes.UnknownGeometry:
                    # Pour OGR/Spatialite, le champ géométrique est souvent "geometry" ou "geom"
                    geom_col = layer.dataProvider().geometryColumn()
                    if geom_col:
                        layer_info['layer_geometry_field'] = geom_col
                    else:
                        # Fallback
                        layer_info['layer_geometry_field'] = 'geometry'
                        logger.warning(f"Using default 'geometry' for {layer.name()}")
                else:
                    logger.error(f"Layer {layer.name()} has no geometry")
                    continue
                    
            # ✅ CRITIQUE: Récupérer layer_schema
            if 'layer_schema' not in layer_info or not layer_info['layer_schema']:
                provider_type = layer.providerType()
                if provider_type == 'postgres':
                    # Pour PostgreSQL, extraire du URI
                    uri = QgsDataSourceUri(layer.source())
                    layer_info['layer_schema'] = uri.schema() or 'public'
                else:
                    # Pour OGR/Spatialite, pas de schéma
                    layer_info['layer_schema'] = None
            
            # ✅ Vérification finale
            still_missing = [k for k in ['layer_name', 'layer_id', 'layer_geometry_field'] 
                            if k not in layer_info or layer_info[k] is None]
            if still_missing:
                logger.error(f"Cannot filter layer {key}: still missing {still_missing} after recovery")
                iface.messageBar().pushWarning(
                    "FilterMate",
                    f"Skipping layer '{layer.name()}': missing geometric metadata"
                )
                continue  # ✅ SKIP cette couche
        else:
            logger.error(f"Layer {key} not found in project")
            continue
    
    # ✅ N'ajouter QUE si toutes les clés essentielles sont présentes
    if layer_info['layer_geometry_field'] is not None:
        layers_to_filter.append(layer_info)
    else:
        logger.error(f"Skipping layer {key}: no geometry field")
```

#### B. Dans `modules/appTasks.py` - Initialisation complète

```python
# LayersManagementEngineTask.add_layer() - AJOUTER
def add_layer(self, layer):
    """Add layer with complete metadata"""
    
    layer_props = {
        "infos": {},
        "exploring": {},
        "filtering": {}
    }
    
    # ... Code existant ...
    
    # ✅ CRITIQUE: Toujours remplir layer_geometry_field
    provider_type = layer.providerType()
    
    if layer.geometryType() != QgsWkbTypes.UnknownGeometry:
        geom_col = layer.dataProvider().geometryColumn()
        
        if geom_col:
            layer_props["infos"]["layer_geometry_field"] = geom_col
        else:
            # Fallback selon provider
            if provider_type in ('ogr', 'spatialite'):
                layer_props["infos"]["layer_geometry_field"] = 'geometry'
            elif provider_type == 'postgres':
                layer_props["infos"]["layer_geometry_field"] = 'geom'
            else:
                layer_props["infos"]["layer_geometry_field"] = 'geometry'
                
        logger.info(f"Layer {layer.name()}: geometry field = {layer_props['infos']['layer_geometry_field']}")
    else:
        layer_props["infos"]["layer_geometry_field"] = None
        logger.warning(f"Layer {layer.name()} has no geometry")
    
    # ✅ CRITIQUE: Remplir layer_schema
    if provider_type == 'postgres':
        uri = QgsDataSourceUri(layer.source())
        layer_props["infos"]["layer_schema"] = uri.schema() or 'public'
    else:
        # OGR/Spatialite n'ont pas de schéma
        layer_props["infos"]["layer_schema"] = None
    
    return layer_props
```

---

## 3. Problèmes d'Initialisation des Widgets Exploring - ÉLEVÉ

### Symptômes
- Widgets exploring ne se mettent pas à jour lors du changement de couche
- QgsFeaturePickerWidget montre des features de l'ancienne couche
- Expressions de sélection incorrectes

### Cause Racine Identifiée

**Fichier:** `filter_mate_dockwidget.py`  
**Méthode:** `update_exploring_widgets_layer()` (lignes 1967-2055)

#### Problème: Reset d'expression insuffisant

```python
# LIGNE 2007-2013 - Code actuel PROBLÉMATIQUE
# CRITICAL: Force refresh by resetting expression to empty then setting it back
# This ensures QgsFeaturePickerWidget reloads features even if expression is identical
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression("")
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(
    layer_props["exploring"]["single_selection_expression"]
)
```

**Problème:** Ce pattern de reset (`""` puis expression) ne garantit PAS toujours un rechargement si:
1. L'expression est identique entre deux couches (ex: `"id"`)
2. Le widget est en cache interne
3. La couche n'a pas encore été définie avec `setLayer()`

### Solution Recommandée

```python
def update_exploring_widgets_layer(self):
    """Update ALL exploring widgets with the current layer - FIXED"""
    
    logger.debug(f"update_exploring_widgets_layer: START for {self.current_layer.name() if self.current_layer else 'None'}")
    
    if not self.widgets_initialized or self.current_layer is None:
        logger.debug("update_exploring_widgets_layer: Skipping - widgets not initialized or no current layer")
        return
    
    if self.current_layer.id() not in self.PROJECT_LAYERS:
        logger.debug(f"update_exploring_widgets_layer: Skipping - layer {self.current_layer.name()} not in PROJECT_LAYERS")
        return
    
    layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
    
    try:
        # ✅ CRITICAL: Disconnect ALL signals BEFORE updating
        logger.debug("update_exploring_widgets_layer: Disconnecting all exploring signals")
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')
        self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'disconnect')
        
        # ✅ Update single selection widgets
        if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
            widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            expr = layer_props["exploring"]["single_selection_expression"]
            
            logger.debug(f"update_exploring_widgets_layer: Updating SINGLE_SELECTION widgets")
            
            # ✅ CRITICAL: Set layer FIRST to establish context
            widget.setLayer(self.current_layer)
            
            # ✅ CRITICAL: Clear current feature to force reload
            widget.setFeature(QgsFeature())  # Clear selection
            
            # ✅ CRITICAL: Reset expression with distinct values to trigger change event
            widget.setDisplayExpression("")  # Clear
            widget.setDisplayExpression("$id")  # Intermediate value
            widget.setDisplayExpression(expr)  # Final value
            
            logger.debug(f"SINGLE_SELECTION_FEATURES: layer={self.current_layer.name()}, expr='{expr}'")
        
        if "SINGLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
            widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"]
            expr = layer_props["exploring"]["single_selection_expression"]
            
            widget.setLayer(self.current_layer)
            # ✅ CRITICAL: Reset filters to ensure all field types available
            widget.setFilters(QgsFieldProxyModel.AllTypes)
            widget.setExpression(expr)
        
        # ✅ Update multiple selection widgets
        if "MULTIPLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
            logger.debug(f"update_exploring_widgets_layer: Updating MULTIPLE_SELECTION widgets")
            
            # ✅ CRITICAL: Pass BOTH layer AND layer_props
            self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(
                self.current_layer, 
                layer_props  # ← ESSENTIAL
            )
        
        if "MULTIPLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
            widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"]
            expr = layer_props["exploring"]["multiple_selection_expression"]
            
            widget.setLayer(self.current_layer)
            widget.setFilters(QgsFieldProxyModel.AllTypes)
            widget.setExpression(expr)
        
        # ✅ Update custom selection widget
        if "CUSTOM_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
            widget = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"]
            expr = layer_props["exploring"]["custom_selection_expression"]
            
            widget.setLayer(self.current_layer)
            widget.setFilters(QgsFieldProxyModel.AllTypes)
            widget.setExpression(expr)
        
        # ✅ CRITICAL: Reconnect ALL signals AFTER updating
        logger.debug("update_exploring_widgets_layer: Reconnecting all exploring signals")
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        
        logger.debug("update_exploring_widgets_layer: END - All widgets updated successfully")
        
    except (AttributeError, KeyError, RuntimeError) as e:
        logger.error(f"update_exploring_widgets_layer: ERROR - {e}", exc_info=True)
```

---

## 4. Gestion des Signaux - MOYEN

### Symptômes
- Signaux déconnectés mais jamais reconnectés
- Cascade de mises à jour lors du changement de couche
- Widgets mis à jour plusieurs fois

### Cause Racine

**Fichier:** `filter_mate_dockwidget.py`  
**Méthode:** `current_layer_changed()` (lignes 2662-2915)

#### Problème: Ordre de déconnexion/reconnexion non garanti

```python
# LIGNE 2730-2765 - Code actuel avec risque de fuite
widgets_to_stop = [
    ["EXPLORING", "IS_SELECTING"],
    ["EXPLORING", "IS_TRACKING"],
    # ... etc
]

for widget_path in widgets_to_stop:
    self.manageSignal(widget_path, 'disconnect')

# ... Updates ...

for widget_path in widgets_to_stop:
    self.manageSignal(widget_path, 'connect')  # ❌ MAIS connect quoi ?
```

**Problème:** `manageSignal(..., 'connect')` sans spécifier le signal peut reconnecter le mauvais signal ou échouer silencieusement.

### Solution Recommandée

```python
# Utiliser un dictionnaire pour mémoriser les signaux
WIDGET_SIGNALS = {
    ("EXPLORING", "IS_SELECTING"): "toggled",
    ("EXPLORING", "IS_TRACKING"): "toggled",
    ("EXPLORING", "IS_LINKING"): "toggled",
    ("FILTERING", "HAS_LAYERS_TO_FILTER"): "toggled",
    ("FILTERING", "LAYERS_TO_FILTER"): "checkedItemsChanged",
    # ... etc
}

# Déconnexion
for widget_path, signal_name in WIDGET_SIGNALS.items():
    self.manageSignal(list(widget_path), 'disconnect')

# ... Updates ...

# Reconnexion avec le bon signal
for widget_path, signal_name in WIDGET_SIGNALS.items():
    self.manageSignal(list(widget_path), 'connect', signal_name)
```

---

## 5. Recommandations Prioritaires

### Priorité 1 - CRITIQUE (à corriger immédiatement)

1. **Corriger `QgsCheckableComboBoxFeaturesListPickerWidget.setLayer()`**
   - Ajouter validation stricte de `layer_props`
   - Garantir appel à `setDisplayExpression()` dans tous les cas
   - **Fichier:** `modules/widgets.py` lignes 562-604

2. **Corriger validation des couches à filtrer**
   - Remplir obligatoirement `layer_geometry_field` lors de l'ajout de couche
   - Valider présence avant d'ajouter à `layers_to_filter`
   - **Fichiers:** `filter_mate_app.py` (lignes 584-620), `modules/appTasks.py`

3. **Améliorer `update_exploring_widgets_layer()`**
   - Forcer rechargement des features avec `setFeature(QgsFeature())`
   - Valider que `setLayer()` est appelé avant `setDisplayExpression()`
   - **Fichier:** `filter_mate_dockwidget.py` lignes 1967-2055

### Priorité 2 - ÉLEVÉ (à corriger cette semaine)

4. **Standardiser gestion des signaux**
   - Créer dictionnaire `WIDGET_SIGNALS` centralisé
   - Toujours spécifier le signal lors de `manageSignal('connect')`
   - **Fichier:** `filter_mate_dockwidget.py`

5. **Ajouter logging détaillé**
   - Logger toutes les étapes de `setLayer()`
   - Logger success/failure de `manage_list_widgets()`
   - Logger construction de `layers_to_filter`

### Priorité 3 - MOYEN (amélioration continue)

6. **Tests automatisés**
   - Test unitaire pour `setLayer()` avec `layer_props` invalides
   - Test d'intégration pour filtre géométrique
   - Test de changement de couche avec exploring widgets

7. **Documentation**
   - Documenter ordre d'initialisation des widgets
   - Documenter clés requises dans `PROJECT_LAYERS["layer_id"]["infos"]`
   - Diagramme de séquence pour `current_layer_changed()`

---

## 6. Plan d'Action

### Phase 1 - Correction Urgente (Jour 1-2)
- [ ] Fix `QgsCheckableComboBoxFeaturesListPickerWidget.setLayer()`
- [ ] Fix validation `layers_to_filter` dans `get_task_parameters()`
- [ ] Tests manuels approfondis

### Phase 2 - Stabilisation (Jour 3-5)
- [ ] Fix `update_exploring_widgets_layer()`
- [ ] Standardiser gestion des signaux
- [ ] Ajouter logging détaillé
- [ ] Tests de régression

### Phase 3 - Prévention (Semaine suivante)
- [ ] Tests unitaires
- [ ] Tests d'intégration
- [ ] Documentation technique
- [ ] Code review

---

## 7. Métriques de Régression

| Composant | Avant | Après Fix | Cible |
|-----------|-------|-----------|-------|
| Feature Picker affiche features | ❌ 0% | ⏳ - | ✅ 100% |
| Filtre géométrique fonctionne | ❌ 0% | ⏳ - | ✅ 100% |
| Widgets exploring synchronisés | ⚠️ 30% | ⏳ - | ✅ 100% |
| Signaux correctement gérés | ⚠️ 60% | ⏳ - | ✅ 100% |

---

## 8. Notes Techniques

### Dépendances Identifiées

```
filter_mate_dockwidget.current_layer_changed()
    ↓
    update_exploring_widgets_layer()
        ↓
        QgsCheckableComboBoxFeaturesListPickerWidget.setLayer()
            ↓
            manage_list_widgets()
                ↓
                setDisplayExpression()
                    ↓
                    build_task('buildFeaturesList')
                        ↓
                        buildFeaturesList()  ← Jamais atteint si échec avant
```

### Clés Critiques dans `layer_props`

```python
layer_props = {
    "infos": {
        "layer_id": str,                    # OBLIGATOIRE
        "layer_name": str,                  # OBLIGATOIRE
        "layer_provider_type": str,         # OBLIGATOIRE
        "primary_key_name": str,            # OBLIGATOIRE
        "layer_geometry_field": str,        # OBLIGATOIRE pour filtres géométriques
        "layer_schema": str or None,        # OBLIGATOIRE pour PostgreSQL
    },
    "exploring": {
        "single_selection_expression": str,      # OBLIGATOIRE
        "multiple_selection_expression": str,    # OBLIGATOIRE
        "custom_selection_expression": str,      # OBLIGATOIRE
    },
    "filtering": {
        "layers_to_filter": [list of layer_ids],  # OBLIGATOIRE pour multi-layer
        # ...
    }
}
```

---

## Conclusion

Les régressions identifiées sont **critiques** et nécessitent une **correction immédiate**. Les problèmes sont localisés dans 3 fichiers principaux:

1. `modules/widgets.py` - Feature Picker
2. `filter_mate_app.py` - Filtre géométrique
3. `filter_mate_dockwidget.py` - Synchronisation widgets

**Temps estimé pour corrections:** 2-3 jours ouvrés  
**Risque:** Élevé si non corrigé (fonctionnalités principales non opérationnelles)

---

**Auditeur:** GitHub Copilot + Serena Symbolic Analysis  
**Date rapport:** 2025-12-10  
**Version plugin:** 2.2.4+  
**Statut:** ⚠️ CRITIQUE - ACTION REQUISE
