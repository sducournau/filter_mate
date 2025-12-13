# User Feedback System - Implementation Guide

## 📋 Vue d'Ensemble

Le système de feedback utilisateur de FilterMate a été refactorisé pour réduire la "notification fatigue" et améliorer l'expérience utilisateur. Au lieu d'afficher **48 messages** pour chaque opération, le plugin utilise maintenant un système de verbosité configurable.

## 🎯 Problèmes Résolus

### Avant (v2.2.x)
- ❌ **16 messages redondants** : Undo/redo, changements config UI
- ❌ **Messages répétitifs** : Comptage features après chaque filtre
- ❌ **Pas de hiérarchisation** : Tous messages ont même importance
- ❌ **Feedback UI dupliqué** : Messages + boutons désactivés

### Après (v2.3.0+)
- ✅ **3 niveaux configurables** : Minimal, Normal, Verbose
- ✅ **-12 messages supprimés** : Undo/redo, config UI
- ✅ **Messages contextuels** : Optionnels selon niveau
- ✅ **Meilleure UX** : Feedback UI suffit pour actions courantes

## 📊 Niveaux de Verbosité

### 1️⃣ Minimal (Erreurs uniquement)
**Usage** : Production, utilisateurs avancés  
**Messages affichés** :
- ✅ Erreurs critiques (connexion, corruption DB)
- ✅ Warnings performance (>100k features)
- ✅ Succès exports (opérations longues)

**Messages masqués** :
- ❌ Comptages features
- ❌ Info backend
- ❌ Progression
- ❌ Undo/redo
- ❌ Config UI

**Réduction** : ~35 messages → **~8 messages**

### 2️⃣ Normal (Équilibré) ⭐ **Défaut**
**Usage** : Usage quotidien, la plupart des utilisateurs  
**Messages affichés** :
- ✅ Erreurs et warnings
- ✅ Comptages features après filtre
- ✅ Succès opérations importantes
- ✅ Performance warnings

**Messages masqués** :
- ❌ Undo/redo (UI feedback suffit)
- ❌ Backend info (une fois au startup)
- ❌ Config UI (visible dans interface)
- ❌ "No more history" (boutons désactivés)

**Réduction** : ~48 messages → **~20 messages**

### 3️⃣ Verbose (Mode Debug)
**Usage** : Développement, debugging, support utilisateur  
**Messages affichés** :
- ✅ **Tous les messages** (48 messages)
- ✅ Info détaillée backend
- ✅ Progression opérations
- ✅ Undo/redo confirmations
- ✅ Changements config

**Utilité** : Diagnostiquer problèmes, comprendre workflow

## 🔧 Configuration

### Via config.json (Recommandé)

Éditer `/config/config.json` :

```json
{
    "APP": {
        "DOCKWIDGET": {
            "FEEDBACK_LEVEL": {
                "choices": ["minimal", "normal", "verbose"],
                "value": "normal"  ← Changer ici
            }
        }
    }
}
```

### Via l'UI (Futur - v2.4)

Configuration visuelle dans l'onglet Settings :
- Radio buttons : Minimal / Normal / Verbose
- Preview : "What you'll see with this level"
- Description de chaque niveau

### Programmatique

```python
from config.feedback_config import set_feedback_level, FeedbackLevel

# Changer le niveau
set_feedback_level(FeedbackLevel.MINIMAL)

# Ou via string
from config.feedback_config import set_feedback_level_from_string
set_feedback_level_from_string("verbose")
```

## 💻 Usage pour Développeurs

### Vérifier si un message doit s'afficher

```python
from config.feedback_config import should_show_message

# Vérifier avant d'afficher
if should_show_message('filter_count'):
    iface.messageBar().pushInfo("FilterMate", f"{count:,} features visible")

if should_show_message('backend_info'):
    iface.messageBar().pushInfo("FilterMate", "Using PostgreSQL backend")
```

### Catégories disponibles

| Catégorie | Description | Minimal | Normal | Verbose |
|-----------|-------------|---------|--------|---------|
| `filter_count` | Comptage features | ❌ | ✅ | ✅ |
| `undo_redo` | Confirmations undo/redo | ❌ | ❌ | ✅ |
| `backend_info` | Info backend utilisé | ❌ | ❌ | ✅ |
| `backend_startup` | Backend au démarrage | ❌ | ✅ | ✅ |
| `config_changes` | Changements config UI | ❌ | ❌ | ✅ |
| `performance_warning` | Warnings performance | ✅ | ✅ | ✅ |
| `progress_info` | Progression opérations | ❌ | ✅ | ✅ |
| `history_status` | Status historique | ❌ | ❌ | ✅ |
| `error_critical` | Erreurs critiques | ✅ | ✅ | ✅ |
| `error_warning` | Warnings non-critiques | ❌ | ✅ | ✅ |

### Ajouter une nouvelle catégorie

Éditer `config/feedback_config.py` :

```python
MESSAGE_CATEGORIES = {
    # ... existing categories ...
    
    'my_new_category': {
        'description': 'Description de la catégorie',
        'minimal': False,  # Masquer en minimal
        'normal': True,    # Afficher en normal
        'verbose': True    # Afficher en verbose
    }
}
```

Utiliser dans le code :

```python
if should_show_message('my_new_category'):
    iface.messageBar().pushInfo("FilterMate", "Mon message")
```

## 📝 Messages Supprimés (v2.3.0)

### 1. Undo/Redo (8 messages → 0)

