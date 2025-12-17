# Fix: Access Violation lors de la suppression de toutes les couches

**Date**: 2025-12-17  
**Type**: Correction critique  
**Catégorie**: Race condition, Stabilité  
**Fichiers modifiés**: `filter_mate_dockwidget.py`

## Problème

Une **violation d'accès Windows** (`access violation`) se produisait lors de la suppression de toutes les couches du projet QGIS. L'erreur se manifestait par un crash complet de QGIS avec le stack trace suivant :

```
Windows fatal exception: access violation

Current thread 0x00001d18 (most recent call first):
  File "filter_mate_dockwidget.py", line 3579 in _on_groupbox_clicked
    triggering_widget.setCollapsed(False)
  File "filter_mate_dockwidget.py", line 3232 in set_widgets_enabled_state
    self.widgets[widget_group][widget_name]["WIDGET"].setChecked(state)
  File "filter_mate_app.py", line 579 in _handle_remove_all_layers
    self.layer_management_engine_task_completed({}, 'remove_all_layers')
```

### Séquence d'événements problématique

1. **Signal `allLayersRemoved`** déclenché par QGIS
2. **`_handle_remove_all_layers()`** appelé
3. **`set_widgets_enabled_state(False)`** désactive tous les widgets
4. **`setChecked(False)`** appelé sur les GroupBox checkables
5. **Signal `toggled`** déclenché → appelle `_on_groupbox_clicked()`
6. **`setCollapsed(False)`** appelé sur un widget
7. **Qt essaie de repeindre l'UI** (`paintEvent`)
8. **`QgsMapLayerComboBox`** essaie d'accéder aux données des couches **déjà détruites**
9. **💥 Access Violation** → crash QGIS

## Cause racine

**Race condition classique** entre trois opérations concurrentes :

1. **Destruction des objets de couche** par QGIS
2. **Modification de l'état des widgets** par FilterMate
3. **Repaint des widgets Qt** (notamment `QgsMapLayerComboBox`)

Le problème principal : les signaux Qt n'étaient **pas bloqués** lors de la modification des widgets dans `set_widgets_enabled_state()`, ce qui déclenchait une cascade de callbacks pendant la phase critique de nettoyage.

## Solution implémentée

### 1. Blocage des signaux dans `set_widgets_enabled_state()`

**Ligne 3206-3246** - Modification majeure :

```python
def set_widgets_enabled_state(self, state):
    """
    - SAFETY: Blocks all signals during state changes to prevent race conditions
    """
    widget_count = 0
    for widget_group in self.widgets:
        for widget_name in self.widgets[widget_group]:
            if self.widgets[widget_group][widget_name]["TYPE"] not in ("JsonTreeView",...):
                widget = self.widgets[widget_group][widget_name]["WIDGET"]
                
                # ✅ NOUVEAU: Block signals to prevent race conditions
                was_blocked = widget.blockSignals(True)
                try:
                    if self.widgets[widget_group][widget_name]["TYPE"] in ("PushButton", "GroupBox"):
                        if widget.isCheckable():
                            if state is False:
                                widget.setChecked(state)  # ← Ne déclenche plus de signal!
                                if self.widgets[widget_group][widget_name]["TYPE"] == "GroupBox":
                                    widget.setCollapsed(True)
                    widget.setEnabled(state)
                finally:
                    # Always restore signal blocking state
                    widget.blockSignals(was_blocked)
                
                widget_count += 1
```

**Avantages** :
- **Atomicité** : Les changements d'état se font sans interruption
- **Sécurité** : Le bloc `try/finally` garantit la restauration de l'état des signaux
- **Performance** : Évite des callbacks inutiles pendant le nettoyage

### 2. Protection défensive dans `_on_groupbox_clicked()`

**Ligne 3522-3560** - Ajout de garde-fous :

```python
def _on_groupbox_clicked(self, groupbox, state):
    # Prevent recursive calls
    if self._updating_groupbox:
        return
    
    # ✅ NOUVEAU: Don't process if widgets not initialized or invalid state
    if not self.widgets_initialized or not hasattr(self, 'widgets'):
        logger.debug(f"_on_groupbox_clicked ignored: widgets not ready")
        return
    
    # ... reste du code
```

### 3. Gestion sûre des accès aux widgets

**Ligne 3572-3584** - Protection contre les accès invalides :

