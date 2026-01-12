#!/usr/bin/env python3
"""
Phase 14.1 Migration Script
Replaces _build_backend_expression method (426 lines) with shim delegating to BackendExpressionBuilder service.
"""

import sys
import re
from pathlib import Path

def migrate_filter_task():
    """Replace the massive _build_backend_expression method with a clean shim."""
    
    filter_task_path = Path(__file__).parent.parent / "core" / "tasks" / "filter_task.py"
    
    if not filter_task_path.exists():
        print(f"ERROR: {filter_task_path} not found")
        return False
    
    # Read the file
    content = filter_task_path.read_text(encoding='utf-8')
    
    # Find the method to replace (from def to the line before _combine_with_old_filter)
    # The method spans lines 3001-3427
    method_pattern = r'(    def _build_backend_expression\(self, backend, layer_props, source_geom\):.*?)(        return expression\n\n)(    def _combine_with_old_filter\(self, expression, layer\):)'
    
    # New shim implementation
    new_method = r'''\1        # PHASE 14.1: Delegate to BackendExpressionBuilder service
        from core.services.backend_expression_builder import create_expression_builder
        
        # Create builder with all required dependencies
        builder = create_expression_builder(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            expr_cache=self.expr_cache,
            format_pk_values_callback=self._format_pk_values_for_sql,
            get_optimization_thresholds_callback=self._get_optimization_thresholds
        )
        
        # Transfer task state to builder
        builder.param_buffer_value = self.param_buffer_value
        builder.param_buffer_expression = self.param_buffer_expression
        builder.param_use_centroids_distant_layers = self.param_use_centroids_distant_layers
        builder.param_use_centroids_source_layer = self.param_use_centroids_source_layer
        builder.param_source_table = self.param_source_table
        builder.param_source_geom = self.param_source_geom
        builder.current_predicates = self.current_predicates
        builder.approved_optimizations = self.approved_optimizations
        builder.auto_apply_optimizations = self.auto_apply_optimizations
        builder.spatialite_source_geom = self.spatialite_source_geom
        builder.ogr_source_geom = self.ogr_source_geom
        builder.source_layer_crs_authid = self.source_layer_crs_authid
        
        # Build expression
        expression = builder.build(backend, layer_props, source_geom)
        
        # Collect created MVs for cleanup
        created_mvs = builder.get_created_mvs()
        if created_mvs:
            self._source_selection_mvs.extend(created_mvs)
        
        return expression

\3'''
    
    # Apply replacement
    new_content, count = re.subn(method_pattern, new_method, content, flags=re.DOTALL)
    
    if count == 0:
        print("ERROR: Could not find method pattern to replace")
        print("Trying alternative approach...")
        
        # Alternative: Find by line numbers
        lines = content.split('\n')
        if len(lines) < 3428:
            print(f"ERROR: File only has {len(lines)} lines, expected at least 3428")
            return False
        
        # Find the method start
        method_start_idx = None
        for i, line in enumerate(lines):
            if 'def _build_backend_expression(self, backend, layer_props, source_geom):' in line:
                method_start_idx = i
                break
        
        if method_start_idx is None:
            print("ERROR: Could not find _build_backend_expression method")
            return False
        
        print(f"Found method at line {method_start_idx + 1}")
        
        # Find the method end (before _combine_with_old_filter)
        method_end_idx = None
        for i in range(method_start_idx + 1, len(lines)):
            if 'def _combine_with_old_filter(self, expression, layer):' in lines[i]:
                # Back up to find the last 'return expression' before this
                for j in range(i - 1, method_start_idx, -1):
                    if lines[j].strip() == 'return expression':
                        method_end_idx = j
                        break
                break
        
        if method_end_idx is None:
            print("ERROR: Could not find method end")
            return False
        
        print(f"Method body ends at line {method_end_idx + 1}")
        print(f"Replacing {method_end_idx - method_start_idx - 1} lines of method body")
        
        # Build new method
        new_method_lines = [
            lines[method_start_idx],  # def line
            lines[method_start_idx + 1],  # """
            '        Build filter expression using backend.',
            '        ',
            '        PHASE 14.1 GOD CLASS REDUCTION: Delegates to BackendExpressionBuilder service.',
            '        Extracted 426 lines to core/services/backend_expression_builder.py (v5.0-alpha).',
            '        ',
            '        For PostgreSQL with few source features, passes WKT for simplified expressions.',
            '        Uses expression cache for repeated operations (Phase 4 optimization).',
            '        ',
            '        Args:',
            '            backend: Backend instance',
            '            layer_props: Layer properties dict',
            '            source_geom: Prepared source geometry',
            '            ',
            '        Returns:',
            '            str: Filter expression or None on error',
            '        """',
            '        # PHASE 14.1: Delegate to BackendExpressionBuilder service',
            '        from core.services.backend_expression_builder import create_expression_builder',
            '        ',
            '        # Create builder with all required dependencies',
            '        builder = create_expression_builder(',
            '            source_layer=self.source_layer,',
            '            task_parameters=self.task_parameters,',
            '            expr_cache=self.expr_cache,',
            '            format_pk_values_callback=self._format_pk_values_for_sql,',
            '            get_optimization_thresholds_callback=self._get_optimization_thresholds',
            '        )',
            '        ',
            '        # Transfer task state to builder',
            '        builder.param_buffer_value = self.param_buffer_value',
            '        builder.param_buffer_expression = self.param_buffer_expression',
            '        builder.param_use_centroids_distant_layers = self.param_use_centroids_distant_layers',
            '        builder.param_use_centroids_source_layer = self.param_use_centroids_source_layer',
            '        builder.param_source_table = self.param_source_table',
            '        builder.param_source_geom = self.param_source_geom',
            '        builder.current_predicates = self.current_predicates',
            '        builder.approved_optimizations = self.approved_optimizations',
            '        builder.auto_apply_optimizations = self.auto_apply_optimizations',
            '        builder.spatialite_source_geom = self.spatialite_source_geom',
            '        builder.ogr_source_geom = self.ogr_source_geom',
            '        builder.source_layer_crs_authid = self.source_layer_crs_authid',
            '        ',
            '        # Build expression',
            '        expression = builder.build(backend, layer_props, source_geom)',
            '        ',
            '        # Collect created MVs for cleanup',
            '        created_mvs = builder.get_created_mvs()',
            '        if created_mvs:',
            '            self._source_selection_mvs.extend(created_mvs)',
            '        ',
            '        return expression',
            ''
        ]
        
        # Replace in lines array
        new_lines = lines[:method_start_idx] + new_method_lines + lines[method_end_idx + 1:]
        new_content = '\n'.join(new_lines)
    
    # Write back
    filter_task_path.write_text(new_content, encoding='utf-8')
    
    old_lines = len(content.split('\n'))
    new_lines_count = len(new_content.split('\n'))
    reduction = old_lines - new_lines_count
    
    print(f"✓ Migration complete!")
    print(f"  Original: {old_lines} lines")
    print(f"  New:      {new_lines_count} lines")
    print(f"  Reduced:  {reduction} lines ({reduction / old_lines * 100:.1f}%)")
    
    return True

if __name__ == '__main__':
    success = migrate_filter_task()
    sys.exit(0 if success else 1)
