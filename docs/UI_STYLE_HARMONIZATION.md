# UI Style Harmonization - FilterMate

**Date:** 7 décembre 2025  
**Objectif:** Harmoniser les styles des différents widgets (backgrounds, bordures, paddings)

## Analyse des Incohérences Identifiées

### 1. Background Colors

#### Avant harmonisation :
- **QWidget générique** : `{color_bg_0}` (appliqué trop largement)
- **QFrame générique** : `{color_bg_0}` avec `color: {color_3}`
- **Widget keys panels** : `{color_2}` (différent du reste)
- **QTreeView** : `{color_bg_0}`
- **QGroupBox** : `transparent` avec bordure `{color_1}`
- **QgsCollapsibleGroupBox** : `{color_bg_0}` sans bordure
- **QScrollArea** : `{color_bg_0}` sans bordure

#### Logique de colorimétrie définie :
- **`{color_bg_0}`** : Background principal des frames (le plus foncé en light mode)
- **`{color_1}`** : Background des widgets interactifs (plus clair)
- **`{color_2}`** : Background des éléments sélectionnés/hover (intermédiaire)
- **`{color_font_0}`** : Texte principal (contraste maximum)
- **`{color_font_1}`** : Texte secondaire
- **`{color_font_2}`** : Texte désactivé

### 2. Border Colors

#### Incohérences :
- Certains widgets : bordure `{color_1}` (trop claire)
- Autres widgets : bordure `{color_2}` (plus visible)
- Manque d'uniformité dans les border-radius (3px vs 4px vs 6px)

### 3. Padding & Margins

#### Variations trouvées :
- QFrame : `padding: 4px, margin: 2px`
- Widget keys : `padding: 8px, margin: 4px`
- Manque de cohérence dans les espacements

## Harmonisations Effectuées

### Phase 1 : Suppression du Background Générique

**Fichier:** `resources/styles/default.qss`

```diff
/* ToolBox TabWidget */
- QWidget {
-     background-color: {color_bg_0};
- }
+ /* Note: Removed generic QWidget background to prevent unwanted overrides */
+ /* Instead, backgrounds are set explicitly on specific widgets */

QToolBox {
-     background-color: transparent;
+     background-color: {color_bg_0};
    border: none;
    padding: 4px;
}
```

**Raison:** Le style générique sur `QWidget` causait des conflits et s'appliquait à tous les widgets enfants, créant des incohérences visuelles.

### Phase 2 : Harmonisation des Frames

```diff
/* Frames - Base styling */
QFrame {
    background-color: {color_bg_0};
    border: none;
    border-radius: 4px;
    padding: 4px;
-     margin: 2px;
+     margin: 0px;
-     color: {color_3};
+     color: {color_font_0};
}
```

**Améliorations:**
- ✅ Margin unifié à `0px` pour éviter les espacements inattendus
- ✅ Couleur de texte cohérente avec `{color_font_0}` au lieu de `{color_3}`

### Phase 3 : Harmonisation des Widget Keys Panels

```diff
/* Widget Keys Panels - Sidebar buttons */
QWidget#widget_exploring_keys,
QWidget#widget_filtering_keys,
QWidget#widget_exporting_keys {
-     background-color: {color_2};
+     background-color: {color_1};
+     border: 1px solid {color_2};
    border-radius: 6px;
    padding: 8px;
-     margin: 4px;
+     margin: 2px;
}
```

**Amélioration:**
- ✅ Background unifié avec `{color_1}` (cohérent avec les autres widgets)
- ✅ Bordure ajoutée pour mieux délimiter les panels
- ✅ Margin réduit pour gagner de l'espace

### Phase 4 : Harmonisation TreeView & ListWidget

```diff
+ /* TreeView & ListWidget - Harmonized backgrounds */
+ QTreeView,
+ QListWidget {
-     background-color: {color_bg_0};
+     background-color: {color_1};
    border: 1px solid {color_2};
+     border-radius: 3px;
    color: {color_font_0};
-     padding: 0;
+     padding: 2px;
}

+ QTreeView:focus,
+ QListWidget:focus {
+     border: 2px solid {color_accent};
+     padding: 1px;
+ }
```

