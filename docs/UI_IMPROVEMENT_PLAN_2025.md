# Plan d'Amélioration UI FilterMate - Décembre 2025

**Date de création**: 5 décembre 2025  
**Version**: 2.0  
**Statut**: 📋 Plan détaillé prêt pour implémentation

---

## 🎯 Objectifs Principaux

Suite à l'analyse approfondie du codebase, voici les objectifs d'amélioration identifiés :

1. **Optimiser les marges et paddings** - Réduire l'espacement excessif et améliorer la densité d'information
2. **Améliorer l'alignement** - Assurer une cohérence visuelle entre les sections
3. **Ajuster les couleurs de fond et frames** - Meilleure distinction hiérarchique et lisibilité
4. **Améliorer la visibilité des textes** - Contraste et tailles de police optimisés
5. **Corriger les titres tronqués** - Augmenter l'espace disponible pour les labels des panneaux

---

## 📊 Analyse des Problèmes Identifiés

### 1. ❌ Problèmes de Marges et Padding

#### A. Frames principaux (Exploring, Toolset, Actions)
**Localisation**: `filter_mate_dockwidget_base.ui` + `default.qss`

**Problèmes détectés**:
```css
/* QFrame général - padding trop important */
QFrame {
    padding: 8px;    /* ❌ Trop d'espace perdu */
    margin: 4px;     /* ❌ Marges inutiles entre frames */
}

/* frame_toolset - sans padding (incohérent) */
QFrame#frame_toolset {
    padding: 0px;    /* ❌ Incohérent avec autres frames */
    margin: 0px;
}
```

**Impact**:
- 16px de padding horizontal total = perte de 32px de largeur utile sur un dockwidget de 421px (7.6%)
- Incohérence visuelle entre les sections
- Sensation d'encombrement

#### B. QToolBox - Tabs trop hauts
**Localisation**: `default.qss` lignes 108-130

**Problèmes détectés**:
```css
QToolBox::tab {
    padding: 0px;
    margin: 3px;              /* ❌ Espacement vertical inutile */
    min-height: 70px;         /* ❌ TROP HAUT - gaspille l'espace */
    max-height: 70px;
}

QToolBox QToolButton {
    padding: 22px 15px 22px 40px;  /* ❌ Padding vertical excessif (44px total) */
    min-height: 70px;
}
```

