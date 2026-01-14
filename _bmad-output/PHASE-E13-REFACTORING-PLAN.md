# Phase E13: Plan de Refactoring FilterEngineTask

**Date**: 14 Janvier 2026  
**Objectif**: Éliminer la God Class FilterEngineTask (4,680 lignes → 2,800 lignes)  
**Réduction visée**: -40% (-1,880 lignes)  
**Durée estimée**: 3-4 jours

---

## 🎯 Objectifs

### Objectifs Quantitatifs

- ✅ Réduire FilterEngineTask de 4,680 → 600 lignes (-87%)
- ✅ Créer 6 nouvelles classes spécialisées (~400 lignes chacune)
- ✅ Passer de 143 méthodes → 25 méthodes dans FilterEngineTask
- ✅ Respecter le Single Responsibility Principle (SRP)

### Objectifs Qualitatifs

- ✅ Améliorer la testabilité (injection de dépendances)
- ✅ Réduire la complexité cyclomatique (<15 par méthode)
- ✅ Faciliter la maintenance (responsabilités claires)
- ✅ **Zéro régression fonctionnelle**

---

## 🏗️ Architecture Proposée

### Nouvelle Structure de Fichiers

```
core/tasks/
├── filter_task.py                      # Orchestrateur principal (600 lignes)
├── executors/
│   ├── __init__.py
│   ├── attribute_filter_executor.py    # Filtrage attributaire (400 lignes)
│   └── spatial_filter_executor.py      # Filtrage spatial (500 lignes)
├── cache/
│   ├── __init__.py
│   ├── geometry_cache.py               # Cache géométrie (300 lignes)
│   └── expression_cache.py             # Cache expression (250 lignes)
├── connectors/
│   ├── __init__.py
│   └── backend_connector.py            # Connexions DB (350 lignes)
└── optimization/
    ├── __init__.py
    └── filter_optimizer.py             # Optimisation (400 lignes)
```

---

## 📋 Étapes de Migration

### Étape 1: Créer AttributeFilterExecutor (~4h)

**Responsabilités**:
- Filtrage par attributs QGIS
- Conversion d'expressions QGIS
- Application type casting PostgreSQL

**Méthodes à extraire** (de `filter_task.py`):

```python
# Actuellement dans FilterEngineTask (lignes 899-985)
- _try_v3_attribute_filter()
- _process_qgis_expression()
- _apply_postgresql_type_casting()
- _build_feature_id_expression()
- _is_pk_numeric()
- _format_pk_values_for_sql()
```

**Nouvelle classe**:

```python
# core/tasks/executors/attribute_filter_executor.py

from typing import List, Optional, Tuple
from qgis.core import QgsVectorLayer, QgsFeature

class AttributeFilterExecutor:
    """
    Handles attribute-based filtering operations.
    
    Responsibilities:
    - QGIS expression processing
    - PostgreSQL type casting
    - Feature ID expression building
    """
    
    def __init__(self, layer: QgsVectorLayer):
        self.layer = layer
        self.provider_type = layer.providerType()
    
    def execute_attribute_filter(
        self, 
        task_expression: str, 
        task_features: Optional[List[int]] = None
    ) -> Tuple[bool, str, List[QgsFeature]]:
        """
        Execute attribute-based filter on layer.
        
        Args:
            task_expression: QGIS expression string
            task_features: Optional list of feature IDs to filter
            
        Returns:
            (success: bool, expression: str, features: List[QgsFeature])
        """
        # Implementation extracted from _try_v3_attribute_filter
        pass
    
    def process_qgis_expression(self, expression: str) -> str:
        """Convert QGIS expression to provider-specific SQL."""
        # Extracted from _process_qgis_expression
        pass
    
    def apply_type_casting(self, expression: str) -> str:
        """Apply PostgreSQL type casting if needed."""
        # Extracted from _apply_postgresql_type_casting
        pass
    
    def build_feature_id_expression(self, feature_ids: List[int]) -> str:
        """Build optimized IN clause for feature IDs."""
        # Extracted from _build_feature_id_expression
        pass
```

**Tests à créer**:
```python
# tests/test_attribute_filter_executor.py
def test_execute_attribute_filter_simple_expression():
    """Test simple expression: population > 1000"""
    pass

def test_execute_attribute_filter_with_feature_ids():
    """Test filtering with specific feature IDs"""
    pass

def test_process_qgis_expression_to_postgresql():
    """Test QGIS → PostgreSQL conversion"""
    pass

def test_apply_type_casting_numeric_field():
    """Test type casting for numeric fields"""
    pass
```

---

### Étape 2: Créer SpatialFilterExecutor (~5h)

**Responsabilités**:
- Filtrage spatial (prédicats géométriques)
- Organisation des layers_to_filter
- Application de prédicats multiples

**Méthodes à extraire**:

```python
# Actuellement dans FilterEngineTask (lignes 986-1042)
- _try_v3_spatial_filter()
- _organize_layers_to_filter()
- _prepare_geometries_by_provider()
- _prepare_source_geometry_via_executor()
```

**Nouvelle classe**:

