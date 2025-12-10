# Wildcard Imports Inventory & Tracking

**Date de création:** 10 décembre 2025  
**Objectif:** Éliminer tous les wildcard imports (33 occurrences)  
**Statut global:** 3/33 (9%) 🔄 En cours

---

## 📊 Vue d'ensemble

| Catégorie | Fichiers | Wildcards | Statut |
|-----------|----------|-----------|--------|
| Petits (<500 lignes) | 3 | 5 | ✅ 2/2 Terminés |
| Moyens (500-1500) | 3 | 8 | ⏳ À faire |
| Grands (>1500) | 3 | 20 | ⏳ À faire |
| **Total** | **9** | **33** | **9%** |

---

## 📋 Inventaire Détaillé

### 🟢 Priorité 1 : Petits Fichiers (Semaine 1)

#### 1. modules/constants.py (305 lignes)
- [ ] Aucun wildcard import détecté ✅
- **Statut:** N/A
- **PR:** -
- **Date:** -

#### 2. modules/signal_utils.py (324 lignes)
- [ ] Aucun wildcard import détecté ✅
- **Statut:** N/A
- **PR:** -
- **Date:** -

#### 3. modules/filter_history.py (377 lignes)
- [ ] Aucun wildcard import détecté ✅
- **Statut:** N/A
- **PR:** -
- **Date:** -

### 🟡 Priorité 2 : Fichiers Moyens (Semaine 2)

#### 4. modules/appUtils.py (584 lignes)
- [x] `from qgis.core import *` (ligne 29) → Remplacé par imports explicites
- [x] `from qgis.utils import *` (ligne 30) → Supprimé (non utilisé)
- **Wildcards:** 0/2 ✅
- **Statut:** ✅ Terminé
- **PR:** -
- **Date:** 10 décembre 2025

#### 5. modules/widgets.py (1,202 lignes)
- [ ] `from qgis.PyQt.QtCore import *` (ligne 2)
- [ ] `from qgis.PyQt.QtGui import *` (ligne 3)
- [ ] `from qgis.PyQt.QtWidgets import *` (ligne 4)
- [ ] `from qgis.core import *` (ligne 6)
- [ ] `from qgis.gui import *` (ligne 7)
- **Wildcards:** 5
- **Statut:** ⏳ À faire
- **PR:** -
- **Date:** -

#### 6. filter_mate.py (311 lignes)
- [x] `from .resources import *` (ligne 31) → Conservé (ressources Qt)
- [x] `from .filter_mate_app import *` (ligne 34) → Remplacé par import explicite
- **Wildcards:** 0/1 ✅ (1 conservé pour ressources Qt)
- **Statut:** ✅ Terminé
- **PR:** -
- **Date:** 10 décembre 2025

### 🔴 Priorité 3 : Gros Fichiers (Semaine 3)

#### 7. filter_mate_app.py (1,670 lignes)
- [ ] `from qgis.PyQt.QtCore import *` (ligne 1)
- [ ] `from qgis.PyQt.QtGui import *` (ligne 2)
- [ ] `from qgis.PyQt.QtWidgets import *` (ligne 3)
- [ ] `from qgis.core import *` (ligne 4)
- [ ] `from qgis.utils import *` (ligne 6)
- [ ] `from .config.config import *` (ligne 18)
- [ ] `from .modules.customExceptions import *` (ligne 21)
- [ ] `from .modules.appTasks import *` (ligne 22)
- [ ] `from .resources import *` (ligne 30)
- **Wildcards:** 9
- **Statut:** ⏳ À faire
- **PR:** -
- **Date:** -

#### 8. filter_mate_dockwidget.py (3,832 lignes)
- [ ] `from .config.config import *` (ligne 25)
- [ ] `from qgis.PyQt.QtCore import *` (ligne 37)
- [ ] `from qgis.PyQt.QtGui import *` (ligne 38)
- [ ] `from qgis.PyQt.QtWidgets import *` (ligne 39)
- [ ] `from qgis.core import *` (ligne 40)
- [ ] `from qgis.gui import *` (ligne 41)
- [ ] `from .modules.customExceptions import *` (ligne 49)
- [ ] `from .modules.appUtils import *` (ligne 50)
- **Wildcards:** 8
- **Statut:** ⏳ À faire
- **PR:** -
- **Date:** -

#### 9. modules/appTasks.py (5,653 lignes)
- [ ] `from qgis.PyQt.QtCore import *` (ligne ~?)
- [ ] `from qgis.PyQt.QtGui import *` (ligne ~?)
- [ ] `from qgis.PyQt.QtWidgets import *` (ligne ~?)
- [ ] `from qgis.core import *` (ligne ~?)
- [ ] `from qgis.utils import *` (ligne ~?)
- [ ] `from ..modules.customExceptions import *` (ligne ~?)
- **Wildcards:** ~6
- **Statut:** ⏳ À faire
- **PR:** -
- **Date:** -

---

## 🔧 Processus de Remplacement

### Pour Chaque Fichier :

