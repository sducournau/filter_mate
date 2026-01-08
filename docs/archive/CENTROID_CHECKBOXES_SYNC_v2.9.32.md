# Configuration des Checkboxes Centroid - v2.9.32

## 📋 Résumé

Les checkboxes de centroïdes sont **désactivées par défaut** et correctement synchronisées avec la base SQLite et PROJECT_LAYERS.

## ✅ Vérifications Effectuées

### 1. Valeurs Par Défaut (Template JSON)

**Fichier** : `modules/tasks/layer_management_task.py` ligne 181

```json
{
  "use_centroids_source_layer": false,
  "use_centroids_distant_layers": false
}
```

✅ **CONFIRMÉ** : Les deux checkboxes sont à `false` par défaut lors de l'initialisation d'un nouveau layer.

### 2. Interface Utilisateur (UI)

#### Checkbox Source Layer
**Fichier** : `filter_mate_dockwidget_base.ui` ligne 2237
**Fichier** : `filter_mate_dockwidget_base.py` ligne 931

```xml
<property name="checked">
  <bool>false</bool>
</property>
```

```python
self.checkBox_filtering_use_centroids_source_layer.setChecked(False)
```

✅ **CONFIRMÉ** : Checkbox source layer désactivée par défaut dans l'UI.

#### Checkbox Distant Layers
**Fichier** : `filter_mate_dockwidget.py` ligne 4872

```python
self.checkBox_filtering_use_centroids_distant_layers.setChecked(False)
```

✅ **CONFIRMÉ** : Checkbox distant layers désactivée par défaut (créée programmatiquement).

### 3. Synchronisation avec Base SQLite

#### Sauvegarde
**Fichier** : `filter_mate_app.py` ligne 4536-4543

```python
cursor.execute(
    """INSERT INTO fm_project_layers_properties 
       VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
    (str(uuid.uuid4()), str(self.project_uuid), layer_id, 
     key_group, key, str(value_typped))
)
```

✅ **CONFIRMÉ** : Les valeurs des checkboxes sont sauvegardées dans `fm_project_layers_properties`.

#### Chargement
**Fichier** : `modules/tasks/layer_management_task.py` ligne 1545-1548

```python
cur.execute(
    """SELECT meta_type, meta_key, meta_value FROM fm_project_layers_properties  
       WHERE fk_project = ? and layer_id = ?""",
    (str(self.project_uuid), layer_id)
)
```

✅ **CONFIRMÉ** : Les propriétés sont restaurées depuis la base SQLite.

#### Synchronisation Widgets
**Fichier** : `filter_mate_dockwidget.py` ligne 9593-9605

```python
elif widget_type == 'CheckBox':
    widget = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"]
    stored_value = layer_props[property_tuple[0]][property_tuple[1]]
    
    # VERIFICATION v2.9.32: Log centroid checkbox synchronization
    if property_tuple[1] in ('use_centroids_source_layer', 'use_centroids_distant_layers'):
        logger.debug(f"🔍 Synchronizing {property_tuple[1]} checkbox: stored_value={stored_value}")
    
    widget.blockSignals(True)
    widget.setChecked(stored_value)
    widget.blockSignals(False)
```

✅ **CONFIRMÉ** : Les checkboxes sont synchronisées avec les valeurs stockées dans PROJECT_LAYERS.

### 4. Logs de Vérification (v2.9.32)

Deux nouveaux logs de debug ont été ajoutés pour vérifier le comportement :

#### A) Lors de la création d'un nouveau layer
```python
logger.debug(f"🔍 Default centroid values for new layer {layer.name()}: "
            f"use_centroids_source_layer={new_layer_variables['filtering']['use_centroids_source_layer']}, "
            f"use_centroids_distant_layers={new_layer_variables['filtering']['use_centroids_distant_layers']}")
```

**Résultat attendu** : `use_centroids_source_layer=False, use_centroids_distant_layers=False`

#### B) Lors de la synchronisation des widgets
```python
logger.debug(f"🔍 Synchronizing {property_tuple[1]} checkbox: stored_value={stored_value}, "
            f"current_checked={widget.isChecked()} for layer {layer.name()}")
```

**Résultat attendu** : `stored_value=False, current_checked=False` (sauf si l'utilisateur a activé l'option)

## 🔄 Flux de Données

```
┌─────────────────────────────────────────────────────────────┐
│ 1. NOUVEAU LAYER                                             │
│    └─> Template JSON (False) → PROJECT_LAYERS → SQLite      │
└─────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. CHANGEMENT DE LAYER                                       │
│    └─> SQLite → PROJECT_LAYERS → _synchronize_layer_widgets │
└─────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. MODIFICATION UTILISATEUR                                  │
│    └─> Checkbox UI → layer_property_changed → SQLite        │
└─────────────────────────────────────────────────────────────┘
```

## 🧪 Test de Vérification

### Scénario 1 : Nouveau Projet
1. Créer un nouveau projet QGIS
2. Ajouter une couche vecteur
3. **Résultat attendu** : Les deux checkboxes centroids sont décochées

### Scénario 2 : Changement de Layer
1. Sélectionner layer A
2. Activer une checkbox centroid
3. Changer vers layer B (nouveau)
4. **Résultat attendu** : Checkboxes décochées pour layer B
5. Revenir à layer A
6. **Résultat attendu** : Checkbox cochée (état sauvegardé)

### Scénario 3 : Réouverture du Projet
1. Activer checkbox centroid pour un layer
2. Sauvegarder et fermer le projet
3. Rouvrir le projet
4. **Résultat attendu** : Checkbox toujours cochée (restaurée depuis SQLite)

## 📊 Traçabilité

| Composant | Fichier | Ligne | État |
|-----------|---------|-------|------|
| Template JSON | `layer_management_task.py` | 181 | ✅ False |
| UI Source Checkbox | `filter_mate_dockwidget_base.ui` | 2237 | ✅ False |
| Prog. Distant Checkbox | `filter_mate_dockwidget.py` | 4872 | ✅ False |
| Sauvegarde SQLite | `filter_mate_app.py` | 4536 | ✅ Fonctionnel |
| Chargement SQLite | `layer_management_task.py` | 1545 | ✅ Fonctionnel |
| Synchronisation Widgets | `filter_mate_dockwidget.py` | 9593 | ✅ Fonctionnel |

## 🎯 Conclusion

✅ **Toutes les vérifications confirment** que les checkboxes centroids sont :
- Désactivées par défaut (`false`)
- Correctement synchronisées avec PROJECT_LAYERS
- Persistées dans la base SQLite
- Restaurées correctement au changement de layer

Les logs de debug v2.9.32 permettent de tracer et vérifier le comportement en temps réel.

## 🔗 Références

- Issue : "les checkboxes centroids doivent être désactivées par défaut et synchroniser les paramètres avec la base sqlite des projets et des propriétés des layers"
- Version : FilterMate v2.9.32
- Date : 2026-01-07
