# Guide de Test Rapide - Améliorations UI FilterMate

**Version**: 2.0  
**Date**: 5 décembre 2025  
**Durée estimée**: 10-15 minutes

---

## 🚀 Démarrage Rapide

### 1. Lancer QGIS et le Plugin
```
1. Ouvrir QGIS 3.44.2
2. Extensions → Gérer et installer les extensions
3. Rechercher "FilterMate"
4. Si désactivé, activer le plugin
5. Le dockwidget devrait apparaître automatiquement
```

### 2. Première Impression Visuelle ✅

**Ce que vous devriez voir immédiatement**:

✅ **Tabs plus compacts**
- Hauteur des onglets EXPLORING/FILTERING/EXPORTING: ~50px (au lieu de 70px)
- Texte plus proche des icônes
- Moins d'espace vide vertical

✅ **Tab actif clairement visible**
- Fond bleu clair
- Barre bleue épaisse à gauche (4px)
- Texte bleu foncé et semi-gras

✅ **Espacements réduits**
- Moins de padding autour des widgets
- Frames plus serrées
- Plus de contenu visible sans scroll

---

## 🎨 Tests Visuels Clés (5 min)

### Test 1: Navigation Tabs
**Actions**:
1. Cliquer sur "EXPLORING"
2. Cliquer sur "FILTERING"
3. Cliquer sur "EXPORTING"

**Vérifications**:
- [ ] Tab actif a fond bleu clair
- [ ] Barre bleue verticale à gauche visible
- [ ] Texte du tab actif en bleu foncé
- [ ] Tabs inactifs en gris

**Capture d'écran suggérée**: Tab FILTERING sélectionné

---

### Test 2: Alignement Inputs
**Actions**:
1. Aller dans tab FILTERING
2. Observer les widgets de saisie (combobox, spinbox, lineedit)

**Vérifications**:
- [ ] Tous les inputs ont la même hauteur (~30px)
- [ ] Alignement horizontal parfait
- [ ] Pas de décalage entre widgets sur même ligne

**Si problème**: Vérifier que default.qss est bien chargé

---

### Test 3: Splitter
**Actions**:
1. Placer la souris entre section EXPLORING (haut) et FILTERING (bas)
2. Le curseur devrait changer en double-flèche ↕
3. Glisser-déposer pour redimensionner

**Vérifications**:
- [ ] Splitter facile à attraper (8px de large)
- [ ] Survol change la couleur (fond bleu)
- [ ] Redimensionnement fluide

---

### Test 4: Boutons Checkables
**Actions**:
1. Dans la barre latérale gauche, cliquer sur les boutons icônes
2. Observer l'état checked vs non-checked

**Vérifications**:
- [ ] État non-checked: fond blanc, texte visible
- [ ] État checked: fond bleu, texte blanc
- [ ] Transition visuelle immédiate
- [ ] Box-shadow visible sur état checked

**Boutons à tester**:
- pushButton_checkable_exploring_selecting
- pushButton_checkable_filtering_auto_current_layer
- pushButton_checkable_exporting_layers

---

### Test 5: Focus Keyboard
**Actions**:
1. Cliquer sur un input (combobox ou spinbox)
2. Appuyer sur Tab plusieurs fois

**Vérifications**:
- [ ] Bordure focus bleue très visible (5px)
- [ ] Fond légèrement teinté bleu
- [ ] Halo externe (box-shadow)
- [ ] Navigation logique entre widgets

---

## 📏 Tests Responsive (3 min)

### Test 6: Largeur Minimale
**Actions**:
1. Redimensionner le dockwidget à sa largeur minimale (421px)
2. Observer les titres de GroupBox

**Vérifications**:
- [ ] Titres longs tronqués avec "..." (ellipse)
- [ ] Pas de chevauchement de texte
- [ ] Widgets restent fonctionnels

---

### Test 7: Hauteur Minimale
**Actions**:
1. Redimensionner le dockwidget à sa hauteur minimale (600px)
2. Observer la présence/absence de scroll

**Vérifications**:
- [ ] Plus de contenu visible qu'avant (gain ~80px)
- [ ] Scroll apparaît naturellement si nécessaire
- [ ] Pas de widgets coupés

---

## 🎯 Tests Interactifs (5 min)

### Test 8: Hover States
**Actions**:
1. Survoler avec la souris (sans cliquer):
   - Boutons
   - Inputs (combobox, spinbox)
   - Tabs

