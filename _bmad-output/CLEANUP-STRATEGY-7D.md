# Phase 7D Cleanup Strategy - Quick Wins

**Objectif:** 4,528 → ~2,000 lignes en 2-3h  
**Approche:** Gains rapides, tests entre chaque batch

## 🎯 BATCH 1: Supprimer méthodes utilitaires obsolètes (30min, -300 lignes)

### Méthodes à supprimer complètement:

Ces méthodes sont déléguées aux executors ET le corps original n'est plus utilisé:

1. **Déjà déléguées mais corps présent:**
   - Les executors ont le code complet
   - FilterEngineTask appelle juste l'executor
   - Le corps original = code mort

**Action:** Garder juste l'appel delegation, supprimer l'implémentation

## 🎯 BATCH 2: Nettoyer imports inutilisés (15min, -50 lignes)

Après suppression méthodes, certains imports deviennent inutiles.

## 🎯 BATCH 3: Supprimer commentaires/docstrings dupliqués (15min, -200 lignes)

De nombreuses méthodes ont des docstrings de 20-30 lignes qui dupliquent les executors.

## 🎯 BATCH 4: Simplifier __init__ (30min, -100 lignes)

Beaucoup de variables d'instance ne sont plus nécessaires après délégation.

## ⚠️ CRITIQUE: NE PAS supprimer

- Méthodes `run()`, `finished()` (orchestration QgsTask)
- Méthodes appelées depuis UI (`filter_mate_app.py`)
- Méthodes legacy encore utilisées

## 🚀 Exécution

On fait batch par batch, commit entre chaque, test smoke.

**Estimation réaliste:** -650 lignes en 2h
**Résultat attendu:** 4,528 → 3,878 lignes (-14%)