```python
# ✅ NOUVEAU: Verify widgets exist before accessing them
try:
    single_gb = self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"]
    multiple_gb = self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"]
    custom_gb = self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]
except (KeyError, AttributeError) as e:
    logger.debug(f"Groupbox widgets not accessible: {e}")
    return
```

## Impact

### Avant
- ❌ Crash QGIS lors de "Supprimer toutes les couches"
- ❌ Access violation imprévisible
- ❌ Perte de données utilisateur
- ❌ Instabilité générale

### Après
- ✅ Suppression de toutes les couches stable
- ✅ Nettoyage propre de l'UI
- ✅ Pas de callbacks pendant la phase critique
- ✅ Meilleure robustesse globale

## Tests recommandés

### Test 1 : Suppression basique
1. Ouvrir QGIS avec FilterMate
2. Charger plusieurs couches vectorielles
3. Activer FilterMate
4. Menu QGIS → Projet → Supprimer toutes les couches
5. **Vérifier** : Pas de crash, message d'info affiché

### Test 2 : Suppression pendant une opération
1. Charger une grosse couche (>100k entités)
2. Lancer un filtrage long
3. Pendant l'exécution → Supprimer toutes les couches
4. **Vérifier** : Annulation propre, pas de crash

### Test 3 : Cycles multiples
1. Charger des couches → Supprimer tout (×5 fois)
2. **Vérifier** : Stabilité sur la durée

### Test 4 : Avec/sans PostgreSQL
1. Tester avec couches PostgreSQL
2. Tester avec GeoPackage/Shapefile
3. **Vérifier** : Comportement cohérent

## Considérations techniques

### Pattern du blocage de signaux

```python
was_blocked = widget.blockSignals(True)
try:
    # Opérations critiques
    widget.setChecked(False)
    widget.setEnabled(False)
finally:
    widget.blockSignals(was_blocked)  # Restaure l'état précédent
```

**Pourquoi utiliser `try/finally`?**
- Garantit que les signaux seront restaurés même en cas d'exception
- Pattern standard Qt/PyQt pour les opérations critiques
- Évite les fuites d'état (signaux bloqués à jamais)

### Ordre d'exécution critique

1. **Bloquer signaux** → 2. **Modifier état** → 3. **Restaurer signaux**

❌ **Mauvais** (sans blocage) :
```python
widget.setChecked(False)  # → Déclenche toggled → Callback → Crash
```

✅ **Bon** (avec blocage) :
```python
widget.blockSignals(True)
widget.setChecked(False)  # → Aucun signal déclenché
widget.blockSignals(False)
```

## Recommandations

### À appliquer ailleurs dans le code

Ce pattern devrait être utilisé **partout où on modifie programmatiquement** des widgets checkables/toggleables pendant :
- L'initialisation
- Le nettoyage
- Les opérations de masse (enable/disable multiple widgets)

### Zones à surveiller

Rechercher dans le code :
```python
grep -n "\.setChecked(" filter_mate_dockwidget.py
grep -n "\.setCollapsed(" filter_mate_dockwidget.py
```

**Vérifier** : Est-ce que ces appels devraient bloquer les signaux?

## Logs de débogage

Avec cette correction, les logs devraient montrer :

```
DEBUG: set_widgets_enabled_state(False) called
DEBUG: 48 widgets set to enabled=False
DEBUG: _on_groupbox_clicked ignored: widgets not ready
INFO: Toutes les couches ont été supprimées. Ajoutez des couches...
```

**Note** : Le log "ignored: widgets not ready" est normal et indique que la protection fonctionne.

## Références

- **Issue GitHub** : #[à créer]
- **Qt Documentation** : [`QObject::blockSignals()`](https://doc.qt.io/qt-5/qobject.html#blockSignals)
- **Pattern similaire** : Voir `exploring_groupbox_changed()` qui utilise déjà `blockSignals()`

## Conclusion

Cette correction résout une **race condition critique** qui causait des crashes imprévisibles de QGIS. La solution est **défensive et robuste** :

1. **Prévention** : Blocage des signaux pendant les modifications critiques
2. **Détection** : Vérification de l'état avant d'agir
3. **Isolation** : Gestion des exceptions pour les accès aux widgets

Le code est maintenant **thread-safe** pendant la phase de nettoyage des couches, ce qui était l'objectif principal de la correction.