**Impact**:
- Tabs occupent 70px de hauteur pour 3 onglets = **210px minimum** (22% d'un écran 939px de haut)
- Icônes et texte ont beaucoup trop d'espace vide autour
- Force le scroll inutilement

#### C. GroupBox et Collapsible GroupBox
**Localisation**: `default.qss` lignes 367-380, 213-232

**Problèmes détectés**:
```css
QGroupBox {
    margin-top: 1ex;          /* ❌ Espacement standardisé mais peut être réduit */
    padding: 12px;            /* ❌ Padding uniforme trop généreux */
}

QgsCollapsibleGroupBox {
    padding: 12px;
    padding-top: 32px;        /* ❌ 32px pour le titre = beaucoup trop */
}
```

**Impact**:
- Perte d'espace vertical dans les sections avec multiples GroupBox
- Titre du collapsible trop espacé du contenu

#### D. Widgets de saisie - Padding incohérent
**Localisation**: `default.qss` lignes 20-65, 505-575

**Problèmes détectés**:
```css
/* Combobox */
QComboBox {
    padding: 7px 5px;         /* ✅ Correct */
    min-height: 30px;
}

/* SpinBox */
QSpinBox, QDoubleSpinBox {
    padding: 8px;             /* ❌ Plus que combobox (incohérent) */
    min-height: 28px;         /* ❌ Plus petit que combobox */
}

/* LineEdit */
QLineEdit {
    padding: 8px;             /* ❌ Incohérent avec combobox */
    min-height: 28px;
}
```

**Impact**:
- Alignement visuel perturbé entre les widgets d'une même ligne
- Hauteurs différentes créent un effet "dentelé"

### 2. ❌ Problèmes d'Alignement

#### A. Splitter handle - Width inappropriée
**Localisation**: `filter_mate_dockwidget_base.ui` ligne 289

**Problème détecté**:
```xml
<property name="handleWidth">
    <number>5</number>  <!-- ❌ Trop fin, difficile à saisir -->
</property>
```

**Impact**:
- Difficile à attraper avec la souris pour redimensionner
- Pas de feedback visuel clair

#### B. Layouts imbriqués - Espacements cumulés
**Localisation**: Multiple dans `.ui` (gridLayout > verticalLayout > gridLayout)

**Problème détecté**:
```xml
<!-- Pas de définition explicite de contentMargins/spacing -->
<!-- Valeurs par défaut Qt appliquées = espacements cumulés -->
<layout class="QVBoxLayout" name="verticalLayout_2">
    <item>
        <layout class="QGridLayout" name="gridLayout_2">
            <item row="0" column="0">
                <layout class="QGridLayout" name="gridLayout">
                    <!-- Marges cumulées à chaque niveau -->
```

**Impact**:
- Espacements non contrôlés qui s'additionnent
- Perte d'espace horizontal et vertical significative

#### C. Spacers - Usage excessif
**Localisation**: Multiple `horizontalSpacer_3`, `verticalSpacer_9` dans `.ui`

**Problème détecté**:
```xml
<spacer name="horizontalSpacer_3">
    <property name="sizeType">
        <enum>QSizePolicy::Fixed</enum>  <!-- ❌ Spacer fixe de 5px -->
    </property>
    <property name="sizeHint" stdset="0">
        <size>
            <width>5</width>
            <height>20</height>
        </size>
    </property>
</spacer>
```

**Impact**:
- Décalages horizontaux inutiles de 5px à gauche de certains widgets
- Alignement perturbé entre les sections

### 3. ❌ Problèmes de Couleurs (Fond et Frames)

#### A. Contraste insuffisant entre niveaux hiérarchiques
**Localisation**: `modules/ui_styles.py` lignes 28-50

**Problèmes détectés**:
```python
COLOR_SCHEMES = {
    'default': {
        'color_bg_0': '#F5F5F5',   # Frame background
        'color_1': '#FFFFFF',      # Widget background
        'color_2': '#DADADA',      # Selected items
        # ❌ Problème: bg_0 et color_1 trop proches (∆E < 5)
        # Difficile de distinguer frame du contenu
    }
}
```

**Impact**:
- Manque de séparation visuelle entre frame et widgets
- Hiérarchie d'information peu claire

#### B. Frame Actions - Fond trop visible
**Localisation**: `default.qss` lignes 873-880

**Problème détecté**:
```css
QFrame#frame_actions {
    background-color: {color_2};   /* ❌ Fond gris attire trop l'œil */
    border-radius: 6px;
    padding: 8px;
    margin: 4px;
}
```

**Impact**:
- Section Actions en bas visuellement trop proéminente
- Devrait être plus discrète (boutons secondaires)

#### C. QToolBox - Contraste tab sélectionné insuffisant
**Localisation**: `default.qss` lignes 132-138

**Problème détecté**:
```css
QToolBox::tab:selected {
    background-color: {color_2};      /* ❌ Même couleur que hover */
    color: {color_font_0};
    font-weight: 500;
    border: 1px solid {color_bg_3};   /* ❌ Bordure bleue peu visible */
}
```

**Impact**:
- Tab active pas assez distincte des autres
- Utilisateur peut perdre le contexte de navigation

### 4. ❌ Problèmes de Visibilité des Textes

#### A. Labels - Contraste limite
**Localisation**: Pas de style explicite pour QLabel dans `default.qss`

**Problème détecté**:
- Aucune règle CSS pour `QLabel` définie
- Hérite des couleurs génériques `color_font_0` (#1A1A1A) sur `color_bg_0` (#F5F5F5)
- Ratio de contraste : **11.7:1** (✅ WCAG AAA mais peut sembler trop fort sur certains écrans)

**Impact**:
- Textes des labels peuvent manquer de hiérarchie visuelle
- Pas de distinction entre labels primaires et secondaires

#### B. Textes désactivés - Trop faibles
**Localisation**: `default.qss` ligne 37

**Problème détecté**:
```css
'color_font_2': '#9E9E9E',    /* Disabled text */
/* + opacity: 0.4 appliquée sur boutons disabled */
```

**Impact**:
- Textes désactivés parfois illisibles (contraste < 3:1)
- Non conforme WCAG même pour textes secondaires

#### C. Boutons checkables - Texte non gras par défaut
**Localisation**: `default.qss` ligne 430

**Problème détecté**:
```css
QPushButton:checkable {
    font-weight: 500;   /* ❌ Normal, pas assez distinct */
}

QPushButton:checkable:checked {
    font-weight: 700;   /* ✅ Gras seulement quand checked */
}
```

**Impact**:
- État non-checked pas assez visible
- Utilisateur ne sait pas toujours qu'il peut cliquer

### 5. ❌ Titres Tronqués des Panneaux

#### A. QToolBox tabs - Texte coupé
**Localisation**: `filter_mate_dockwidget_base.ui` (tabs FILTERING, EXPLORING, EXPORTING)

**Problèmes détectés**:
```xml
<!-- Dockwidget width -->
<width>421</width>

<!-- Tab button padding excessif à gauche -->
QToolBox QToolButton {
    padding: 22px 15px 22px 40px;   /* ❌ 40px à gauche pour icône */
}
```

**Impact avec textes**:
- "FILTERING" = ~90px (estimation police 10pt Segoe UI Semibold)
- "EXPLORING" = ~95px
- "EXPORTING" = ~95px
- Espace disponible : 421px - 40px (left) - 15px (right) = **366px** ✅ OK actuellement
- **MAIS**: Si icônes alignées à gauche + texte long, risque de troncature

**Cas problématiques potentiels**:
- Ajout d'onglets futurs avec noms plus longs
- Traductions i18n (langues avec mots composés)

#### B. GroupBox titles - Positionnement fixe
**Localisation**: `default.qss` lignes 372-377

**Problème détecté**:
```css
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;             /* ❌ Padding minimal */
    color: {color_font_0};
}
```

**Impact**:
- Titre peut déborder si texte long
- Pas d'ellipse automatique
- Peut chevaucher bordure du groupbox

#### C. Collapsible GroupBox - Titre mal positionné
**Localisation**: `default.qss` lignes 226-233

**Problème détecté**:
```css
QgsCollapsibleGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    margin-left: 20px;          /* ❌ Espace pour checkbox collapse */
    margin-top: 4px;
    left: 0px;
    top: 6px;
}
```

**Impact**:
- Titre décalé de 20px pour faire place à la checkbox
- Si texte long, peut dépasser la largeur disponible
- Pas de gestion du text-overflow

---

## 🎨 Solutions Proposées

### Phase 1: Optimisation des Marges et Padding (Priorité HAUTE) 🔴

#### 1.1 Réduire les paddings des frames principaux

**Fichier**: `resources/styles/default.qss`

**Modifications**:
```css
/* AVANT */
QFrame {
    background-color: {color_bg_0};
    border: none;
    border-radius: 4px;
    padding: 8px;
    margin: 4px;
    color: {color_3};
}

/* APRÈS */
QFrame {
    background-color: {color_bg_0};
    border: none;
    border-radius: 4px;
    padding: 4px;              /* Réduit de 8px → 4px (-50%) */
    margin: 2px;               /* Réduit de 4px → 2px (-50%) */
    color: {color_3};
}
```

**Impact**:
- Gain horizontal: **16px** (8px × 2 côtés)
- Gain vertical: **8px** par frame
- Largeur utile: 421px → **437px** (+3.8%)

#### 1.2 Réduire la hauteur des tabs QToolBox

**Fichier**: `resources/styles/default.qss`

**Modifications**:
```css
/* AVANT */
QToolBox::tab {
    background-color: {color_1};
    border: 1px solid {color_1};
    border-radius: 4px;
    padding: 0px;
    margin: 3px;
    color: {color_font_0};
    font-weight: normal;
    min-height: 70px;           /* ❌ Trop haut */
    max-height: 70px;
}

QToolBox QToolButton {
    background-color: transparent;
    border: none;
    padding: 22px 15px 22px 40px;   /* ❌ Padding vertical excessif */
    min-height: 70px;
    max-height: 70px;
    height: 70px;
    color: {color_font_0};
    font-weight: normal;
    text-align: left;
}

/* APRÈS */
QToolBox::tab {
    background-color: {color_1};
    border: 1px solid {color_1};
    border-radius: 4px;
    padding: 0px;
    margin: 2px;                /* Réduit de 3px → 2px */
    color: {color_font_0};
    font-weight: normal;
    min-height: 50px;           /* Réduit de 70px → 50px (-28%) */
    max-height: 50px;
}

QToolBox QToolButton {
    background-color: transparent;
    border: none;
    padding: 12px 15px 12px 40px;   /* Réduit vertical: 22px → 12px */
    min-height: 50px;
    max-height: 50px;
    height: 50px;
    color: {color_font_0};
    font-weight: normal;
    text-align: left;
}
```

**Impact**:
- Gain vertical: **60px** pour 3 onglets (20px × 3)
- Hauteur tabs: 210px → **150px** (-28%)
- Libère espace pour contenu

#### 1.3 Harmoniser le padding des widgets de saisie

**Fichier**: `resources/styles/default.qss`

**Modifications**:
```css
/* Uniformiser tous les inputs à padding: 6px et min-height: 30px */

/* Combobox - OK, juste ajuster */
QComboBox {
    background-color: {color_1};
    border: 1px solid {color_2};
    border-radius: 3px;
    padding: 6px 5px;           /* Ajusté: 7px → 6px */
    color: {color_font_0};
    min-height: 30px;           /* ✅ Maintenu */
}

/* SpinBox - Harmoniser */
QSpinBox, QDoubleSpinBox, QgsDoubleSpinBox {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 4px;
    padding: 6px;               /* Réduit: 8px → 6px */
    color: {color_font_0};
    min-height: 30px;           /* Augmenté: 28px → 30px */
}

/* LineEdit - Harmoniser */
QLineEdit {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 4px;
    padding: 6px;               /* Réduit: 8px → 6px */
    color: {color_font_0};
    min-height: 30px;           /* Augmenté: 28px → 30px */
}
```

**Impact**:
- Alignement parfait des widgets sur une même ligne
- Hauteur cohérente = meilleure harmonie visuelle
- Padding réduit = plus d'espace pour le texte

#### 1.4 Réduire le padding des GroupBox

**Fichier**: `resources/styles/default.qss`

**Modifications**:
```css
/* AVANT */
QGroupBox {
    background-color: transparent;
    border: 1px solid {color_1};
    border-radius: 3px;
    margin-top: 1ex;
    padding: 12px;
    font-weight: bold;
    color: {color_font_0};
}

QgsCollapsibleGroupBox {
    background-color: {color_bg_0};
    border: none;
    border-radius: 4px;
    padding: 12px;
    padding-top: 32px;
    color: {color_font_0};
    min-height: 50px;
}

/* APRÈS */
QGroupBox {
    background-color: transparent;
    border: 1px solid {color_1};
    border-radius: 3px;
    margin-top: 0.8ex;          /* Réduit: 1ex → 0.8ex */
    padding: 8px;               /* Réduit: 12px → 8px (-33%) */
    font-weight: bold;
    color: {color_font_0};
}

QgsCollapsibleGroupBox {
    background-color: {color_bg_0};
    border: none;
    border-radius: 4px;
    padding: 8px;               /* Réduit: 12px → 8px */
    padding-top: 24px;          /* Réduit: 32px → 24px (-25%) */
    color: {color_font_0};
    min-height: 50px;
}
```

**Impact**:
- Gain vertical: **8px** par GroupBox (top) + **8px** (bottom) = 16px
- Contenu des groups plus compact et dense
- Moins de scroll nécessaire

### Phase 2: Amélioration de l'Alignement (Priorité HAUTE) 🔴

#### 2.1 Augmenter la largeur du splitter handle

**Fichier**: `filter_mate_dockwidget_base.ui`

**Modification**:
```xml
<!-- AVANT -->
<property name="handleWidth">
    <number>5</number>
</property>

<!-- APRÈS -->
<property name="handleWidth">
    <number>8</number>  <!-- Augmenté de 5px → 8px (+60%) -->
</property>
```

**Impact**:
- Handle plus facile à saisir avec la souris
- Meilleure affordance

#### 2.2 Définir explicitement les marges des layouts

**Fichier**: `filter_mate_dockwidget_base.ui`

**Modification**: Ajouter sur TOUS les layouts principaux

```xml
<!-- Exemple pour verticalLayout_5 (layout principal) -->
<layout class="QVBoxLayout" name="verticalLayout_5">
    <property name="spacing">
        <number>4</number>        <!-- Espacement entre items: 4px -->
    </property>
    <property name="leftMargin">
        <number>2</number>        <!-- Marge gauche: 2px -->
    </property>
    <property name="topMargin">
        <number>2</number>        <!-- Marge haut: 2px -->
    </property>
    <property name="rightMargin">
        <number>2</number>        <!-- Marge droite: 2px -->
    </property>
    <property name="bottomMargin">
        <number>2</number>        <!-- Marge bas: 2px -->
    </property>
    <!-- items... -->
</layout>
```

**Layouts à modifier** (liste non exhaustive):
- `verticalLayout_5` (ligne 259)
- `verticalLayout_2` (ligne 342)
- `gridLayout_2` (ligne 363)
- `gridLayout` (ligne 365)
- `verticalLayout_3` (frame_toolset, ligne ~1314)
- `horizontalLayout_5` (FILTERING tab)
- `horizontalLayout_6` (EXPLORING tab)
- `horizontalLayout_7` (EXPORTING tab)

**Impact**:
- Contrôle total des espacements
- Évite les marges par défaut cumulées
- Gain potentiel: **10-20px** horizontal et vertical

#### 2.3 Supprimer les spacers fixes inutiles

**Fichier**: `filter_mate_dockwidget_base.ui`

**Modification**: Supprimer les spacers horizontaux fixes

**Spacers à supprimer**:
- `horizontalSpacer_3` (ligne ~370) : 5px fixe à gauche
- Tous les spacers `QSizePolicy::Fixed` horizontaux de 5px

**Conserver**:
- Spacers `QSizePolicy::Expanding` (utiles pour centrage)
- Spacers verticaux flexibles pour espacement items

**Impact**:
- Alignement cohérent sans décalages artificiels
- Gain horizontal: **5-10px** par section

### Phase 3: Optimisation des Couleurs (Priorité MOYENNE) 🟡

#### 3.1 Augmenter le contraste hiérarchique

**Fichier**: `modules/ui_styles.py`

**Modification**:
```python
# AVANT
COLOR_SCHEMES = {
    'default': {
        'color_bg_0': '#F5F5F5',      # Frame background
        'color_1': '#FFFFFF',         # Widget background
        'color_2': '#DADADA',         # Selected items
    }
}

# APRÈS
COLOR_SCHEMES = {
    'default': {
        'color_bg_0': '#EFEFEF',      # Frame background (plus foncé: F5→EF)
        'color_1': '#FFFFFF',         # Widget background (maintenu)
        'color_2': '#D0D0D0',         # Selected items (plus foncé: DA→D0)
    }
}
```

**Impact**:
- ∆E (bg_0 vs color_1) : ~5 → **~8** (+60% de contraste)
- Séparation visuelle frames/widgets plus claire
- Hiérarchie d'information améliorée

#### 3.2 Réduire la visibilité du frame_actions

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QFrame#frame_actions {
    background-color: {color_2};
    border-radius: 6px;
    padding: 8px;
    margin: 4px;
}

/* APRÈS */
QFrame#frame_actions {
    background-color: transparent;      /* Plus de fond gris */
    border-top: 1px solid {color_2};    /* Bordure subtile en haut */
    border-radius: 0px;                 /* Plus de coins arrondis */
    padding: 6px 4px;                   /* Padding réduit */
    margin: 0px;                        /* Plus de marge */
}
```

**Impact**:
- Boutons actions moins proéminents visuellement
- Focus utilisateur sur le contenu principal
- Gain vertical: **2px** (padding) + **8px** (margin) = 10px

#### 3.3 Améliorer le contraste tab sélectionné

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QToolBox::tab:selected {
    background-color: {color_2};
    color: {color_font_0};
    font-weight: 500;
    border: 1px solid {color_bg_3};
}

/* APRÈS */
QToolBox::tab:selected {
    background-color: {color_accent_light_bg};  /* Fond bleu clair */
    color: {color_accent_dark};                 /* Texte bleu foncé */
    font-weight: 600;                           /* Semi-gras */
    border: 2px solid {color_accent};           /* Bordure bleue visible */
    border-left: 4px solid {color_accent};      /* Barre gauche accentuée */
}
```

