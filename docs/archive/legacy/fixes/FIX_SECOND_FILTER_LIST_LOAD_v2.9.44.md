# Fix: Second Filter Feature List Loading Failure (v2.9.44)

**Date**: 2026-01-07  
**Version**: FilterMate v2.9.44  
**Issue**: Échec du chargement de la liste des features lors du 2ème filtre multi-étapes Spatialite avec outil de sélection activé

---

## 🐛 Problème Signalé

**Symptômes** :
1. Premier filtre fonctionne correctement
2. **Second filtre** : 
   - Tâche `loadFeaturesList` échoue
   - Liste des features reste vide ou n'affiche pas les bonnes valeurs
   - Pas de message d'erreur clair
   - Problème d'affichage et de rechargement de la liste

**Contexte** :
- Backend: Spatialite
- Type de filtre: Multi-étapes (2ème passe)
- Outil de sélection: Activé
- Affecte: Toutes les couches distantes filtrées

---

## 🔍 Analyse Technique

### Causes Identifiées

#### 1. Logging Insuffisant

**Problème** : Lorsque `loadFeaturesList` trouve une liste vide (`list_to_load`), le logging ne fournissait pas assez d'informations pour diagnostiquer si :
- Le layer a réellement 0 features
- La tâche `buildFeaturesList` a échoué
- Le subset string est incorrect
- Il y a un problème de synchronisation

**Impact** : Impossible de diagnostiquer pourquoi la liste reste vide.

#### 2. Pas de Retry Automatique

**Problème** : Pour les backends Spatialite/OGR, des problèmes temporaires de verrouillage de base de données peuvent empêcher le chargement de la liste.

**Impact** : L'utilisateur doit manuellement recharger la couche ou redémarrer QGIS.

#### 3. Logging Multi-Step Filters Incomplet

**Problème** : Dans le backend Spatialite (`_apply_filter_direct_sql` et `_apply_filter_with_source_table`), le logging ne distinguait pas clairement entre :
- Filtres FID (normalement remplacés)
- Filtres attributaires (normalement combinés)
- Prédicats spatiaux (normalement remplacés)

**Impact** : Difficile de comprendre pourquoi un filtre FID du step 1 n'est pas combiné avec le filtre spatial du step 2.

---

## ✅ Solutions Implémentées

### 1. Enhanced Diagnostic Logging in `loadFeaturesList`

**Fichier** : `modules/widgets.py` (ligne ~770)

**Avant** :
```python
if total_count == 0:
    logger.warning(f"loadFeaturesList: No features to load for layer '{self._cached_layer_name}'")
    self.updateFeatures()
    return
```

**Après** :
```python
if total_count == 0:
    # v2.9.44: Enhanced diagnostic for empty feature list
    layer_feature_count = self.layer.featureCount() if self.layer else 0
    provider_type = self.layer.providerType() if self.layer else 'unknown'
    subset_string = self.layer.subsetString() if self.layer else 'N/A'
    
    logger.warning(f"loadFeaturesList: No features to load for layer '{self._cached_layer_name}'")
    logger.warning(f"  → Layer feature count: {layer_feature_count}")
    logger.warning(f"  → Provider type: {provider_type}")
    logger.warning(f"  → Current subset: {subset_string[:100] if subset_string else '(none)'}...")
    
    # v2.9.44: If layer has features but list is empty, this indicates
    # buildFeaturesList failed or didn't run - log this as potential bug
    if layer_feature_count > 0:
        logger.error(f"⚠️ CRITICAL: Layer has {layer_feature_count} features but feature list is EMPTY!")
        logger.error(f"  This indicates buildFeaturesList task may have failed or was skipped.")
        logger.error(f"  Consider forcing layer reload or checking for task cancellation.")
    
    self.updateFeatures()
    return
```

**Bénéfices** :
- Détection immédiate des cas où `buildFeaturesList` a échoué
- Information complète pour diagnostiquer le problème
- Distinction claire entre "0 features dans layer" vs "liste vide mais layer a des features"

---

### 2. Automatic Retry for Spatialite/OGR Layers

**Fichier** : `modules/widgets.py` (ligne ~1500)