**Avant** :
```python
iface.messageBar().pushSuccess("FilterMate", f"Global undo successful ({count} layers)")
iface.messageBar().pushSuccess("FilterMate", f"Undo: {description}")
iface.messageBar().pushWarning("FilterMate", "No more undo history")
# + 5 autres similaires
```

**Après** :
```python
# Supprimé - le feedback UI (boutons désactivés) suffit
# Les logs restent pour debugging
logger.info(f"FilterMate: Undo to {description}")
```

**Justification** :
- L'utilisateur voit le résultat immédiatement dans le canvas
- Les boutons undo/redo sont désactivés quand plus d'historique
- Messages créaient du bruit sans valeur ajoutée

### 2. Config UI Changes (4 messages → 0)

**Avant** :
```python
iface.messageBar().pushSuccess("FilterMate", "UI profile changed to COMPACT mode")
iface.messageBar().pushInfo("FilterMate", "Export style changed to QML")
# + 2 autres
```

**Après** :
```python
# Supprimé - le changement est visible dans l'interface
logger.info(f"UI profile changed to {profile}")
```

**Justification** :
- Le combobox montre déjà la nouvelle valeur
- L'UI se met à jour visuellement
- Message redondant avec feedback visuel

### 3. "No More History" (4 messages → 0)

**Avant** :
```python
iface.messageBar().pushWarning("FilterMate", "No more undo history")
iface.messageBar().pushWarning("FilterMate", "No more redo history")
```

**Après** :
```python
# Supprimé - boutons déjà désactivés
# Condition est vérifiée, mais pas de message
```

**Justification** :
- Les boutons sont déjà grisés (disabled)
- Double feedback inutile
- L'utilisateur comprend visuellement

## 🎨 Alternatives Futures

### Option A : Widget Status Intégré (v2.4+)

Au lieu de la messageBar QGIS, widget status dans le panel :

```
┌─ FilterMate ─────────────────────┐
│ Status: 45,231 features visible │  ← Status permanent
│ Backend: PostgreSQL              │
│ Last: Filtered 3 layers          │
├──────────────────────────────────┤
│ [Filter] [Undo] [Redo] [Reset]   │
└──────────────────────────────────┘
```

**Avantages** :
- ✅ Non-intrusif (pas de popup)
- ✅ Contexte permanent
- ✅ Historique visible
- ❌ Requiert refonte UI

### Option B : Toast Notifications (v2.5+)

Notifications style "toast" coin de l'écran :

```
╭─────────────────────────╮
│ ✓ 3 layers filtered     │  ← Auto-hide après 2s
│   45,231 features       │
╰─────────────────────────╯
```

**Avantages** :
- ✅ Non-bloquant
- ✅ Élégant
- ✅ Auto-dismiss
- ❌ Nécessite Qt custom widget

## 📈 Impact Mesuré

### Statistiques d'utilisation typique

**Session de travail (1h)** :

| Opération | Fréquence | Messages (Avant) | Messages (Normal) | Messages (Minimal) |
|-----------|-----------|------------------|-------------------|-------------------|
| Filtrage | 20× | 60 (3 par filtre) | 40 (2 par filtre) | 0 |
| Undo/Redo | 15× | 15 | 0 | 0 |
| Config UI | 3× | 3 | 0 | 0 |
| Exports | 5× | 10 (2 par export) | 10 | 5 |
| Erreurs | 2× | 2 | 2 | 2 |
| **TOTAL** | - | **90 messages** | **52 messages** | **7 messages** |

**Réduction** :
- Normal : **-42% de messages** (-38 messages)
- Minimal : **-92% de messages** (-83 messages)

## 🐛 Debugging

### Problème : Aucun message ne s'affiche

**Diagnostic** :
```python
from config.feedback_config import get_feedback_level, get_feedback_config_summary

# Vérifier niveau actuel
print(get_feedback_level())  # FeedbackLevel.MINIMAL ?

# Voir config complète
summary = get_feedback_config_summary()
print(f"Level: {summary['level']}")
print(f"Enabled: {summary['enabled_categories']}")
```

**Solution** :
- Changer niveau dans `config.json`
- Redémarrer QGIS
- Vérifier que `config.json` n'est pas en lecture seule

### Problème : Tous les messages s'affichent

**Cause possible** :
- Niveau = "verbose"
- Fichier `feedback_config.py` pas importé

**Vérification** :
```python
# Dans filter_mate_app.py __init__
try:
    from config.feedback_config import set_feedback_level_from_string
    # Si ça échoue, fallback à "show all"
except ImportError:
    print("WARN: feedback_config not available")
```

## 📚 Références

- Code principal : `config/feedback_config.py`
- Utilisation : `modules/feedback_utils.py`
- Configuration : `config/config.default.json`
- Initialisation : `filter_mate_app.py` ligne ~177

## 🔜 Roadmap

### v2.3.0 (Actuel)
- ✅ Système de verbosité
- ✅ Suppression messages redondants
- ✅ Configuration JSON

### v2.4.0 (Q1 2026)
- 🔄 UI Settings pour feedback level
- 🔄 Widget status intégré
- 🔄 Preview des niveaux

### v2.5.0 (Q2 2026)
- 📋 Toast notifications
- 📋 Message batching (regroupement)
- 📋 Smart filtering (apprendre préférences)

---

**Dernière mise à jour** : 2025-12-13  
**Auteur** : FilterMate Dev Team  
**Version** : 2.3.0