**Impact**:
- Tab active immédiatement identifiable
- Cohérent avec le code couleur accent du plugin
- Meilleure navigation pour l'utilisateur

### Phase 4: Amélioration Visibilité Textes (Priorité MOYENNE) 🟡

#### 4.1 Ajouter styles explicites pour QLabel

**Fichier**: `resources/styles/default.qss`

**Ajout**:
```css
/* Ajout APRÈS la section QTreeView (fin du fichier) */

/* Labels - Hiérarchie claire */
QLabel {
    color: {color_font_0};
    padding: 2px;
}

/* Labels primaires (titres de sections) */
QLabel[objectName*="label_title"],
QLabel[objectName*="label_section"] {
    color: {color_font_0};
    font-weight: 600;
    font-size: 11pt;
    padding: 4px 2px;
}

/* Labels secondaires (descriptions) */
QLabel[objectName*="label_info"],
QLabel[objectName*="label_description"] {
    color: {color_font_1};
    font-weight: normal;
    font-size: 9pt;
    padding: 2px;
}

/* Labels dans GroupBox (moins bold que titre) */
QGroupBox QLabel {
    color: {color_font_0};
    font-weight: normal;
}
```

**Impact**:
- Hiérarchie typographique claire
- Meilleure scannabilité visuelle
- Cohérence avec le design system

