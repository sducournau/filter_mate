---
stepsCompleted: ["step-01-init", "step-02-discovery", "step-03-success", "step-04-journeys", "step-05-domain", "step-06-innovation", "step-07-project-type", "step-08-scoping", "step-09-functional", "step-10-nonfunctional", "step-11-polish"]
inputDocuments:
  - "docs/ARCHITECTURE.md"
  - "docs/TECHNICAL_SUMMARY.md"
  - "_bmad-output/planning-artifacts/architecture.md"
  - "_bmad-output/planning-artifacts/EPIC-1-completion-report.md"
workflowType: "prd"
projectType: "brownfield"
documentCounts:
  briefs: 0
  research: 0
  projectDocs: 4
  brainstorming: 1
classification:
  projectType: "QGIS Desktop Plugin"
  domain: "Geomatics / Advanced Spatial Analysis"
  complexity: "VERY HIGH"
  projectContext: "brownfield"
elicitationSessions:
  - method: "User Persona Focus Group"
    date: "2026-01-27"
    participants: ["Marie (Geomatician)", "Thomas (Urban Planner)", "Élise (Risk Analyst)", "Lucas (Forest Engineer)", "Sophia (Data Scientist)"]
  - method: "Cross-Functional War Room"
    date: "2026-01-27"
    participants: ["Jean-Marc (PM)", "Amélie (Dev Lead)", "Karim (UX Designer)"]
  - method: "Party Mode - Success Criteria Review"
    date: "2026-01-27"
    participants: ["John (PM)", "Winston (Architect)", "Sally (UX Designer)", "Murat (Test Architect)"]
    improvements:
      - "NPS in-app + track real feature activations"
      - "Histogram visible by default (not hidden in 'More options')"
      - "Graceful degradation criteria + no memory crash requirement"
      - "LiDAR load tests + stats precision validation + novice UX tests"
uiDecisions:
  layout: "Accordion (Option B)"
  rationale: "Preserves sequential workflow, fits in 400px dockwidget"
scopeDecision:
  selected: "MVP+"
  definition: "MVP + Interactive Histogram"
  estimatedEffort: "8 weeks"
  targetDate: "March 2026"
roadmap:
  phase1:
    name: "MVP+"
    duration: "8 weeks"
    target: "March 2026"
    features: ["Raster foundation", "Exploring Raster accordion", "Basic zonal stats", "Interactive histogram", "Range filter", "Stats export to attributes"]
  phase2:
    name: "Standard"
    duration: "6 weeks"
    target: "May 2026"
    features: ["Elevation profile", "DEM derivatives", "Big raster performance", "Multi-format support"]
  phase3:
    name: "Advanced"
    duration: "6 weeks"
    target: "July 2026"
    features: ["Python API", "Auto mosaicking", "Raster Calculator", "3D preview"]
---

# Product Requirements Document - FilterMate Raster Integration (EPIC-2)

**Author:** Simon
**Date:** 2026-01-27

## Brainstorming Context

This PRD is based on the brainstorming session conducted on 2026-01-27 which validated:

- **Proposition B++**: Double Exploring (Vector + Raster/LiDAR)
- **UI Concept**: Parallel exploration of vector and raster data
- **Key Features**:
  - Dual exploring panels (Vector + Raster/LiDAR)
  - Linked exploration (vector selection defines raster analysis zone)
  - Combined filtering criteria (vector attributes + raster values)
  - Interactive histogram for raster value selection
  - Profile tool for LiDAR/DEM analysis
  - Zonal statistics integration

## User Persona Focus Group Insights (2026-01-27)

### Validated Features (Strong Consensus)

| Feature                             | Validation Level     |
| ----------------------------------- | -------------------- |
| Dual Exploring Vector + Raster      | ⭐⭐⭐⭐⭐ Unanimous |
| Interactive histogram               | ⭐⭐⭐⭐⭐ Unanimous |
| Vector selection → raster zone link | ⭐⭐⭐⭐⭐ Unanimous |
| Zonal statistics                    | ⭐⭐⭐⭐⭐ Unanimous |
| Automatic NoData masking            | ⭐⭐⭐⭐⭐ Unanimous |
| Elevation profile                   | ⭐⭐⭐⭐ High demand |

### Newly Revealed Requirements

