#!/usr/bin/env python3
"""
Test script for CombinedQueryOptimizer v2.9.0 multi-step optimization.

Tests the new optimization for MV + EXISTS with large FID lists.
Including SOURCE_MV_OPTIMIZE for creating source MV with pre-computed buffer.
"""

import re
import hashlib
from typing import Optional, Dict, Any, Tuple, List, NamedTuple
from dataclasses import dataclass, field
from enum import Enum, auto


# ============== Mock Logger ==============
class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def debug(self, msg): pass  # Quiet for tests
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

logger = MockLogger()


# ============== Copied Classes from combined_query_optimizer.py ==============

class OptimizationType(Enum):
    """Types of query optimizations applied."""
    NONE = auto()
    MV_REUSE = auto()
    FID_LIST_OPTIMIZE = auto()
    SUBQUERY_MERGE = auto()
    EXPRESSION_SIMPLIFY = auto()
    CACHE_HIT = auto()
    RANGE_OPTIMIZE = auto()
    SOURCE_MV_OPTIMIZE = auto()  # v2.9.0: Create source MV with pre-computed buffer


@dataclass
class MaterializedViewInfo:
    """Information about a detected materialized view reference."""
    schema: str
    view_name: str
    primary_key: str
    full_match: str
    
    @property
    def qualified_name(self) -> str:
        return f'"{self.schema}"."{self.view_name}"'


@dataclass
class SourceMVInfo:
    """Information about source MV with pre-computed buffer to create."""
    schema: str
    view_name: str
    source_table: str
    source_schema: str
    source_geom_col: str
    fid_column: str
    fid_list: List[int]
    buffer_distance: str
    buffer_style: str
    create_sql: str
    
    @property
    def qualified_name(self) -> str:
        return f'"{self.schema}"."{self.view_name}"'


@dataclass
class OptimizationResult:
    """Result of query optimization."""
    success: bool
    optimized_expression: str
    optimization_type: OptimizationType
    original_expression: str
    performance_hint: str = ""
    mv_info: Optional[MaterializedViewInfo] = None
    source_mv_info: Optional[SourceMVInfo] = None
    estimated_speedup: float = 1.0
    complexity_reduction: float = 0.0


# ============== Simplified Optimizer for Testing ==============

