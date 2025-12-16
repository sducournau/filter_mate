# Correction du problème de démarrage après renommage

## Problème
Après l'exécution du script `remove_ui_suffixes.py` et la recompilation avec `compile_ui.bat`, le plugin FilterMate ne démarrait plus dans QGIS.

## Cause
Le générateur PyQt5 (`pyuic5`) a créé des imports incorrects à la fin du fichier `filter_mate_dockwidget_base.py`. Au lieu d'importer les widgets QGIS depuis `qgis.gui`, il a généré des imports invalides comme :

```python
from qgscheckablecombobox import QgsCheckableComboBox
from qgscollapsiblegroupbox import QgsCollapsibleGroupBox
# etc.
```

Ces modules n'existent pas en tant que modules Python autonomes - ils font partie du package `qgis.gui`.

## Solution appliquée
Les imports incorrects ont été remplacés par l'import correct :

```python
from qgis.gui import (
    QgsCheckableComboBox,
    QgsCollapsibleGroupBox,
    QgsDoubleSpinBox,
    QgsFeaturePickerWidget,
    QgsFieldExpressionWidget,
    QgsMapLayerComboBox,
    QgsProjectionSelectionWidget,
    QgsPropertyOverrideButton
)
```

## Fichiers modifiés
- `filter_mate_dockwidget_base.py` : Correction des imports à la ligne 1585

## Actions effectuées
1. ✅ Identification du problème d'import
2. ✅ Correction des imports dans `filter_mate_dockwidget_base.py`
3. ✅ Nettoyage du cache Python (`__pycache__` et `*.pyc`)

## Prochaines étapes
1. Redémarrer QGIS
2. Tester le plugin FilterMate
3. Si le problème persiste, consulter les logs dans la console Python de QGIS (Ctrl+Alt+P)

## Pour éviter ce problème à l'avenir

### Option 1: Post-processing du fichier généré
Après chaque compilation avec `compile_ui.bat`, vérifier automatiquement les imports incorrects :

```bat
REM Ajouter à compile_ui.bat après la compilation
python remove_incorrect_imports.py
```

### Option 2: Utiliser un script Python pour la compilation
Remplacer `compile_ui.bat` par un script Python qui :
1. Compile le .ui avec pyuic5
2. Post-traite le fichier pour corriger les imports
3. Valide les imports

### Option 3: Utiliser Qt Designer avec précaution
Les imports incorrects sont générés par pyuic5 à partir des déclarations `<customwidget>` dans le fichier .ui. S'assurer que Qt Designer utilise les bonnes déclarations de widgets QGIS.

## Notes techniques
- Le problème existe aussi dans le fichier `.backup`, ce qui indique qu'il était présent avant le renommage
- Le renommage n'a fait que révéler le problème en nécessitant une recompilation
- Les widgets QGIS doivent TOUJOURS être importés depuis `qgis.gui` ou `qgis.core`, jamais depuis des modules séparés

## Date de correction
2025-12-14