```python
# core/tasks/executors/spatial_filter_executor.py

from typing import List, Dict, Optional
from qgis.core import QgsVectorLayer, QgsGeometry

class SpatialFilterExecutor:
    """
    Handles spatial filtering operations.
    
    Responsibilities:
    - Geometric predicate application
    - Multi-layer spatial filtering
    - Geometry preparation for different providers
    """
    
    def __init__(
        self, 
        source_layer: QgsVectorLayer,
        backend_registry=None
    ):
        self.source_layer = source_layer
        self.backend_registry = backend_registry
        self.predicates = []
    
    def execute_spatial_filter(
        self,
        layer: QgsVectorLayer,
        layer_props: Dict,
        predicates: List[str]
    ) -> Tuple[bool, List[int]]:
        """
        Execute spatial filter with geometric predicates.
        
        Args:
            layer: Target layer to filter
            layer_props: Layer properties dict
            predicates: List of geometric predicates (intersects, contains, etc.)
            
        Returns:
            (success: bool, matching_feature_ids: List[int])
        """
        # Extracted from _try_v3_spatial_filter
        pass
    
    def organize_layers_to_filter(
        self, 
        layers_dict: Dict
    ) -> Dict[str, Dict]:
        """
        Organize and validate layers for filtering.
        
        Returns:
            Dict with organized layer information by provider
        """
        # Extracted from _organize_layers_to_filter
        pass
    
    def prepare_source_geometry(
        self,
        feature_ids: Optional[List[int]] = None,
        use_centroids: bool = False
    ) -> QgsGeometry:
        """
        Prepare source geometry for spatial operations.
        
        Uses backend executor if available, falls back to QGIS.
        """
        # Extracted from _prepare_source_geometry_via_executor
        pass
```

**Tests à créer**:
```python
# tests/test_spatial_filter_executor.py
def test_execute_spatial_filter_intersects():
    """Test intersects predicate"""
    pass

def test_execute_spatial_filter_multiple_predicates():
    """Test combining multiple predicates (intersects + contains)"""
    pass

def test_organize_layers_to_filter_mixed_providers():
    """Test organizing PostgreSQL + Spatialite layers"""
    pass

def test_prepare_source_geometry_with_centroids():
    """Test centroid calculation"""
    pass
```

---

### Étape 3: Créer GeometryCache (~3h)

**Responsabilités**:
- Cache de géométries préparées
- Invalidation de cache
- Gestion de la mémoire

**Méthodes à extraire**:

```python
# Actuellement dans FilterEngineTask (attribut de classe _geometry_cache)
- get_geometry_cache() (ligne 263)
- Logic dans execute_source_layer_filtering() pour cache usage
```

**Nouvelle classe**:

```python
# core/tasks/cache/geometry_cache.py

from typing import Optional, Dict, Tuple
from qgis.core import QgsGeometry
import time

class GeometryCache:
    """
    Cache for prepared geometries.
    
    Responsibilities:
    - Store prepared geometries with TTL
    - Invalidate cache on layer changes
    - Memory management (size limits)
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: float = 300.0):
        """
        Initialize geometry cache.
        
        Args:
            max_size: Maximum number of cached geometries
            ttl_seconds: Time-to-live for cache entries (default: 5 min)
        """
        self._cache: Dict[str, Tuple[QgsGeometry, float]] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
    
    def get(
        self, 
        layer_id: str, 
        feature_ids: Optional[List[int]] = None
    ) -> Optional[QgsGeometry]:
        """
        Get cached geometry for layer.
        
        Args:
            layer_id: Layer ID
            feature_ids: Optional feature IDs (for subset)
            
        Returns:
            Cached geometry or None if not found/expired
        """
        cache_key = self._build_cache_key(layer_id, feature_ids)
        
        if cache_key not in self._cache:
            return None
        
        geometry, timestamp = self._cache[cache_key]
        
        # Check TTL
        if time.time() - timestamp > self._ttl:
            del self._cache[cache_key]
            return None
        
        return geometry
    
    def put(
        self, 
        layer_id: str, 
        geometry: QgsGeometry,
        feature_ids: Optional[List[int]] = None
    ):
        """Store geometry in cache."""
        cache_key = self._build_cache_key(layer_id, feature_ids)
        
        # Evict oldest entry if cache full
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        self._cache[cache_key] = (geometry, time.time())
    
    def invalidate(self, layer_id: Optional[str] = None):
        """
        Invalidate cache entries.
        
        Args:
            layer_id: If provided, only invalidate for this layer.
                      If None, clear entire cache.
        """
        if layer_id is None:
            self._cache.clear()
        else:
            keys_to_delete = [
                k for k in self._cache.keys() 
                if k.startswith(f"{layer_id}:")
            ]
            for key in keys_to_delete:
                del self._cache[key]
    
    def _build_cache_key(
        self, 
        layer_id: str, 
        feature_ids: Optional[List[int]]
    ) -> str:
        """Build unique cache key."""
        if feature_ids:
            ids_str = ",".join(str(fid) for fid in sorted(feature_ids))
            return f"{layer_id}:{ids_str}"
        return f"{layer_id}:all"
    
    def _evict_oldest(self):
        """Evict oldest cache entry."""
        if not self._cache:
            return
        
        oldest_key = min(
            self._cache.keys(), 
            key=lambda k: self._cache[k][1]
        )
        del self._cache[oldest_key]
```