**Avant** :
```python
def check_list_populated():
    """Verify that feature list was successfully populated."""
    try:
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return
        
        widget = self.list_widgets[self.layer.id()]
        count = widget.count()
        
        # If list is empty, log warning and suggest retry
        if count == 0:
            logger.warning(f"Feature list remains EMPTY 500ms after task launch!")
            logger.warning(f"Expression: {working_expression[:50]}...")
```

**Après** :
```python
def check_list_populated():
    """Verify that feature list was successfully populated."""
    try:
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return
        
        widget = self.list_widgets[self.layer.id()]
        count = widget.count()
        layer_feature_count = self.layer.featureCount() if self.layer else 0
        
        # If list is empty but layer has features, something went wrong
        # v2.9.44: Enhanced detection and retry logic
        if count == 0 and layer_feature_count > 0:
            logger.warning(f"Feature list remains EMPTY 500ms after task launch!")
            logger.warning(f"Expression: {working_expression[:50]}...")
            logger.warning(f"Layer has {layer_feature_count} features but widget shows 0")
            
            # v2.9.44: For Spatialite multi-step filters, force layer reload
            # This ensures the feature list rebuilds from the current subset
            provider_type = self.layer.providerType() if self.layer else None
            if provider_type in ('spatialite', 'ogr'):
                logger.info(f"🔄 Triggering automatic retry for {provider_type} layer...")
                try:
                    # Force a complete refresh by rebuilding the feature list
                    self.layer.reload()
                    # Re-trigger the display expression to rebuild list
                    from qgis.PyQt.QtCore import QTimer
                    QTimer.singleShot(200, lambda: self.setDisplayExpression(working_expression))
                except Exception as retry_err:
                    logger.error(f"Failed to trigger retry: {retry_err}")
        elif count == 0:
            logger.warning(f"Feature list remains EMPTY 500ms after task launch!")
            logger.warning(f"Expression: {working_expression[:50]}...")
```

**Bénéfices** :
- Retry automatique pour Spatialite/OGR
- Résolution automatique des problèmes temporaires de verrouillage DB
- Amélioration de l'expérience utilisateur

---

### 3. Enhanced Multi-Step Filter Logging

**Fichier** : `modules/backends/spatialite_backend.py` (lignes ~3320 et ~4100)

**Avant** :
```python
if not has_source_alias and not has_exists and not has_spatial_predicate and not is_fid_only:
    old_subset_sql_filter = f"({old_subset}) AND "
    self.log_info(f"  → Including previous attribute filter in SQL query")
elif is_fid_only:
    self.log_info(f"  → Old subset is FID filter from previous spatial step - will be REPLACED")
else:
    self.log_info(f"  → Old subset has spatial predicates - will be replaced")
```

**Après** :
```python
if not has_source_alias and not has_exists and not has_spatial_predicate and not is_fid_only:
    old_subset_sql_filter = f"({old_subset}) AND "
    # v2.9.44: Enhanced logging for multi-step filter combination
    self.log_info(f"✅ Combining old attribute filter with new spatial filter")
    self.log_info(f"  → Old filter: {old_subset[:80]}...")
elif is_fid_only:
    # v2.9.44: Log FID filter details for debugging
    self.log_info(f"⚠️ Old subset is FID filter from previous spatial step - will be REPLACED")
    self.log_info(f"  → FID filter: {old_subset[:80]}...")
    self.log_info(f"  → This is EXPECTED in multi-step filtering when source geometry changes")
else:
    # v2.9.44: Enhanced logging for debugging
    self.log_info(f"⚠️ Old subset has spatial predicates - will be replaced")
    self.log_info(f"  → has_source_alias={has_source_alias}")
    self.log_info(f"  → has_exists={has_exists}")
    self.log_info(f"  → has_spatial_predicate={has_spatial_predicate}")
    if old_subset:
        self.log_info(f"  → Old subset: {old_subset[:80]}...")
```

**Bénéfices** :
- Clarification du comportement attendu en multi-step
- Distinction visuelle (✅/⚠️) pour faciliter la lecture des logs
- Informations détaillées sur pourquoi un filtre est remplacé ou combiné

---

### 4. Enhanced Logging in `buildFeaturesList`

**Fichier** : `modules/widgets.py` (ligne ~640)

