# Guide Rapide : Réduire les Notifications FilterMate

## 🎯 Objectif

Vous trouvez que FilterMate affiche **trop de messages** ? Ce guide vous montre comment réduire les notifications.

## ⚡ Solution Rapide (30 secondes)

### 1. Ouvrir la configuration

Naviguez vers :
```
<QGIS_profile>/python/plugins/filter_mate/config/config.json
```

Par exemple :
- Windows : `C:\Users\VotreNom\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\filter_mate\config\config.json`
- Linux : `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/config/config.json`
- macOS : `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/config/config.json`

### 2. Modifier le niveau de feedback

Cherchez cette section (lignes 3-12) :

```json
{
    "APP": {
        "DOCKWIDGET": {
            "FEEDBACK_LEVEL": {
                "choices": ["minimal", "normal", "verbose"],
                "value": "normal"  ← CHANGER ICI
            },
```

Changez `"normal"` en `"minimal"` :

```json
"value": "minimal"
```

### 3. Redémarrer QGIS

Fermez et relancez QGIS. C'est tout ! ✅

## 📊 Comparaison des Niveaux

### 🔴 Minimal (Recommandé si vous n'aimez pas les notifications)

**Ce que vous verrez** :
- ✅ Erreurs critiques uniquement (connexion échouée, etc.)
- ✅ Warnings performance (si >100k features)
- ✅ Confirmation exports

**Ce que vous NE verrez PAS** :
- ❌ "X features visible" après chaque filtre
- ❌ Messages undo/redo
- ❌ Info sur le backend utilisé
- ❌ Confirmations changements config

**Réduction** : **92% moins de messages** (7 vs 90 par session)

---

### 🟡 Normal (Défaut - Équilibré)

**Ce que vous verrez** :
- ✅ Erreurs et warnings importants
- ✅ Comptage features après filtrage
- ✅ Succès des exports
- ✅ Warnings performance

**Ce que vous NE verrez PAS** :
- ❌ Messages undo/redo (les boutons suffisent)
- ❌ "No more history" (boutons déjà grisés)
- ❌ Confirmations config UI

**Réduction** : **42% moins de messages** (52 vs 90 par session)

---

### 🟢 Verbose (Mode Debug)

**Ce que vous verrez** :
- ✅ **TOUS les messages** (48 messages)
- ✅ Détails techniques backend
- ✅ Progression détaillée
- ✅ Confirmations undo/redo

**Usage** : Développement, support technique, debugging

---

## 🎯 Quel Niveau Choisir ?

### Vous êtes... → Utilisez :

- 👤 **Utilisateur avancé** qui connaît bien QGIS → **Minimal**
- 👥 **Utilisateur régulier** → **Normal** (défaut)
- 🔧 **Développeur / Support** → **Verbose**
- 😤 **Agacé par les popups** → **Minimal**
- 🆕 **Débutant** qui veut comprendre → **Normal** ou **Verbose**

## 🐛 Résolution de Problèmes

### "Je ne vois AUCUN message, même les erreurs"

**Vérifiez** :
1. Le fichier `config.json` est bien sauvegardé
2. Pas de faute de frappe : `"minimal"` (pas `"minimum"`)
3. JSON valide (virgules, guillemets)
4. QGIS redémarré

**Exemple JSON correct** :
```json
{
    "APP": {
        "DOCKWIDGET": {
            "FEEDBACK_LEVEL": {
                "choices": ["minimal", "normal", "verbose"],
                "value": "minimal"
            },
            "_FEEDBACK_LEVEL_META": {
                ...
            }
        }
    }
}
```

### "Je vois TOUS les messages malgré minimal"

**Cause possible** : Configuration non chargée

**Solution** :
1. Vérifier logs QGIS : Menu → Plugins → Python Console
2. Chercher : `FilterMate: Feedback level set to 'minimal'`
3. Si absent, problème de chargement config

### "Je veux des niveaux intermédiaires"

**Possible mais avancé** : Modifier `config/feedback_config.py`

Exemple : Créer un niveau "silent" (aucun message) :

```python
MESSAGE_CATEGORIES = {
    'filter_count': {
        'minimal': False,
        'normal': True,
        'silent': False,  # ← Ajouter
        'verbose': True
    },
    # ... pour toutes les catégories
}
```

Puis dans `config.json` :
```json
"choices": ["silent", "minimal", "normal", "verbose"],
"value": "silent"
```

## 📚 Documentation Complète

Pour comprendre en détail le système :
- **Guide développeur** : `docs/USER_FEEDBACK_SYSTEM.md`
- **Code source** : `config/feedback_config.py`
- **Changelog** : `CHANGELOG.md` (section 2.3.0)

## 🎨 Futures Améliorations (v2.4+)

- UI graphique pour changer le niveau (sans éditer JSON)
- Widget de status intégré (au lieu de la messagebar QGIS)
- Toast notifications (disparaissent automatiquement)
- Personnalisation catégorie par catégorie

---

**Besoin d'aide ?** Ouvrez une issue sur GitHub : https://github.com/sducournau/filter_mate

**Version** : FilterMate 2.3.0  
**Dernière mise à jour** : 2025-12-13
