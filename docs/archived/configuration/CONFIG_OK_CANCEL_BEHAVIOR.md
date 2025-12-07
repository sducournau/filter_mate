# Configuration Tree View - OK/Cancel Button Behavior

## Vue d'ensemble

Le système de configuration utilise désormais un modèle **validation manuelle** avec boutons OK/Cancel. Les changements ne sont **pas appliqués immédiatement** mais stockés en attente jusqu'à ce que l'utilisateur clique sur OK.

## État des boutons

### 🔴 Désactivés par défaut

Les boutons OK et Cancel sont **désactivés** dans ces situations :

1. **Au démarrage** - Lors de l'initialisation du plugin
2. **Après application** - Quand l'utilisateur clique sur OK et que les changements sont appliqués
3. **Après annulation** - Quand l'utilisateur clique sur Cancel et que les changements sont annulés
4. **Aucun changement en attente** - Quand la configuration est synchronisée avec le fichier

**Indication visuelle** : Boutons grisés et non cliquables

### 🟢 Activés quand changements en attente

Les boutons OK et Cancel sont **activés** automatiquement dès que :

- L'utilisateur **modifie une valeur** dans le JSON Tree View
- Des changements sont stockés dans `pending_config_changes[]`
- Le flag `config_changes_pending = True`

**Indication visuelle** : Boutons actifs et cliquables

## Flux de travail utilisateur

### Scénario 1 : Application des changements (OK)

```
[État initial]
  └─> Boutons désactivés ❌
  └─> Aucun changement en attente

[Utilisateur modifie une valeur]
  └─> Valeur modifiée dans le tree view
  └─> Changement stocké en mémoire (pas de sauvegarde)
  └─> Boutons activés ✅
  └─> Log: "Configuration change pending: ..."

[Utilisateur modifie d'autres valeurs]
  └─> Changements accumulés
  └─> Boutons restent activés ✅
  └─> Chaque changement loggé

[Utilisateur clique OK]
  └─> Tous les changements appliqués :
      • UI_PROFILE → Redimensionnement interface
      • ACTIVE_THEME → Changement de thème
      • DATATYPE_TO_EXPORT → Mise à jour combobox
      • STYLES_TO_EXPORT → Mise à jour combobox
      • ICONS → Rechargement icônes
  └─> config.json sauvegardé
  └─> Boutons désactivés ❌
  └─> Message récapitulatif : "Configuration applied: Theme: dark, UI Profile: compact"
```

### Scénario 2 : Annulation des changements (Cancel)

```
[État initial]
  └─> Boutons désactivés ❌

[Utilisateur modifie plusieurs valeurs]
  └─> Changements accumulés
  └─> Boutons activés ✅

[Utilisateur clique Cancel]
  └─> config.json rechargé depuis le disque
  └─> Modèle JSON recréé avec données originales
  └─> Tree view restauré à l'état initial
  └─> Changements en attente effacés
  └─> Boutons désactivés ❌
  └─> Message : "Configuration changes cancelled and reverted"
```

### Scénario 3 : Navigation sans changements

```
[Utilisateur navigue dans le tree view]
  └─> Collapse/expand des sections
  └─> Lecture des valeurs
  └─> Boutons restent désactivés ❌
  └─> Aucun changement détecté
```

## Architecture technique

### Variables de suivi

```python
# Dans __init__()
self.config_changes_pending = False        # Flag : y a-t-il des changements ?
self.pending_config_changes = []           # Liste des changements en attente
```

### Signal Flow

```
JsonModel.itemChanged (signal Qt)
    ↓
data_changed_configuration_model()
    ↓
┌─────────────────────────────────────────┐
│ 1. Récupération du chemin modifié      │
│ 2. Stockage du changement en mémoire   │
│ 3. config_changes_pending = True       │
│ 4. buttonBox.setEnabled(True) ✅       │
│ 5. Log du changement                    │
└─────────────────────────────────────────┘
    ↓
Changements en attente...
    ↓
[Utilisateur clique OK ou Cancel]
    ↓
┌──────────────────────────────┬──────────────────────────────┐
│  on_config_buttonbox_accepted │  on_config_buttonbox_rejected │
└──────────────────────────────┴──────────────────────────────┘
    ↓                                    ↓
apply_pending_config_changes()    cancel_pending_config_changes()
    ↓                                    ↓
Pour chaque changement:               Rechargement config.json
  • Appliquer selon type                Recréation du modèle
  • Gérer les erreurs                   Restauration tree view
  • Logger les actions                     ↓
    ↓                                    Nettoyage
Sauvegarde config.json                     ↓
    ↓                                buttonBox.setEnabled(False) ❌
Nettoyage
    ↓
buttonBox.setEnabled(False) ❌
    ↓
Message récapitulatif
```

## Méthodes clés

### 1. `data_changed_configuration_model(input_data)`

**Rôle** : Détecter et stocker les changements

**Actions** :
- ✅ Récupère le chemin de la clé modifiée
- ✅ Stocke le changement dans `pending_config_changes[]`
- ✅ Active les boutons OK/Cancel
- ❌ N'applique PAS le changement immédiatement

### 2. `apply_pending_config_changes()`

**Rôle** : Appliquer tous les changements en attente

**Actions** :
- Parcourt `pending_config_changes[]`
- Applique chaque type de changement :
  - `ICONS` → `set_widget_icon()`
  - `ACTIVE_THEME` → `StyleLoader.set_theme_from_config()`
  - `UI_PROFILE` → `UIConfig.set_profile()` + `apply_dynamic_dimensions()`
  - `STYLES_TO_EXPORT` → Mise à jour combobox
  - `DATATYPE_TO_EXPORT` → Mise à jour combobox
