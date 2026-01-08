# Fix: QgsMessageLog.logMessage TypeError

**Date**: 6 janvier 2026  
**Version**: v2.8.15  
**Gravité**: CRITICAL  
**Backend concerné**: OGR (tous types de couches)

## 🐛 Problème

### Symptômes

Exception récurrente empêchant l'affichage des messages de log lors de l'utilisation du backend OGR:

```
2026-01-06T15:07:22     CRITICAL    OGR apply_filter EXCEPTION for 'Ducts': 
QgsMessageLog.logMessage(): argument 2 has unexpected type 'MessageLevel'
Traceback: Traceback (most recent call last):
  File "C:\Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3\profiles\default/python/plugins\filter_mate\modules\backends\ogr_backend.py", line 933, in apply_filter
  QgsMessageLog.logMessage(
TypeError: QgsMessageLog.logMessage(): argument 2 has unexpected type 'MessageLevel'
```

### Impact utilisateur

- Messages de debug non affichés dans le panneau Messages QGIS
- Diagnostic des problèmes de filtrage rendu difficile
- Erreurs masquées par des exceptions de logging
- Expérience utilisateur dégradée (messages d'erreur techniques au lieu d'informations utiles)

## 🔍 Analyse technique

### Signature API correcte

La méthode `QgsMessageLog.logMessage()` de l'API QGIS attend 3 arguments:

```python
QgsMessageLog.logMessage(
    message: str,      # Le message à afficher
    tag: str,          # Le tag/catégorie (ex: "FilterMate")
    level: Qgis.MessageLevel  # Le niveau (Qgis.Info, Qgis.Warning, Qgis.Critical)
)
```

### Erreurs trouvées

**Erreur 1: Utilisation de `Qgis.MessageLevel(0)` au lieu de constantes**

```python
# ❌ INCORRECT
QgsMessageLog.logMessage(
    f"Message de debug",
    "FilterMate", Qgis.MessageLevel(0)  # Crée une instance au lieu d'utiliser la constante
)

# ✅ CORRECT
QgsMessageLog.logMessage(
    f"Message de debug",
    "FilterMate", Qgis.Info  # Utilise la constante appropriée
)
```

**Erreur 2: Arguments dans le mauvais ordre**

```python
# ❌ INCORRECT - Manque le tag "FilterMate"
QgsMessageLog.logMessage(
    f"OGR apply_filter: result {result}",
    Qgis.MessageLevel(0) if result else Qgis.Warning
)

# ✅ CORRECT
QgsMessageLog.logMessage(
    f"OGR apply_filter: result {result}",
    "FilterMate", Qgis.Info if result else Qgis.Warning
)
```

### Constantes Qgis.MessageLevel disponibles

```python
Qgis.Info      # Niveau INFO (messages informatifs)
Qgis.Warning   # Niveau WARNING (avertissements)
Qgis.Critical  # Niveau CRITICAL (erreurs graves)
Qgis.Success   # Niveau SUCCESS (opérations réussies)
Qgis.NoLevel   # Pas de niveau spécifique
```

## ✅ Solution implémentée

### Changements apportés

**1. Remplacement global de `Qgis.MessageLevel(0)` par `Qgis.Info`**

```bash
# Commande sed utilisée
sed -i 's/Qgis\.MessageLevel(0)/Qgis.Info/g' fichier.py
```

**2. Correction des appels avec arguments manquants**

Avant:
```python
QgsMessageLog.logMessage(
    f"OGR apply_filter: _apply_filter_standard returned {result} for '{layer.name()}'",
    Qgis.MessageLevel(0) if result else Qgis.Warning  # ❌ Manque "FilterMate"
)
```

Après:
```python
QgsMessageLog.logMessage(
    f"OGR apply_filter: _apply_filter_standard returned {result} for '{layer.name()}'",
    "FilterMate", Qgis.Info if result else Qgis.Warning  # ✅ Ordre correct
)
```

### Fichiers modifiés