#### 4.2 Améliorer le contraste des textes désactivés

**Fichier**: `modules/ui_styles.py`

**Modification**:
```python
# AVANT
COLOR_SCHEMES = {
    'default': {
        'color_font_2': '#9E9E9E',    # Disabled text
    }
}

# APRÈS
COLOR_SCHEMES = {
    'default': {
        'color_font_2': '#888888',    # Disabled text (plus foncé: 9E→88)
    }
}
```

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QPushButton:!checkable:disabled {
    background-color: {color_1};
    border: 2px solid {color_2};
    color: {color_font_2};
    opacity: 0.4;               /* ❌ Opacity réduit encore le contraste */
}

/* APRÈS */
QPushButton:!checkable:disabled {
    background-color: {color_1};
    border: 2px solid {color_2};
    color: {color_font_2};
    opacity: 0.6;               /* Augmenté: 0.4 → 0.6 (+50%) */
}
```

**Impact**:
- Contraste amélioré: **~2.5:1 → ~3.5:1** (proche WCAG AA pour textes secondaires)
- Textes désactivés lisibles mais clairement désactivés
- Meilleure accessibilité

#### 4.3 Rendre les boutons checkables plus visibles par défaut

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QPushButton:checkable {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 5px;
    padding: 10px 16px;
    color: {color_font_0};
    font-weight: 500;           /* ❌ Normal */
    min-height: 32px;
}

/* APRÈS */
QPushButton:checkable {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 5px;
    padding: 10px 16px;
    color: {color_font_0};
    font-weight: 600;           /* Augmenté: 500 → 600 (semi-gras) */
    min-height: 32px;
}

/* Ajouter un indicateur visuel subtil */
QPushButton:checkable::after {
    content: "";
    position: absolute;
    bottom: 2px;
    left: 50%;
    transform: translateX(-50%);
    width: 20px;
    height: 2px;
    background-color: {color_2};
    border-radius: 1px;
}
```