- Sauvegarde `config.json`
- Efface `pending_config_changes[]`
- Désactive les boutons
- Affiche message récapitulatif

### 3. `cancel_pending_config_changes()`

**Rôle** : Annuler et réverser les changements

**Actions** :
- Recharge `config.json` depuis le disque
- Recrée le `JsonModel` avec données originales
- Met à jour le tree view
- Efface `pending_config_changes[]`
- Désactive les boutons
- Affiche message d'annulation

### 4. `on_config_buttonbox_accepted()` & `on_config_buttonbox_rejected()`

**Rôle** : Handlers des signaux Qt des boutons

**Actions** :
- `accepted` → Appelle `apply_pending_config_changes()`
- `rejected` → Appelle `cancel_pending_config_changes()`

### 5. `manage_configuration_model()`

**Rôle** : Initialisation du tree view

**Modification** :
- ✅ Désactive les boutons par défaut : `self.buttonBox.setEnabled(False)`

## Avantages du système

### ✅ Contrôle utilisateur

- L'utilisateur peut **réviser** ses changements avant de les appliquer
- Possibilité d'**annuler** facilement sans conséquences
- **Visibilité** claire de l'état (boutons actifs/inactifs)

### ✅ Sécurité

- Évite les changements accidentels
- Pas d'effets de bord inattendus
- Rollback simple en cas d'erreur

### ✅ Performance

- Les changements sont appliqués **en batch**
- Une seule sauvegarde du `config.json`
- Une seule mise à jour de l'UI

### ✅ Expérience utilisateur

- Comportement familier (comme les boîtes de dialogue standards)
- Feedback visuel clair (boutons actifs/inactifs)
- Messages informatifs sur les actions effectuées

## Comparaison Avant/Après

### ❌ Ancien comportement (application immédiate)

```
Modification → Sauvegarde immédiate → Application immédiate → Pas de rollback
```

**Problèmes** :
- Changements accidentels difficiles à annuler
- Effets de bord inattendus
- Pas de possibilité de révision
- Multiples sauvegardes (performance)

### ✅ Nouveau comportement (validation manuelle)

```
Modification(s) → Stockage en mémoire → [Révision] → OK/Cancel → Application/Annulation
```

**Avantages** :
- Contrôle total de l'utilisateur
- Rollback facile
- Application groupée (performance)
- Visibilité de l'état via les boutons

## Messages utilisateur

### Lors de l'application (OK)

```
✅ Success: "Configuration applied: Theme: dark, UI Profile: compact, Export Format: GPKG"
```

ou si aucun changement applicable :

```
ℹ️ Info: "Configuration saved"
```

### Lors de l'annulation (Cancel)

```
ℹ️ Info: "Configuration changes cancelled and reverted"
```

### En cas d'erreur

```
❌ Critical: "Error cancelling changes: [message d'erreur]"
```

## Tests manuels

### Test 1 : Boutons désactivés par défaut

1. Ouvrir FilterMate
2. Aller dans l'onglet Configuration
3. **Vérifier** : Boutons OK/Cancel grisés ❌

### Test 2 : Activation sur modification

1. Double-cliquer sur une valeur dans le tree view
2. Modifier la valeur
3. **Vérifier** : Boutons OK/Cancel activés ✅

### Test 3 : Application des changements

1. Modifier `UI_PROFILE` de `auto` à `compact`
2. Modifier `ACTIVE_THEME` de `auto` à `dark`
3. Cliquer sur **OK**
4. **Vérifier** :
   - Interface redimensionnée (compact mode)
   - Thème sombre appliqué
   - Boutons désactivés ❌
   - Message récapitulatif affiché

### Test 4 : Annulation des changements

1. Modifier plusieurs valeurs
2. **Vérifier** : Boutons activés ✅
3. Cliquer sur **Cancel**
4. **Vérifier** :
   - Valeurs restaurées dans le tree view
   - Boutons désactivés ❌
   - Message d'annulation affiché

### Test 5 : Modifications multiples

1. Modifier 5+ valeurs différentes
2. **Vérifier** : Boutons restent activés ✅
3. Cliquer sur **OK**
4. **Vérifier** : Toutes les modifications appliquées

### Test 6 : Navigation sans modification

1. Expand/collapse des sections
2. Cliquer sur différentes valeurs (sans éditer)
3. **Vérifier** : Boutons restent désactivés ❌

## Fichiers concernés

### Modifiés

- `filter_mate_dockwidget.py` :
  - `__init__()` : Ajout variables tracking
  - `data_changed_configuration_model()` : Stockage au lieu d'application
  - `manage_configuration_model()` : Désactivation boutons par défaut
  - Nouvelles méthodes : `apply_pending_config_changes()`, `cancel_pending_config_changes()`, handlers

### Créés

- `config_ok_cancel_methods.py` : Méthodes prêtes à intégrer (temporaire)
- `docs/CONFIG_OK_CANCEL_BEHAVIOR.md` : Cette documentation

### Inchangés

- `filter_mate_dockwidget_base.ui` : QDialogButtonBox déjà présent
- `modules/qt_json_view/` : Pas de modifications nécessaires
- `config/config.json` : Structure inchangée

## Prochaines étapes

1. ✅ **Code prêt** dans `config_ok_cancel_methods.py`
2. ⏳ **Intégration** : Copier les méthodes dans `filter_mate_dockwidget.py`
3. ⏳ **Connexion signaux** : Ajouter dans `connect_widgets_signals()`
4. ⏳ **Nettoyage** : Supprimer l'ancien code d'application immédiate
5. ⏳ **Tests** : Valider tous les scénarios ci-dessus

---

**Date de création** : 7 décembre 2025  
**Version** : 2.2.0 - OK/Cancel button validation system  
**Auteur** : FilterMate Development Team
