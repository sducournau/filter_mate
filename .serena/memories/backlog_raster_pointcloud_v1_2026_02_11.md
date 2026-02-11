# Backlog Raster & Point Cloud V1 - Summary (2026-02-11)

## Full document
`BACKLOG_RASTER_POINTCLOUD_V1.md` at project root (17 user stories, 5 sprints)

## Strategic Decisions
- DS-1: No refactoring block — Sprint 0 = merge raster + pass 3, then alternate features/stabilization
- DS-2: QGIS min 3.22 (raster), 3.26 (PC basic), 3.32 (PC advanced, optional)
- DS-3: Cherry-pick selective from raster branch (NOT merge direct)
- DS-4: MVP Raster first (foundations exist), MVP PC second (starts from zero)

## EPICs (MoSCoW)
- R0: Fondations Raster — MUST
- R1: Raster Value Sampling — MUST
- R2: Zonal Stats as Filter — MUST (key differentiator)
- R3: Raster-Driven Highlight — SHOULD
- R4: Raster Clip by Vector — COULD
- R5: Multi-Band Composite — WON'T V1
- PC1: Point Cloud Basic Filter — SHOULD
- PC2: Point Cloud Advanced (PDAL) — COULD

## Sprint Sequence
- Sprint 0 (1.5w): US-R0.1 cherry-pick + US-R0.2 pass3 + US-R0.3 UI wiring
- Sprint 1 (1.5w): US-R1.2 info + US-R1.1 sampling + US-R1.3 multi-band → Alpha Raster
- Sprint 2 (2.5w): US-R2.1 zonal stats + US-R2.2 filter + US-R2.3 histogram → Beta Raster
- Sprint 3 (2.5w): US-R3.1 highlight + US-PC1.0 archi + US-PC1.1 classification → Release Raster V1 + Alpha PC
- Sprint 4 (2w): US-PC1.2 attrs/Z + US-PC1.3 combined + US-R4.1 clip → FilterMate 5.0

## Total effort: 55-75 working days (11-15 weeks)

## Key Technical Notes (from Atlas research)
- Raster: provider.sample() for interactive, provider.block()+numpy for batch (50-200x faster)
- Zonal Stats: custom implementation recommended (NOT QgsZonalStatistics which modifies layer in-place)
- Point Cloud: layer.setSubsetString() — same pattern as vector filtering
- COPC = recommended format (octree, LOD, range requests)
- No QGIS plugin competitor for interactive raster or point cloud filtering

## Related Serena Memories
- atlas_raster_lidar_research_2026_02_11 — full technical research report
- audit_filtermate_2026_02_11 — refactoring state