**Tests à créer**:
```python
# tests/test_geometry_cache.py
def test_cache_get_put():
    """Test basic get/put operations"""
    pass

def test_cache_ttl_expiration():
    """Test TTL expiration"""
    pass

def test_cache_max_size_eviction():
    """Test LRU eviction when max size reached"""
    pass

def test_cache_invalidate_specific_layer():
    """Test invalidating specific layer"""
    pass

def test_cache_invalidate_all():
    """Test clearing entire cache"""
    pass
```

---

### Étape 4: Créer ExpressionCache (~3h)

**Responsabilités**:
- Cache d'expressions compilées
- Optimisation de requêtes
- Déduplication de clauses

**Méthodes à extraire**:

```python
# Actuellement dans FilterEngineTask
- _optimize_duplicate_in_clauses() (ligne 1411)
- _combine_with_old_subset() (ligne 1332)
- _sanitize_subset_string() (ligne 1237)
```

**Nouvelle classe**:

```python
# core/tasks/cache/expression_cache.py

from typing import Optional, Dict, Tuple
import time
import re

class ExpressionCache:
    """
    Cache for compiled and optimized expressions.
    
    Responsibilities:
    - Cache compiled expressions
    - Optimize duplicate IN clauses
    - Expression sanitization
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: float = 60.0):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
    
    def get_optimized_expression(
        self, 
        expression: str,
        optimize_duplicates: bool = True,
        sanitize: bool = True
    ) -> str:
        """
        Get optimized expression (from cache or newly optimized).
        
        Args:
            expression: Raw expression
            optimize_duplicates: Whether to optimize duplicate IN clauses
            sanitize: Whether to sanitize expression
            
        Returns:
            Optimized expression string
        """
        cache_key = f"{expression}:{optimize_duplicates}:{sanitize}"
        
        # Check cache
        if cache_key in self._cache:
            cached_expr, timestamp = self._cache[cache_key]
            if time.time() - timestamp <= self._ttl:
                return cached_expr
            else:
                del self._cache[cache_key]
        
        # Optimize
        optimized = expression
        
        if sanitize:
            optimized = self.sanitize_expression(optimized)
        
        if optimize_duplicates:
            optimized = self.optimize_duplicate_in_clauses(optimized)
        
        # Cache result
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        self._cache[cache_key] = (optimized, time.time())
        
        return optimized
    
    def optimize_duplicate_in_clauses(self, expression: str) -> str:
        """
        Optimize duplicate IN clauses.
        
        Example:
            "field IN (1,2) OR field IN (3,4)"
            → "field IN (1,2,3,4)"
        """
        # Extracted from FilterEngineTask._optimize_duplicate_in_clauses
        
        # Regex to find IN clauses
        in_pattern = r'(\w+)\s+IN\s*\(([^)]+)\)'
        matches = re.findall(in_pattern, expression, re.IGNORECASE)
        
        if not matches:
            return expression
        
        # Group by field name
        field_values = {}
        for field, values in matches:
            field_lower = field.lower()
            if field_lower not in field_values:
                field_values[field_lower] = set()
            
            # Extract values
            vals = [v.strip() for v in values.split(',')]
            field_values[field_lower].update(vals)
        
        # Rebuild expression with consolidated IN clauses
        for field_lower, values in field_values.items():
            if len(values) > 1:
                # Find original field name (preserve case)
                original_field = next(
                    (f for f, _ in matches if f.lower() == field_lower),
                    field_lower
                )
                
                # Replace all occurrences
                old_pattern = rf'{original_field}\s+IN\s*\([^)]+\)'
                new_clause = f"{original_field} IN ({','.join(sorted(values))})"
                
                # Replace first occurrence, remove others
                expression = re.sub(
                    old_pattern, 
                    new_clause, 
                    expression, 
                    count=1,
                    flags=re.IGNORECASE
                )
                expression = re.sub(
                    rf'\s+(OR|AND)\s+{old_pattern}', 
                    '', 
                    expression,
                    flags=re.IGNORECASE
                )
        
        return expression
    
    def sanitize_expression(self, expression: str) -> str:
        """
        Sanitize expression (remove dangerous patterns).
        
        Prevents SQL injection and malformed expressions.
        """
        # Extracted from FilterEngineTask._sanitize_subset_string
        
        if not expression or not expression.strip():
            return ""
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', expression.strip())
        
        # Remove comments (-- and /* */)
        sanitized = re.sub(r'--[^\n]*', '', sanitized)
        sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
        
        # Check for dangerous keywords (PostgreSQL)
        dangerous_keywords = [
            'DROP', 'DELETE FROM', 'UPDATE', 'INSERT INTO',
            'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE'
        ]
        
        upper_expr = sanitized.upper()
        for keyword in dangerous_keywords:
            if keyword in upper_expr:
                raise ValueError(
                    f"Dangerous keyword '{keyword}' found in expression"
                )
        
        return sanitized
    
    def combine_with_old_subset(
        self, 
        new_expression: str,
        old_expression: str,
        operator: str = 'AND'
    ) -> str:
        """
        Combine new expression with existing subset string.
        
        Args:
            new_expression: New filter expression
            old_expression: Existing subset string
            operator: Logical operator ('AND' or 'OR')
            
        Returns:
            Combined expression
        """
        # Extracted from FilterEngineTask._combine_with_old_subset
        
        if not old_expression or not old_expression.strip():
            return new_expression
        
        if not new_expression or not new_expression.strip():
            return old_expression
        
        # Wrap both in parentheses
        combined = f"({old_expression}) {operator.upper()} ({new_expression})"
        
        return self.sanitize_expression(combined)
    
    def _evict_oldest(self):
        """Evict oldest cache entry."""
        if not self._cache:
            return
        
        oldest_key = min(
            self._cache.keys(), 
            key=lambda k: self._cache[k][1]
        )
        del self._cache[oldest_key]
```