| Requirement                                 | Persona Source          | Priority     |
| ------------------------------------------- | ----------------------- | ------------ |
| Export zonal stats to vector attributes     | Élise (Risk Analyst)    | 🔴 Critical  |
| DEM derivatives calculation (slope, aspect) | Lucas (Forest Engineer) | 🔴 Critical  |
| Performance on large rasters (> 1 GB)       | Élise, Lucas            | 🔴 Critical  |
| Multi-format support (GeoTIFF, ASCII, ECW)  | Thomas (Urban Planner)  | 🟡 Important |
| Automatic tile mosaicking                   | Lucas                   | 🟡 Important |
| Scriptable Python API                       | Sophia (Data Scientist) | 🟢 Desirable |
| Smart histogram sampling                    | Sophia                  | 🟢 Desirable |
| Simplified UX for non-experts               | Thomas                  | 🟡 Important |

### Identified Risks

1. **Performance**: IGN LiDAR files are very large (several GB). Without optimization (tiling, streaming), the tool will be unusable.
2. **UI Complexity**: Risk of creating an overly technical interface. Non-expert users must be able to use the tool.
3. **DEM Derivatives**: Users need slope/aspect, not just elevation. This requires prior calculation or raster calculator integration.

## Cross-Functional War Room Insights (2026-01-27)

### Participants

- **Jean-Marc (PM)**: Product viability, roadmap, priorities
- **Amélie (Dev Lead)**: Technical feasibility, architecture, effort
- **Karim (UX Designer)**: Desirability, user experience, simplicity

### Key Decisions

| Decision                                  | Justification                                   | Owner |
| ----------------------------------------- | ----------------------------------------------- | ----- |
| **Accordion Layout** (Option B)           | Preserves sequential workflow, fits 400px width | UX    |
| **MVP+ scope**                            | MVP + interactive histogram (differentiator)    | PM    |
| **Zonal stats via QgsZonalStatistics**    | Already in QGIS, fast to integrate              | Dev   |
| **GDAL windowed reading** for performance | Mandatory for IGN LiDAR                         | Dev   |
| **Explicit visual link** vector↔raster    | Critical for user understanding                 | UX    |

### Accepted Trade-offs (Deferred to Phase 2+)

| Deferred Feature               | Saved Effort | Target Phase |
| ------------------------------ | ------------ | ------------ |
| Elevation profile              | 3 weeks      | Phase 2      |
| DEM derivatives (slope/aspect) | 2 weeks      | Phase 2      |
| Scriptable Python API          | 2 weeks      | Phase 3      |
| Automatic tile mosaicking      | 2 weeks      | Phase 3      |

### Technical Constraints Identified

1. **400px dockwidget width**: Side-by-side panels don't fit → Accordion chosen
2. **Large raster RAM usage**: `QgsRasterLayer.dataProvider().block()` loads all in RAM → Use GDAL windowed reading
3. **DEM derivatives**: Require `native:slope`/`native:aspect` or on-the-fly GDAL/NumPy calculation
4. **Architecture impact**: Current FilterMate built around `QgsVectorLayer` → Need new raster port in `core/ports/`

### Proposed Roadmap

```
PHASE 1 - MVP+ (8 weeks) ────────────────────────────── March 2026
├─ Raster foundation (ports, adapters, services)
├─ Exploring Raster (accordion, value reading)
├─ Basic zonal statistics
├─ Interactive histogram with range selection
├─ Filter by raster value range
└─ Export stats to vector attributes

PHASE 2 - Standard (6 weeks) ────────────────────────── May 2026
├─ Elevation profile
├─ DEM derivatives (slope, aspect)
├─ Big raster performance (GDAL streaming)
└─ Multi-format support

PHASE 3 - Advanced (6 weeks) ────────────────────────── July 2026
├─ Python API (scriptable)
├─ Automatic tile mosaicking
├─ Integrated Raster Calculator
└─ 3D preview
```

## Simplified UI Design (Final - User Approved)

### Philosophy

- **Simple by default**: Non-expert users see only essential controls
- **Raster = "just another criteria"**: Integrates naturally with existing multi-step workflow
- **Progressive disclosure**: Advanced features behind "More options"

### EXPLORING Panel - Raster Tab

```
┌─────────────────────────────────────────────────────────────┐
│ 🏔️ RASTER                                                  │
├─────────────────────────────────────────────────────────────┤
│ Raster layer: [▼ MNT_LiDAR_BZH              ▼]             │
│                                                             │
│ 🔗 Linked to vector selection                              │
│    Zone: "Saint-Malo" (36.58 km²)                          │
│                                                             │
│ ── Filter by values ────────────────────────────────────── │
│                                                             │
│   Min: [___0___]  Max: [__100__]  m                        │
│                                                             │
│   Quick: [< 50m ▼]  (Flood zones, Low elevation, etc.)     │
│                                                             │
│   ▼ More options                                           │
│     ☐ Exclude NoData                                       │
│     ☐ Show histogram                                       │
│     ☐ Zonal statistics                                     │
│                                                             │
│ [➕ Add to criteria]                                        │
└─────────────────────────────────────────────────────────────┘
```

