# Backlog FilterMate -- Raster & Point Cloud V1
## Date: 2026-02-11 | Auteur: Jordan (PO)

## Decisions strategiques
- **DS-1**: Pas de blocage refactoring. Sprint 0 = merge raster + fin refactoring, puis alternance features/stabilisation
- **DS-2**: QGIS min 3.22 (raster), 3.26 (PC basic), 3.32 (PC avance, optionnel)
- **DS-3**: Cherry-pick selectif de la branche raster, PAS merge direct (20 commits divergents chaque cote)
- **DS-4**: MVP Raster premier (fondations posees), MVP PC deuxieme (plus simple mais part de zero)

## EPICs
- **R0**: Fondations Raster (prerequis) -- MUST
- **R1**: Raster Value Sampling -- MUST
- **R2**: Zonal Stats as Filter (differentiateur) -- MUST
- **R3**: Raster-Driven Highlight -- SHOULD
- **R4**: Raster Clip by Vector -- COULD
- **R5**: Multi-Band Composite -- WON'T V1
- **PC1**: Point Cloud Filtrage Basique -- SHOULD
- **PC2**: Point Cloud Avance -- COULD

## Sprints
- **Sprint 0** (1.5w): US-R0.1 merge + US-R0.2 pass3 + US-R0.3 cablage UI
- **Sprint 1** (1.5w): US-R1.2 info + US-R1.1 sampling + US-R1.3 multi-bandes
- **Sprint 2** (2.5w): US-R2.1 zonal stats + US-R2.2 filtrage + US-R2.3 histogramme
- **Sprint 3** (2.5w): US-R3.1 highlight + US-PC1.0 archi + US-PC1.1 classification
- **Sprint 4** (2w): US-PC1.2 attributs/Z + US-PC1.3 combine + US-R4.1 clip
- **Sprint 5+**: PC2 avance (clip polygone, export)

## Effort total: 55-75 jours ouvrables (11-15 semaines)

## Milestones
- Alpha Raster: fin Sprint 1
- Beta Raster: fin Sprint 2
- Release Raster V1: fin Sprint 3
- Alpha Point Cloud: fin Sprint 3
- Release Point Cloud V1: fin Sprint 4
- Release FilterMate 5.0: Sprint 4 termine

## 17 User Stories numerotees (US-R0.1 a US-PC2.2)
Voir conversation Jordan du 2026-02-11 pour le detail complet (criteres d'acceptation, regles metier, notes Marco).
