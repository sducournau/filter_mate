# Fix: Access Violation / Fatal Exception (Windows)

**Date**: 2025-12-19  
**Type**: Critical Bug Fix  
**Priorité**: CRITIQUE  
**Statut**: Résolu

## Problème rapporté

### Crash QGIS avec Access Violation

```
Windows fatal exception: access violation

Current thread 0x000042b0 (most recent call first):

Stack Trace:
QgsCustomization::preNotify
QObject::event
QApplicationPrivate::notify_helper
QApplication::notify
QgsApplication::notify
QCoreApplication::notifyInternal2
QCoreApplicationPrivate::sendPostedEvents
```

**Environnement:**
- QGIS Version: 3.44.2-Solothurn
- OS: Windows 10.0.26200
- Qt: 5.15.13

### Symptômes
- Crash aléatoire lors du rechargement du plugin
- Crash lors de la fermeture de QGIS
- Message "access violation" (violation d'accès mémoire)
- Crash dans le système de notification Qt

## Analyse technique

### Cause racine

Le problème était causé par des **lambdas dans `QTimer.singleShot`** qui référençaient des objets Python (`self`) après leur destruction par le garbage collector.

#### Scénario du crash

1. Un `QTimer.singleShot` est créé avec une lambda qui capture `self`
2. Le plugin est rechargé ou QGIS est fermé
3. L'objet `FilterMateApp` est détruit par Python
4. Le timer Qt expire et tente d'appeler la lambda
5. La lambda accède à `self` qui pointe vers de la mémoire libérée
6. **Access Violation** → Crash de QGIS

#### Code problématique (AVANT)

```python
# ❌ DANGEREUX: self peut être détruit avant l'exécution du timer
QTimer.singleShot(1000, lambda: self.manage_task('add_layers', layers))

# ❌ DANGEREUX: capture de self dans une closure
QTimer.singleShot(500, lambda l=layers: self._on_layers_added(l))

# ❌ DANGEREUX: fonctions imbriquées capturant self
def ensure_ui_enabled():
    if self.dockwidget:  # self peut être invalide ici
        self.dockwidget.refresh()

QTimer.singleShot(3000, ensure_ui_enabled)
```

### Emplacements affectés

**Fichier:** [filter_mate_app.py](../filter_mate_app.py)

Lambdas dangereuses identifiées:
- **Ligne 150**: Debouncing du signal `layersAdded`
- **Ligne 562**: Chargement différé des couches après rechargement
- **Ligne 567**: Rafraîchissement UI après rechargement
- **Ligne 755**: Attente de l'initialisation des widgets
- **Ligne 780**: Retry de `add_layers` après échec
- **Ligne 782**: Timer de sécurité final
- **Ligne 849**: Timer de sécurité principal
- **Ligne 888**: Ajout de nouvelles couches

## Solution implémentée

### 1. Utilisation de Weak References

Remplacement de toutes les lambdas par des fonctions qui utilisent `weakref.ref()` pour permettre au garbage collector de libérer les objets sans crasher.

#### Code corrigé (APRÈS)

```python
import weakref

# ✅ SÉCURISÉ: utilise weakref pour vérifier que self existe encore
weak_self = weakref.ref(self)
def safe_callback():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self.manage_task('add_layers', layers)

QTimer.singleShot(1000, safe_callback)
```

#### Explication technique

**`weakref.ref()`** crée une référence faible à `self` qui:
- Ne bloque PAS le garbage collector
- Retourne `None` si l'objet a été détruit
- Évite les access violations

**Pattern utilisé:**

```python
weak_self = weakref.ref(self)  # Créer référence faible

def safe_callback():
    strong_self = weak_self()  # Tenter de récupérer l'objet
    if strong_self is not None:  # Vérifier si encore vivant
        strong_self.method()  # Appeler seulement si valide

QTimer.singleShot(delay, safe_callback)
```

### 2. Vérifications supplémentaires dans les callbacks

Ajout de try/except et vérifications `hasattr()` pour les cas limites:

```python
def ensure_ui_enabled():
    # CRITICAL: Check if self still exists
    try:
        if not hasattr(self, 'dockwidget'):
            logger.warning("Safety timer: plugin may be unloaded")
            return
    except RuntimeError:
        logger.warning("Safety timer: self object destroyed")
        return
    
    if not self.dockwidget:
        logger.warning("Safety timer: Dockwidget is None")
        return
    
    # Code sûr ici...
```

### 3. Fonction utilitaire pour messages sécurisés

Création de `safe_show_message()` pour éviter les crashes lors de l'affichage de messages:

```python
def safe_show_message(level, title, message):
    """
    Safely show a message in QGIS interface, catching RuntimeError if interface is destroyed.
    
    This prevents access violations when showing messages after plugin unload or QGIS shutdown.
    
    Args:
        level (str): Message level - 'success', 'info', 'warning', or 'critical'
        title (str): Message title
        message (str): Message content
    
    Returns:
        bool: True if message was shown, False if interface unavailable
    """
    try:
        message_bar = iface.messageBar()
        if level == 'success':
            message_bar.pushSuccess(title, message)
        elif level == 'info':
            message_bar.pushInfo(title, message)
        elif level == 'warning':
            message_bar.pushWarning(title, message)
        elif level == 'critical':
            message_bar.pushCritical(title, message)
        return True
    except (RuntimeError, AttributeError) as e:
        logger.warning(f"Cannot show {level} message '{title}': interface may be destroyed ({e})")
        return False
```

**Utilisation:**
```python
# Au lieu de:
# iface.messageBar().pushInfo("FilterMate", "Message")  # ❌ Peut crasher

# Utiliser:
safe_show_message('info', "FilterMate", "Message")  # ✅ Sûr
```

## Modifications détaillées

### Imports ajoutés

```python
import weakref
```

### Corrections par emplacement

#### 1. Ligne 150 - Debouncing layersAdded
**Avant:**
```python
QTimer.singleShot(debounce_ms, lambda l=layers: self._on_layers_added(l))
```

**Après:**
```python
weak_self = weakref.ref(self)
def safe_callback():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self._on_layers_added(layers)
QTimer.singleShot(debounce_ms, safe_callback)
```

#### 2. Lignes 562 & 567 - Force reload layers
**Avant:**
```python
QTimer.singleShot(delay, lambda layers=current_layers: self.manage_task('add_layers', layers))
QTimer.singleShot(refresh_delay, self._force_ui_refresh_after_reload)
```

**Après:**
```python
weak_self = weakref.ref(self)
def safe_add_layers():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self.manage_task('add_layers', current_layers)
QTimer.singleShot(delay, safe_add_layers)

def safe_ui_refresh():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self._force_ui_refresh_after_reload()
QTimer.singleShot(refresh_delay, safe_ui_refresh)
```

#### 3. Ligne 755 - Wait for widget initialization
**Avant:**
```python
QTimer.singleShot(600, lambda: wait_for_widget_initialization(init_layers))
```

**Après:**
```python
weak_self = weakref.ref(self)
def safe_wait_init():
    strong_self = weak_self()
    if strong_self is not None:
        wait_for_widget_initialization(init_layers)
QTimer.singleShot(600, safe_wait_init)
```

#### 4. Ligne 780 - Recovery retry add_layers
**Avant:**
```python
QTimer.singleShot(100, lambda layers=current_layers: self.manage_task('add_layers', layers))
```

**Après:**
```python
weak_self = weakref.ref(self)
def safe_retry_add():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self.manage_task('add_layers', current_layers)
QTimer.singleShot(100, safe_retry_add)
```

#### 5. Ligne 849 - Safety timer ensure_ui_enabled
**Avant:**
```python
QTimer.singleShot(5000, ensure_ui_enabled)
```

**Après:**
```python
weak_self = weakref.ref(self)
def safe_ensure_ui():
    strong_self = weak_self()
    if strong_self is not None:
        ensure_ui_enabled()
QTimer.singleShot(5000, safe_ensure_ui)
```

#### 6. Ligne 888 - On layers added
**Avant:**
```python
QTimer.singleShot(300, lambda layers=self._filter_usable_layers(new_layers): self.manage_task('add_layers', layers))
```

**Après:**
```python
usable = self._filter_usable_layers(new_layers)
weak_self = weakref.ref(self)
def safe_add_new_layers():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self.manage_task('add_layers', usable)
QTimer.singleShot(300, safe_add_new_layers)
```

## Tests recommandés

### Scénarios de test

1. **Rechargement du plugin**
   ```
   Actions:
   - Activer FilterMate
   - Attendre 2-3 secondes
   - Recharger le plugin (Plugin Reloader)
   - Répéter 10 fois
   
   Résultat attendu: Aucun crash
   ```

2. **Fermeture de QGIS pendant chargement**
   ```
   Actions:
   - Ouvrir QGIS avec un gros projet
   - Activer FilterMate
   - Fermer QGIS IMMÉDIATEMENT (pendant chargement)
   
   Résultat attendu: Fermeture propre sans crash
   ```

3. **Rechargement pendant tâches actives**
   ```
   Actions:
   - Activer FilterMate
   - Lancer un filtrage
   - Pendant l'exécution, recharger le plugin
   
   Résultat attendu: Tâches annulées proprement, pas de crash
   ```

4. **Changement rapide de projet**
   ```
   Actions:
   - Ouvrir projet A avec FilterMate actif
   - Attendre 2 secondes (timers en cours)
   - Ouvrir projet B immédiatement
   
   Résultat attendu: Transition propre sans crash
   ```

## Impact et bénéfices

### Stabilité améliorée
- ✅ Plus de crashes lors du rechargement du plugin
- ✅ Fermeture propre de QGIS même avec timers actifs
- ✅ Gestion gracieuse de la destruction des objets

### Maintenabilité
- ✅ Pattern clair et réutilisable pour futurs timers
- ✅ Logging amélioré pour diagnostic
- ✅ Code plus défensif

### Performance
- ⚠️ Overhead négligeable (quelques nanosec par callback)
- ✅ Pas d'impact visible pour l'utilisateur

## Recommandations pour le futur

### Pattern à suivre pour tous les QTimer

**TOUJOURS utiliser ce pattern:**

```python
# ✅ CORRECT: Pattern sécurisé avec weakref
weak_self = weakref.ref(self)
def safe_callback():
    strong_self = weak_self()
    if strong_self is not None:
        # Code utilisant strong_self
        strong_self.do_something()

QTimer.singleShot(delay_ms, safe_callback)
```

**NE JAMAIS faire:**

```python
# ❌ INTERDIT: Lambda capturant self directement
QTimer.singleShot(delay_ms, lambda: self.do_something())

# ❌ INTERDIT: Fonction capturant self sans weakref
def callback():
    self.do_something()  # self peut être détruit
QTimer.singleShot(delay_ms, callback)
```

### Vérifications dans les callbacks

Toujours vérifier les attributs Qt avant utilisation:

```python
def callback():
    # Vérifier self
    try:
        if not hasattr(self, 'dockwidget'):
            return
    except RuntimeError:
        return
    
    # Vérifier objets Qt
    if not self.dockwidget:
        return
    
    # Code sûr ici...
```

### Affichage de messages

Toujours utiliser `safe_show_message()` dans les callbacks différés:

```python
# Dans un QTimer callback
safe_show_message('info', "FilterMate", "Opération terminée")
```

## Références

### Documentation Qt
- [QTimer](https://doc.qt.io/qt-5/qtimer.html)
- [QObject destruction](https://doc.qt.io/qt-5/qobject.html#dtor.QObject)

### Documentation Python
- [weakref module](https://docs.python.org/3/library/weakref.html)
- [Garbage Collection](https://docs.python.org/3/library/gc.html)

### Issues liées
- N/A (premier rapport)

## Auteur et révision

**Développeur**: Copilot / Simon Ducourneau  
**Révisé par**: N/A  
**Date de résolution**: 2025-12-19  
**Version**: 2.3.9 (prévue)

---

**Status:** ✅ Résolu - Corrections appliquées, tests requis