class TestCombinedQueryOptimizer:
    """Simplified optimizer for testing the new patterns."""
    
    SOURCE_FID_MV_THRESHOLD = 50
    FID_RANGE_THRESHOLD = 20
    MAX_INLINE_FIDS = 30
    
    FILTERMATE_MV_PATTERN = re.compile(
        r'"?(\w+)"?\s+IN\s*\(\s*SELECT\s+"?(\w+)"?\s+FROM\s+"?(\w+)"?\s*\.\s*"?((?:filtermate_mv_|mv_)\w+)"?\s*\)',
        re.IGNORECASE
    )
    
    EXISTS_BUFFER_FID_PATTERN = re.compile(
        r'EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"([^"]+)"\s*\.\s*"([^"]+)"\s+AS\s+(\w+)\s+'
        r'WHERE\s+(ST_\w+)\s*\(\s*"([^"]+)"\s*\.\s*"([^"]+)"\s*,\s*'
        r'ST_Buffer\s*\(\s*\3\s*\.\s*"([^"]+)"\s*,\s*([^,)]+)\s*(?:,\s*[\'"]([^"\']+)[\'"])?\s*\)\s*\)\s*'
        r'AND\s*\(\s*\3\s*\.\s*"(\w+)"\s+IN\s*\(\s*([\d\s,]+)\s*\)\s*\)\s*\)',
        re.IGNORECASE | re.DOTALL
    )
    
    def detect_mv(self, expression: str) -> Optional[MaterializedViewInfo]:
        match = self.FILTERMATE_MV_PATTERN.search(expression)
        if match:
            return MaterializedViewInfo(
                primary_key=match.group(1),
                schema=match.group(3),
                view_name=match.group(4),
                full_match=match.group(0)
            )
        return None
    
    def _build_mv_buffered_subquery(
        self,
        mv_info: MaterializedViewInfo,
        source_schema: str,
        source_table: str,
        source_geom_col: str,
        spatial_predicate: str,
        buffer_distance: str,
        buffer_style: str,
        fid_column: str,
        fid_list: List[int],
        primary_key: str
    ) -> Tuple[str, Optional[SourceMVInfo]]:
        """Build optimized subquery, creating source MV if threshold exceeded."""
        fid_count = len(fid_list)
        fid_list_str = ', '.join(str(fid) for fid in fid_list)
        source_mv_info = None
        
        if fid_count > self.SOURCE_FID_MV_THRESHOLD:
            # Generate unique source MV name
            fid_hash = hashlib.md5(','.join(str(f) for f in sorted(fid_list)).encode()).hexdigest()[:8]
            src_mv_name = f"filtermate_src_{fid_hash}"
            
            create_sql = f'''CREATE MATERIALIZED VIEW IF NOT EXISTS "{source_schema}"."{src_mv_name}" AS
    SELECT "{fid_column}", 
           "{source_geom_col}" AS geom,
           ST_Buffer("{source_geom_col}", {buffer_distance}, '{buffer_style}') AS geom_buffered
    FROM "{source_schema}"."{source_table}"
    WHERE "{fid_column}" IN ({fid_list_str})
    WITH DATA;'''
            
            source_mv_info = SourceMVInfo(
                schema=source_schema,
                view_name=src_mv_name,
                source_table=source_table,
                source_schema=source_schema,
                source_geom_col=source_geom_col,
                fid_column=fid_column,
                fid_list=fid_list,
                buffer_distance=buffer_distance,
                buffer_style=buffer_style,
                create_sql=create_sql
            )
            
            optimized = f'''"{primary_key}" IN (
    SELECT mv."pk" 
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1 
        FROM "{source_schema}"."{src_mv_name}" AS __src
        WHERE {spatial_predicate}(mv."geom", __src.geom_buffered)
    )
)'''
            logger.info(f"🔧 v2.9.0: Will create source MV '{src_mv_name}' for {fid_count} FIDs")
        else:
            optimized = f'''"{primary_key}" IN (
    SELECT mv."pk" 
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1 
        FROM (
            SELECT "{source_geom_col}", 
                   ST_Buffer("{source_geom_col}", {buffer_distance}, '{buffer_style}') AS geom_buffered
            FROM "{source_schema}"."{source_table}"
            WHERE "{fid_column}" IN ({fid_list_str})
        ) AS __src
        WHERE {spatial_predicate}(mv."geom", __src.geom_buffered)
    )
)'''
        
        return optimized, source_mv_info
    
    def optimize(self, old_subset: str, new_expression: str) -> OptimizationResult:
        original = f"({old_subset}) AND ({new_expression})"
        
        mv_info = self.detect_mv(old_subset)
        if not mv_info:
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )
        
        match = self.EXISTS_BUFFER_FID_PATTERN.search(new_expression)
        
        if match:
            source_schema = match.group(1)
            source_table = match.group(2)
            spatial_predicate = match.group(4)
            source_geom_col = match.group(7)
            buffer_distance = match.group(8).strip()
            buffer_style = match.group(9) if match.group(9) else 'quad_segs=5'
            fid_column = match.group(10)
            fid_list_str = match.group(11)
            
            try:
                fid_list = [int(fid.strip()) for fid in fid_list_str.split(',') if fid.strip()]
            except ValueError:
                return OptimizationResult(
                    success=False,
                    optimized_expression=original,
                    optimization_type=OptimizationType.NONE,
                    original_expression=original
                )
            
            fid_count = len(fid_list)
            
            optimized, source_mv_info = self._build_mv_buffered_subquery(
                mv_info=mv_info,
                source_schema=source_schema,
                source_table=source_table,
                source_geom_col=source_geom_col,
                spatial_predicate=spatial_predicate,
                buffer_distance=buffer_distance,
                buffer_style=buffer_style,
                fid_column=fid_column,
                fid_list=fid_list,
                primary_key=mv_info.primary_key or 'fid'
            )
            
            optimized = ' '.join(optimized.split())
            
            if source_mv_info:
                opt_type = OptimizationType.SOURCE_MV_OPTIMIZE
                hint = f"Source MV with pre-computed buffer ({fid_count} FIDs → {source_mv_info.view_name})"
                speedup = 20.0
            else:
                opt_type = OptimizationType.MV_REUSE
                hint = f"Restructured with pre-computed buffer ({fid_count} FIDs)"
                speedup = 10.0
            
            return OptimizationResult(
                success=True,
                optimized_expression=optimized,
                optimization_type=opt_type,
                original_expression=original,
                performance_hint=hint,
                mv_info=mv_info,
                source_mv_info=source_mv_info,
                estimated_speedup=speedup,
                complexity_reduction=0.7 if source_mv_info else 0.6
            )
        
        return OptimizationResult(
            success=False,
            optimized_expression=original,
            optimization_type=OptimizationType.NONE,
            original_expression=original
        )


