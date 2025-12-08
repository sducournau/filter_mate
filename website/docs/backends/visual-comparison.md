---
sidebar_position: 5
---

# Visual Performance Comparison

This guide provides visual comparisons of FilterMate's three backends to help you choose the optimal setup for your workflow.

## 📊 Performance by Dataset Size

### Filtering Time Comparison

```mermaid
gantt
    title Filtering Time: 10,000 Features
    dateFormat X
    axisFormat %S.%Ls
    
    section PostgreSQL
    Query: 0, 200
    
    section Spatialite
    Query: 0, 800
    
    section OGR
    Query: 0, 3000
```

```mermaid
gantt
    title Filtering Time: 100,000 Features
    dateFormat X
    axisFormat %Ss
    
    section PostgreSQL
    Query: 0, 1
    
    section Spatialite
    Query: 0, 5
    
    section OGR
    Query: 0, 30
```

```mermaid
gantt
    title Filtering Time: 1,000,000 Features
    dateFormat X
    axisFormat %Ss
    
    section PostgreSQL
    Query: 0, 2
    
    section Spatialite
    Query: 0, 45
    
    section OGR
    Query: 0, 300
```

### Performance Summary Table

| Dataset Size | PostgreSQL | Spatialite | OGR | Recommended |
|--------------|------------|------------|-----|-------------|
| **1k-10k** | 0.2s (Excellent) | 0.8s (Good) | 3s (Good) | All backends OK |
| **10k-50k** | 0.5s (Excellent) | 3s (Good) | 15s (Acceptable) | PostgreSQL or Spatialite |
| **50k-100k** | 1s (Excellent) | 5s (Good) | 30s (Poor) | PostgreSQL recommended |
| **100k-500k** | 1.5s (Excellent) | 25s (Acceptable) | 2min (Poor) | PostgreSQL strongly recommended |
| **500k-1M** | 2s (Excellent) | 45s (Acceptable) | 5min (Poor) | PostgreSQL required |
| **>1M** | 3-5s (Excellent) | N/A (Poor) | N/A (Poor) | PostgreSQL only |

**Legend:**
- **Excellent**: < 2 seconds
- **Good**: < 10 seconds
- **Acceptable**: 10-60 seconds
- **Poor**: > 60 seconds

---

## 🔧 Backend Capabilities Comparison

### Feature Support Matrix

```mermaid
graph TB
    subgraph "PostgreSQL Backend"
        PG[PostgreSQL/PostGIS]
        PG --> PG1[Materialized Views]
        PG --> PG2[GIST Spatial Index]
        PG --> PG3[Server-side Operations]
        PG --> PG4[Advanced PostGIS Functions]
        PG --> PG5[Concurrent Access]
        style PG fill:#51cf66
    end
    
    subgraph "Spatialite Backend"
        SL[Spatialite]
        SL --> SL1[Temporary Tables]
        SL --> SL2[R-tree Spatial Index]
        SL --> SL3[Local Operations]
        SL --> SL4[90% PostGIS Compatible]
        SL --> SL5[Single User]
        style SL fill:#ffd43b
    end
    
    subgraph "OGR Backend"
        OGR[OGR/GDAL]
        OGR --> OGR1[Memory Layers]
        OGR --> OGR2[QGIS Processing]
        OGR --> OGR3[File-based Index]
        OGR --> OGR4[Universal Format Support]
        OGR --> OGR5[No Database Required]
        style OGR fill:#74c0fc
    end
```

### Detailed Comparison

| Feature | PostgreSQL | Spatialite | OGR |
|---------|------------|------------|-----|
| **Installation** | ⚠️ Requires server + psycopg2 | ✅ Built-in | ✅ Built-in |
| **Setup Complexity** | 🔴 High | 🟢 Low | 🟢 Low |
| **Performance (large data)** | 🟢 Excellent | 🟡 Good | 🔴 Poor |
| **Memory Usage** | 🟢 Low (server-side) | 🟡 Moderate | 🔴 High |
| **Spatial Index** | ✅ GIST | ✅ R-tree | ⚠️ File-based (.qix) |
| **Concurrent Users** | ✅ Yes | ❌ Single file lock | ❌ File access |
| **Spatial Functions** | ✅ Full PostGIS | ✅ 90% compatible | ⚠️ Limited |
| **Data Format Support** | PostgreSQL only | Spatialite only | 🟢 Universal |
| **Network Support** | ✅ Remote server | ❌ Local only | ❌ Local only |
| **Transaction Support** | ✅ Full ACID | ✅ Full ACID | ⚠️ Limited |
| **Best for** | Production, large data | Medium projects | Quick analysis, any format |

---

## 🎯 Decision Matrix

