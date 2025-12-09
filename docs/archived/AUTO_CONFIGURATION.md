# Auto-Configuration du Système UI - FilterMate

## Vue d'ensemble

Le système d'auto-configuration de FilterMate détecte automatiquement :
1. **La résolution d'écran** → Sélectionne le profil UI (compact/normal)
2. **Le thème QGIS** → Sélectionne le thème de couleurs (light/dark)

Plus besoin de configurer manuellement ! Le plugin s'adapte automatiquement à votre environnement.

## Activation

### Méthode 1 : Configuration automatique (recommandé)

Dans `config/config.json`, définissez :

```json
{
    "APP": {
        "DOCKWIDGET": {
            "UI_PROFILE": "auto",
            "COLORS": {
                "ACTIVE_THEME": "auto"
            }
        }
    }
}
```

**C'est tout !** Le plugin détectera automatiquement les paramètres optimaux.

### Méthode 2 : Configuration manuelle

Vous pouvez forcer des valeurs spécifiques :

```json
{
    "APP": {
        "DOCKWIDGET": {
            "UI_PROFILE": "compact",    // ou "normal" ou "auto"
            "COLORS": {
                "ACTIVE_THEME": "dark"  // ou "light" ou "default" ou "auto"
            }
        }
    }
}
```

## Détection du Profil UI

### Règles de détection

Le profil est sélectionné selon la résolution de l'écran principal :

| Résolution | Profil | Raison |
|------------|--------|--------|
| < 1920x1080 | **COMPACT** | Laptops 13-15", tablettes, petits écrans |
| ≥ 1920x1080 | **NORMAL** | Desktops, grands laptops, écrans HD+ |

### Exemples de résolutions

