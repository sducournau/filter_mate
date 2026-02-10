# FilterMate Action Plan (Updated 2026-02-10)

**Last Updated:** February 10, 2026
**Current Version on main:** v4.4.5
**Status:** Production (Vector only) - Raster integration PLANNED

> **Audit 2026-02-10:** Previous v5.4.0 raster claims were branch-only (never merged).
> No raster features exist on `main`. See `raster_integration_plan_atlas_2026_02_10`.

---

## ✅ Recently Completed on `main` (Jan 2026)

### ~~v5.4.0 - Raster Exploring Tools~~ BRANCH ONLY (never merged)
> These existed on `fix/widget-visibility-and-styles-2026-02-02` only.

### v4.4.5 (Jan 25, 2026) - Primary Key Detection ✅
- [x] Automatic PK detection from PostgreSQL metadata
- [x] Fallback to common PK names (id, fid, ogc_fid, cleabs, gid, objectid)
- [x] Fixed dynamic buffer on BDTopo/OSM tables
- [x] Graceful handling when no PK found

**Impact:** Dynamic buffers now work on ANY PostgreSQL table

### v4.4.4 (Jan 25, 2026) - Naming Harmonization ✅
- [x] Unified `fm_temp_*` prefix for all temp objects
- [x] Simplified cleanup logic
- [x] Consistent naming across PostgreSQL backend

**Impact:** Better maintainability, easier debugging

### v4.4.0 (Jan 22, 2026) - Quality Release ✅
- [x] 396 standalone unit tests
- [x] DockwidgetSignalManager extracted (778 lines)
- [x] Hexagonal architecture complete
- [x] Test coverage: 75%
- [x] Quality score: 8.5/10

**Impact:** Solid foundation for future development

---

## 🚀 Current Sprint (Q1 2026)

### Priority 1: Translation Coverage

**Goal:** Improve non-FR/EN language coverage

| Language | Current | Target | Gap |
|----------|---------|--------|-----|
| German (DE) | 48% | 70% | 127 strings |
| Spanish (ES) | 45% | 70% | 145 strings |
| Italian (IT) | 40% | 65% | 145 strings |

**Tasks:**
- [ ] Extract missing translations with `pylupdate5`
- [ ] Use AI translation for batch DE/ES/IT updates
- [ ] Manual review of critical UI strings
- [ ] Update .qm compiled files

**Estimated:** 2 days

### Priority 2: Test Coverage

**Goal:** 75% → 80%

**Focus Areas:**
- [ ] Raster tools unit tests (new in v5.4.0)
- [ ] PostgreSQL PK detection tests
- [ ] Edge cases in filter chaining
- [ ] Export functionality coverage

**Estimated:** 1 week

### Priority 3: Documentation

**Goal:** Complete user and developer docs

- [ ] Raster tools user guide
- [ ] Primary key detection technical note
- [ ] Backend selection algorithm documentation
- [ ] API documentation for services

**Estimated:** 3 days

---

## 📋 Next Release: v5.5 (Planned March 2026) - Atlas Roadmap

### Raster Value Sampling (QUICK WIN - Foundation)
- [ ] `RasterFilterService` in `core/services/` (hexagonal)
- [ ] `RasterFilterCriteria` frozen dataclass in `core/domain/`
- [ ] `provider.sample(QgsPointXY, band)` per feature centroid
- [ ] Reuse existing predicate dropdown (Min/Max + between/>/< etc.)
- [ ] Single "Apply to vector" button in raster UI panel
- **Effort:** S (3-5 days) | **Impact:** HIGH | **UI Reuse:** 95%

### EPIC-4: Raster Export UI + Clip by Vector
- [ ] Export filtered raster to GeoTIFF/COG
- [ ] Clip raster by filtered vector features (`gdal.Warp` + `cutlineDSName`)
- [ ] Export with compression/NoData options
- **Effort:** M (2 weeks) | **Impact:** MED-HIGH

### Quality Improvements
- [ ] Reduce dockwidget.py complexity
- [ ] Test coverage: 75% → 80%

---

## 📋 v5.6 (Planned April 2026) - Atlas Roadmap

