# Guide d'Utilisation - Nouvelle API Signal Utils

## 🎯 Vue d'Ensemble

FilterMate dispose désormais d'une API robuste et unifiée pour la gestion des signaux Qt. Cette API prévient les bugs courants liés aux signaux et simplifie le code.

---

## 📦 Import

```python
from modules.signal_utils import (
    SignalBlocker,          # Context manager pour blocage temporaire
    safe_connect,           # Connexion sécurisée sans doublon
    safe_disconnect,        # Déconnexion sans erreur
    SignalConnection,       # Context manager pour connexion temporaire
    SignalBlockerGroup      # Gestion de groupes de widgets
)
```

---

## 🔧 Cas d'Usage

### 1. Blocage Temporaire de Signaux

**Scénario**: Vous devez modifier plusieurs widgets sans déclencher leurs signaux.

```python
from modules.signal_utils import SignalBlocker

# Bloquer un seul widget
with SignalBlocker(combo_box):
    combo_box.setCurrentIndex(5)  # Pas de signal currentIndexChanged émis

# Bloquer plusieurs widgets
with SignalBlocker(combo1, combo2, spin_box):
    combo1.setCurrentIndex(0)
    combo2.setCurrentText("Option B")
    spin_box.setValue(100)
    # Aucun signal émis pendant ces modifications
```