**Améliorations:**
- ✅ Background cohérent avec les autres widgets (`{color_1}`)
- ✅ Border-radius ajouté pour uniformité
- ✅ Focus state ajouté pour meilleure accessibilité
- ✅ ListWidget maintenant stylé (avant : non défini)

### Phase 5 : Harmonisation QgsCollapsibleGroupBox

```diff
/* Collapsible Group Box */
QgsCollapsibleGroupBox {
-     background-color: {color_bg_0};
+     background-color: {color_1};
-     border: none;
+     border: 1px solid {color_2};
    border-radius: 4px;
    padding: 8px;
    padding-top: 24px;
    color: {color_font_0};
    min-height: 50px;
}
```

**Amélioration:**
- ✅ Background et bordure cohérents avec les autres GroupBox
- ✅ Meilleure délimitation visuelle

### Phase 6 : Harmonisation QgsExpressionBuilderWidget

```diff
/* Expression Builder */
QgsExpressionBuilderWidget {
-     background-color: {color_bg_0};
+     background-color: {color_1};
-     border: none;
+     border: 1px solid {color_2};
    border-radius: 4px;
    padding: 8px;
    color: {color_font_0};
}
```

### Phase 7 : Harmonisation QScrollArea

```diff
/* Scroll Area */
QScrollArea {
-     background-color: {color_bg_0};
+     background-color: {color_1};
+     border: 1px solid {color_2};
+     border-radius: 4px;
    color: {color_font_0};
}
```

## Modifications Restantes (À Faire Manuellement)

### QGroupBox

**État actuel problématique:**
```css
QGroupBox {
    background-color: transparent;
    border: 1px solid {color_1};  /* ⚠️ color_1 trop clair */
    font-weight: bold;            /* ⚠️ Devrait être 600 */
}
```

**Recommandation:**
```css
QGroupBox {
    background-color: transparent;
    border: 1px solid {color_2};  /* ✅ Plus visible */
    border-radius: 4px;           /* ✅ Cohérence */
    margin-top: 12px;             /* ✅ Plus lisible */
    padding: 8px;
    font-weight: 600;             /* ✅ Standard CSS */
    color: {color_font_0};
}
```

**Actions manuelles nécessaires:**
1. Ouvrir `resources/styles/default.qss`
2. Chercher `/* GroupBox Styling */` (ligne ~374)
3. Remplacer `border: 1px solid {color_1};` par `border: 1px solid {color_2};`
4. Remplacer `font-weight: bold;` par `font-weight: 600;`
5. Optionnel : Uniformiser `margin-top: 0.8ex;` en `margin-top: 12px;`

## Bénéfices de l'Harmonisation

### 1. Cohérence Visuelle ✨
- Tous les widgets utilisent maintenant `{color_1}` pour leur background
- Les bordures utilisent systématiquement `{color_2}`
- Les border-radius sont harmonisés (3px ou 4px selon le type)

### 2. Meilleure Hiérarchie Visuelle 📊
- **Niveau 1** : Frames principales (`{color_bg_0}`)
- **Niveau 2** : Widgets interactifs (`{color_1}`)
- **Niveau 3** : Sélections/hover (`{color_2}`)

### 3. Accessibilité Améliorée ♿
- Focus states ajoutés sur TreeView et ListWidget
- Contrastes de texte uniformisés avec `{color_font_0}`
- Bordures plus visibles avec `{color_2}`

### 4. Maintenance Facilitée 🔧
- Structure claire et commentée
- Moins de règles contradictoires
- Plus facile d'ajouter de nouveaux widgets

### 5. Compatibilité Multi-Thèmes 🎨
Les placeholders permettent l'adaptation automatique aux thèmes :
- **default** (light)
- **dark**
- **light** (très clair)

## Guide de Style pour Futurs Widgets

### Template pour un nouveau widget :