### When to Use Each Backend

```mermaid
flowchart TD
    Start[Starting new project] --> Q1{Data size?}
    
    Q1 -->|< 10k features| Small[Small Dataset]
    Q1 -->|10k-50k features| Medium[Medium Dataset]
    Q1 -->|> 50k features| Large[Large Dataset]
    
    Small --> Q2{Data source?}
    Q2 -->|PostgreSQL| UsePG1[Use PostgreSQL<br/>✅ Fast & reliable]
    Q2 -->|Spatialite| UseSL1[Use Spatialite<br/>✅ Built-in, easy]
    Q2 -->|Shapefile/GPKG| UseOGR1[Use OGR<br/>✅ Works great]
    
    Medium --> Q3{PostgreSQL available?}
    Q3 -->|Yes| UsePG2[Use PostgreSQL<br/>⚡ Optimal choice]
    Q3 -->|No| Q4{Can convert to Spatialite?}
    Q4 -->|Yes| UseSL2[Use Spatialite<br/>✅ Good performance]
    Q4 -->|No| UseOGR2[Use OGR<br/>⚠️ May be slow]
    
    Large --> Q5{PostgreSQL available?}
    Q5 -->|Yes| UsePG3[Use PostgreSQL<br/>⚡ REQUIRED for good performance]
    Q5 -->|No| Critical[❌ Critical Issue]
    
    Critical --> Action{What to do?}
    Action -->|Best| Install[Install PostgreSQL + psycopg2<br/>Follow installation guide]
    Action -->|Acceptable| Convert[Convert to Spatialite<br/>Performance degraded]
    Action -->|Not recommended| Slow[Continue with OGR<br/>Very slow performance]
    
    Install --> UsePG3
    Convert --> UseSL3[Use Spatialite<br/>⚠️ 20-40s filter time]
    Slow --> UseOGR3[Use OGR<br/>❌ 2-5min filter time]
    
    style UsePG1 fill:#51cf66
    style UsePG2 fill:#51cf66
    style UsePG3 fill:#51cf66
    style UseSL1 fill:#ffd43b
    style UseSL2 fill:#ffd43b
    style UseSL3 fill:#ffd43b
    style UseOGR1 fill:#74c0fc
    style UseOGR2 fill:#ff8787
    style UseOGR3 fill:#ff6b6b
    style Critical fill:#ff6b6b
```

---

## 📈 Real-World Performance Benchmarks

### Test Configuration
- Hardware: Intel i7-9700K, 32GB RAM, NVMe SSD
- QGIS: Version 3.34 LTR
- PostgreSQL: Version 15.3 (PostGIS 3.3)
- Test: Intersect 100k polygons with 1 buffer zone

### Benchmark Results Summary

**Filtering Time by Dataset Size:**

| Dataset Size | PostgreSQL | Spatialite | OGR |
|--------------|------------|------------|-----|
| 10k features | 0.2s | 0.8s | 3s |
| 25k features | 0.3s | 1.5s | 7s |
| 50k features | 0.5s | 3s | 15s |
| 75k features | 0.8s | 4s | 22s |
| 100k features | 1s | 5s | 30s |
| 250k features | 1.5s | 15s | 75s |
| 500k features | 2s | 25s | 120s |
| 1M features | 3s | 45s | 300s |

**Key Insights:**
- 🟢 **PostgreSQL**: Sub-second performance up to 100k features, linear scaling
- 🟡 **Spatialite**: Good performance up to 50k features, acceptable up to 100k
- 🔴 **OGR**: Usable for small datasets (< 10k), slow for larger datasets

### Memory Usage Summary

**Memory Consumption by Dataset Size:**

| Dataset Size | PostgreSQL | Spatialite | OGR |
|--------------|------------|------------|-----|
| 10k features | 50 MB | 100 MB | 300 MB |
| 25k features | 55 MB | 200 MB | 750 MB |
| 50k features | 60 MB | 400 MB | 1500 MB |
| 75k features | 65 MB | 600 MB | 2250 MB |
| 100k features | 70 MB | 800 MB | 3000 MB |

**Key Insights:**
- 🟢 **PostgreSQL**: Constant low memory (server-side processing)
- 🟡 **Spatialite**: Linear memory growth (local database)
- 🔴 **OGR**: High memory usage (in-memory processing)

---

## 🔍 Detailed Backend Architecture

### PostgreSQL Backend Flow

