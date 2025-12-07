# Plan d'Harmonisation de l'UI FilterMate

## 📊 Analyse de l'État Actuel

### Problèmes Identifiés

1. **Hauteurs Inconsistantes des Inputs**
   - QLineEdit, QComboBox, QgsFieldExpressionWidget : hauteurs variées (30px-50px)
   - Boutons dans les sidebars : 40-50px
   - Widgets QGIS personnalisés : padding et hauteur non uniformes

2. **Alignement Vertical Défaillant**
   - Les inputs et boutons dans les frames Filtering et Exporting ne sont pas alignés
   - Espacements variables entre les éléments (20-40px)
   - Marges et padding non cohérents

3. **Taille Excessive des GroupBox**
   - Padding internes trop importants (8px)
   - Marges supérieures (margin-top: 0.8ex)
   - Espacement interne non optimisé

4. **Incohérences dans le QSS**
   - Hauteurs définies à plusieurs endroits (QSS + UI)
   - Certains widgets ont min-height: 30px, d'autres 32px
   - Padding compensatoires créent des inconsistances

## 🎯 Objectifs de l'Harmonisation

### 1. Standardisation des Hauteurs

**Inputs et ComboBox**
- **Nouvelle hauteur standard : 28px** (actuellement 30-32px)
- Réduction du padding vertical : 4px (actuellement 6px)
- Border uniformisée : 2px

**Boutons**
- **Boutons action principaux : 30px** (actuellement 32px)
- **Boutons sidebar (checkable) : 36px** (actuellement 40-50px)
- Padding réduit et cohérent

### 2. Optimisation de l'Alignement

**Frames Filtering et Exporting**
- Alignement baseline pour tous les widgets d'une même ligne
- Espacement vertical uniforme : 12px (actuellement 20px)
- Marges latérales cohérentes : 6px

**Layout Spacing**
- Vertical spacing : 8px (actuellement variable)
- Horizontal spacing : 8px
- Padding des containers : 6px (actuellement 8px)

### 3. Réduction des GroupBox

**Optimisation de l'Espace**
- Padding interne : 4px (actuellement 8px)
- Margin-top : 0.5ex (actuellement 0.8ex)
- Padding du titre : 2px 6px (actuellement 4px 8px)
- Border : 1px (inchangé)

## 📐 Spécifications Détaillées

### A. Modifications du QSS (resources/styles/default.qss)

#### 1. Inputs Standards (QLineEdit)

```css
/* AVANT */
QLineEdit {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 4px;
    padding: 6px;
    color: {color_font_0};
    min-height: 30px;
}

/* APRÈS */
QLineEdit {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 3px;
    padding: 4px 6px;
    color: {color_font_0};
    min-height: 28px;
    max-height: 28px;
}

QLineEdit:hover {
    border: 2px solid {color_accent};
    padding: 4px 6px;  /* Pas de compensation */
}

QLineEdit:focus {
    border: 3px solid {color_accent};
    background-color: {color_accent_light_bg};
    padding: 3px 5px;  /* Compensation réduite */
    outline: none;
    box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
}
```

#### 2. ComboBox et Widgets QGIS

```css
/* AVANT */
QgsFeaturePickerWidget,
QgsMapLayerComboBox,
QgsFieldComboBox,
QgsFieldExpressionWidget,
QgsCheckableComboBox,
QComboBox {
    background-color: {color_1};
    border: 1px solid {color_2};
    border-radius: 3px;
    padding: 6px 5px;
    color: {color_font_0};
    min-height: 30px;
}

/* APRÈS */
QgsFeaturePickerWidget,
QgsMapLayerComboBox,
QgsFieldComboBox,
QgsFieldExpressionWidget,
QgsCheckableComboBox,
QComboBox {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 3px;
    padding: 4px 6px;
    color: {color_font_0};
    min-height: 28px;
    max-height: 28px;
}

QgsFeaturePickerWidget:hover,
QgsMapLayerComboBox:hover,
/* ... autres widgets ... */
QComboBox:hover {
    border: 2px solid {color_accent};
    padding: 4px 6px;
}

QgsFeaturePickerWidget:focus,
/* ... autres widgets ... */
QComboBox:focus {
    border: 3px solid {color_accent};
    background-color: {color_accent_light_bg};
    padding: 3px 5px;
    outline: none;
    box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
}
```

#### 3. SpinBox et DoubleSpinBox

