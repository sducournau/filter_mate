# Fix: Amélioration du diagnostic d'échec de chargement des couches

**Date**: 2025-12-19  
**Type**: Fix + Amélioration  
**Priorité**: Haute  
**Statut**: Complété

## Problème rapporté

Message d'avertissement lors du démarrage du plugin:
```
2025-12-19T16:21:41  WARNING  FilterMate : Échec du chargement des couches. Essayez de recharger le plugin.
```

## Analyse

Le message apparaissait dans un timer de sécurité après 6 secondes si aucune couche n'était chargée. Causes possibles:

1. **Timeout trop court** pour les projets volumineux ou les systèmes lents
2. **Manque de diagnostics** pour identifier la cause réelle du problème
3. **Pas de vérification préventive** de la santé de la base de données
4. **Logging insuffisant** pour diagnostiquer les échecs

## Solutions implémentées

### 1. Message d'erreur enrichi avec diagnostics

**Fichier**: [filter_mate_app.py](../filter_mate_app.py#L761)

Le message d'erreur affiche maintenant:
- Nombre total de couches dans le projet
- Nombre de couches utilisables détectées  
- Nombre de tâches en attente
- État de la base de données
- Solution claire (utiliser F5 pour recharger)

```python
diagnostic_msg = (
    f"Échec du chargement des couches.\n\n"
    f"Diagnostic:\n"
    f"- Couches totales dans le projet: {len(all_layers)}\n"
    f"- Couches utilisables détectées: {len(current_layers)}\n"
    f"- Tâches en attente (add_layers): {self._pending_add_layers_tasks}\n\n"
    f"Solution: Utilisez F5 pour forcer le rechargement des couches."
)
```

### 2. Augmentation des timeouts

**Changement**: `3s` → `5s` (premier timer), `3s` → `5s` (timer final)  
**Total**: `6s` → `10s`

Permet aux projets volumineux et aux systèmes lents d'avoir plus de temps pour initialiser les couches.

### 3. Vérification de santé de la base de données

**Fichier**: [filter_mate_app.py](../filter_mate_app.py#L625)

Ajout d'une vérification au démarrage:
```python
# HEALTH CHECK: Verify database is accessible
try:
    db_conn = self.get_spatialite_connection()
    if db_conn is None:
        logger.error("Database health check failed")
        iface.messageBar().pushCritical(...)
        return
    else:
        logger.info("Database health check: OK")
        db_conn.close()
except Exception as db_err:
    logger.error(f"Database health check failed: {db_err}")
    iface.messageBar().pushCritical(...)
    return
```

### 4. Logging détaillé

#### A. Dans `_filter_usable_layers()`

Maintenant affiche pour chaque couche filtrée:
- Pourquoi elle a été filtrée (pas vectorielle / invalide / source indisponible)
- Statistiques globales du filtrage

```python
logger.info(f"_filter_usable_layers: {input_count} input layers -> {len(usable)} usable layers. Filtered: {len(filtered_reasons)}")
```

#### B. Dans les timers de sécurité

Ajout de logs détaillés à chaque étape:
- État du dockwidget
- Nombre de couches à chaque étape
- Informations sur les tentatives de récupération

#### C. Dans `LayersManagementEngineTask`

**Fichier**: [layer_management_task.py](../modules/tasks/layer_management_task.py#L192)

Ajout de logs au début de `run()`:
```python
logger.info(f"LayersManagementEngineTask.run() started: action={self.task_action}, db_path={self.db_file_path}")
logger.info(f"add_layers task: processing {len(self.layers)} layers, current project_layers count: {len(self.project_layers)}")
```

### 5. Message de progression

**Fichier**: [filter_mate_app.py](../filter_mate_app.py#L804)

Affichage d'un message informatif pendant le chargement:
```python
iface.messageBar().pushInfo(
    "FilterMate",
    "Chargement des couches en cours... Veuillez patienter."
)
```

## Impact utilisateur

### Avant
- ❌ Message d'erreur générique sans indication de la cause
- ❌ Timeout de 6s trop court pour certains cas
- ❌ Impossible de diagnostiquer le problème sans accès aux logs
- ❌ Pas de retour visuel pendant le chargement

### Après
- ✅ Message d'erreur détaillé avec diagnostics précis
- ✅ Timeout de 10s plus adapté aux projets volumineux
- ✅ Vérification préventive de la base de données
- ✅ Message de progression pendant le chargement
- ✅ Logging exhaustif pour diagnostic par l'équipe de développement

## Instructions de test

1. **Cas normal**: Ouvrir un projet avec plusieurs couches vectorielles
   - ✅ Les couches doivent se charger sans message d'erreur
   - ✅ Logs doivent montrer les étapes de chargement

2. **Cas timeout**: Projet avec nombreuses couches (>50) ou système lent
   - ✅ Message "Chargement en cours" doit apparaître
   - ✅ Timeout de 10s doit être suffisant dans la plupart des cas

3. **Cas base de données inaccessible**: Simuler un problème de permissions
   - ✅ Message d'erreur clair au démarrage
   - ✅ Le plugin ne doit pas se charger partiellement

4. **Cas échec après timeout**: Si échec après 10 secondes
   - ✅ Message d'erreur avec diagnostics détaillés
   - ✅ Instructions claires pour résoudre (F5)

## Logs à surveiller

Lors de problèmes, vérifier dans les logs:

```
FilterMate App.run(): Database health check: OK
_filter_usable_layers: 10 input layers -> 8 usable layers. Filtered: 2
LayersManagementEngineTask.run() started: action=add_layers
Safety timer: Task completed successfully with 8 layers
```

En cas d'échec:
```
Database health check failed: [raison]
_filter_usable_layers: Filtered: [layer_name]: source not available
Safety timer: PROJECT_LAYERS still empty after 3s
Final safety timer: Failed to load layers after recovery attempt
Layer loading failure diagnostic: total=10, usable=0, pending_tasks=0
```

## Fichiers modifiés

1. **filter_mate_app.py** (3 zones modifiées)
   - Méthode `run()`: Vérification santé DB (ligne ~625)
   - Méthode `run()`: Timers de sécurité améliorés (lignes ~760-850)
   - Méthode `_filter_usable_layers()`: Logging détaillé (ligne ~100)

2. **modules/tasks/layer_management_task.py**
   - Méthode `run()`: Logging au démarrage (ligne ~192)

## Prochaines étapes recommandées

1. **Monitoring**: Observer les logs en production pour identifier les cas d'échec restants
2. **Optimisation**: Si timeouts restent insuffisants, envisager un chargement asynchrone progressif
3. **Amélioration UX**: Ajouter une barre de progression pour visualiser l'avancement du chargement
4. **Documentation**: Ajouter une section dans la FAQ pour expliquer le message F5

## Compatibilité

- ✅ Compatible avec tous les backends (PostgreSQL, Spatialite, OGR)
- ✅ Pas de changement d'API ou de comportement fonctionnel
- ✅ Amélioration transparente pour l'utilisateur
- ✅ Aucune migration nécessaire

## Références

- Issue: Message d'avertissement "Échec du chargement des couches"
- Commit: [À compléter après commit]
- Related: POSTGRESQL_LOADING_OPTIMIZATION.md (optimisations complémentaires)