**Vérifications**:
- [ ] Bordure s'épaissit légèrement (2px → 3px)
- [ ] Couleur change légèrement
- [ ] Feedback visuel instantané
- [ ] Curseur devient "main" sur boutons

---

### Test 9: Contraste et Lisibilité
**Actions**:
1. Lire les textes dans différentes zones:
   - Titres de GroupBox
   - Labels de widgets
   - Textes des boutons

**Vérifications**:
- [ ] Tous les textes lisibles
- [ ] Hiérarchie claire (titres vs descriptions)
- [ ] Pas d'éblouissement
- [ ] Contraste suffisant

---

### Test 10: Boutons Désactivés
**Actions**:
1. Identifier un bouton désactivé (grisé)
2. Observer sa visibilité

**Vérifications**:
- [ ] Texte lisible mais clairement désactivé
- [ ] Contraste suffisant (~3.5:1)
- [ ] Pas totalement invisible
- [ ] Distinction claire avec boutons actifs

---

## ✅ Checklist Finale

### Gains Visuels Confirmés
- [ ] **-28% hauteur tabs**: 210px → 150px
- [ ] **+4% largeur utile**: Plus d'espace horizontal
- [ ] **+60% contraste**: Séparation frames/widgets claire
- [ ] **Alignement parfait**: Tous inputs à 30px
- [ ] **Tab actif visible**: Fond bleu + barre gauche

### Pas de Régression
- [ ] Plugin se charge sans erreur
- [ ] Toutes fonctionnalités existantes OK
- [ ] Pas de console Python error
- [ ] Performance équivalente

### Expérience Utilisateur
- [ ] Interface plus compacte
- [ ] Navigation plus intuitive
- [ ] Meilleure lisibilité
- [ ] Design plus moderne

---

## 🐛 Si Problème

### Les styles ne sont pas appliqués
**Cause**: QSS non chargé

**Solution**:
```python
# Vérifier dans QGIS Python Console
from filter_mate.modules.ui_styles import StyleLoader
StyleLoader._styles_cache.clear()  # Clear cache
```

Puis recharger le plugin.

---

### Tabs toujours à 70px
**Cause**: Fichier .qss non sauvegardé ou cache navigateur

**Solution**:
1. Vérifier que `resources/styles/default.qss` contient `min-height: 50px`
2. Redémarrer QGIS complètement
3. Recharger le plugin

---

### Inputs désalignés
**Cause**: Fichier .ui non recompilé

**Solution**:
```bash
cd filter_mate
compile_ui.bat
```

Puis redémarrer QGIS.

---

### Splitter invisible ou trop fin
**Cause**: Fichier .ui non recompilé

**Vérifier**: `filter_mate_dockwidget_base.py` devrait contenir:
```python
self.splitter.setHandleWidth(8)  # Au lieu de 5
```

**Solution**: Recompiler avec `compile_ui.bat`

---

## 📊 Métriques de Succès

| Aspect | Objectif | Status |
|--------|----------|--------|
| Hauteur tabs | 50px | ⬜ À vérifier |
| Splitter handle | 8px | ⬜ À vérifier |
| Inputs alignés | 30px tous | ⬜ À vérifier |
| Tab actif visible | Fond bleu | ⬜ À vérifier |
| Contraste textes | ≥4.5:1 | ⬜ À vérifier |
| Pas d'erreur console | 0 erreurs | ⬜ À vérifier |

---

## 📸 Captures d'Écran Suggérées

1. **Vue d'ensemble**: Dockwidget complet avec tab FILTERING actif
2. **Alignement**: Zoom sur section avec inputs alignés
3. **Tab actif**: Zoom sur tabs montrant la barre bleue gauche
4. **Splitter**: Curseur en position hover sur splitter
5. **Boutons checked**: État checked vs non-checked côte à côte
6. **Focus**: Input avec bordure focus bleue visible

---

## ✨ Prochaines Étapes

### Si tests OK ✅
1. Valider les modifications
2. Commiter avec le message suggéré dans `UI_IMPLEMENTATION_SUMMARY.md`
3. Créer une release note
4. Mettre à jour la documentation utilisateur

### Si ajustements nécessaires 🔧
1. Noter les problèmes spécifiques
2. Consulter section "Problèmes Potentiels" dans `UI_IMPLEMENTATION_SUMMARY.md`
3. Ajuster les valeurs dans `default.qss`
4. Tester à nouveau

---

**Bon test! 🎉**

Si tout fonctionne comme attendu, vous devriez avoir une interface **plus compacte**, **plus claire**, et **plus moderne** tout en conservant toutes les fonctionnalités existantes.