**Impact**:
- État "checkable" plus évident
- Utilisateur comprend mieux l'interactivité
- Cohérent avec les patterns UI modernes

### Phase 5: Correction Titres Tronqués (Priorité MOYENNE) 🟡

#### 5.1 Optimiser le padding des QToolButton

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QToolBox QToolButton {
    background-color: transparent;
    border: none;
    padding: 22px 15px 22px 40px;   /* ❌ 40px left pour icône */
    min-height: 70px;
    max-height: 70px;
    height: 70px;
    color: {color_font_0};
    font-weight: normal;
    text-align: left;
}

/* APRÈS */
QToolBox QToolButton {
    background-color: transparent;
    border: none;
    padding: 12px 10px 12px 45px;   /* Ajusté: left 40→45px, right 15→10px */
    min-height: 50px;
    max-height: 50px;
    height: 50px;
    color: {color_font_0};
    font-weight: normal;
    text-align: left;
}

/* Icônes plus proches du bord gauche */
QToolBox QToolButton::icon {
    margin-left: -5px;              /* Rapproche l'icône du bord */
}
```

**Impact**:
- Espace texte disponible: **366px → 366px** (maintenu)
- Meilleur équilibre visuel icône/texte
- Prêt pour textes plus longs

#### 5.2 Ajouter text-overflow pour GroupBox titles

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: {color_font_0};
}

/* APRÈS */
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;                 /* Augmenté: 5px → 8px */
    color: {color_font_0};
    max-width: 350px;               /* Limite la largeur */
    text-overflow: ellipsis;        /* Ellipse si trop long */
    white-space: nowrap;            /* Pas de retour à la ligne */
    overflow: hidden;               /* Cache le débordement */
}
```