**→ COMPACT** :
- 1366x768 (laptop 14")
- 1440x900 (laptop 15")
- 1600x900 (laptop 15.6")
- 1680x1050 (écran 20")

**→ NORMAL** :
- 1920x1080 (Full HD)
- 2560x1440 (QHD)
- 3840x2160 (4K)

### Algorithme de détection

```python
if screen_width < 1920 OR screen_height < 1080:
    profile = COMPACT
else:
    profile = NORMAL
```

## Détection du Thème

### Règles de détection

Le thème est détecté en analysant la palette de QGIS :

```python
# Analyse de la luminance du fond d'écran QGIS
luminance = 0.299 * R + 0.587 * G + 0.114 * B

if luminance < 128:
    theme = "dark"    # Thème sombre
else:
    theme = "default" # Thème clair
```

### Synchronisation automatique

Lorsque `ACTIVE_THEME: "auto"`, FilterMate :
1. Lit la palette de couleurs de QGIS
2. Calcule la luminance du fond
3. Sélectionne "dark" ou "default" (light)
4. Applique automatiquement le bon schéma de couleurs

**Avantage** : Votre plugin s'intègre parfaitement avec l'apparence de QGIS !

## Ordre de priorité

L'auto-configuration respecte cette hiérarchie :

### Profil UI

1. **Config explicite** : Si `UI_PROFILE` = "compact" ou "normal" → utilise cette valeur
2. **Auto-détection** : Si `UI_PROFILE` = "auto" → détecte depuis l'écran
3. **Défaut** : Si absent ou invalide → utilise "normal"

### Thème de couleurs

1. **Config explicite** : Si `ACTIVE_THEME` = "dark", "light", "default" → utilise cette valeur
2. **Auto-détection** : Si `ACTIVE_THEME` = "auto" → détecte depuis QGIS
3. **Défaut** : Si absent ou invalide → utilise "default"

## Utilisation dans le code

### Forcer l'auto-configuration

```python
from modules import ui_widget_utils as ui_utils

# Déclencher l'auto-configuration manuellement
result = ui_utils.auto_configure_from_environment(config_data)

print(f"Profil détecté : {result['profile_detected']}")
print(f"Source : {result['profile_source']}")
print(f"Thème détecté : {result['theme_detected']}")
print(f"Résolution : {result['screen_resolution']}")
```

### Résultat de l'auto-configuration

```python
{
    'profile_detected': 'compact',
    'profile_source': 'auto-detected from screen',
    'theme_detected': 'dark',
    'theme_source': 'auto-detected from QGIS',
    'screen_resolution': '1366x768',
    'qgis_theme': 'dark'
}
```

### Vérifier la configuration active

```python
from modules.ui_config import UIConfig

# Profil actif
current_profile = UIConfig.get_profile_name()
print(f"Profil actif : {current_profile}")  # "compact" ou "normal"

# Informations détaillées
from modules import ui_widget_utils as ui_utils
info = ui_utils.get_profile_info()
print(info)
# {
#     'available': True,
#     'profile': 'compact',
#     'button_height': 32,
#     'icon_size': 18,
#     'spacing_medium': 6
# }
```

## Logs et débogage

Lors de l'initialisation, FilterMate affiche dans la console :

```
============================================================
FilterMate Auto-Configuration
============================================================
Screen Resolution: 1366x768
UI Profile: compact (auto-detected from screen)
QGIS Theme: dark
Color Theme: dark (auto-detected from QGIS)
============================================================

FilterMate UIConfig: Screen resolution detected: 1366x768
FilterMate UIConfig: Small screen detected → COMPACT profile
FilterMate: Detected QGIS dark theme (luminance: 45)
```

## Cas d'usage

### Cas 1 : Laptop 13" avec QGIS dark

**Configuration** :
```json
{
    "UI_PROFILE": "auto",
    "COLORS": {
        "ACTIVE_THEME": "auto"
    }
}
```

**Résultat** :
- Résolution : 1366x768 → **Profil COMPACT**
- QGIS dark → **Thème DARK**
- Interface compacte et sombre ✅

### Cas 2 : Desktop 27" avec QGIS light

**Configuration** :
```json
{
    "UI_PROFILE": "auto",
    "COLORS": {
        "ACTIVE_THEME": "auto"
    }
}
```

**Résultat** :
- Résolution : 2560x1440 → **Profil NORMAL**
- QGIS light → **Thème DEFAULT** (light)
- Interface spacieuse et claire ✅

### Cas 3 : Forcer compact sur grand écran

**Configuration** :
```json
{
    "UI_PROFILE": "compact",
    "COLORS": {
        "ACTIVE_THEME": "auto"
    }
}
```

**Résultat** :
- Profil forcé → **COMPACT**
- Thème auto-détecté → selon QGIS
- Utile pour préférence personnelle ✅

### Cas 4 : Configuration totalement manuelle

**Configuration** :
```json
{
    "UI_PROFILE": "normal",
    "COLORS": {
        "ACTIVE_THEME": "dark"
    }
}
```

**Résultat** :
- Profil forcé → **NORMAL**
- Thème forcé → **DARK**
- Aucune auto-détection, contrôle total ✅

## Personnalisation des seuils

Si vous souhaitez modifier les seuils de détection, éditez `modules/ui_config.py` :

```python
# Dans la méthode detect_optimal_profile()

# Seuils actuels
if width < 1920 or height < 1080:
    return DisplayProfile.COMPACT

# Exemple de seuils personnalisés
if width < 1600 or height < 900:
    return DisplayProfile.COMPACT
```

Ou dans `config.json` (documentation uniquement, non utilisé actuellement) :

```json
"UI_PROFILE_OPTIONS": {
    "auto_detection_thresholds": {
        "compact_if_width_less_than": 1920,
        "compact_if_height_less_than": 1080
    }
}
```

## Avantages de l'auto-configuration

### ✅ Expérience utilisateur optimale

- Interface adaptée automatiquement à l'écran
- Cohérence visuelle avec QGIS
- Pas de configuration manuelle

### ✅ Support multi-écrans

- Détection lors du démarrage
- S'adapte à l'écran principal
- Fonctionne sur laptop + écran externe

### ✅ Maintenance simplifiée

- Un seul fichier config.json
- Pas de profils multiples à maintenir
- Configuration par défaut optimale

### ✅ Flexibilité

- Auto-détection activable/désactivable
- Override possible pour cas spécifiques
- Transition douce entre profils

## Limitations connues

1. **Détection au démarrage uniquement**
   - La détection se fait à l'initialisation du plugin
   - Pas de re-détection en temps réel si vous changez d'écran
   - **Solution** : Redémarrer QGIS ou recharger le plugin

2. **Écran multi-moniteurs**
   - Détecte uniquement l'écran principal
   - Si QGIS est sur écran secondaire, peut ne pas être optimal
   - **Solution** : Configurer manuellement le profil

3. **Thème QGIS personnalisé**
   - Détection basée sur la luminance
   - Peut ne pas être parfait avec thèmes très customisés
   - **Solution** : Forcer le thème dans config.json

## Dépannage

### Le profil détecté ne correspond pas

**Problème** : Grand écran mais profil COMPACT sélectionné

**Causes possibles** :
1. Résolution réelle < 1920x1080 (vérifier résolution effective)
2. Scaling/DPI élevé (Windows/macOS)
3. Écran secondaire plus petit détecté

**Solution** :
```json
{
    "UI_PROFILE": "normal"  // Forcer le profil
}
```

### Le thème ne correspond pas à QGIS

**Problème** : QGIS dark mais plugin light (ou inverse)

**Causes possibles** :
1. Thème QGIS personnalisé non standard
2. Palette modifiée manuellement
3. Plugin chargé avant l'application du thème QGIS

**Solution** :
```json
{
    "COLORS": {
        "ACTIVE_THEME": "dark"  // Forcer le thème
    }
}
```

### Pas de détection (erreurs)

**Problème** : Messages d'erreur dans la console

**Causes possibles** :
1. UIConfig non disponible
2. QGIS API non accessible
3. Erreur d'import

**Solution** :
1. Vérifier les logs pour l'erreur exacte
2. Vérifier que `modules/ui_config.py` existe
3. Redémarrer QGIS
4. Forcer une configuration manuelle

## Tests

### Test manuel de détection

```python
from modules.ui_config import UIConfig

# Test détection profil
detected = UIConfig.detect_optimal_profile()
print(f"Profil détecté : {detected.value}")

# Test détection thème
from modules.ui_styles import StyleLoader
theme = StyleLoader.detect_qgis_theme()
print(f"Thème détecté : {theme}")
```

### Test avec différentes résolutions

Pour tester le comportement sur différentes résolutions :

1. Changer la résolution d'écran
2. Redémarrer QGIS
3. Vérifier les logs de détection
4. Observer l'interface

## Migration depuis version précédente

Si vous utilisez déjà FilterMate :

### Avant

```json
{
    "UI_PROFILE": "normal"
}
```

### Après (recommandé)

```json
{
    "UI_PROFILE": "auto"
}
```

**Changement** : Remplacer la valeur fixe par "auto"

**Compatibilité** : Les valeurs "compact" et "normal" continuent de fonctionner

## Ressources

- **Code source** : `modules/ui_config.py` (méthode `detect_optimal_profile`)
- **Code source** : `modules/ui_styles.py` (méthode `detect_qgis_theme`)
- **Utilitaires** : `modules/ui_widget_utils.py` (fonction `auto_configure_from_environment`)
- **Configuration** : `config/config.json`

---

**Note** : L'auto-configuration rend FilterMate plus intelligent et adaptatif, tout en restant entièrement personnalisable selon vos besoins.