**Tests à créer**:
```python
# tests/test_expression_cache.py
def test_optimize_duplicate_in_clauses():
    """Test IN clause optimization"""
    cache = ExpressionCache()
    expr = "field IN (1,2) OR field IN (3,4)"
    result = cache.optimize_duplicate_in_clauses(expr)
    assert "field IN (1,2,3,4)" in result

def test_sanitize_expression_remove_comments():
    """Test comment removal"""
    pass

def test_sanitize_expression_dangerous_keywords():
    """Test blocking dangerous keywords"""
    pass

def test_combine_with_old_subset_and():
    """Test combining expressions with AND"""
    pass

def test_cache_ttl():
    """Test expression cache TTL"""
    pass
```

---

### Étape 5: Créer BackendConnector (~4h)

**Responsabilités**:
- Connexions PostgreSQL/Spatialite
- Détection de provider
- Gestion d'erreurs de connexion

**Méthodes à extraire**:

```python
# Actuellement dans FilterEngineTask
- _get_valid_postgresql_connection() (ligne 549)
- _safe_spatialite_connect() (ligne 545)
- _is_postgresql_available() (ligne 434)
```

**Nouvelle classe**:

```python
# core/tasks/connectors/backend_connector.py

from typing import Optional, Tuple
from qgis.core import QgsVectorLayer
import logging

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

import sqlite3

logger = logging.getLogger(__name__)

class BackendConnector:
    """
    Manages database connections for different backends.
    
    Responsibilities:
    - PostgreSQL connection management
    - Spatialite connection management
    - Provider type detection
    - Connection pooling (future)
    """
    
    def __init__(self, layer: QgsVectorLayer):
        self.layer = layer
        self.provider_type = self._detect_provider_type()
    
    def _detect_provider_type(self) -> str:
        """
        Detect provider type from layer.
        
        Returns:
            'postgresql', 'spatialite', 'ogr', or 'unknown'
        """
        qgis_provider = self.layer.providerType()
        
        if qgis_provider == 'postgres':
            return 'postgresql'
        elif qgis_provider == 'spatialite':
            return 'spatialite'
        elif qgis_provider == 'ogr':
            return 'ogr'
        else:
            return 'unknown'
    
    def get_connection(self) -> Optional[object]:
        """
        Get appropriate connection for layer's provider.
        
        Returns:
            psycopg2.connection or sqlite3.Connection, or None
        """
        if self.provider_type == 'postgresql':
            return self.get_postgresql_connection()
        elif self.provider_type == 'spatialite':
            return self.get_spatialite_connection()
        else:
            logger.warning(
                f"No connection available for provider: {self.provider_type}"
            )
            return None
    
    def get_postgresql_connection(self) -> Optional['psycopg2.connection']:
        """
        Get PostgreSQL connection from layer URI.
        
        Returns:
            psycopg2 connection or None if unavailable/error
        """
        if not POSTGRESQL_AVAILABLE:
            logger.info("psycopg2 not available")
            return None
        
        if self.provider_type != 'postgresql':
            logger.warning(
                f"Layer is not PostgreSQL (is: {self.provider_type})"
            )
            return None
        
        try:
            from infrastructure.utils.layer_utils import (
                get_datasource_connexion_from_layer
            )
            
            connexion, source_uri = get_datasource_connexion_from_layer(
                self.layer
            )
            
            if connexion is None:
                logger.error("Failed to get PostgreSQL connection")
                return None
            
            return connexion
            
        except Exception as e:
            logger.error(
                f"Error getting PostgreSQL connection: {e}",
                exc_info=True
            )
            return None
    
    def get_spatialite_connection(
        self, 
        db_path: Optional[str] = None
    ) -> Optional[sqlite3.Connection]:
        """
        Get Spatialite connection.
        
        Args:
            db_path: Optional path to Spatialite DB.
                     If None, extracted from layer URI.
        
        Returns:
            sqlite3.Connection with Spatialite extension loaded
        """
        if db_path is None:
            # Extract from layer data source
            data_source = self.layer.dataProvider().dataSourceUri()
            # Format: dbname='/path/to/db.sqlite' table="tablename" ...
            import re
            match = re.search(r"dbname='([^']+)'", data_source)
            if match:
                db_path = match.group(1)
            else:
                logger.error("Could not extract db_path from layer URI")
                return None
        
        try:
            conn = sqlite3.connect(db_path)
            conn.enable_load_extension(True)
            
            # Try to load Spatialite extension
            try:
                conn.load_extension('mod_spatialite')
            except sqlite3.OperationalError:
                # Windows fallback
                try:
                    conn.load_extension('mod_spatialite.dll')
                except sqlite3.OperationalError as e:
                    logger.error(
                        f"Could not load Spatialite extension: {e}"
                    )
                    conn.close()
                    return None
            
            return conn
            
        except Exception as e:
            logger.error(
                f"Error connecting to Spatialite: {e}",
                exc_info=True
            )
            return None
    
    def is_postgresql_available(self) -> bool:
        """Check if PostgreSQL support is available."""
        return POSTGRESQL_AVAILABLE and self.provider_type == 'postgresql'
    
    def is_spatialite(self) -> bool:
        """Check if layer is Spatialite."""
        return self.provider_type == 'spatialite'
    
    def close_connection(self, connection: object):
        """
        Close database connection safely.
        
        Args:
            connection: psycopg2 or sqlite3 connection
        """
        if connection is None:
            return
        
        try:
            connection.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
```