### Zonal Stats as Filter (DIFFERENTIATOR)
- [ ] `QgsZonalStatistics` or GDAL-based stats per vector feature
- [ ] "Show buildings where mean altitude > 500m" workflow
- [ ] Non-destructive (temp memory layer, not modifying source)
- [ ] Integrated with undo/redo and histogram preview
- **Effort:** M (2-3 weeks) | **Impact:** VERY HIGH | **UNIQUE**

### Raster-Driven Selection Highlight (UX Premium)
- [ ] Real-time vector feature highlight as user adjusts raster range
- [ ] Debounced (300ms) on range change signal
- [ ] MVP: combine with Sampling (centroid) instead of full polygonization
- **Effort:** M (1 week) | **Impact:** HIGH | **UNIQUE**

---

## 🔮 Future Roadmap: v6.0 (Q2-Q3 2026)

### Raster Features
- [ ] Multi-Band Composite Filtering (AND/OR on multiple bands) -- 4 weeks, if demand confirmed
- [ ] CAUTION: Do NOT recreate Raster Calculator (resist feature creep)

### Other Features
- [ ] Plugin API for Extensibility
- [ ] Cloud Data Sources (S3, Azure, STAC)
- [ ] Performance: tile-based processing for large rasters

---

## 🐛 Known Issues & Technical Debt

### Priority 1 (Must Fix)

- [ ] **Dockwidget complexity** (~6,925 lines - needs refactoring)
  - Split into logical modules (RasterPanel, VectorPanel, FilteringPanel, ExportingPanel)
  - Extract signal management (partially done with DockwidgetSignalManager)
  - Separate UI state from business logic

### Priority 2 (Should Fix)

- [ ] **Memory usage** with very large rasters (>2GB)
  - Profile memory consumption
  - Implement streaming/chunked processing
  - Add memory usage warnings

- [ ] **Translation coverage** for 19 secondary languages (~29%)
  - Automated translation review workflow
  - Community contribution process
  - Translation memory integration

### Priority 3 (Nice to Have)

- [ ] **Performance** on shapefiles with >1M features
  - Recommend PostgreSQL/Spatialite migration
  - Add performance advisor
  - Implement progressive loading

- [ ] **Documentation** completeness
  - Video tutorials
  - Interactive examples
  - Developer API docs

---

## 📊 Quality Metrics Tracking

| Metric | v4.4.0 | v5.4.0 | Target v6.0 |
|--------|--------|--------|-------------|
| Test Coverage | 75% | 75% | 80% |
| Unit Tests | 396 | 400+ | 500+ |
| Quality Score | 8.5/10 | 8.5/10 | 9.0/10 |
| LOC (prod) | ~130k | ~130k | ~140k |
| FR/EN Translation | 96% | 96% | 98% |
| DE/ES Translation | 48%/45% | 48%/45% | 70%/70% |
| Bare Excepts | 0 ✅ | 0 ✅ | 0 ✅ |
| Debug Prints | 0 ✅ | 0 ✅ | 0 ✅ |

---

## 🎯 Success Criteria

### v5.5 (March 2026)
- ✅ Test coverage ≥ 80%
- ✅ DE/ES translation ≥ 70%
- ✅ Raster export UI complete
- ✅ Documentation complete

### v6.0 (Q3 2026)
- ✅ Plugin API stable and documented
- ✅ Cloud data source support
- ✅ Performance: 10× improvement on large datasets
- ✅ Quality score: 9.0/10
- ✅ Community contributions: ≥5 plugins

---

## 📝 Notes

### Development Priorities
1. **Stability**: No breaking changes in minor versions
2. **Performance**: Optimize before adding features
3. **Quality**: Maintain 80%+ test coverage
4. **UX**: Consistent patterns across vector/raster

### Architecture Principles
- **Hexagonal Architecture**: Maintain clean separation
- **SOLID Principles**: Single responsibility, dependency injection
- **DRY**: Extract common patterns to services
- **KISS**: Keep it simple, avoid over-engineering

### Commit Strategy
- **Atomic commits**: One logical change per commit
- **Conventional commits**: feat/fix/docs/test/refactor
- **Descriptive messages**: Explain WHY, not WHAT
- **Reference issues**: Link to GitHub issues/PRDs

---

**Last Review:** February 1, 2026  
**Next Review:** March 1, 2026  
**Owner:** Simon (@sducournau)