# ============== Tests ==============

def test_mv_exists_fid_optimization():
    """Test the MV + EXISTS + FID list optimization."""
    print("=" * 60)
    print("TEST: MV + EXISTS with FID list optimization")
    print("=" * 60)
    
    optimizer = TestCombinedQueryOptimizer()
    
    # Real-world test case from FilterMate
    old_subset = '"fid" IN (SELECT "pk" FROM "public"."filtermate_mv_f4d4d2fd")'
    new_expression = '''EXISTS (SELECT 1 FROM "public"."troncon_de_route" AS __source WHERE ST_Intersects("batiment"."geometrie", ST_Buffer(__source."geometrie", 50.0, 'quad_segs=5')) AND (__source."fid" IN (347130, 156482, 161579, 158992, 347567, 221939, 261209, 161452, 158952, 161417, 291595, 161576, 358889, 163551, 158993, 161085, 161302, 158963, 161393, 159008, 347485, 163564, 161137, 156483, 161581, 163560, 163652, 347566, 161588, 163565, 156498, 291597, 347132, 222100, 161578, 347764, 161418, 221937, 161390, 249830, 163554, 152941)))'''
    
    result = optimizer.optimize(old_subset, new_expression)
    
    print(f"\n✓ Success: {result.success}")
    print(f"✓ Type: {result.optimization_type.name}")
    print(f"✓ Speedup: {result.estimated_speedup}x")
    print(f"✓ Hint: {result.performance_hint}")
    print(f"\nOriginal length: {len(result.original_expression)} chars")
    print(f"Optimized length: {len(result.optimized_expression)} chars")
    
    print("\n" + "-" * 40)
    print("ORIGINAL (first 200 chars):")
    print(result.original_expression[:200] + "...")
    
    print("\n" + "-" * 40)
    print("OPTIMIZED:")
    # Pretty print
    opt_pretty = result.optimized_expression.replace('SELECT', '\n    SELECT').replace('FROM', '\n    FROM').replace('WHERE', '\n    WHERE')
    print(opt_pretty)
    
    # Assertions
    assert result.success, "Optimization should succeed"
    assert result.optimization_type == OptimizationType.MV_REUSE
    assert "ST_Buffer" in result.optimized_expression
    assert "geom_buffered" in result.optimized_expression
    assert "filtermate_mv_f4d4d2fd" in result.optimized_expression
    
    print("\n✅ All assertions passed!")
    return True


def test_pattern_detection():
    """Test the regex pattern detection."""
    print("\n" + "=" * 60)
    print("TEST: Pattern Detection")
    print("=" * 60)
    
    optimizer = TestCombinedQueryOptimizer()
    
    # Test MV pattern
    mv_expr = '"fid" IN (SELECT "pk" FROM "public"."filtermate_mv_abc123")'
    mv_info = optimizer.detect_mv(mv_expr)
    assert mv_info is not None, "Should detect MV"
    assert mv_info.view_name == "filtermate_mv_abc123"
    assert mv_info.schema == "public"
    print(f"✓ MV detected: {mv_info.view_name}")
    
    # Test EXISTS pattern
    exists_expr = '''EXISTS (SELECT 1 FROM "public"."roads" AS __source WHERE ST_Intersects("buildings"."geom", ST_Buffer(__source."geom", 100.0, 'quad_segs=8')) AND (__source."id" IN (1, 2, 3, 4, 5)))'''
    
    match = optimizer.EXISTS_BUFFER_FID_PATTERN.search(exists_expr)
    assert match is not None, "Should match EXISTS pattern"
    print(f"✓ EXISTS pattern matched")
    print(f"  - Source: {match.group(1)}.{match.group(2)}")
    print(f"  - Predicate: {match.group(4)}")
    print(f"  - Buffer: {match.group(8)}")
    print(f"  - FIDs: {match.group(11)}")
    
    print("\n✅ Pattern detection tests passed!")
    return True