**Tests à créer**:
```python
# tests/test_backend_connector.py
def test_detect_provider_type_postgresql():
    """Test PostgreSQL provider detection"""
    pass

def test_detect_provider_type_spatialite():
    """Test Spatialite provider detection"""
    pass

def test_get_postgresql_connection():
    """Test PostgreSQL connection retrieval"""
    pass

def test_get_spatialite_connection():
    """Test Spatialite connection with extension loading"""
    pass

def test_is_postgresql_available():
    """Test psycopg2 availability check"""
    pass
```

---

### Étape 6: Créer FilterOptimizer (~4h)

**Responsabilités**:
- Optimisation de requêtes
- Combinaison d'expressions
- Analyse de performance

**Méthodes à extraire**:

```python
# Déjà couvert par ExpressionCache
# Mais ajouter des optimisations avancées:
- Analyse d'index
- Réécriture de requêtes
- Estimation de coût
```

**Nouvelle classe**:

```python
# core/tasks/optimization/filter_optimizer.py

from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class FilterOptimizer:
    """
    Advanced query optimization for filters.
    
    Responsibilities:
    - Index usage analysis
    - Query rewriting for performance
    - Cost estimation
    """
    
    def __init__(self, layer, backend_connector=None):
        self.layer = layer
        self.backend_connector = backend_connector
    
    def optimize_spatial_filter(
        self, 
        expression: str,
        use_spatial_index: bool = True
    ) -> str:
        """
        Optimize spatial filter expression.
        
        Args:
            expression: Spatial filter expression
            use_spatial_index: Whether to use spatial index
            
        Returns:
            Optimized expression
        """
        # Add spatial index hints for PostgreSQL
        if self.backend_connector and \
           self.backend_connector.is_postgresql_available():
            
            # Example: Add USING GIST hint
            # This is provider-specific optimization
            pass
        
        return expression
    
    def estimate_cost(self, expression: str) -> Dict[str, any]:
        """
        Estimate query cost.
        
        Returns:
            Dict with:
            - estimated_rows: int
            - uses_index: bool
            - cost_score: float (0-100, lower is better)
        """
        # For PostgreSQL: Use EXPLAIN ANALYZE
        # For Spatialite: Estimate based on heuristics
        
        if self.backend_connector and \
           self.backend_connector.is_postgresql_available():
            
            return self._estimate_cost_postgresql(expression)
        
        return {
            'estimated_rows': None,
            'uses_index': False,
            'cost_score': 50.0  # Unknown
        }
    
    def _estimate_cost_postgresql(self, expression: str) -> Dict:
        """Estimate cost using PostgreSQL EXPLAIN."""
        conn = self.backend_connector.get_connection()
        
        if conn is None:
            return {'estimated_rows': None, 'uses_index': False, 'cost_score': 50.0}
        
        try:
            cursor = conn.cursor()
            
            # EXPLAIN without executing
            explain_query = f"EXPLAIN SELECT * FROM {self.layer.name()} WHERE {expression}"
            cursor.execute(explain_query)
            
            plan = cursor.fetchall()
            
            # Parse EXPLAIN output
            uses_index = any('Index Scan' in str(line) for line in plan)
            
            # Extract cost estimate (rough heuristic)
            cost_score = 50.0  # Default
            for line in plan:
                if 'cost=' in str(line):
                    # Extract cost value
                    import re
                    match = re.search(r'cost=(\d+\.?\d*)', str(line))
                    if match:
                        cost_score = float(match.group(1))
                        break
            
            cursor.close()
            
            return {
                'estimated_rows': None,  # Could extract from plan
                'uses_index': uses_index,
                'cost_score': cost_score
            }
            
        except Exception as e:
            logger.warning(f"Error estimating cost: {e}")
            return {'estimated_rows': None, 'uses_index': False, 'cost_score': 50.0}
    
    def suggest_index(self, expression: str) -> Optional[str]:
        """
        Suggest index creation for expression.
        
        Returns:
            SQL statement to create index, or None
        """
        # Analyze expression and suggest appropriate index
        # Example: For "population > 1000" → CREATE INDEX idx_population ON layer(population)
        
        # This is a simplified heuristic
        import re
        
        # Look for field comparisons
        field_pattern = r'(\w+)\s*[><=]'
        matches = re.findall(field_pattern, expression)
        
        if matches:
            field = matches[0]
            table_name = self.layer.name()
            
            return f"CREATE INDEX idx_{table_name}_{field} ON {table_name}({field})"
        
        return None
```