```css
/* AVANT */
QSpinBox,
QDoubleSpinBox,
QgsDoubleSpinBox {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 4px;
    padding: 6px;
    color: {color_font_0};
    min-height: 30px;
}

/* APRÈS */
QSpinBox,
QDoubleSpinBox,
QgsDoubleSpinBox {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 3px;
    padding: 4px 6px;
    color: {color_font_0};
    min-height: 28px;
    max-height: 28px;
}

QSpinBox:hover,
QDoubleSpinBox:hover,
QgsDoubleSpinBox:hover {
    border: 2px solid {color_accent};
    padding: 4px 6px;
}

QSpinBox:focus,
QDoubleSpinBox:focus,
QgsDoubleSpinBox:focus {
    border: 3px solid {color_accent};
    background-color: {color_accent_light_bg};
    padding: 3px 5px;
    outline: none;
    box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
}
```

#### 4. Boutons Principaux (non-checkable)

```css
/* AVANT */
QPushButton:!checkable {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 5px;
    padding: 10px 16px;
    color: {color_font_0};
    font-weight: 500;
    min-height: 32px;
}

/* APRÈS */
QPushButton:!checkable {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 4px;
    padding: 6px 12px;
    color: {color_font_0};
    font-weight: 500;
    min-height: 30px;
    max-height: 30px;
}

QPushButton:!checkable:hover {
    background-color: {color_accent_light_bg};
    border: 2px solid {color_accent};
    color: {color_accent_dark};
    padding: 6px 12px;
}

QPushButton:!checkable:pressed {
    background-color: {color_accent_pressed};
    border: 2px solid {color_accent_dark};
    color: white;
    padding: 6px 12px;
}
```

#### 5. Boutons Checkable (sidebar)

```css
/* AVANT */
QPushButton:checkable {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 5px;
    padding: 10px 16px;
    color: {color_font_0};
    font-weight: 600;
    min-height: 32px;
}

/* APRÈS */
QPushButton:checkable {
    background-color: {color_1};
    border: 2px solid {color_2};
    border-radius: 4px;
    padding: 8px 12px;
    color: {color_font_0};
    font-weight: 600;
    min-height: 30px;
    max-height: 30px;
}

/* Boutons sidebar spécifiques - taille carrée */
QPushButton[objectName^="pushButton_filtering_"],
QPushButton[objectName^="pushButton_checkable_filtering_"],
QPushButton[objectName^="pushButton_exporting_"],
QPushButton[objectName^="pushButton_checkable_exporting_"] {
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 6px;
}

/* Boutons dans widget_keys - encore plus compacts */
QWidget#widget_filtering_keys QPushButton:checkable,
QWidget#widget_exporting_keys QPushButton:checkable {
    background-color: transparent;
    border: 2px solid transparent;
    border-radius: 6px;
    padding: 8px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
}

QWidget#widget_filtering_keys QPushButton:checkable:checked,
QWidget#widget_exporting_keys QPushButton:checkable:checked {
    background-color: {color_accent};
    border: 3px solid {color_accent_dark};
    padding: 7px;
    box-shadow: 0 2px 4px rgba(25, 118, 210, 0.4);
}
```

#### 6. GroupBox Optimisés

```css
/* AVANT */
QGroupBox {
    background-color: transparent;
    border: 1px solid {color_1};
    border-radius: 3px;
    margin-top: 0.8ex;
    padding: 8px;
    font-weight: bold;
    color: {color_font_0};
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {color_font_0};
    max-width: 350px;
}

/* APRÈS */
QGroupBox {
    background-color: transparent;
    border: 1px solid {color_1};
    border-radius: 3px;
    margin-top: 0.5ex;
    padding: 4px;
    font-weight: bold;
    color: {color_font_0};
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: {color_font_0};
    max-width: 350px;
    font-size: 10pt;
}
```

#### 7. QgsCollapsibleGroupBox Optimisé

```css
/* AVANT */
QgsCollapsibleGroupBox {
    background-color: {color_bg_0};
    border: none;
    border-radius: 4px;
    padding: 8px;
    padding-top: 24px;
    color: {color_font_0};
    min-height: 50px;
}

QgsCollapsibleGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    margin-left: 24px;
    margin-top: 2px;
    left: 0px;
    top: 4px;
    max-width: 340px;
}

/* APRÈS */
QgsCollapsibleGroupBox {
    background-color: {color_bg_0};
    border: none;
    border-radius: 3px;
    padding: 4px;
    padding-top: 20px;
    color: {color_font_0};
    min-height: 40px;
}

QgsCollapsibleGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 6px;
    margin-left: 20px;
    margin-top: 1px;
    left: 0px;
    top: 2px;
    max-width: 340px;
    font-size: 9pt;
}
```

