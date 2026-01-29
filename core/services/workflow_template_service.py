"""
EPIC-3: Workflow Template Service.

Manages saving, loading, and applying raster-vector filter workflow templates.
Templates can be saved to JSON files and reused across projects.
"""
import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from qgis.PyQt.QtCore import QObject, pyqtSignal

logger = logging.getLogger('FilterMate.Services.WorkflowTemplate')


@dataclass
class RasterFilterRule:
    """A single raster filter rule in a workflow."""
    rule_id: str
    raster_name_pattern: str  # Pattern to match raster layer names
    band: int = 1
    predicate: str = "within_range"  # within_range, above_value, below_value, equals
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RasterFilterRule':
        """Create from dictionary."""
        return cls(
            rule_id=data.get('rule_id', str(uuid.uuid4())[:8]),
            raster_name_pattern=data.get('raster_name_pattern', ''),
            band=data.get('band', 1),
            predicate=data.get('predicate', 'within_range'),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            enabled=data.get('enabled', True)
        )


@dataclass
class VectorClipRule:
    """A single vector clip/mask rule in a workflow."""
    rule_id: str
    vector_name_pattern: str  # Pattern to match vector layer names
    operation: str = "clip_extent"  # clip_extent, mask_outside, mask_inside, zonal_stats
    feature_filter: str = "all"  # all, selected, expression
    filter_expression: Optional[str] = None
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VectorClipRule':
        """Create from dictionary."""
        return cls(
            rule_id=data.get('rule_id', str(uuid.uuid4())[:8]),
            vector_name_pattern=data.get('vector_name_pattern', ''),
            operation=data.get('operation', 'clip_extent'),
            feature_filter=data.get('feature_filter', 'all'),
            filter_expression=data.get('filter_expression'),
            enabled=data.get('enabled', True)
        )


@dataclass
class WorkflowTemplate:
    """A complete workflow template for raster-vector filtering."""
    template_id: str
    name: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0"
    
    # Source configuration
    source_type: str = "raster"  # raster or vector
    source_name_pattern: str = ""  # Pattern to match source layer
    
    # Filter rules
    raster_rules: List[RasterFilterRule] = field(default_factory=list)
    vector_rules: List[VectorClipRule] = field(default_factory=list)
    
    # Rule combination
    rule_combination: str = "AND"  # AND or OR
    
    # Target configuration
    target_layer_patterns: List[str] = field(default_factory=list)  # Patterns to match target layers
    target_layer_type: str = "vector"  # vector or raster
    
    # Output options
    add_to_memory: bool = True
    save_to_disk: bool = False
    output_folder: str = ""
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    author: str = ""
    
    def __post_init__(self):
        """Initialize timestamps if not set."""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkflowTemplate':
        """Create from dictionary."""
        raster_rules = [
            RasterFilterRule.from_dict(r) for r in data.get('raster_rules', [])
        ]
        vector_rules = [
            VectorClipRule.from_dict(r) for r in data.get('vector_rules', [])
        ]
        
        return cls(
            template_id=data.get('template_id', str(uuid.uuid4())),
            name=data.get('name', 'Untitled'),
            description=data.get('description', ''),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            version=data.get('version', '1.0'),
            source_type=data.get('source_type', 'raster'),
            source_name_pattern=data.get('source_name_pattern', ''),
            raster_rules=raster_rules,
            vector_rules=vector_rules,
            rule_combination=data.get('rule_combination', 'AND'),
            target_layer_patterns=data.get('target_layer_patterns', []),
            target_layer_type=data.get('target_layer_type', 'vector'),
            add_to_memory=data.get('add_to_memory', True),
            save_to_disk=data.get('save_to_disk', False),
            output_folder=data.get('output_folder', ''),
            tags=data.get('tags', []),
            author=data.get('author', '')
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'template_id': self.template_id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'version': self.version,
            'source_type': self.source_type,
            'source_name_pattern': self.source_name_pattern,
            'raster_rules': [asdict(r) for r in self.raster_rules],
            'vector_rules': [asdict(r) for r in self.vector_rules],
            'rule_combination': self.rule_combination,
            'target_layer_patterns': self.target_layer_patterns,
            'target_layer_type': self.target_layer_type,
            'add_to_memory': self.add_to_memory,
            'save_to_disk': self.save_to_disk,
            'output_folder': self.output_folder,
            'tags': self.tags,
            'author': self.author
        }