| Fichier | Lignes corrigées | Type de correction |
|---------|------------------|-------------------|
| `modules/backends/ogr_backend.py` | 18 | `MessageLevel(0)` → `Qgis.Info` |
| `modules/backends/spatialite_cache.py` | 2 | `MessageLevel(0)` → `Qgis.Info` |
| `config/config.py` | 1 | `MessageLevel(0)` → `Qgis.Info` |

### Lignes spécifiques corrigées (ogr_backend.py)

- L525: Log multi-step ATTRIBUTE_FIRST
- L833: Log source_geom summary
- L847: Log first geometry details
- L871: Log target layer feature count
- L891: Log MULTI-STEP optimizer attempt
- L903: Log MULTI-STEP result
- L909: Log fallback to STANDARD
- L915: Log STANDARD method usage
- L933: Log _apply_filter_standard result
- L1762-L2483: Logs _safe_select_by_location et validation

## 🧪 Vérification

### Test de régression

1. **Avant le fix**: Exception TypeError à chaque filtrage OGR
2. **Après le fix**: Aucune exception, messages affichés correctement

### Commande de vérification

```bash
# Vérifier qu'il n'y a plus d'usages de MessageLevel()
grep -r "MessageLevel(" modules/ config/
# Résultat attendu: aucune correspondance
```

## 📊 Impact

### Stabilité

- ✅ Suppression de 21 points d'échec potentiels (21 appels corrigés)
- ✅ Backend OGR 100% stable pour le logging
- ✅ Aucune exception TypeError dans les logs

### Diagnostic

- ✅ Messages de debug affichés correctement dans QGIS
- ✅ Traçabilité complète du workflow de filtrage
- ✅ Meilleure visibilité sur les opérations en cours

### Maintenance

- ✅ Code conforme à l'API QGIS
- ✅ Pattern cohérent pour tous les appels QgsMessageLog
- ✅ Facilite le débogage futur

## 🎓 Bonnes pratiques établies

### Pattern recommandé pour QgsMessageLog

```python
# ✅ TOUJOURS utiliser ce pattern
from qgis.core import QgsMessageLog, Qgis

# Info (messages de debug)
QgsMessageLog.logMessage(
    f"Message descriptif avec {variable}",
    "FilterMate", Qgis.Info
)

# Warning (avertissements)
QgsMessageLog.logMessage(
    f"Attention: {probleme_potentiel}",
    "FilterMate", Qgis.Warning
)

# Critical (erreurs graves)
QgsMessageLog.logMessage(
    f"ERREUR: {erreur_critique}",
    "FilterMate", Qgis.Critical
)

# Success (succès)
QgsMessageLog.logMessage(
    f"✓ Opération réussie: {resultat}",
    "FilterMate", Qgis.Success
)
```

### À éviter

```python
# ❌ Ne JAMAIS faire
Qgis.MessageLevel(0)  # Utiliser Qgis.Info à la place
Qgis.MessageLevel(1)  # Utiliser Qgis.Warning à la place
Qgis.MessageLevel(2)  # Utiliser Qgis.Critical à la place

# ❌ Ne JAMAIS omettre le tag
QgsMessageLog.logMessage("Message", Qgis.Info)  # Manque "FilterMate"
```

## 📝 Notes pour les développeurs

1. **Toujours vérifier l'ordre des arguments** lors de l'utilisation de `QgsMessageLog.logMessage()`
2. **Utiliser les constantes Qgis.Info/Warning/Critical** au lieu de créer des instances
3. **Tester les messages de log** dans le panneau Messages QGIS après modification
4. **Utiliser `grep -r "MessageLevel(" .`** avant de committer pour détecter les usages incorrects

## 🔗 Références

- [Documentation QGIS API - QgsMessageLog](https://qgis.org/pyqgis/master/core/QgsMessageLog.html)
- [QGIS Source - Qgis.MessageLevel enum](https://github.com/qgis/QGIS/blob/master/python/core/auto_generated/qgis.py)
- Issue GitHub: N/A (fix proactif basé sur logs utilisateur)

---

**Résolution**: ✅ RÉSOLU  
**Version**: v2.8.15  
**Date**: 6 janvier 2026