### B. Modifications du UI (filter_mate_dockwidget_base.ui)

#### 1. Widgets QGIS - Hauteur Standard

**Rechercher et remplacer dans tout le fichier UI :**

```xml
<!-- AVANT (exemple QgsFieldExpressionWidget) -->
<property name="minimumSize">
    <size>
        <width>30</width>
        <height>30</height>
    </size>
</property>
<property name="maximumSize">
    <size>
        <width>16777215</width>
        <height>30</height>
    </size>
</property>

<!-- APRÈS -->
<property name="minimumSize">
    <size>
        <width>30</width>
        <height>28</height>
    </size>
</property>
<property name="maximumSize">
    <size>
        <width>16777215</width>
        <height>28</height>
    </size>
</property>
<property name="baseSize">
    <size>
        <width>0</width>
        <height>28</height>
    </size>
</property>
```

**Widgets concernés :**
- QgsFieldExpressionWidget
- QgsFeaturePickerWidget
- QgsMapLayerComboBox
- QgsFieldComboBox
- QComboBox
- QLineEdit
- QgsDoubleSpinBox
- QgsProjectionSelectionWidget

#### 2. Boutons Sidebar - Taille Réduite

**Boutons dans widget_filtering_keys et widget_exporting_keys :**

```xml
<!-- AVANT -->
<property name="minimumSize">
    <size>
        <width>20</width>
        <height>20</height>
    </size>
</property>
<property name="maximumSize">
    <size>
        <width>20</width>
        <height>20</height>
    </size>
</property>

<!-- APRÈS -->
<property name="minimumSize">
    <size>
        <width>36</width>
        <height>36</height>
    </size>
</property>
<property name="maximumSize">
    <size>
        <width>36</width>
        <height>36</height>
    </size>
</property>
<property name="baseSize">
    <size>
        <width>36</width>
        <height>36</height>
    </size>
</property>
```

#### 3. Espacements des Layouts

**Layouts verticaux principaux :**

```xml
<!-- AVANT -->
<layout class="QVBoxLayout" name="verticalLayout_filtering_keys">
    <property name="spacing">
        <number>0</number>  <!-- ou non défini -->
    </property>
    <!-- items avec spacer de 20px -->
    <item>
        <spacer name="verticalSpacer_42">
            <property name="sizeHint" stdset="0">
                <size>
                    <width>20</width>
                    <height>20</height>
                </size>
            </property>
        </spacer>
    </item>
</layout>

<!-- APRÈS -->
<layout class="QVBoxLayout" name="verticalLayout_filtering_keys">
    <property name="spacing">
        <number>8</number>
    </property>
    <!-- items avec spacer de 12px -->
    <item>
        <spacer name="verticalSpacer_42">
            <property name="sizeHint" stdset="0">
                <size>
                    <width>20</width>
                    <height>12</height>
                </size>
            </property>
        </spacer>
    </item>
</layout>
```

**Layouts horizontaux :**

```xml
<layout class="QHBoxLayout" name="horizontalLayout">
    <property name="spacing">
        <number>8</number>
    </property>
    <property name="leftMargin">
        <number>6</number>
    </property>
    <property name="topMargin">
        <number>6</number>
    </property>
    <property name="rightMargin">
        <number>6</number>
    </property>
    <property name="bottomMargin">
        <number>6</number>
    </property>
</layout>
```

#### 4. GroupBox - Padding Réduit

**QgsCollapsibleGroupBox dans l'onglet Exploring :**

```xml
<layout class="QGridLayout" name="gridLayout_10">
    <property name="sizeConstraint">
        <enum>QLayout::SetMaximumSize</enum>
    </property>
    <property name="spacing">
        <number>6</number>
    </property>
    <property name="leftMargin">
        <number>4</number>
    </property>
    <property name="topMargin">
        <number>4</number>
    </property>
    <property name="rightMargin">
        <number>4</number>
    </property>
    <property name="bottomMargin">
        <number>4</number>
    </property>
</layout>
```

## 🔄 Plan d'Implémentation

### Phase 1 : Modifications QSS (default.qss)
**Durée estimée : 1-2h**

1. ✅ Modifier les hauteurs des inputs (QLineEdit, QComboBox, etc.)
2. ✅ Ajuster le padding et border-radius
3. ✅ Réduire les hauteurs des boutons
4. ✅ Optimiser les GroupBox et QgsCollapsibleGroupBox
5. ✅ Harmoniser les états :hover et :focus