### FILTERING Panel - Multi-Step Integration

```
┌─────────────────────────────────────────────────────────────┐
│ FILTERING                                          [≡ Chain]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─ Active criteria ───────────────────────────────────────┐│
│ │                                                          ││
│ │  1️⃣ 📦 name = 'Saint-Malo'              [×]            ││
│ │     ↳ Layer: communes_bzh                               ││
│ │                                                          ││
│ │  2️⃣ 🏔️ elevation BETWEEN 0 AND 50      [×]            ││
│ │     ↳ Raster: MNT_LiDAR_BZH                             ││
│ │     ↳ Linked to: criterion 1                            ││
│ │                                                          ││
│ │  [AND ▼]  ← Logic operator                              ││
│ │                                                          ││
│ │  ─────── Drop a criterion here ───────                  ││
│ │                                                          ││
│ └──────────────────────────────────────────────────────────┘│
│                                                             │
│ Estimation: 847 features │ 12.3 km² in flood zone          │
│                                                             │
│ [▶ FILTER]  [💾 Save chain]  [📂 Load]                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### EXPORTING Panel - Raster Adaptations

```
┌─────────────────────────────────────────────────────────────┐
│ EXPORTING                                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Export type: [▼ Vector with raster statistics        ▼]    │
│                                                             │
│ ┌─ Vector options ────────────────────────────────────────┐│
│ │  Format: [GeoPackage ▼]  [📁 output.gpkg]               ││
│ │  ☑ Include filter criteria as attributes                ││
│ └──────────────────────────────────────────────────────────┘│
│                                                             │
│ ┌─ Raster statistics to add ──────────────────────────────┐│
│ │  ☑ Mean elevation      → elev_mean                      ││
│ │  ☑ Min elevation       → elev_min                       ││
│ │  ☑ Max elevation       → elev_max                       ││
│ │  ☐ Standard deviation  → elev_std                       ││
│ │  ☐ Pixel count         → pixel_count                    ││
│ └──────────────────────────────────────────────────────────┘│
│                                                             │
│ ▼ Raster clip (advanced)                                   │
│   ☐ Export clipped raster                                  │
│   ☐ Apply mask from vector selection                       │
│                                                             │
│ [▶ EXPORT]                                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### CONFIG Panel - Raster Settings