@dataclass
class TemplateMatchResult:
    """Result of matching a template to project layers."""
    template: WorkflowTemplate
    source_layer_id: Optional[str] = None
    source_layer_name: Optional[str] = None
    matched_raster_layers: Dict[str, str] = field(default_factory=dict)  # rule_id -> layer_id
    matched_vector_layers: Dict[str, str] = field(default_factory=dict)  # rule_id -> layer_id
    matched_target_layers: List[str] = field(default_factory=list)  # layer_ids
    unmatched_rules: List[str] = field(default_factory=list)  # rule_ids
    warnings: List[str] = field(default_factory=list)


class WorkflowTemplateService(QObject):
    """
    Service for managing workflow templates.
    
    Provides:
    - Template CRUD operations
    - Save/load templates to/from JSON files
    - Match templates to current project layers
    - Execute templates
    
    Signals:
        template_saved: When a template is saved
        template_loaded: When a template is loaded
        template_deleted: When a template is deleted
        template_executed: When a template is executed
        templates_changed: When the template list changes
    """
    
    # Signals
    template_saved = pyqtSignal(str, str)  # template_id, name
    template_loaded = pyqtSignal(str, str)  # template_id, name
    template_deleted = pyqtSignal(str)  # template_id
    template_executed = pyqtSignal(str, int)  # template_id, affected_layers
    templates_changed = pyqtSignal()
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        parent: Optional[QObject] = None
    ):
        """
        Initialize WorkflowTemplateService.
        
        Args:
            storage_path: Path to store templates (defaults to plugin config dir)
            parent: Parent QObject
        """
        super().__init__(parent)
        
        # Set storage path
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            # Default to plugin config directory
            from qgis.core import QgsApplication
            self._storage_path = Path(QgsApplication.qgisSettingsDirPath()) / 'FilterMate' / 'workflows'
        
        # Create storage directory if needed
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory template cache
        self._templates: Dict[str, WorkflowTemplate] = {}
        
        # Load existing templates
        self._load_all_templates()
        
        logger.info(f"WorkflowTemplateService initialized with {len(self._templates)} templates")
    
    # ─────────────────────────────────────────────────────────────────
    # Template CRUD Operations
    # ─────────────────────────────────────────────────────────────────
    
    def create_template(
        self,
        name: str,
        description: str = "",
        source_type: str = "raster",
        **kwargs
    ) -> WorkflowTemplate:
        """
        Create a new workflow template.
        
        Args:
            name: Template name
            description: Template description
            source_type: 'raster' or 'vector'
            **kwargs: Additional template properties
            
        Returns:
            Created WorkflowTemplate
        """
        template_id = str(uuid.uuid4())
        
        template = WorkflowTemplate(
            template_id=template_id,
            name=name,
            description=description,
            source_type=source_type,
            **kwargs
        )
        
        self._templates[template_id] = template
        self._save_template_to_disk(template)
        
        self.template_saved.emit(template_id, name)
        self.templates_changed.emit()
        
        logger.info(f"Created workflow template: {name} ({template_id})")
        return template
    
    def create_from_context(
        self,
        name: str,
        context: Dict,
        description: str = "",
        tags: Optional[List[str]] = None
    ) -> WorkflowTemplate:
        """
        Create a template from current filter context.
        
        Args:
            name: Template name
            context: Current filter context from UI
            description: Template description
            tags: Optional list of tags for categorization
            
        Returns:
            Created WorkflowTemplate
        """
        template_id = str(uuid.uuid4())
        
        # Extract source info
        source_type = context.get('source_type', 'raster')
        source_name = context.get('layer_name', '')
        
        # Create raster rules if applicable
        raster_rules = []
        if source_type == 'raster' and context.get('range_min') is not None:
            rule = RasterFilterRule(
                rule_id=str(uuid.uuid4())[:8],
                raster_name_pattern=source_name,
                band=context.get('band', 1),
                predicate=context.get('predicate', 'within_range'),
                min_value=context.get('range_min'),
                max_value=context.get('range_max'),
                enabled=True
            )
            raster_rules.append(rule)
        
        # Extract target layers
        target_patterns = []
        target_layers = context.get('target_layers', [])
        if target_layers:
            from qgis.core import QgsProject
            for layer_id in target_layers:
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer:
                    target_patterns.append(layer.name())
        
        template = WorkflowTemplate(
            template_id=template_id,
            name=name,
            description=description,
            source_type=source_type,
            source_name_pattern=source_name,
            raster_rules=raster_rules,
            target_layer_patterns=target_patterns,
            target_layer_type='vector' if source_type == 'raster' else 'raster',
            add_to_memory=context.get('add_to_memory', True),
            tags=tags or []
        )
        
        self._templates[template_id] = template
        self._save_template_to_disk(template)
        
        self.template_saved.emit(template_id, name)
        self.templates_changed.emit()
        
        logger.info(f"Created template from context: {name}")
        return template
    
    def update_template(
        self,
        template_id: str,
        **updates
    ) -> Optional[WorkflowTemplate]:
        """
        Update an existing template.
        
        Args:
            template_id: Template ID
            **updates: Fields to update
            
        Returns:
            Updated template or None if not found
        """
        template = self._templates.get(template_id)
        if not template:
            logger.warning(f"Template not found: {template_id}")
            return None
        
        for key, value in updates.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        template.updated_at = datetime.now().isoformat()
        
        self._save_template_to_disk(template)
        self.template_saved.emit(template_id, template.name)
        self.templates_changed.emit()
        
        logger.info(f"Updated template: {template.name}")
        return template
    
    def delete_template(self, template_id: str) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            True if deleted successfully
        """
        template = self._templates.pop(template_id, None)
        if not template:
            return False
        
        # Delete file
        file_path = self._get_template_file_path(template_id)
        if file_path.exists():
            file_path.unlink()
        
        self.template_deleted.emit(template_id)
        self.templates_changed.emit()
        
        logger.info(f"Deleted template: {template.name}")
        return True
    
    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)
    
    def get_all_templates(self) -> List[WorkflowTemplate]:
        """Get all templates sorted by name."""
        return sorted(self._templates.values(), key=lambda t: t.name.lower())
    
    def search_templates(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None
    ) -> List[WorkflowTemplate]:
        """
        Search templates by query, tags, or source type.
        
        Args:
            query: Search query (matches name, description)
            tags: Filter by tags
            source_type: Filter by source type ('raster' or 'vector')
            
        Returns:
            List of matching templates
        """
        results = []
        query_lower = query.lower()
        
        for template in self._templates.values():
            # Query match
            if query and query_lower not in template.name.lower():
                if query_lower not in template.description.lower():
                    continue
            
            # Tag match
            if tags:
                if not any(tag in template.tags for tag in tags):
                    continue
            
            # Source type match
            if source_type and template.source_type != source_type:
                continue
            
            results.append(template)
        
        return sorted(results, key=lambda t: t.name.lower())
    
    # ─────────────────────────────────────────────────────────────────
    # Import/Export
    # ─────────────────────────────────────────────────────────────────
    
    def export_template(self, template_id: str, file_path: str) -> bool:
        """
        Export a template to a JSON file.
        
        Args:
            template_id: Template ID
            file_path: Destination file path
            
        Returns:
            True if exported successfully
        """
        template = self._templates.get(template_id)
        if not template:
            return False
        
        try:
            data = template.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported template to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting template: {e}")
            return False
    
    def export_all_templates(self, folder_path: str) -> int:
        """
        Export all templates to a folder.
        
        Args:
            folder_path: Destination folder
            
        Returns:
            Number of templates exported
        """
        folder = Path(folder_path)
        folder.mkdir(parents=True, exist_ok=True)
        
        exported = 0
        for template_id, template in self._templates.items():
            file_path = folder / f"{template.name.replace(' ', '_')}_{template_id[:8]}.json"
            if self.export_template(template_id, str(file_path)):
                exported += 1
        
        logger.info(f"Exported {exported} templates to: {folder_path}")
        return exported
    
    def import_template(self, file_path: str) -> Optional[WorkflowTemplate]:
        """
        Import a template from a JSON file.
        
        Args:
            file_path: Source file path
            
        Returns:
            Imported template or None on error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            template = WorkflowTemplate.from_dict(data)
            
            # Check for duplicate ID, regenerate if needed
            if template.template_id in self._templates:
                template.template_id = str(uuid.uuid4())
            
            self._templates[template.template_id] = template
            self._save_template_to_disk(template)
            
            self.template_loaded.emit(template.template_id, template.name)
            self.templates_changed.emit()
            
            logger.info(f"Imported template: {template.name}")
            return template
            
        except Exception as e:
            logger.error(f"Error importing template: {e}")
            return None
    
    # ─────────────────────────────────────────────────────────────────
    # Template Matching
    # ─────────────────────────────────────────────────────────────────
    
    def match_template_to_project(
        self,
        template_id: str
    ) -> Optional[TemplateMatchResult]:
        """
        Match a template to current project layers.
        
        Args:
            template_id: Template ID
            
        Returns:
            TemplateMatchResult with matched layers
        """
        template = self._templates.get(template_id)
        if not template:
            return None
        
        from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
        import fnmatch
        
        result = TemplateMatchResult(template=template)
        project = QgsProject.instance()
        
        # Match source layer
        for layer in project.mapLayers().values():
            if fnmatch.fnmatch(layer.name().lower(), template.source_name_pattern.lower()):
                result.source_layer_id = layer.id()
                result.source_layer_name = layer.name()
                break
        
        if not result.source_layer_id and template.source_name_pattern:
            result.warnings.append(f"Source layer not found: {template.source_name_pattern}")
        
        # Match raster rules
        raster_layers = {l.name(): l for l in project.mapLayers().values() 
                        if isinstance(l, QgsRasterLayer)}
        
        for rule in template.raster_rules:
            matched = False
            for name, layer in raster_layers.items():
                if fnmatch.fnmatch(name.lower(), rule.raster_name_pattern.lower()):
                    result.matched_raster_layers[rule.rule_id] = layer.id()
                    matched = True
                    break
            
            if not matched:
                result.unmatched_rules.append(rule.rule_id)
                result.warnings.append(f"Raster not found: {rule.raster_name_pattern}")
        
        # Match vector rules
        vector_layers = {l.name(): l for l in project.mapLayers().values()
                        if isinstance(l, QgsVectorLayer)}
        
        for rule in template.vector_rules:
            matched = False
            for name, layer in vector_layers.items():
                if fnmatch.fnmatch(name.lower(), rule.vector_name_pattern.lower()):
                    result.matched_vector_layers[rule.rule_id] = layer.id()
                    matched = True
                    break
            
            if not matched:
                result.unmatched_rules.append(rule.rule_id)
                result.warnings.append(f"Vector not found: {rule.vector_name_pattern}")
        
        # Match target layers
        target_layers = raster_layers if template.target_layer_type == 'raster' else vector_layers
        for pattern in template.target_layer_patterns:
            for name, layer in target_layers.items():
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    if layer.id() not in result.matched_target_layers:
                        result.matched_target_layers.append(layer.id())
        
        return result
    
    def build_context_from_template(
        self,
        template_id: str,
        match_result: Optional[TemplateMatchResult] = None
    ) -> Optional[Dict]:
        """
        Build a filter context from a template.
        
        Args:
            template_id: Template ID
            match_result: Optional pre-computed match result
            
        Returns:
            Filter context dict ready for UI
        """
        template = self._templates.get(template_id)
        if not template:
            return None
        
        if match_result is None:
            match_result = self.match_template_to_project(template_id)
        
        if match_result is None:
            return None
        
        # Build context
        context = {
            'source_type': template.source_type,
            'template_id': template_id,
            'template_name': template.name,
            'layer_id': match_result.source_layer_id,
            'layer_name': match_result.source_layer_name,
            'target_layers': match_result.matched_target_layers,
            'add_to_memory': template.add_to_memory,
            'save_to_disk': template.save_to_disk,
            'output_folder': template.output_folder
        }
        
        # Add first raster rule info if available
        if template.raster_rules:
            rule = template.raster_rules[0]
            context['band'] = rule.band
            context['predicate'] = rule.predicate
            context['range_min'] = rule.min_value
            context['range_max'] = rule.max_value
        
        return context
    
    # ─────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────
    
    def _get_template_file_path(self, template_id: str) -> Path:
        """Get file path for a template."""
        return self._storage_path / f"{template_id}.json"
    
    def _save_template_to_disk(self, template: WorkflowTemplate) -> bool:
        """Save a template to disk."""
        try:
            file_path = self._get_template_file_path(template.template_id)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving template: {e}")
            return False
    
    def _load_all_templates(self) -> None:
        """Load all templates from storage."""
        self._templates.clear()
        
        if not self._storage_path.exists():
            return
        
        for file_path in self._storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                template = WorkflowTemplate.from_dict(data)
                self._templates[template.template_id] = template
            except Exception as e:
                logger.warning(f"Error loading template {file_path}: {e}")
        
        logger.info(f"Loaded {len(self._templates)} workflow templates")