def test_source_mv_creation():
    """Test SOURCE_MV_OPTIMIZE when FID count > SOURCE_FID_MV_THRESHOLD (50)."""
    print("\n" + "=" * 60)
    print("TEST: Source MV Creation (> 50 FIDs)")
    print("=" * 60)
    
    optimizer = TestCombinedQueryOptimizer()
    
    # Generate 223 FIDs (user's real case)
    fids = [347567, 381242, 257650, 221939, 163534, 161456, 261209, 161452, 347488, 158952, 161417, 291595, 158946, 161576, 161504, 257652, 161450, 163551, 161423, 158993, 249975, 161302, 158963, 161393, 159008, 347485, 163564, 161581, 161577, 158961, 161254, 163560, 158994, 161298, 163652, 347566, 163567, 161588, 163565, 291597, 347132, 221938, 161574, 222100, 161580, 161578, 347764, 161418, 221937, 161390, 161398, 163708, 163554, 161315, 161391, 161300, 161589, 163561, 249585, 161243, 163598, 222086, 158959, 161396, 158972, 161314, 163557, 161392, 161453, 159031, 163649, 161310, 221935, 158934, 161447, 163587, 336786, 161474, 291584, 161301, 161413, 161477, 163566, 291594, 161607, 163684, 163599, 347544, 221982, 161454, 161421, 158958, 161420, 161445, 261206, 221936, 161514, 163604, 291593, 221984, 249885, 161253, 161461, 158965, 161316, 158951, 347748, 158962, 161416, 161245, 161516, 161422, 161349, 161306, 161397, 158955, 159001, 163600, 163555, 347135, 291586, 222101, 347131, 261207, 249887, 158948, 367636, 161524, 161463, 347179, 221946, 249976, 158960, 161304, 288303, 161471, 158964, 163552, 249711, 163620, 163553, 161473, 291588, 161608, 159032, 158947, 158973, 221983, 367661, 257651, 163559, 158976, 158945, 291592, 261210, 161303, 257633, 374210, 161399, 158956, 163666, 158954, 161532, 159005, 161590, 222141, 347765, 163563, 158942, 261212, 221942, 161357, 158974, 161457, 161299, 257632, 261213, 291589, 161472, 161446, 163558, 347754, 161415, 161476, 261208, 347570, 161419, 161297, 347547, 347183, 347128, 159004, 161572, 161311, 163588, 291596, 158943, 161468, 161305, 257653, 158971, 158975, 158950, 158953, 159030, 161451, 161605, 158944, 163556, 257628, 159002, 161395, 161520, 163651, 221977, 163550, 347124, 347130, 158957, 161579, 161533, 158992, 158949]
    fid_str = ', '.join(str(f) for f in fids)
    
    old_subset = '"fid" IN (SELECT "pk" FROM "public"."filtermate_mv_e3f49718")'
    new_expression = f'''EXISTS (SELECT 1 FROM "public"."troncon_de_route" AS __source WHERE ST_Intersects("batiment"."geometrie", ST_Buffer(__source."geometrie", 50.0, 'quad_segs=5')) AND (__source."fid" IN ({fid_str})))'''
    
    result = optimizer.optimize(old_subset, new_expression)
    
    print(f"\n✓ Success: {result.success}")
    print(f"✓ Type: {result.optimization_type.name}")
    print(f"✓ Speedup: {result.estimated_speedup}x")
    print(f"✓ Hint: {result.performance_hint}")
    
    # Key assertions for SOURCE_MV_OPTIMIZE
    assert result.success, "Optimization should succeed"
    assert result.optimization_type == OptimizationType.SOURCE_MV_OPTIMIZE, f"Expected SOURCE_MV_OPTIMIZE, got {result.optimization_type.name}"
    assert result.source_mv_info is not None, "Should have source_mv_info"
    assert result.source_mv_info.view_name.startswith("filtermate_src_"), f"View name should start with filtermate_src_, got {result.source_mv_info.view_name}"
    
    print(f"\n📦 Source MV to create:")
    print(f"   Name: {result.source_mv_info.view_name}")
    print(f"   Schema: {result.source_mv_info.schema}")
    print(f"   FID count: {len(result.source_mv_info.fid_list)}")
    
    print(f"\n📄 CREATE SQL (first 300 chars):")
    print(result.source_mv_info.create_sql[:300] + "...")
    
    print(f"\n📏 Lengths:")
    print(f"   Original: {len(result.original_expression)} chars")
    print(f"   Optimized: {len(result.optimized_expression)} chars")
    print(f"   Reduction: {(1 - len(result.optimized_expression)/len(result.original_expression))*100:.1f}%")
    
    # Verify optimized query uses the source MV
    assert result.source_mv_info.view_name in result.optimized_expression, "Optimized query should reference source MV"
    assert "geom_buffered" in result.optimized_expression, "Should use pre-computed geom_buffered"
    
    # Verify NO inline FID list in optimized expression
    assert fid_str[:50] not in result.optimized_expression, "Optimized query should NOT have inline FID list"
    
    print("\n✅ Source MV creation test passed!")
    return True


if __name__ == "__main__":
    test_pattern_detection()
    test_mv_exists_fid_optimization()
    test_source_mv_creation()
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