**Tests à créer**:
```python
# tests/test_filter_optimizer.py
def test_estimate_cost_postgresql():
    """Test cost estimation with PostgreSQL"""
    pass

def test_suggest_index_simple_comparison():
    """Test index suggestion for simple comparison"""
    pass

def test_optimize_spatial_filter_with_index():
    """Test spatial filter optimization"""
    pass
```

---

### Étape 7: Refactoriser FilterEngineTask (Orchestrateur) (~6h)

**Objectif**: Réduire FilterEngineTask à un pur orchestrateur.

**Nouvelle structure** (600 lignes):

```python
# core/tasks/filter_task.py (refactoré)

from qgis.core import QgsTask, QgsVectorLayer
from PyQt5.QtCore import pyqtSignal

from .executors.attribute_filter_executor import AttributeFilterExecutor
from .executors.spatial_filter_executor import SpatialFilterExecutor
from .cache.geometry_cache import GeometryCache
from .cache.expression_cache import ExpressionCache
from .connectors.backend_connector import BackendConnector
from .optimization.filter_optimizer import FilterOptimizer

import logging

logger = logging.getLogger(__name__)


class FilterEngineTask(QgsTask):
    """
    Main QgsTask orchestrator for filtering operations.
    
    Responsibilities (ONLY):
    - QgsTask lifecycle (run, finished, cancel)
    - Delegation to specialized executors
    - Result aggregation
    - Signal emission
    
    All heavy logic delegated to:
    - AttributeFilterExecutor
    - SpatialFilterExecutor
    - GeometryCache
    - ExpressionCache
    - BackendConnector
    - FilterOptimizer
    """
    
    # Signals
    applySubsetRequest = pyqtSignal(QgsVectorLayer, str)
    
    # Shared caches (class-level)
    _geometry_cache = None
    _expression_cache = None
    
    @classmethod
    def get_geometry_cache(cls):
        """Get or create shared geometry cache."""
        if cls._geometry_cache is None:
            cls._geometry_cache = GeometryCache(max_size=100, ttl_seconds=300.0)
        return cls._geometry_cache
    
    @classmethod
    def get_expression_cache(cls):
        """Get or create shared expression cache."""
        if cls._expression_cache is None:
            cls._expression_cache = ExpressionCache(max_size=100, ttl_seconds=60.0)
        return cls._expression_cache
    
    def __init__(self, description, task_action, task_parameters, backend_registry=None):
        """
        Initialize FilterEngineTask.
        
        Args:
            description: Task description for UI
            task_action: Action to perform ('filter', 'spatial_filter', 'export', etc.)
            task_parameters: Dict with task-specific parameters
            backend_registry: Optional backend registry for multi-backend support
        """
        super().__init__(description, QgsTask.CanCancel)
        
        self.task_action = task_action
        self.task_parameters = task_parameters
        self.backend_registry = backend_registry
        
        # Extract common parameters
        self.source_layer = task_parameters.get('source_layer')
        self.exception = None
        self.result_data = {}
        
        # Initialize components (lazy - only when needed)
        self._attribute_executor = None
        self._spatial_executor = None
        self._backend_connector = None
        self._optimizer = None
    
    def _get_attribute_executor(self) -> AttributeFilterExecutor:
        """Get or create attribute filter executor."""
        if self._attribute_executor is None:
            self._attribute_executor = AttributeFilterExecutor(self.source_layer)
        return self._attribute_executor
    
    def _get_spatial_executor(self) -> SpatialFilterExecutor:
        """Get or create spatial filter executor."""
        if self._spatial_executor is None:
            self._spatial_executor = SpatialFilterExecutor(
                self.source_layer,
                self.backend_registry
            )
        return self._spatial_executor
    
    def _get_backend_connector(self) -> BackendConnector:
        """Get or create backend connector."""
        if self._backend_connector is None:
            self._backend_connector = BackendConnector(self.source_layer)
        return self._backend_connector
    
    def _get_optimizer(self) -> FilterOptimizer:
        """Get or create filter optimizer."""
        if self._optimizer is None:
            self._optimizer = FilterOptimizer(
                self.source_layer,
                self._get_backend_connector()
            )
        return self._optimizer
    
    def run(self) -> bool:
        """
        Main task execution (called in background thread).
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delegate to action-specific method
            if self.task_action == 'filter':
                return self._execute_attribute_filter()
            
            elif self.task_action == 'spatial_filter':
                return self._execute_spatial_filter()
            
            elif self.task_action == 'multi_step_filter':
                return self._execute_multi_step_filter()
            
            elif self.task_action == 'export':
                return self._execute_export()
            
            else:
                logger.error(f"Unknown task action: {self.task_action}")
                return False
        
        except Exception as e:
            self.exception = e
            logger.error(f"Task failed: {e}", exc_info=True)
            return False
    
    def _execute_attribute_filter(self) -> bool:
        """Execute attribute-based filter."""
        expression = self.task_parameters.get('expression', '')
        feature_ids = self.task_parameters.get('feature_ids')
        
        # Get cached/optimized expression
        expr_cache = self.get_expression_cache()
        optimized_expr = expr_cache.get_optimized_expression(expression)
        
        # Delegate to attribute executor
        executor = self._get_attribute_executor()
        success, final_expr, features = executor.execute_attribute_filter(
            optimized_expr,
            feature_ids
        )
        
        if success:
            # Queue subset string application (main thread)
            self.queue_subset_request(self.source_layer, final_expr)
            
            self.result_data = {
                'expression': final_expr,
                'feature_count': len(features) if features else 0
            }
        
        return success
    
    def _execute_spatial_filter(self) -> bool:
        """Execute spatial filter."""
        target_layer_props = self.task_parameters.get('layer_props', {})
        predicates = self.task_parameters.get('predicates', ['intersects'])
        
        # Delegate to spatial executor
        executor = self._get_spatial_executor()
        success, matching_ids = executor.execute_spatial_filter(
            self.source_layer,
            target_layer_props,
            predicates
        )
        
        if success and matching_ids:
            # Build feature ID expression
            attr_executor = self._get_attribute_executor()
            id_expr = attr_executor.build_feature_id_expression(matching_ids)
            
            # Queue subset string
            self.queue_subset_request(self.source_layer, id_expr)
            
            self.result_data = {
                'expression': id_expr,
                'feature_count': len(matching_ids)
            }
        
        return success
    
    def _execute_multi_step_filter(self) -> bool:
        """Execute multi-step filter strategy."""
        # Import multi-step strategy
        from core.strategies.multi_step_filter import MultiStepFilterStrategy
        
        layers_dict = self.task_parameters.get('layers_dict', {})
        
        strategy = MultiStepFilterStrategy(
            self.source_layer,
            self._get_backend_connector(),
            self.get_geometry_cache()
        )
        
        success, final_ids = strategy.execute(layers_dict, self.setProgress)
        
        if success and final_ids:
            attr_executor = self._get_attribute_executor()
            id_expr = attr_executor.build_feature_id_expression(final_ids)
            
            self.queue_subset_request(self.source_layer, id_expr)
            
            self.result_data = {
                'expression': id_expr,
                'feature_count': len(final_ids)
            }
        
        return success
    
    def _execute_export(self) -> bool:
        """Execute layer export."""
        from core.export.layer_exporter import LayerExporter
        
        output_path = self.task_parameters.get('output_path')
        format_type = self.task_parameters.get('format', 'GPKG')
        
        exporter = LayerExporter(self.source_layer)
        success, error_msg = exporter.export(
            output_path,
            format_type,
            progress_callback=self.setProgress
        )
        
        if success:
            self.result_data = {'output_path': output_path}
        else:
            logger.error(f"Export failed: {error_msg}")
        
        return success
    
    def queue_subset_request(self, layer, expression):
        """
        Queue subset string application on main thread.
        
        Args:
            layer: QgsVectorLayer
            expression: Subset string to apply
        """
        # Emit signal to apply on main thread (thread-safe)
        self.applySubsetRequest.emit(layer, expression)
    
    def finished(self, result: bool):
        """
        Called when task completes (on main thread).
        
        Args:
            result: True if successful
        """
        if result:
            logger.info(
                f"Task '{self.description()}' completed successfully. "
                f"Result: {self.result_data}"
            )
        else:
            if self.exception:
                logger.error(
                    f"Task '{self.description()}' failed with exception: "
                    f"{self.exception}"
                )
            else:
                logger.warning(f"Task '{self.description()}' failed (no exception)")
    
    def cancel(self):
        """Cancel task."""
        logger.info(f"Task '{self.description()}' cancelled")
        super().cancel()
```