1. **Créer une branche**
   ```bash
   git checkout -b refactor/remove-wildcards-<filename>
   ```

2. **Identifier les symboles utilisés**
   ```bash
   # Utiliser autoflake pour aide
   autoflake --remove-all-unused-imports <file.py>
   ```

3. **Remplacer manuellement**
   - Lister tous les symboles utilisés
   - Remplacer `import *` par imports explicites
   - Grouper les imports par catégorie

4. **Tester**
   ```bash
   # Tests automatiques
   pytest tests/ -v
   
   # Test manuel dans QGIS
   # Charger le plugin et tester les fonctionnalités
   ```

5. **Commit**
   ```bash
   git add <file.py>
   git commit -m "refactor(imports): remove wildcard imports from <file>"
   ```

6. **Mettre à jour ce document**
   - Cocher la case
   - Ajouter le numéro de PR
   - Noter la date

---

## 📈 Progression

### Par Semaine

**Semaine 1** (11-15 décembre)
- [ ] modules/appUtils.py
- [ ] modules/widgets.py (50% - fichier plus gros)

**Semaine 2** (16-22 décembre)
- [ ] modules/widgets.py (50% restant)
- [ ] filter_mate.py

**Semaine 3** (23-29 décembre)
- [ ] filter_mate_app.py
- [ ] filter_mate_dockwidget.py (30%)

**Semaine 4** (30 déc - 5 jan)
- [ ] filter_mate_dockwidget.py (70% restant)
- [ ] modules/appTasks.py

---

## 🎯 Jalons

### Jalon 1 : Premier Succès ✅
- **Date cible:** 15 décembre
- **Objectif:** 2 fichiers complétés (appUtils.py, filter_mate.py)
- **Validation:** Tests passent, syntaxe valide
- **Date réelle:** 10 décembre 2025 ⚡ (5 jours d'avance)

### Jalon 2 : Fichiers Moyens ⏳
- **Date cible:** 22 décembre
- **Objectif:** 3 fichiers moyens complétés
- **Progression:** 0/3 (0%)

### Jalon 3 : Tous les Fichiers ⏳
- **Date cible:** 5 janvier
- **Objectif:** 33 wildcards éliminés
- **Progression:** 0/33 (0%)

---

## 📝 Notes de Migration

### Patterns Courants à Remplacer

#### qgis.PyQt.QtCore
```python
# Avant
from qgis.PyQt.QtCore import *

# Après (exemple typique)
from qgis.PyQt.QtCore import (
    Qt, QSettings, QTranslator, QCoreApplication,
    QTimer, pyqtSignal, QObject, QVariant,
    QSize, QPoint, QRect, QUrl
)
```

#### qgis.PyQt.QtWidgets
```python
# Avant
from qgis.PyQt.QtWidgets import *

# Après (exemple typique)
from qgis.PyQt.QtWidgets import (
    QAction, QApplication, QMenu, QMessageBox,
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox
)
```

#### qgis.core
```python
# Avant
from qgis.core import *

# Après (exemple typique)
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsTask, QgsFeature,
    QgsGeometry, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsMessageLog, Qgis,
    QgsExpressionContextUtils, QgsRectangle
)
```

### Outils Utiles

```bash
# Trouver tous les symboles QGIS utilisés
grep -o "Qgs[A-Za-z]*" file.py | sort -u

# Trouver tous les symboles Qt utilisés
grep -o "Q[A-Z][A-Za-z]*" file.py | sort -u

# Compter les wildcards
grep -c "from .* import \*" file.py
```

---

## ⚠️ Risques et Atténuation

### Risques Identifiés

1. **Casser la compatibilité**
   - Mitigation : Tests après chaque changement
   - Rollback facile avec git

2. **Oublier des imports**
   - Mitigation : Tests complets dans QGIS
   - Vérification manuelle de toutes les fonctionnalités

3. **Conflits de noms**
   - Mitigation : Imports explicites montrent les conflits
   - Résolution avec alias : `import X as Y`

### Plan B

Si un fichier pose trop de problèmes :
1. Revenir à la version précédente (`git checkout`)
2. Créer une issue pour documentation
3. Passer au fichier suivant
4. Revenir plus tard avec plus d'information

---

## 📊 Métriques de Succès

| Métrique | Objectif | Actuel | Statut |
|----------|----------|--------|--------|
| Wildcards éliminés | 33 | 3 | 🔄 9% |
| Fichiers traités | 9 | 2 | 🔄 22% |
| Tests qui passent | 100% | 100% | ✅ |
| Régressions | 0 | 0 | ✅ |

---

## 🏆 Célébrations

### Premiers Succès
- [x] Premier fichier sans wildcard (appUtils.py) ✅ 10 déc 2025
- [x] Deuxième fichier terminé (filter_mate.py) ✅ 10 déc 2025
- [ ] Premier PR mergé
- [ ] 50% des wildcards éliminés
- [ ] 100% des wildcards éliminés 🎉

---

**Dernière mise à jour:** 10 décembre 2025  
**Prochaine revue:** 15 décembre 2025  
**Responsable:** Équipe de développement