### Phase 2 : Modifications UI (filter_mate_dockwidget_base.ui)
**Durée estimée : 2-3h**

1. ✅ Mettre à jour les hauteurs minimales/maximales de tous les widgets QGIS
2. ✅ Ajuster les tailles des boutons sidebar
3. ✅ Réduire les espacements entre éléments (spacers 20px → 12px)
4. ✅ Uniformiser les marges des layouts (8px → 6px)
5. ✅ Optimiser les padding des GroupBox

### Phase 3 : Recompilation et Tests
**Durée estimée : 30min**

1. ✅ Recompiler l'UI : `bash compile_ui.sh`
2. ✅ Tester visuellement dans QGIS
3. ✅ Vérifier l'alignement dans les frames Filtering et Exporting
4. ✅ Valider la cohérence sur différentes résolutions

### Phase 4 : Documentation et Validation
**Durée estimée : 30min**

1. ✅ Capturer des screenshots avant/après
2. ✅ Documenter les changements dans CHANGELOG.md
3. ✅ Mettre à jour docs/UI_IMPROVEMENTS_SUMMARY.md
4. ✅ Valider avec les utilisateurs

## 📊 Métriques de Succès

### Gains d'Espace Attendus

| Élément | Avant | Après | Gain |
|---------|-------|-------|------|
| Input height | 30-32px | 28px | -10-13% |
| Button height | 32px | 30px | -6% |
| Sidebar button | 40-50px | 36px | -10-28% |
| GroupBox padding | 8px | 4px | -50% |
| Layout margin | 8px | 6px | -25% |
| Vertical spacer | 20px | 12px | -40% |

**Gain vertical total estimé par section : ~20-25%**

### Amélioration de la Cohérence

- ✅ Hauteur uniforme pour tous les inputs : 28px
- ✅ Padding cohérent : 4px 6px
- ✅ Border uniforme : 2px
- ✅ Border-radius standardisé : 3-4px
- ✅ Espacements verticaux : 8px (layout) + 12px (spacers)
- ✅ Marges containers : 6px

## 🎨 Validation Visuelle

### Checklist de Vérification

**Frame Filtering :**
- [ ] Tous les inputs ont la même hauteur (28px)
- [ ] Les boutons sidebar sont alignés avec les inputs adjacents
- [ ] L'espacement entre les sections est uniforme (12px)
- [ ] Les marges gauche/droite sont cohérentes (6px)

**Frame Exporting :**
- [ ] Même cohérence que Filtering
- [ ] Les widgets QgsProjectionSelectionWidget s'alignent correctement
- [ ] Les QLineEdit ont la même hauteur que les ComboBox

**GroupBox Globaux :**
- [ ] Padding réduit mais lisible (4px)
- [ ] Titres bien positionnés
- [ ] Borders propres et cohérentes

**États Interactifs :**
- [ ] :hover visible mais subtil
- [ ] :focus avec indicateur clair (border 3px + shadow)
- [ ] :checked bien distinct pour les boutons checkable
- [ ] Transitions fluides

## 📝 Notes Techniques

### Propriétés CSS Critiques

**Compensation de Border :**
Lorsque la border change (hover/focus), le padding doit compenser pour éviter le "saut" visuel :

```css
/* État normal : border 2px + padding 4px = total 6px */
border: 2px solid {color_2};
padding: 4px 6px;

/* État focus : border 3px + padding 3px = total 6px (identique) */
border: 3px solid {color_accent};
padding: 3px 5px;
```

**Box-Shadow pour Focus :**
L'indicateur de focus utilise maintenant un shadow externe réduit :

```css
box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);  /* Avant : 3px et 0.25 */
```

### Compatibilité QGIS

**Widgets Personnalisés :**
Les widgets QGIS (Qgs*) peuvent avoir des styles internes qui surchargent le QSS. Toujours tester visuellement.

**Thèmes :**
Les changements s'appliquent aux 3 thèmes (default, dark, light) via le système de placeholders de couleurs.

## 🚀 Prochaines Étapes

1. **Implémenter les modifications QSS** (Phase 1)
2. **Modifier le fichier UI** (Phase 2)
3. **Recompiler et tester** (Phase 3)
4. **Documenter** (Phase 4)
5. **Commit et deploy** (si validé)

---

**Date de création :** 2025-12-07  
**Auteur :** GitHub Copilot  
**Version :** 1.0  
**Statut :** ✅ Plan complet - Prêt pour implémentation