**Métriques du nouveau FilterEngineTask**:
- **Lignes**: ~600 (vs 4,680 = -87%)
- **Méthodes**: ~25 (vs 143 = -82%)
- **Responsabilités**: 1 (orchestration uniquement)

---

## 📝 Checklist de Migration

### Étape 1: AttributeFilterExecutor
- [ ] Créer fichier `core/tasks/executors/attribute_filter_executor.py`
- [ ] Implémenter classe AttributeFilterExecutor
- [ ] Extraire méthodes de filter_task.py:
  - [ ] `_try_v3_attribute_filter`
  - [ ] `_process_qgis_expression`
  - [ ] `_apply_postgresql_type_casting`
  - [ ] `_build_feature_id_expression`
  - [ ] `_is_pk_numeric`
  - [ ] `_format_pk_values_for_sql`
- [ ] Créer tests unitaires (6 tests minimum)
- [ ] Validation: tests passent ✅

### Étape 2: SpatialFilterExecutor
- [ ] Créer fichier `core/tasks/executors/spatial_filter_executor.py`
- [ ] Implémenter classe SpatialFilterExecutor
- [ ] Extraire méthodes:
  - [ ] `_try_v3_spatial_filter`
  - [ ] `_organize_layers_to_filter`
  - [ ] `_prepare_geometries_by_provider`
  - [ ] `_prepare_source_geometry_via_executor`
- [ ] Créer tests unitaires (5 tests minimum)
- [ ] Validation: tests passent ✅

### Étape 3: GeometryCache
- [ ] Créer fichier `core/tasks/cache/geometry_cache.py`
- [ ] Implémenter classe GeometryCache
- [ ] Extraire logique de cache de filter_task.py
- [ ] Créer tests unitaires (6 tests minimum)
- [ ] Validation: tests passent ✅