**Impact**:
- Titres longs tronqués proprement avec "..."
- Plus de chevauchement avec bordure
- Meilleure gestion responsive

#### 5.3 Optimiser Collapsible GroupBox title

**Fichier**: `resources/styles/default.qss`

**Modification**:
```css
/* AVANT */
QgsCollapsibleGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    margin-left: 20px;
    margin-top: 4px;
    left: 0px;
    top: 6px;
}

/* APRÈS */
QgsCollapsibleGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    margin-left: 24px;              /* Augmenté: 20px → 24px (checkbox + espace) */
    margin-top: 2px;                /* Réduit: 4px → 2px */
    left: 0px;
    top: 4px;                       /* Réduit: 6px → 4px */
    max-width: 340px;               /* Limite (421px - 24px - marges) */
    text-overflow: ellipsis;
    white-space: nowrap;
    overflow: hidden;
}
```

**Impact**:
- Titre aligné avec checkbox
- Gestion élégante des longs textes
- Meilleur positionnement vertical

---

## 📋 Plan d'Implémentation par Phases

### ✅ Phase 1: Marges et Padding (CRITIQUE)
**Durée estimée**: 2-3 heures  
**Fichiers modifiés**: 2
- [ ] 1.1 `resources/styles/default.qss` - Réduire padding QFrame
- [ ] 1.2 `resources/styles/default.qss` - Réduire hauteur QToolBox tabs
- [ ] 1.3 `resources/styles/default.qss` - Harmoniser padding inputs
- [ ] 1.4 `resources/styles/default.qss` - Réduire padding GroupBox

