# Guide Rapide BMAD pour FilterMate

## 🚀 Démarrage

BMAD (Business Model Architecture & Development) v6.0.0-alpha.22 est installé et configuré pour FilterMate.

## 📋 Commandes de Base

### Charger l'Agent Master

```
@bmad-master présente-toi
```

### Lister les Ressources Disponibles

```
@bmad-master liste toutes les ressources disponibles
```

### Démarrer un Workflow

```
@bmad-master charge le workflow brainstorming
@bmad-master lance party-mode pour discuter de [sujet]
```

## 👥 Agents Principaux

### Pour l'Analyse et la Planification

- **@analyst** (Mary) - Analyse des besoins, recherche marché, spécifications
- **@architect** (Winston) - Architecture technique, choix technologiques
- **@pm** (John) - Product Requirements Documents (PRD)

### Pour le Développement

- **@dev** (Amelia) - Implémentation stricte selon user stories
- **@quick-flow-solo-dev** (Barry) - Développement rapide, prototypes
- **@sm** (Bob) - Préparation de stories développeur

### Pour la Qualité

- **@tea** (Murat) - Tests, CI/CD, qualité
- **@tech-writer** (Paige) - Documentation technique
- **@ux-designer** (Sally) - Interface utilisateur, UX

## 🔄 Workflows Typiques

### 1. Nouvelle Fonctionnalité

```
1. @pm crée un PRD pour [fonctionnalité]
2. @architect propose l'architecture
3. @sm prépare les user stories
4. @dev implémente selon les stories
5. @tea crée les tests
6. @tech-writer documente
```

### 2. Correction de Bug

```
1. @analyst analyse le problème
2. @architect identifie la cause racine
3. @quick-flow-solo-dev corrige rapidement
4. @tea ajoute des tests de régression
```

### 3. Amélioration Performance

```
1. @analyst mesure l'impact actuel
2. @architect propose des optimisations
3. @dev implémente les changements
4. @tea valide les gains de performance
```

## 📁 Structure BMAD

```
_bmad/
├── _config/
│   ├── agent-manifest.csv      → Liste complète des agents
│   ├── workflow-manifest.csv   → Workflows disponibles
│   └── manifest.yaml           → Configuration BMAD
├── core/
│   ├── agents/                 → Agents du core BMAD
│   ├── workflows/              → Workflows génériques
│   └── resources/              → Ressources partagées
└── bmm/
    ├── agents/                 → Agents métier (BMM)
    ├── data/                   → PRDs, stories, docs
    ├── workflows/              → Workflows BMM
    └── teams/                  → Configurations d'équipes
```

## 💡 Exemples Pratiques pour FilterMate

### Ajouter un Backend

```
@architect révise l'architecture pour ajouter le support [format]
@dev implémente le backend [format] selon le pattern existant
@tea crée les tests pour le backend [format]
```

### Améliorer les Performances

```
@analyst analyse les performances actuelles avec des datasets > 100k features
@architect propose des optimisations pour Spatialite
@dev implémente les optimisations
```

### Documenter une Fonctionnalité

```
@tech-writer documente le système de filtrage avancé
@ux-designer crée un guide utilisateur visuel
```

## 🎯 Bonnes Pratiques

### DO ✅

- Spécifier l'agent approprié pour chaque tâche
- Référencer les fichiers existants dans `_bmad/bmm/data/`
- Utiliser les workflows pour les tâches complexes
- Suivre les standards de `documentation-standards.md`

### DON'T ❌

- Mélanger les rôles (ex: demander à @dev de faire de l'architecture)
- Ignorer les user stories existantes
- Contourner les workflows pour les features majeures

## 🔍 Vérification de la Configuration

### Vérifier BMAD est Actif

```
@bmad-master quelle est ta version?
```

Devrait répondre: **v6.0.0-alpha.22**

### Lister les Modules Chargés

```
@bmad-master quels modules sont chargés?
```

Devrait montrer: **core** et **bmm**

## 📚 Ressources

- **Documentation Standards**: `_bmad/bmm/data/documentation-standards.md`
- **Project Context Template**: `_bmad/bmm/data/project-context-template.md`
- **Agents Details**: `_bmad/_config/agent-manifest.csv`
- **FilterMate Guidelines**: `.github/copilot-instructions.md`

## 🆘 Support

En cas de problème:

1. Vérifier que BMAD est installé: `_bmad/_config/manifest.yaml`
2. Consulter les logs d'installation dans le manifest
3. Vérifier la configuration dans `.github/copilot-instructions.md`
4. Utiliser `@bmad-master diagnostique` pour identifier les problèmes

---

**Version**: BMAD 6.0.0-alpha.22  
**Installation**: 2026-01-06  
**Modules**: core + bmm  
**IDE**: GitHub Copilot