```
┌─────────────────────────────────────────────────────────────┐
│ CONFIGURATION                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─ Raster settings ───────────────────────────────────────┐│
│ │                                                          ││
│ │  Performance                                             ││
│ │  ├─ Max pixels for histogram: [1000000 ▼]               ││
│ │  └─ Use GDAL windowed reading: [☑]                      ││
│ │                                                          ││
│ │  Display                                                 ││
│ │  ├─ Default histogram bins: [256  ▼]                    ││
│ │  └─ Show NoData in histogram: [☐]                       ││
│ │                                                          ││
│ │  Zonal Statistics                                        ││
│ │  ├─ Default statistics: [mean, min, max ▼]              ││
│ │  └─ Prefix for attributes: [zs_ ▼]                      ││
│ │                                                          ││
│ └──────────────────────────────────────────────────────────┘│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Success Criteria (Party Mode Enhanced)

### User Success

| Critère                               | Mesure                              | Cible                 |
| ------------------------------------- | ----------------------------------- | --------------------- |
| **Moment "aha!" - Histogramme**       | Sélection plage de valeurs          | < 3 clics             |
| **Moment "aha!" - Stats zonales**     | Stats auto dans attributs           | Immédiat après filtre |
| **Moment "aha!" - Multi-critères**    | Filtrer vecteur + raster            | 1 clic sur "FILTER"   |
| **Visualisation raster par métrique** | Coloration min/max/mean             | Palette auto-adaptée  |
| **Filtrage pixel par range**          | Masquage pixels hors plage          | Rendu temps réel      |
| **NPS Score**                         | Popup après 1ère utilisation raster | ≥ 8/10 (moyenne)      |

**Émotions cibles :**

- 😌 **Soulagement** : "C'était compliqué, maintenant c'est simple"
- 💪 **Puissance** : "Analyses complexes sans scripts"
- ⚡ **Rapidité** : "2 clics au lieu de 10"

**Indicateur de recommandation :**

> "J'ai filtré mes parcelles en zone inondable avec stats d'altitude en 30 secondes"

### Business Success

| Métrique                | 3 mois (Mars 2026)      | 12 mois (Janvier 2027)           |
| ----------------------- | ----------------------- | -------------------------------- |
| **Téléchargements**     | +500 nouveaux           | +3,000 cumulés                   |
| **Activations raster**  | 200 utilisateurs actifs | 1,500 utilisateurs actifs        |
| **Avis positifs**       | 10 reviews ≥4★          | 50 reviews ≥4★                   |
| **Organisations**       | 3 orgas utilisatrices   | 15 orgas                         |
| **Mentions communauté** | 5 posts/articles        | Référencé dans tutoriels QGIS FR |

### Technical Success

| Opération                       | Cible Performance | Raster Test                   |
| ------------------------------- | ----------------- | ----------------------------- |
| **Histogramme (petit)**         | < 2 secondes      | Raster 100 Mo                 |
| **Histogramme (gros)**          | < 10 secondes     | Raster IGN LiDAR (1 Go)       |
| **Histogramme (échantillonné)** | < 2 secondes      | Raster > 500 Mo (1M pixels)   |
| **Application filtre raster**   | < 1 seconde       | Mise à jour rendu             |
| **Export avec stats zonales**   | < 30 secondes     | 1,000 entités × raster 100 Mo |
| **Filtre couche rapide**        | < 500 ms          | Changement visibilité pixels  |

**Critères de robustesse (Party Mode) :**

- ✅ **Pas de crash mémoire** : Aucun OOM sur rasters jusqu'à 2 Go
- ✅ **Dégradation gracieuse** : Si raster > 500 Mo → histogramme échantillonné auto
- ✅ **Précision stats** : Écart < 0.001% vs QGIS natif

### Quality Assurance Criteria (Murat)

| Type de Test          | Description                                     | Cible                   |
| --------------------- | ----------------------------------------------- | ----------------------- |
| **Test de charge**    | 10 rasters IGN LiDAR différents                 | 100% sans crash         |
| **Test de précision** | Stats zonales vs QGIS natif                     | Écart < 0.001%          |
| **Test UX novices**   | 5 utilisateurs novices parcours "filtre raster" | 100% réussite sans aide |
| **Test régression**   | Suite vectorielle existante                     | 100% pass               |

## Product Scope

### MVP - Minimum Viable Product (8 semaines)

| Fonctionnalité                         | Priorité     |
| -------------------------------------- | ------------ |
| Onglet Raster dans EXPLORING           | 🔴 Critique  |
| Sélection plage min/max                | 🔴 Critique  |
| **Histogramme VISIBLE par défaut**     | 🔴 Critique  |
| Filtre pixels par range                | 🔴 Critique  |
| Lien avec sélection vectorielle        | 🔴 Critique  |
| Stats zonales de base (mean, min, max) | 🔴 Critique  |
| Export stats vers attributs            | 🔴 Critique  |
| Visualisation raster par métrique      | 🟡 Important |
| Dégradation gracieuse (sampling)       | 🟡 Important |
| NPS popup in-app                       | 🟢 Désirable |

### Growth Features (Post-MVP - Phase 2)

| Fonctionnalité               | Valeur Ajoutée     |
| ---------------------------- | ------------------ |
| Profil d'élévation           | Analyse linéaire   |
| Dérivées DEM (pente, aspect) | Géomorphologie     |
| Multi-format (ECW, ASCII)    | Compatibilité      |
| Performance GDAL streaming   | IGN LiDAR optimisé |

### Vision (Future - Phase 3)

| Fonctionnalité        | Vision Long Terme |
| --------------------- | ----------------- |
| API Python scriptable | Automatisation    |
| Mosaïquage auto       | Tuiles IGN        |
| Calculatrice raster   | Analyses custom   |
| Prévisualisation 3D   | Immersion         |

---

## ✅ APPROVAL RECORD

### Sign-Off

| Role | Name | Decision | Date |
|------|------|----------|------|
| **Product Owner** | Simon Ducournau | ✅ **APPROVED** | 2026-01-27 |
| Tech Lead | - | ⏳ Pending | - |
| UX Designer | - | ⏳ Pending | - |

### Approval Notes

**Product Owner (Simon):**
> PRD approved for implementation. MVP scope validated with 10 features and 12.5 days effort.
> Key decisions:
> - Option B Hybride pour pushbuttons (boutons communs + raster-specific)
> - Stats inline discrètes (pas de bouton dédié)
> - Sync bidirectionnelle histogramme ↔ sélection
> - Expression Filter raster (comme vecteurs)
> - PostGIS Raster reporté à Phase 2

### Next Actions

| # | Action | Owner | Due Date |
|---|--------|-------|----------|
| 1 | Create Architecture Document | Architect | 2026-02-03 |
| 2 | Generate User Stories | SM | 2026-02-03 |
| 3 | Sprint 1 Planning | Team | 2026-02-05 |
| 4 | Begin Implementation | Dev | 2026-02-10 |

---

**PRD Status: ✅ APPROVED**
**Approval Date: January 27, 2026**