**Tests**:
- Vérifier visuel sur QGIS 3.44.2
- Tester redimensionnement dockwidget
- Vérifier scroll sections

### ✅ Phase 2: Alignement (CRITIQUE)
**Durée estimée**: 3-4 heures  
**Fichiers modifiés**: 1
- [ ] 2.1 `filter_mate_dockwidget_base.ui` - Augmenter splitter handle
- [ ] 2.2 `filter_mate_dockwidget_base.ui` - Définir marges layouts (10+ layouts)
- [ ] 2.3 `filter_mate_dockwidget_base.ui` - Supprimer spacers fixes

**Tests**:
- Vérifier alignement widgets
- Tester splitter dragging
- Valider espacement visuel

**Post-modification obligatoire**:
```bash
# Recompiler le .ui en .py
call "C:\Program Files\QGIS 3.44.2\OSGeo4W.bat" pyuic5 -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
```

### ✅ Phase 3: Couleurs (IMPORTANTE)
**Durée estimée**: 1-2 heures  
**Fichiers modifiés**: 2
- [ ] 3.1 `modules/ui_styles.py` - Ajuster contraste bg_0 et color_2
- [ ] 3.2 `resources/styles/default.qss` - Réduire visibilité frame_actions
- [ ] 3.3 `resources/styles/default.qss` - Améliorer tab selected

**Tests**:
- Vérifier contraste hiérarchique
- Tester thèmes dark/light
- Valider lisibilité

### ✅ Phase 4: Textes (IMPORTANTE)
**Durée estimée**: 1-2 heures  
**Fichiers modifiés**: 2
- [ ] 4.1 `resources/styles/default.qss` - Ajouter styles QLabel
- [ ] 4.2 `modules/ui_styles.py` + `default.qss` - Améliorer disabled text
- [ ] 4.3 `resources/styles/default.qss` - Améliorer checkables visibilité

**Tests**:
- Vérifier contraste WCAG
- Tester états disabled
- Valider hiérarchie typographique

### ✅ Phase 5: Titres (UTILE)
**Durée estimée**: 1 heure  
**Fichiers modifiés**: 1
- [ ] 5.1 `resources/styles/default.qss` - Optimiser QToolButton padding
- [ ] 5.2 `resources/styles/default.qss` - Ajouter ellipsis GroupBox
- [ ] 5.3 `resources/styles/default.qss` - Optimiser Collapsible title

**Tests**:
- Tester textes longs
- Vérifier ellipses
- Valider responsive

---

## 🧪 Checklist de Tests Complets

### Tests Visuels
- [ ] Ouvrir FilterMate dans QGIS 3.44.2
- [ ] Vérifier les 3 tabs (EXPLORING, FILTERING, EXPORTING)
- [ ] Redimensionner le dockwidget (min/max)
- [ ] Drag splitter entre sections
- [ ] Tester scroll dans toutes les sections
- [ ] Vérifier alignement de tous les widgets
- [ ] Valider espacement visuel cohérent