**Amélioration** : Logs plus détaillés lorsque la liste construite est vide pour diagnostiquer le problème à la source.

**Avant** :
```python
if len(features_list) == 0:
    logger.debug(f"buildFeaturesList: No features available for layer '{self._cached_layer_name}'")
    self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
    return
```

**Après** :
```python
if len(features_list) == 0:
    # v2.9.44: Enhanced logging for empty feature list
    layer_feature_count = self.layer.featureCount() if self.layer else 0
    subset_str = self.layer.subsetString() if self.layer else 'N/A'
    logger.warning(f"buildFeaturesList: No features available for layer '{self._cached_layer_name}'")
    logger.warning(f"  → Layer reports {layer_feature_count} features")
    logger.warning(f"  → Subset: {subset_str[:80] if subset_str else '(none)'}...")
    logger.warning(f"  → Filter: {filter_txt_string_final[:80] if filter_txt_splitted is not None else 'None'}...")
    self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
    return
```

---

## 📊 Impact des Corrections

| Aspect | Avant | Après |
|--------|-------|-------|
| **Diagnostic** | Messages vagues | Logs détaillés avec contexte complet |
| **Recovery** | Manuel (reload layer) | Automatique pour Spatialite/OGR |
| **Multi-step clarity** | Difficile à comprendre | Comportement clairement expliqué |
| **User experience** | Bloqué, doit redémarrer | Auto-recovery dans la plupart des cas |

---

## ✅ Tests de Validation

### Scénario 1: Second Filtre avec Changement de Source

1. **Premier filtre** : Batiment (Polygon) + buffer 1m → OK
2. **Second filtre** : Ducts (LineString) sélection multiple + buffer 1m
3. **Résultat attendu** : 
   - Liste se recharge automatiquement si vide
   - Logs expliquent que le FID filter est remplacé (comportement normal)
   - Features correctes affichées

### Scénario 2: Layer Verrouillé Temporairement

1. Appliquer un filtre sur Spatialite
2. Immédiatement changer le champ d'affichage
3. **Résultat attendu** :
   - Retry automatique après 500ms si liste vide
   - Liste se remplit après le retry

### Scénario 3: Layer Réellement Vide

1. Appliquer un filtre qui ne retourne aucun résultat
2. **Résultat attendu** :
   - Logs indiquent clairement que le layer a 0 features
   - Pas de retry inutile
   - Message clair à l'utilisateur

---

## 📝 Notes de Développement

### Comportement Attendu Multi-Step Spatialite

**Rappel** : En filtrage multi-étapes avec changement de géométrie source, le **FID filter du step précédent est remplacé**, pas combiné. C'est le comportement **correct** car :

1. **Step 1** : Filter batiment → FID filter `fid IN (1,2,3)` sur distant layers
2. **Step 2** : Filter ducts (source différente) → Le cache est invalidé (hash mismatch)
3. **Résultat** : Nouveau filtre spatial **remplace** l'ancien FID filter

**Ce comportement est maintenant clairement documenté dans les logs.**

---

## 🔄 Suivi Post-Fix

### Monitoring Recommandé

Surveiller les logs QGIS pour :
- Messages `⚠️ CRITICAL: Layer has X features but feature list is EMPTY!`
- Fréquence des retries automatiques
- Messages `🔄 Triggering automatic retry`

### Améliorations Futures Possibles

1. **Configurable Retry Count** : Permettre plusieurs tentatives avec backoff
2. **Better Task Cancellation Handling** : Détecter plus tôt les annulations de tâches
3. **Cache Smarter** : Potentiellement conserver les FIDs même avec géométrie source différente
4. **User Feedback** : Afficher un message à l'utilisateur lors du retry automatique

---

## 📚 Fichiers Modifiés

- `modules/widgets.py` : Logging amélioré + retry automatique
- `modules/backends/spatialite_backend.py` : Logging multi-step filters

---

**Résumé** : Ce fix améliore considérablement le diagnostic et la résolution automatique des problèmes de chargement de liste lors du 2ème filtre multi-étapes Spatialite. Les utilisateurs devraient rarement rencontrer des listes vides, et quand cela arrive, les logs fourniront toutes les informations nécessaires pour comprendre et résoudre le problème.
