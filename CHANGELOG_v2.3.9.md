# CHANGELOG - FilterMate v2.3.9 (2025-12-19)

## 🔥 Critical Bug Fix - Access Violation Crash

### Description
Résolution d'un crash critique "Windows fatal exception: access violation" qui se produisait lors du rechargement du plugin ou de la fermeture de QGIS.

### Problème
- **Symptôme**: Crash QGIS avec "access violation" dans le système de notification Qt
- **Déclencheur**: Rechargement du plugin, fermeture de QGIS pendant timers actifs
- **Impact**: Perte de travail, expérience utilisateur dégradée

### Cause technique
Les lambdas dans `QTimer.singleShot` capturaient des références directes à `self`, qui étaient détruites avant l'exécution des callbacks, causant des accès à de la mémoire libérée.

### Solution
**1. Weak References pour tous les timers Qt**
```python
# Avant (❌ DANGEREUX)
QTimer.singleShot(1000, lambda: self.method())

# Après (✅ SÉCURISÉ)
weak_self = weakref.ref(self)
def safe_callback():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self.method()
QTimer.singleShot(1000, safe_callback)
```

**2. Vérifications de sécurité dans les callbacks**
```python
def callback():
    try:
        if not hasattr(self, 'dockwidget'):
            return
    except RuntimeError:
        return
    # Code sûr...
```

**3. Fonction utilitaire safe_show_message()**
```python
safe_show_message('info', "FilterMate", "Message")
```

### Emplacements corrigés
- ✅ Ligne 150: Debouncing layersAdded
- ✅ Lignes 562-567: Force reload layers + UI refresh
- ✅ Ligne 755: Wait for widget initialization
- ✅ Ligne 780: Recovery retry add_layers
- ✅ Ligne 849: Safety timer ensure_ui_enabled
- ✅ Ligne 888: On layers added

### Impact
- ✅ Plus de crashes lors du rechargement du plugin
- ✅ Fermeture propre de QGIS même avec timers actifs
- ✅ Stabilité accrue lors de changements rapides de projet
- ⚠️ Tests requis pour validation complète

### Documentation
- 📄 [FIX_ACCESS_VIOLATION_CRASH_2025-12-19.md](docs/fixes/FIX_ACCESS_VIOLATION_CRASH_2025-12-19.md)
- Pattern de développement mis à jour pour futurs timers

### Tests recommandés
1. Rechargement rapide du plugin (10x)
2. Fermeture QGIS pendant chargement des couches
3. Rechargement pendant filtrage actif
4. Changement rapide entre projets

---

**Version**: 2.3.9  
**Date**: 2025-12-19  
**Priorité**: CRITIQUE  
**Status**: ✅ Résolu - Tests en attente