### Tests Interactifs
- [ ] Cliquer tous les boutons checkables
- [ ] Hover sur tous les widgets
- [ ] Focus sur inputs (Tab navigation)
- [ ] Disabled states
- [ ] Expand/Collapse GroupBox
- [ ] Sélection dans combos/lists

### Tests Thèmes
- [ ] Theme `default` (light)
- [ ] Theme `dark` (si configuré)
- [ ] Auto-détection theme QGIS

### Tests Responsive
- [ ] Largeur minimale (421px)
- [ ] Largeur maximale
- [ ] Hauteur minimale (600px)
- [ ] Hauteur maximale

### Tests Accessibilité
- [ ] Contraste WCAG AA (4.5:1)
- [ ] Focus visible
- [ ] Navigation clavier
- [ ] Screen reader (optionnel)

---

## 📊 Gains Estimés Post-Implémentation

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| **Padding horizontal total** | 32px | 16px | **-50%** |
| **Hauteur tabs (3)** | 210px | 150px | **-28%** |
| **Espace vertical libéré** | - | ~80px | **+8.5%** |
| **Largeur utile** | 389px | 405px | **+4.1%** |
| **Contraste hiérarchique (∆E)** | ~5 | ~8 | **+60%** |
| **Contraste disabled text** | 2.5:1 | 3.5:1 | **+40%** |

---

## 🎯 Résultats Attendus

### UX Améliorée
✅ **Densité d'information**: +10-15% de contenu visible sans scroll  
✅ **Clarté visuelle**: Hiérarchie claire entre frames/widgets/textes  
✅ **Navigation**: Tab active immédiatement identifiable  
✅ **Accessibilité**: Conformité WCAG 2.1 AA améliorée  

### Performance Visuelle
✅ **Alignement**: Parfait sur toutes les sections  
✅ **Cohérence**: Padding/margin uniformes  
✅ **Responsive**: Fonctionne du min (421px) au max  
✅ **Professionnalisme**: Design moderne et épuré  

### Maintenance
✅ **CSS centralisé**: Toutes les modifications dans `default.qss`  
✅ **Thèmes**: Facilement extensible (dark, light, custom)  
✅ **i18n ready**: Gestion des textes longs avec ellipses  
✅ **Testable**: Checklist complète fournie  

---

## 📝 Notes Importantes

### Backups Obligatoires
Avant toute modification, créer des backups :
```bash
cp filter_mate_dockwidget_base.ui filter_mate_dockwidget_base.ui.backup_20251205
cp filter_mate_dockwidget_base.py filter_mate_dockwidget_base.py.backup_20251205
cp resources/styles/default.qss resources/styles/default.qss.backup_20251205
cp modules/ui_styles.py modules/ui_styles.py.backup_20251205
```

### Compilation UI
**TOUJOURS** recompiler après modification du `.ui` :
```bash
cd /d "C:\Users\Simon\OneDrive\Documents\GitHub\filter_mate"
call "C:\Program Files\QGIS 3.44.2\OSGeo4W.bat" pyuic5 -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
```

### Git Workflow
```bash
# Créer branche dédiée
git checkout -b feature/ui-improvements-phase1

# Commit par phase
git add resources/styles/default.qss
git commit -m "feat(ui): Phase 1 - Reduce padding and optimize spacing"

git add filter_mate_dockwidget_base.ui filter_mate_dockwidget_base.py
git commit -m "feat(ui): Phase 2 - Improve alignment and layouts"

# etc.
```

### Tests Régression
Après chaque phase, vérifier que :
- Plugin se charge correctement
- Pas d'erreur console Python
- Fonctionnalités existantes OK

---

## 📚 Ressources et Références

### Documentation
- [Qt Stylesheets Reference](https://doc.qt.io/qt-5/stylesheet-reference.html)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Material Design Color System](https://material.io/design/color/the-color-system.html)

### Outils
- **Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Color Palette Generator**: https://coolors.co/
- **Qt Designer**: Pour visualiser `.ui` avant compilation

### Fichiers Clés
- `filter_mate_dockwidget_base.ui` - Structure UI (Qt Designer)
- `resources/styles/default.qss` - Styles CSS (913 lignes)
- `modules/ui_styles.py` - Loader et thèmes (350 lignes)
- `config/config.json` - Configuration couleurs

---

**Dernière mise à jour**: 5 décembre 2025  
**Auteur**: GitHub Copilot  
**Version**: 2.0 - Plan détaillé complet