### Étape 4: ExpressionCache
- [ ] Créer fichier `core/tasks/cache/expression_cache.py`
- [ ] Implémenter classe ExpressionCache
- [ ] Extraire méthodes:
  - [ ] `_optimize_duplicate_in_clauses`
  - [ ] `_combine_with_old_subset`
  - [ ] `_sanitize_subset_string`
- [ ] Créer tests unitaires (6 tests minimum)
- [ ] Validation: tests passent ✅

### Étape 5: BackendConnector
- [ ] Créer fichier `core/tasks/connectors/backend_connector.py`
- [ ] Implémenter classe BackendConnector
- [ ] Extraire méthodes:
  - [ ] `_get_valid_postgresql_connection`
  - [ ] `_safe_spatialite_connect`
  - [ ] `_is_postgresql_available`
- [ ] Créer tests unitaires (5 tests minimum)
- [ ] Validation: tests passent ✅

### Étape 6: FilterOptimizer
- [ ] Créer fichier `core/tasks/optimization/filter_optimizer.py`
- [ ] Implémenter classe FilterOptimizer
- [ ] Ajouter optimisations avancées
- [ ] Créer tests unitaires (4 tests minimum)
- [ ] Validation: tests passent ✅

### Étape 7: Refactoriser FilterEngineTask
- [ ] Réduire filter_task.py à orchestrateur pur
- [ ] Remplacer anciennes méthodes par délégation
- [ ] Supprimer code dupliqué
- [ ] Validation: tous les tests passent ✅
- [ ] Validation: tests de régression OK ✅

### Étape 8: Tests d'Intégration
- [ ] Tests end-to-end filtrage attributaire
- [ ] Tests end-to-end filtrage spatial
- [ ] Tests end-to-end multi-step
- [ ] Tests end-to-end export
- [ ] Performance: benchmark avant/après
- [ ] Validation: aucune régression ✅

### Étape 9: Documentation
- [ ] Documenter nouvelle architecture
- [ ] Mettre à jour diagrammes
- [ ] Exemples d'utilisation
- [ ] Guide de migration

### Étape 10: Cleanup
- [ ] Supprimer ancien code commenté
- [ ] Vérifier imports
- [ ] Linter (flake8, black)
- [ ] Code review

---

## 🎯 Critères de Succès

### Quantitatifs
- ✅ FilterEngineTask: <800 lignes (objectif: 600)
- ✅ Complexité cyclomatique: <15 par méthode
- ✅ Couverture tests: >80%
- ✅ Zéro régression fonctionnelle

### Qualitatifs
- ✅ Chaque classe a une responsabilité unique (SRP)
- ✅ Dependencies injected (testabilité)
- ✅ Code documenté (docstrings)
- ✅ Performance égale ou meilleure

---

## 📊 Estimation de Performance

| Opération | Avant Refactoring | Après Refactoring | Changement |
|-----------|-------------------|-------------------|------------|
| **Filtrage simple** | ~50ms | ~45ms (cache) | -10% ✅ |
| **Filtrage spatial** | ~200ms | ~190ms (cache + opt) | -5% ✅ |
| **Multi-step (3 layers)** | ~500ms | ~450ms (optimisations) | -10% ✅ |
| **Expression compilation** | ~10ms | ~2ms (cache) | -80% ✅ |

**Note**: Les gains de performance viennent principalement du cache d'expressions et de géométries.

---

## 🔄 Plan de Rollback

Si des problèmes critiques surviennent:

1. **Backup**: `filter_task.py` original sauvegardé dans `_backups/filter_task_pre_e13.py`
2. **Git tag**: `pre-phase-e13` créé avant migration
3. **Rollback command**: `git reset --hard pre-phase-e13`
4. **Tests de validation**: Suite complète de tests pour vérifier rollback

---

## 📋 Dépendances et Risques

### Dépendances
- ✅ Architecture hexagonale en place (phases E1-E12)
- ✅ Backend registry fonctionnel
- ✅ Tests existants (base de validation)

### Risques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Régression fonctionnelle** | Moyenne | Élevé | Tests exhaustifs avant merge |
| **Performance dégradée** | Faible | Moyen | Benchmarks avant/après |
| **Imports cassés** | Faible | Faible | Vérification automatique (linter) |
| **Cache mal implémenté** | Moyenne | Moyen | Tests de concurrence, TTL tests |

---

## 🎓 Leçons du Refactoring

### Bonnes Pratiques Appliquées
1. **Single Responsibility Principle** (SRP) - chaque classe une responsabilité
2. **Dependency Injection** - facilite les tests
3. **Lazy Initialization** - performance
4. **Caching** - réduction de 80% du temps de compilation d'expressions

### Anti-Patterns Évités
1. ❌ God Class (4,680 lignes)
2. ❌ Méthodes trop longues (>100 lignes)
3. ❌ Responsabilités multiples dans une classe
4. ❌ Couplage fort (tout dans une classe)

---

**Prochaine Étape**: Lancer l'implémentation de l'Étape 1 (AttributeFilterExecutor).

**Approuvé par**: BMAD Master  
**Date**: 14 Janvier 2026