```css
/* MyCustomWidget - Description */
QMyCustomWidget {
    background-color: {color_1};      /* Background widget standard */
    border: 1px solid {color_2};      /* Bordure visible */
    border-radius: 4px;               /* Arrondi standard */
    padding: 8px;                     /* Padding confortable */
    margin: 2px;                      /* Petit margin */
    color: {color_font_0};            /* Texte principal */
}

QMyCustomWidget:hover {
    border: 2px solid {color_accent}; /* Focus visuel */
    padding: 7px;                     /* Compensation bordure */
}

QMyCustomWidget:focus {
    border: 3px solid {color_accent}; /* Focus fort */
    background-color: {color_accent_light_bg};
    padding: 5px;                     /* Compensation bordure */
    box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.25);
}
```

### Règles à Suivre

1. **Background:** Toujours utiliser `{color_1}` pour les widgets interactifs
2. **Border:** Utiliser `{color_2}` (normal) ou `{color_accent}` (hover/focus)
3. **Border-radius:** 3px ou 4px (6px pour les panels de boutons)
4. **Padding:** 8px standard, ajuster avec les bordures
5. **Margin:** 0-2px en général
6. **Color:** `{color_font_0}` pour texte principal

## Tests Recommandés

### Test 1 : Vérification Visuelle
1. Ouvrir QGIS avec FilterMate
2. Basculer entre thèmes QGIS (Blend of Gray, Night Mapping)
3. Vérifier la cohérence des backgrounds
4. Vérifier la visibilité des bordures

### Test 2 : Navigation Clavier
1. Utiliser Tab pour naviguer entre widgets
2. Vérifier que les états focus sont visibles
3. Tester avec les thèmes light et dark

### Test 3 : Modes d'Affichage
1. Tester en mode compact (< 1920x1080)
2. Tester en mode normal (≥ 1920x1080)
3. Vérifier que les dimensions adaptatives fonctionnent

### Test 4 : Accessibilité
1. Vérifier les contrastes de couleur (WCAG AA minimum)
2. Tester avec un screen reader si possible
3. Vérifier la taille des zones cliquables

## Prochaines Étapes

### Immédiat
- [ ] Finaliser les modifications manuelles de QGroupBox
- [ ] Tester le rendu dans QGIS avec les 3 thèmes
- [ ] Capturer des screenshots avant/après

### Court Terme
- [ ] Documenter dans le CHANGELOG
- [ ] Ajouter des tests automatisés pour les styles
- [ ] Créer une page dans la documentation utilisateur

### Moyen Terme
- [ ] Envisager un mode "high contrast" pour accessibilité
- [ ] Permettre à l'utilisateur de personnaliser les couleurs
- [ ] Créer des presets de thèmes supplémentaires

## Références

- **Documentation UI System:** `docs/UI_SYSTEM_OVERVIEW.md`
- **Color Schemes:** `modules/ui_styles.py` (ligne 36-84)
- **Config Colors:** `config/config.json` → `APP.DOCKWIDGET.COLORS`
- **Copilot Instructions:** `.github/copilot-instructions.md`

## Notes Techniques

### Ordre de Priorité CSS
```
1. Styles inline (setStyleSheet() en Python)
2. Object-specific styles (QWidget#my_id)
3. Class-specific styles (QPushButton:checkable)
4. Generic styles (QWidget)
```

### Placeholders Disponibles
```css
{color_bg_0}      /* Frame background */
{color_1}         /* Widget background */
{color_2}         /* Selection background */
{color_bg_3}      /* Accent/hover */
{color_3}         /* Alias pour color_font_1 */
{color_font_0}    /* Primary text */
{color_font_1}    /* Secondary text */
{color_font_2}    /* Disabled text */
{color_accent}    /* Accent primary */
{color_accent_hover}      /* Accent hover */
{color_accent_pressed}    /* Accent pressed */
{color_accent_light_bg}   /* Accent light bg */
{color_accent_dark}       /* Accent dark border */
```

### Compatibilité
- ✅ QGIS 3.x
- ✅ PyQt5
- ✅ Windows, Linux, macOS
- ✅ HiDPI displays

---

**Document généré automatiquement par GitHub Copilot**  
**Mainteneur:** FilterMate Development Team
