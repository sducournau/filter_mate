# The Elder Scrolls -- Index de la Grande Bibliotheque
> Derniere mise a jour : 2026-02-10
> Nombre de rouleaux Serena : 21
> Nombre de rouleaux Auto-Memory : 1 (MEMORY.md)

## Guide pour les Agents
1. Consultez cet index AVANT de chercher une memoire
2. Les memoires marquees [BRANCHE] ne refletent PAS l'etat de main
3. Les memoires marquees [PERIME] doivent etre reverifiees avant usage
4. En cas de doute, demandez a The Elder Scrolls de synthetiser

## Rouleaux par Domaine

### Architecture & Design
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `project_overview` | Serena | 2026-02-10 | FIABLE | Vue d'ensemble du projet (version, architecture, metriques) |
| `CONSOLIDATED_PROJECT_CONTEXT` | Serena | 2026-02-09 | FIABLE | Contexte architectural complet, hexagonal v5.4 |
| `code_style_conventions` | Serena | 2026-01-22 | FIABLE | PEP 8, patterns, conventions de code |
| `documentation_structure` | Serena | non verifie | ATTENTION | Structure de la documentation du projet |

### Services & Domain
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `primary_key_detection_system` | Serena | 2025-12-16 | FIABLE | Detection PK par provider (PG, Spatialite, OGR, Memory) |
| `geographic_crs_handling` | Serena | 2026-01-03 | FIABLE | Conversion auto CRS geographique -> EPSG:3857 |
| `negative_buffer_wkt_handling` | Serena | non verifie | ATTENTION | Gestion des buffers negatifs et WKT |
| `filter_preservation_feature` | Serena | non verifie | ATTENTION | Fonctionnalite de preservation des filtres |

### Optimisation & Performance
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `performance_optimizations` | Serena | 2026-01-06 | FIABLE | 6 optimisations (3-45x speedup), strategies progressives |
| `enhanced_optimizer_v2.8.0` | Serena | non verifie | ATTENTION | Optimiseur ameliore v2.8 |
| `postgresql_timeout_fix_v2.5.18` | Serena | non verifie | ATTENTION | Fix timeout PostgreSQL |

### UI & Tests
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `ui_system` | Serena | 2026-01-06 | FIABLE | Architecture UI complete (themes, dimensions, widgets) |
| `testing_documentation` | Serena | 2026-01-17 | FIABLE | 157 fichiers tests, ~47,600 lignes, 75% coverage |

### Audits & Plans
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `implementation_plan_2026_02_10` | Serena | 2026-02-10 | FIABLE | Plan en 6 phases (Quick Wins -> Consolidation) |
| `action_plan_v5.0` | Serena | non verifie | ATTENTION | Plan d'action v5.0 |
| `code_quality_audit_2026` | Serena | non verifie | ATTENTION | Audit qualite code 2026 |
| `task_completion_checklist` | Serena | non verifie | ATTENTION | Checklist de completion des taches |

### Veille Technologique (Atlas)
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `raster_integration_plan_atlas_2026_02_10` | Serena | 2026-02-10 | FIABLE | Roadmap raster (5 features priorisees par Atlas) |
| `filtermate_synthesis_for_atlas_kb_2026_02_10` | Serena | 2026-02-10 | FIABLE | Synthese exhaustive FilterMate pour Atlas KB |

### Integration & Tooling
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `bmad_integration` | Serena | non verifie | ATTENTION | Integration BMAD v6.0 |
| `suggested_commands` | Serena | non verifie | ATTENTION | Commandes suggerees pour le projet |

### Auto-Memory (Claude)
| Rouleau | Stockage | Derniere MaJ | Statut | Resume |
|---------|----------|--------------|--------|--------|
| `MEMORY.md` | Claude Auto | 2026-02-10 | FIABLE | Patterns operationnels, pitfalls, roadmap raster |

## Rouleaux Recemment Modifies
- 2026-02-10 : `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Creation (synthese pour Atlas KB)
- 2026-02-10 : `elder_scrolls_index` -- Creation (index maitre de la Bibliotheque)
- 2026-02-10 : `implementation_plan_2026_02_10` -- Plan d'implementation en 6 phases
- 2026-02-10 : `raster_integration_plan_atlas_2026_02_10` -- Roadmap raster Atlas
- 2026-02-10 : `project_overview` -- Mise a jour avec etat raster audite

## Rouleaux Supprimes (historique)
- `signal_audit_fixes_2026_02_09` -- SUPPRIME (branch-only, jamais merge)
- `merge_analysis_v9_integration_2026_02_09` -- SUPPRIME (v9 branch-only, obsolete)
- `signal_combobox_fixes_2026_02_10` -- SUPPRIME (branch-only)

## Rouleaux a Revoir (ATTENTION)
- `documentation_structure` -- Date de derniere verification inconnue
- `negative_buffer_wkt_handling` -- Date de derniere verification inconnue
- `filter_preservation_feature` -- Date de derniere verification inconnue
- `enhanced_optimizer_v2.8.0` -- Possiblement depasse par les optimisations v2.9.x
- `action_plan_v5.0` -- Potentiellement remplace par `implementation_plan_2026_02_10`
- `bmad_integration` -- A verifier contre l'etat reel de BMAD
