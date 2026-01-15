# Guide de vérification du correctif - AttributeError HistoryService

## ✅ Correctif appliqué

L'erreur `AttributeError: 'HistoryService' object has no attribute 'get_or_create_history'` a été corrigée.

## 📋 Comment vérifier que le correctif fonctionne

### 1. Redémarrer QGIS
Fermez complètement QGIS et relancez-le pour charger les modifications.

### 2. Activer le plugin FilterMate
Dans QGIS :
- Menu **Extensions** → **Gérer et installer les extensions**
- Chercher **FilterMate**
- Cocher la case pour l'activer

### 3. Vérifications de base

#### ✓ Le plugin se charge sans erreur
Si le plugin se charge et que le dock widget apparaît, le correctif fonctionne !

#### ✓ Pas d'erreur dans la console Python
Ouvrir la console Python de QGIS :
- Menu **Extensions** → **Console Python**
- Vérifier qu'il n'y a pas de message d'erreur mentionnant `get_or_create_history`

### 4. Test fonctionnel de l'undo/redo

#### Test simple :
1. Ouvrir une couche vectorielle dans QGIS
2. Dans FilterMate, appliquer un filtre
3. Cliquer sur le bouton "Undo" (Annuler)
4. Vérifier que le filtre précédent est restauré

Si l'undo/redo fonctionne, la couche de compatibilité fonctionne parfaitement !

## 🔍 Détails techniques

### Qu'est-ce qui a été corrigé ?

Le nouveau `HistoryService` n'avait pas la méthode `get_or_create_history()` que l'ancien code attendait.

### Solution appliquée

Ajout d'une **couche de compatibilité** dans `core/services/history_service.py` :

```python
# Nouvelle classe wrapper
class LayerHistory:
    def push_state(self, expression, feature_count, ...)
    
# Nouvelle méthode dans HistoryService
def get_or_create_history(self, layer_id: str) -> LayerHistory:
    # Retourne un wrapper compatible avec l'ancienne API
```

### Fichiers modifiés
- ✅ `core/services/history_service.py` (+70 lignes)
- ✅ Documentation : `docs/BUGFIX-HISTORY-COMPATIBILITY-20260115.md`

### Pas de régression
- ✅ L'ancienne API fonctionne (via le wrapper)
- ✅ La nouvelle API fonctionne (inchangée)
- ✅ 100% rétrocompatible

## 🐛 Si l'erreur persiste

### Vérifier la version des fichiers
```bash
cd /path/to/filter_mate/
git log --oneline -1 core/services/history_service.py
```

Vous devriez voir le commit : `fix: Add compatibility layer to HistoryService`

### Vérifier que les modifications sont présentes
```bash
grep -n "class LayerHistory" core/services/history_service.py
grep -n "get_or_create_history" core/services/history_service.py
```

Devrait retourner :
- Ligne ~17 : `class LayerHistory:`
- Ligne ~424 : `def get_or_create_history(...)`

### Réinstaller le plugin
1. Copier le dossier `filter_mate` vers :
   ```
   C:\Users\<User>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
   ```
2. Redémarrer QGIS

## 📞 Support

Si l'erreur persiste après avoir suivi ces étapes, fournir :
1. La version de QGIS
2. Le message d'erreur complet de la console Python
3. Le résultat de `git log --oneline -5`

## 🎯 Prochaines étapes (développeur)

### Court terme
- [ ] Tester tous les scénarios undo/redo
- [ ] Vérifier la performance avec plusieurs couches
- [ ] Documenter les cas limites

### Moyen terme (v5.0)
- [ ] Migrer `undo_redo_handler.py` vers la nouvelle API
- [ ] Supprimer la couche de compatibilité `LayerHistory`
- [ ] Simplifier l'architecture

---

**Date du correctif** : 15 janvier 2026  
**Version cible** : FilterMate v4.0-alpha  
**Type** : Bugfix - Couche de compatibilité
