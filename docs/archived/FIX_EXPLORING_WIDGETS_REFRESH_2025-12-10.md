# Fix: Mise à jour des widgets exploring lors du changement de couche

**Date**: 10 décembre 2025  
**Problème**: Les widgets exploring ne se mettaient pas à jour lors du changement de couche courante

## Symptômes

Lorsque l'utilisateur change de couche courante (current layer), les widgets de la section "Exploring" conservaient les données de l'ancienne couche au lieu de charger les features et champs de la nouvelle couche.

## Cause racine

### 1. Widget custom `MULTIPLE_SELECTION_FEATURES`

**Fichier**: `modules/widgets.py`  
**Classe**: `QgsCheckableComboBoxFeaturesListPickerWidget`  
**Méthode**: `setLayer()`

**Problème**: La logique conditionnelle ne rechargeait les features que si l'expression d'affichage changeait :

```python
# ANCIEN CODE (buggy)
if self.list_widgets[self.layer.id()].getDisplayExpression() != layer_props["exploring"]["multiple_selection_expression"]:
    self.setDisplayExpression(layer_props["exploring"]["multiple_selection_expression"])
else:
    # Seulement loadFeaturesList(), pas de rebuild complet
    description = 'Loading features'
    action = 'loadFeaturesList'
    self.build_task(description, action, True)
    self.launch_task(action)
```

**Scénario problématique**: Si deux couches utilisent la même expression (ex: "nom" ou "id"), le widget ne recharge pas les features de la nouvelle couche.

**Solution**: Toujours appeler `setDisplayExpression()` lors d'un changement de couche :

```python
# NOUVEAU CODE (corrigé)
# CRITICAL: Always call setDisplayExpression() when layer changes to force reload of features
# Even if the expression is the same (e.g., "id" on both layers), the features are different
self.setDisplayExpression(layer_props["exploring"]["multiple_selection_expression"])
```

### 2. Widget natif `SINGLE_SELECTION_FEATURES` (QgsFeaturePickerWidget)

**Fichier**: `filter_mate_dockwidget.py`  
**Méthode**: `update_exploring_widgets_layer()`

**Problème**: Les widgets natifs QGIS peuvent avoir un cache interne qui n'est pas invalidé automatiquement si l'expression est identique.

**Solution**: Forcer le rafraîchissement en réinitialisant l'expression à vide puis en la remettant :

```python
# CRITICAL: Force refresh by resetting expression to empty then setting it back
# This ensures QgsFeaturePickerWidget reloads features even if expression is identical
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression("")
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(
    layer_props["exploring"]["single_selection_expression"]
)
```

## Modifications apportées

### 1. `modules/widgets.py` (ligne ~563-593)

**Méthode modifiée**: `QgsCheckableComboBoxFeaturesListPickerWidget.setLayer()`

**Changement**:
- ❌ Supprimé: Logique conditionnelle `if getDisplayExpression() != new_expression`
- ✅ Ajouté: Appel systématique à `setDisplayExpression()` lors du changement de couche

**Impact**: Le widget recharge toujours les features, même si l'expression est identique.

### 2. `filter_mate_dockwidget.py` (ligne ~2001-2007)

**Méthode modifiée**: `update_exploring_widgets_layer()`

**Changement**:
- ✅ Ajouté: Réinitialisation de l'expression à `""` avant de la remettre

**Impact**: Force le `QgsFeaturePickerWidget` à invalider son cache et recharger les features.

### 3. Widgets non modifiés (déjà corrects)

Les widgets suivants n'ont pas besoin de modification car ils appellent déjà `setLayer()` + `setExpression()` à chaque changement :

- `SINGLE_SELECTION_EXPRESSION` (QgsFieldExpressionWidget)
- `MULTIPLE_SELECTION_EXPRESSION` (QgsFieldExpressionWidget)
- `CUSTOM_SELECTION_EXPRESSION` (QgsFieldExpressionWidget)

Les `QgsFieldExpressionWidget` rechargent automatiquement la liste des champs lors de `setLayer()`.

## Tests ajoutés

### `test_exploring_widgets_layer_change.py`

Test spécifique pour le widget `MULTIPLE_SELECTION_FEATURES` vérifiant que `setDisplayExpression()` est toujours appelé même avec une expression identique.

### `test_all_exploring_widgets_refresh.py`

Test complet vérifiant que tous les 5 widgets exploring se rafraîchissent correctement :
1. SINGLE_SELECTION_FEATURES ✅
2. SINGLE_SELECTION_EXPRESSION ✅
3. MULTIPLE_SELECTION_FEATURES ✅
4. MULTIPLE_SELECTION_EXPRESSION ✅
5. CUSTOM_SELECTION_EXPRESSION ✅

## Flux de mise à jour

Lors du changement de couche courante (`current_layer_changed()`):

1. **Déconnexion des signaux** pour éviter les cascades
2. **`update_exploring_widgets_layer()`** : Met à jour TOUS les widgets avec la nouvelle couche
   - Appelle `setLayer()` pour chaque widget
   - Force le rafraîchissement des expressions (reset à "" puis remise)
3. **Reconnexion des signaux**
4. **`exploring_groupbox_changed()`** : Active le groupbox approprié
5. **`exploring_link_widgets()`** : Synchronise les widgets entre eux (si linking activé)
6. **`get_current_features()`** : Charge les features pour le mode actif

## Validation

Pour tester manuellement :
1. Charger deux couches avec des champs identiques (ex: "id", "nom")
2. Configurer les expressions exploring sur "nom" pour les deux couches
3. Ouvrir le plugin FilterMate
4. Sélectionner la première couche
5. Observer les features disponibles dans le widget "Multiple Selection"
6. **Changer de couche courante**
7. ✅ Les features devraient se mettre à jour immédiatement
8. ✅ Le widget devrait afficher les features de la nouvelle couche, pas de l'ancienne

## Notes techniques

### Pourquoi forcer le rafraîchissement ?

Les widgets QGIS utilisent souvent un système de cache pour améliorer les performances. Quand on appelle `setDisplayExpression()` avec la **même** valeur que celle déjà définie, le widget peut considérer qu'aucun changement n'est nécessaire et ne pas recharger les données.

**Techniques de rafraîchissement forcé** :
1. **Pour widgets custom** : Toujours appeler la méthode de chargement (ex: `setDisplayExpression()`)
2. **Pour widgets natifs QGIS** : Reset à vide puis remise de l'expression
3. **Alternative** : Appeler explicitement une méthode `reload()` ou `refresh()` si disponible

### Widgets natifs QGIS concernés

- `QgsFeaturePickerWidget` : Dropdown de sélection de feature unique
- `QgsFieldExpressionWidget` : Sélecteur de champs avec support des expressions

Ces widgets se synchronisent généralement bien avec `setLayer()`, mais un reset de l'expression garantit un comportement cohérent.

## Compatibilité

- ✅ QGIS 3.x
- ✅ Python 3.7+
- ✅ Backends : PostgreSQL, Spatialite, OGR
- ✅ Pas d'impact sur les performances (le rechargement est nécessaire de toute façon)

## Références

- Issue GitHub : [À compléter]
- Commit : [À compléter]
- Tests : `test_exploring_widgets_layer_change.py`, `test_all_exploring_widgets_refresh.py`