```mermaid
sequenceDiagram
    participant FM as FilterMate
    participant PG as PostgreSQL Backend
    participant DB as PostgreSQL Server
    
    FM->>PG: Execute filter request
    PG->>DB: CREATE MATERIALIZED VIEW filtered_data AS<br/>SELECT * FROM source<br/>WHERE ST_Intersects(geom, buffer)
    DB->>DB: Execute query server-side
    DB->>DB: Create GIST spatial index
    DB-->>PG: Materialized view created
    PG->>DB: SELECT id FROM filtered_data
    DB-->>PG: Return feature IDs
    PG-->>FM: IDs (< 1 second)
    
    Note over FM,DB: All heavy lifting on server<br/>Minimal network traffic
```

### Spatialite Backend Flow

```mermaid
sequenceDiagram
    participant FM as FilterMate
    participant SL as Spatialite Backend
    participant DB as Spatialite File
    
    FM->>SL: Execute filter request
    SL->>DB: CREATE TEMP TABLE filtered_data AS<br/>SELECT * FROM source<br/>WHERE ST_Intersects(geom, buffer)
    DB->>DB: Execute query locally
    DB->>DB: Create R-tree spatial index
    DB-->>SL: Temp table created
    SL->>DB: SELECT id FROM filtered_data
    DB-->>SL: Return feature IDs
    SL-->>FM: IDs (1-10 seconds)
    
    Note over FM,DB: Local file processing<br/>No network overhead
```

### OGR Backend Flow

```mermaid
sequenceDiagram
    participant FM as FilterMate
    participant OGR as OGR Backend
    participant QP as QGIS Processing
    participant MEM as Memory Layer
    
    FM->>OGR: Execute filter request
    OGR->>QP: Call processing algorithm
    QP->>MEM: Load source features to memory
    QP->>QP: Iterate each feature<br/>Test spatial predicate
    QP->>MEM: Store matching features
    MEM-->>OGR: Return feature IDs
    OGR-->>FM: IDs (10-60+ seconds)
    
    Note over FM,MEM: All data in memory<br/>Feature-by-feature processing
```

---

## 💡 Optimization Recommendations

### By Use Case

#### 1. **Rapid Prototyping**
```mermaid
graph LR
    A[Quick Test] --> B[Use OGR Backend]
    B --> C[Any data format]
    C --> D[No setup needed]
    D --> E[Fast to start]
    style A fill:#74c0fc
```
**Best backend:** OGR  
**Why:** Zero setup, works with any format

#### 2. **Production Analysis (Large Data)**
```mermaid
graph LR
    A[Production] --> B[Use PostgreSQL]
    B --> C[Import to PostGIS]
    C --> D[Create spatial indexes]
    D --> E[Sub-second queries]
    style A fill:#51cf66
```
**Best backend:** PostgreSQL  
**Why:** Maximum performance, scalability

#### 3. **Medium Projects (Local Files)**
```mermaid
graph LR
    A[Local Project] --> B[Convert to Spatialite]
    B --> C[Use Spatialite Backend]
    C --> D[Good performance]
    D --> E[No server needed]
    style A fill:#ffd43b
```
**Best backend:** Spatialite  
**Why:** Balance of performance and simplicity

---

## 📋 Quick Reference Guide

### Backend Selection Cheat Sheet

| Your Situation | Recommended Backend | Setup Required |
|----------------|-------------------|----------------|
| Quick test, any format, < 10k features | **OGR** | None |
| Shapefile/GeoPackage, 10k-50k features | **Spatialite** | Convert format |
| Local project, no server, < 50k features | **Spatialite** | None (if .sqlite) |
| Production, >50k features | **PostgreSQL** | Install PostgreSQL + psycopg2 |
| Remote/shared data, any size | **PostgreSQL** | Database server |
| Million+ features | **PostgreSQL** | Database server (required) |

### Installation Priority

```mermaid
flowchart LR
    Start[Choose Backend] --> Daily{Daily<br/>workflow?}
    
    Daily -->|Yes| Size{Dataset<br/>size?}
    Daily -->|No| Quick[OGR is fine]
    
    Size -->|> 50k| Install[Install PostgreSQL<br/>Priority: HIGH ⚡]
    Size -->|10k-50k| Consider[Consider Spatialite<br/>Priority: MEDIUM ✅]
    Size -->|< 10k| Quick
    
    style Install fill:#51cf66
    style Consider fill:#ffd43b
    style Quick fill:#74c0fc
```

---

## 🚀 Next Steps

- **Install PostgreSQL**: Follow our [PostgreSQL Setup Guide](./postgresql.md)
- **Convert to Spatialite**: See [Spatialite Guide](./spatialite.md)
- **Understand backend selection**: Read [Backend Selection Logic](./backend-selection.md)
- **Optimize your workflow**: Check [Performance Tuning](../advanced/performance-tuning.md)

Have questions? [Open an issue on GitHub](https://github.com/sducournau/filter_mate/issues) for support.