**Avantages**:
- ✅ Signaux automatiquement restaurés (même en cas d'exception)
- ✅ Code lisible et concis
- ✅ Impossible d'oublier de débloquer

---

### 2. Connexion Sécurisée (Sans Doublon)

**Scénario**: Vous connectez des signaux qui peuvent être reconnectés (rechargement plugin, etc.).

```python
from modules.signal_utils import safe_connect

# ✅ RECOMMANDÉ: Connexion sécurisée
safe_connect(widget.valueChanged, on_value_changed)
safe_connect(button.clicked, on_button_clicked)

# Même si appelé plusieurs fois, une seule connexion existe
safe_connect(widget.valueChanged, on_value_changed)  # OK, pas de doublon
```

**Comparaison avec l'ancienne méthode**:

```python
# ❌ ANCIEN (risque de doublon)
widget.valueChanged.connect(on_value_changed)
# Si appelé 2x → handler appelé 2x par signal !

# ✅ NOUVEAU (sûr)
safe_connect(widget.valueChanged, on_value_changed)
# Toujours une seule connexion, même si appelé plusieurs fois
```

---

### 3. Déconnexion Sécurisée

**Scénario**: Vous devez déconnecter un signal mais n'êtes pas sûr qu'il soit connecté.

```python
from modules.signal_utils import safe_disconnect

# Déconnecter un slot spécifique
safe_disconnect(widget.valueChanged, on_value_changed)

# Déconnecter tous les slots
safe_disconnect(widget.valueChanged)

# Pas d'exception levée si non connecté
```

---

### 4. Connexion Temporaire

**Scénario**: Vous avez besoin d'un signal connecté uniquement pour une opération spécifique.

```python
from modules.signal_utils import SignalConnection

# Connexion temporaire
with SignalConnection(widget.finished, on_finished_handler):
    widget.start_operation()
    # Handler sera appelé quand 'finished' est émis
# Signal automatiquement déconnecté après le bloc
```

---

### 5. Gestion de Groupes de Widgets

**Scénario**: Vous avez plusieurs groupes fonctionnels de widgets à gérer ensemble.

```python
from modules.signal_utils import SignalBlockerGroup

# Initialisation
blocker = SignalBlockerGroup()

# Définir des groupes
blocker.add_group('exploring', 
                  exploring_widget1, 
                  exploring_widget2, 
                  exploring_widget3)

blocker.add_group('filtering',
                  filter_combo,
                  filter_button,
                  filter_options)

# Bloquer un groupe spécifique
with blocker.block('exploring'):
    # Mise à jour des widgets exploring
    exploring_widget1.setValue(10)
    exploring_widget2.setText("Test")

# Bloquer plusieurs groupes
with blocker.block('exploring', 'filtering'):
    # Mise à jour massive
    pass

# Bloquer tous les groupes
with blocker.block_all():
    # Reset complet de l'UI
    pass
```

---

## 🚨 Anti-Patterns à Éviter

### ❌ Mauvais: Blocage Manuel

```python
# ❌ NE PAS FAIRE
widget.blockSignals(True)
try:
    widget.setValue(10)
finally:
    widget.blockSignals(False)  # Oubli facile en cas d'exception !
```

### ✅ Bon: Context Manager

```python
# ✅ FAIRE
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    widget.setValue(10)
# Automatiquement restauré, même en cas d'erreur
```

---

### ❌ Mauvais: Connexion Simple

```python
# ❌ NE PAS FAIRE
def setup_ui(self):
    self.widget.valueChanged.connect(self.on_value_changed)
    # Si setup_ui() appelé 2x → handler exécuté 2x par signal
```

### ✅ Bon: safe_connect

```python
# ✅ FAIRE
from modules.signal_utils import safe_connect

def setup_ui(self):
    safe_connect(self.widget.valueChanged, self.on_value_changed)
    # Toujours une seule connexion, même si setup_ui() appelé plusieurs fois
```

---

### ❌ Mauvais: Déconnexion Sans Protection

```python
# ❌ NE PAS FAIRE
try:
    widget.valueChanged.disconnect(handler)
except:
    pass  # Masque toutes les exceptions !
```

### ✅ Bon: safe_disconnect

```python
# ✅ FAIRE
from modules.signal_utils import safe_disconnect

safe_disconnect(widget.valueChanged, handler)
# Gestion d'erreur propre, logging intégré
```

---

## 🔍 Debugging

### Activer les Logs de Debug

```python
import logging
from modules.logging_config import set_log_level

# Activer debug pour signal_utils
set_log_level('FilterMate.SignalUtils', logging.DEBUG)
```

**Sortie exemple**:
```
[DEBUG] FilterMate.SignalUtils: Blocked signals for QComboBox
[DEBUG] FilterMate.SignalUtils: Restored signals for QComboBox to False
[DEBUG] FilterMate.SignalUtils: Safely connected signal to on_value_changed
```

---

## 📊 Patterns Recommandés par Composant

### Dans `filter_mate_app.py`

```python
from modules.signal_utils import safe_connect

def connect_dockwidget_signals(self):
    """Connecte les signaux du dockwidget de manière sécurisée."""
    safe_connect(self.dockwidget.launchingTask, 
                 lambda x: self.manage_task(x))
    safe_connect(self.dockwidget.settingLayerVariable, 
                 lambda layer, props: self.save_variables_from_layer(layer, props))
    # etc.
```

### Dans `filter_mate_dockwidget.py`

```python
from modules.signal_utils import SignalBlocker

def update_ui_from_layer(self, layer):
    """Met à jour l'UI sans déclencher les signaux."""
    with SignalBlocker(
        self.combo_layer,
        self.combo_predicate,
        self.spin_buffer
    ):
        # Mise à jour massive de l'UI
        self.combo_layer.setLayer(layer)
        self.combo_predicate.setCurrentIndex(0)
        self.spin_buffer.setValue(layer_buffer_value)
```

### Dans `appTasks.py`

```python
from modules.signal_utils import safe_connect

class FilterTask(QgsTask):
    def __init__(self):
        super().__init__()
        # Connexion sécurisée des signaux de progression
        safe_connect(self.progressChanged, self.on_progress_update)
```

---

## 🧪 Tests

### Tester le Blocage de Signaux

```python
def test_signal_blocking():
    """Vérifie que SignalBlocker bloque et restaure correctement."""
    from modules.signal_utils import SignalBlocker
    
    widget = QSpinBox()
    signal_count = 0
    
    def on_value_changed(value):
        nonlocal signal_count
        signal_count += 1
    
    widget.valueChanged.connect(on_value_changed)
    
    # Sans blocage
    widget.setValue(10)
    assert signal_count == 1
    
    # Avec blocage
    with SignalBlocker(widget):
        widget.setValue(20)
        widget.setValue(30)
    
    # Signaux non émis pendant le blocage
    assert signal_count == 1
    
    # Après déblocage, signaux fonctionnent
    widget.setValue(40)
    assert signal_count == 2
```

### Tester safe_connect

```python
def test_safe_connect_prevents_duplicates():
    """Vérifie que safe_connect prévient les doublons."""
    from modules.signal_utils import safe_connect
    
    button = QPushButton()
    click_count = 0
    
    def on_clicked():
        nonlocal click_count
        click_count += 1
    
    # Connecter 3 fois
    safe_connect(button.clicked, on_clicked)
    safe_connect(button.clicked, on_clicked)
    safe_connect(button.clicked, on_clicked)
    
    # Cliquer une fois
    button.click()
    
    # Handler appelé une seule fois
    assert click_count == 1
```

---

## 📚 API Complète

### SignalBlocker

```python
class SignalBlocker:
    """Context manager pour bloquer temporairement des signaux."""
    
    def __init__(self, *widgets: QObject):
        """Initialise avec les widgets à bloquer."""
        
    def __enter__(self):
        """Entre dans le contexte, bloque les signaux."""
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sort du contexte, restaure les signaux."""
        
    def is_active(self) -> bool:
        """Vérifie si le blocage est actif."""
```

### safe_connect

```python
def safe_connect(signal, slot, connection_type=None) -> bool:
    """
    Connecte un signal de manière sécurisée.
    
    Args:
        signal: Signal Qt à connecter
        slot: Fonction/méthode handler
        connection_type: Type de connexion Qt (optionnel)
        
    Returns:
        True si succès, False sinon
    """
```

### safe_disconnect

```python
def safe_disconnect(signal, slot=None) -> bool:
    """
    Déconnecte un signal sans lever d'erreur.
    
    Args:
        signal: Signal Qt à déconnecter
        slot: Handler spécifique (None = tous)
        
    Returns:
        True si succès, False sinon
    """
```

---

## 🎓 Formation Rapide

### Checklist pour Nouveaux Développeurs

- [ ] Lire ce guide complètement
- [ ] Activer les logs debug pour signal_utils
- [ ] Remplacer blockSignals() par SignalBlocker
- [ ] Remplacer .connect() par safe_connect()
- [ ] Remplacer .disconnect() par safe_disconnect()
- [ ] Tester le rechargement du plugin
- [ ] Vérifier les logs pour connexions multiples

---

## 📞 Support

**Questions?** Consulter:
1. Ce guide
2. Docstrings dans `modules/signal_utils.py`
3. Exemples dans `filter_mate_app.py`
4. Tests dans `tests/test_signal_utils.py`

---

**Dernière mise à jour**: 10 décembre 2025  
**Version**: 1.0
