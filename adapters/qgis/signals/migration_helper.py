"""
Signal Migration Helper for FilterMate.

Provides utilities for migrating legacy signal connections
to the centralized SignalManager.

Story: MIG-086
Phase: 6 - God Class DockWidget Migration
"""

import functools
import logging
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto

logger = logging.getLogger(__name__)


class SignalCategory(Enum):
    """Categories of signals in FilterMate."""
    WIDGET = auto()      # UI widget signals (buttons, combos, etc.)
    LAYER = auto()       # Layer-specific signals
    PROJECT = auto()     # QGIS project signals
    TASK = auto()        # QgsTask signals
    CONTROLLER = auto()  # Controller signals
    INTERNAL = auto()    # Internal plugin signals


@dataclass
class SignalDefinition:
    """Definition of a signal to be registered."""
    name: str
    widget_attr: str
    signal_name: str
    handler_name: str
    category: SignalCategory = SignalCategory.WIDGET
    context: Optional[str] = None
    priority: int = 1  # 1=high, 2=medium, 3=low
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'widget_attr': self.widget_attr,
            'signal_name': self.signal_name,
            'handler_name': self.handler_name,
            'category': self.category.name,
            'context': self.context,
            'priority': self.priority
        }


@dataclass
class MigrationResult:
    """Result of a signal migration operation."""
    total_signals: int = 0
    migrated: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_signals == 0:
            return 100.0
        return (self.migrated / self.total_signals) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_signals': self.total_signals,
            'migrated': self.migrated,
            'failed': self.failed,
            'skipped': self.skipped,
            'success_rate': f"{self.success_rate:.1f}%",
            'errors': self.errors
        }


# ─────────────────────────────────────────────────────────────────
# Deprecated Decorator
# ─────────────────────────────────────────────────────────────────

def deprecated_signal_connection(new_method: str):
    """
    Mark a signal connection method as deprecated.
    
    Args:
        new_method: The new method to use instead
    
    Usage:
        @deprecated_signal_connection('use SignalManager.connect()')
        def connect_signals_legacy(self):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated. "
                f"Use {new_method} instead.",
                DeprecationWarning,
                stacklevel=2
            )
            logger.warning(
                f"Deprecated signal connection method called: {func.__name__}"
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────
# Signal Definitions Registry
# ─────────────────────────────────────────────────────────────────

# Widget signals in filter_mate_dockwidget.py
DOCKWIDGET_WIDGET_SIGNALS: List[SignalDefinition] = [
    # Layer selection
    SignalDefinition(
        'filtering_layer_changed',
        'comboBox_filtering_current_layer',
        'currentIndexChanged',
        '_on_filtering_layer_changed',
        SignalCategory.WIDGET,
        'filtering',
        1
    ),
    SignalDefinition(
        'exploring_layer_changed',
        'comboBox_exploring_current_layer',
        'currentIndexChanged',
        '_on_exploring_layer_changed',
        SignalCategory.WIDGET,
        'exploring',
        1
    ),
    
    # Action buttons
    SignalDefinition(
        'apply_filter_clicked',
        'pushButton_apply_filter',
        'clicked',
        '_on_apply_filter',
        SignalCategory.WIDGET,
        'actions',
        1
    ),
    SignalDefinition(
        'clear_filter_clicked',
        'pushButton_clear_filter',
        'clicked',
        '_on_clear_filter',
        SignalCategory.WIDGET,
        'actions',
        1
    ),
    SignalDefinition(
        'reset_all_clicked',
        'pushButton_reset_all',
        'clicked',
        '_on_reset_all',
        SignalCategory.WIDGET,
        'actions',
        1
    ),
    
    # Exploring groupboxes
    SignalDefinition(
        'groupbox_1_toggled',
        'groupBox_exploring_1',
        'toggled',
        '_on_groupbox_1_toggled',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    SignalDefinition(
        'groupbox_2_toggled',
        'groupBox_exploring_2',
        'toggled',
        '_on_groupbox_2_toggled',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    SignalDefinition(
        'groupbox_3_toggled',
        'groupBox_exploring_3',
        'toggled',
        '_on_groupbox_3_toggled',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    
    # Property combos
    SignalDefinition(
        'property_1_changed',
        'comboBox_exploring_1_property',
        'currentIndexChanged',
        '_on_property_1_changed',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    SignalDefinition(
        'property_2_changed',
        'comboBox_exploring_2_property',
        'currentIndexChanged',
        '_on_property_2_changed',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    SignalDefinition(
        'property_3_changed',
        'comboBox_exploring_3_property',
        'currentIndexChanged',
        '_on_property_3_changed',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    
    # Value combos
    SignalDefinition(
        'value_1_changed',
        'comboBox_exploring_1_value',
        'currentIndexChanged',
        '_on_value_1_changed',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    SignalDefinition(
        'value_2_changed',
        'comboBox_exploring_2_value',
        'currentIndexChanged',
        '_on_value_2_changed',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    SignalDefinition(
        'value_3_changed',
        'comboBox_exploring_3_value',
        'currentIndexChanged',
        '_on_value_3_changed',
        SignalCategory.WIDGET,
        'exploring',
        2
    ),
    
    # Buffer settings
    SignalDefinition(
        'buffer_value_changed',
        'doubleSpinBox_buffer_value',
        'valueChanged',
        '_on_buffer_value_changed',
        SignalCategory.WIDGET,
        'filtering',
        2
    ),
    SignalDefinition(
        'buffer_unit_changed',
        'comboBox_buffer_unit',
        'currentIndexChanged',
        '_on_buffer_unit_changed',
        SignalCategory.WIDGET,
        'filtering',
        2
    ),
    
    # Export buttons
    SignalDefinition(
        'export_gpkg_clicked',
        'pushButton_export_gpkg',
        'clicked',
        '_on_export_gpkg',
        SignalCategory.WIDGET,
        'exporting',
        2
    ),
    SignalDefinition(
        'export_shp_clicked',
        'pushButton_export_shp',
        'clicked',
        '_on_export_shp',
        SignalCategory.WIDGET,
        'exporting',
        2
    ),
]


# ─────────────────────────────────────────────────────────────────
# Signal Migration Helper
# ─────────────────────────────────────────────────────────────────

class SignalMigrationHelper:
    """
    Helper for migrating legacy signal connections to SignalManager.
    
    Provides:
    - Batch registration of predefined signals
    - Validation of migration completeness
    - Statistics on signal usage
    - Deprecation warnings for legacy patterns
    
    Usage:
        helper = SignalMigrationHelper(dockwidget, signal_manager)
        result = helper.migrate_widget_signals()
        helper.validate_migration()
    """
    
    def __init__(
        self,
        target: Any,
        signal_manager: Any,
        debug: bool = False
    ):
        """
        Initialize the migration helper.
        
        Args:
            target: Object containing widgets (dockwidget)
            signal_manager: SignalManager instance
            debug: Enable debug logging
        """
        self._target = target
        self._signal_manager = signal_manager
        self._debug = debug
        self._migrated_signals: Dict[str, str] = {}  # name -> conn_id
        self._failed_signals: List[str] = []
    
    def migrate_signals(
        self,
        signal_definitions: List[SignalDefinition]
    ) -> MigrationResult:
        """
        Migrate a list of signal definitions.
        
        Args:
            signal_definitions: List of SignalDefinition to migrate
        
        Returns:
            MigrationResult with details
        """
        result = MigrationResult(total_signals=len(signal_definitions))
        
        for sig_def in signal_definitions:
            try:
                success = self._migrate_single_signal(sig_def)
                if success:
                    result.migrated += 1
                else:
                    result.skipped += 1
            except Exception as e:
                result.failed += 1
                result.errors.append(f"{sig_def.name}: {str(e)}")
                logger.error(f"Failed to migrate {sig_def.name}: {e}")
        
        if self._debug:
            logger.debug(
                f"Migration complete: {result.migrated}/{result.total_signals} "
                f"({result.success_rate:.1f}%)"
            )
        
        return result
    
    def _migrate_single_signal(self, sig_def: SignalDefinition) -> bool:
        """
        Migrate a single signal definition.
        
        Args:
            sig_def: Signal definition to migrate
        
        Returns:
            True if migrated successfully
        """
        # Get widget
        widget = getattr(self._target, sig_def.widget_attr, None)
        if widget is None:
            if self._debug:
                logger.debug(f"Widget not found: {sig_def.widget_attr}")
            return False
        
        # Get handler
        handler = getattr(self._target, sig_def.handler_name, None)
        if handler is None:
            if self._debug:
                logger.debug(f"Handler not found: {sig_def.handler_name}")
            return False
        
        # Get signal
        signal = getattr(widget, sig_def.signal_name, None)
        if signal is None:
            if self._debug:
                logger.debug(f"Signal not found: {sig_def.signal_name}")
            return False
        
        # Register with SignalManager
        conn_id = self._signal_manager.connect(
            sender=widget,
            signal_name=sig_def.signal_name,
            receiver=handler,
            context=sig_def.context
        )
        
        self._migrated_signals[sig_def.name] = conn_id
        
        if self._debug:
            logger.debug(f"Migrated: {sig_def.name} -> {conn_id}")
        
        return True
    
    def migrate_widget_signals(self) -> MigrationResult:
        """
        Migrate all predefined widget signals.
        
        Returns:
            MigrationResult with details
        """
        return self.migrate_signals(DOCKWIDGET_WIDGET_SIGNALS)
    
    def validate_migration(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate that migration is complete.
        
        Returns:
            Tuple of (success, details)
        """
        expected = len(DOCKWIDGET_WIDGET_SIGNALS)
        actual = len(self._migrated_signals)
        
        stats = {
            'expected_signals': expected,
            'migrated_signals': actual,
            'failed_signals': len(self._failed_signals),
            'coverage': f"{(actual / expected * 100):.1f}%" if expected > 0 else "N/A",
            'signal_manager_count': self._signal_manager.get_connection_count()
        }
        
        success = actual >= expected * 0.8  # 80% threshold
        
        if success:
            logger.debug(f"Signal migration validated: {actual}/{expected}")
        else:
            logger.warning(f"Signal migration incomplete: {actual}/{expected}")
        
        return success, stats
    
    def get_migration_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the migration.
        
        Returns:
            Dictionary with migration statistics
        """
        return {
            'migrated': list(self._migrated_signals.keys()),
            'failed': self._failed_signals,
            'total_migrated': len(self._migrated_signals),
            'total_failed': len(self._failed_signals),
            'by_category': self._get_stats_by_category()
        }
    
    def _get_stats_by_category(self) -> Dict[str, int]:
        """Get migration stats grouped by category."""
        stats = {}
        for sig_def in DOCKWIDGET_WIDGET_SIGNALS:
            cat = sig_def.category.name
            if cat not in stats:
                stats[cat] = {'total': 0, 'migrated': 0}
            stats[cat]['total'] += 1
            if sig_def.name in self._migrated_signals:
                stats[cat]['migrated'] += 1
        return stats
    
    def disconnect_all_migrated(self) -> int:
        """
        Disconnect all migrated signals.
        
        Returns:
            Number of signals disconnected
        """
        count = 0
        for name, conn_id in list(self._migrated_signals.items()):
            if self._signal_manager.disconnect(conn_id):
                count += 1
                del self._migrated_signals[name]
        
        return count
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<SignalMigrationHelper: "
            f"{len(self._migrated_signals)} migrated, "
            f"{len(self._failed_signals)} failed>"
        )


# ─────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────

def get_all_signal_definitions() -> List[SignalDefinition]:
    """Get all predefined signal definitions."""
    return DOCKWIDGET_WIDGET_SIGNALS.copy()


def get_signals_by_category(
    category: SignalCategory
) -> List[SignalDefinition]:
    """Get signal definitions by category."""
    return [
        sig for sig in DOCKWIDGET_WIDGET_SIGNALS
        if sig.category == category
    ]


def get_signals_by_context(context: str) -> List[SignalDefinition]:
    """Get signal definitions by context."""
    return [
        sig for sig in DOCKWIDGET_WIDGET_SIGNALS
        if sig.context == context
    ]


def audit_signals_in_file(filepath: str) -> Dict[str, List[str]]:
    """
    Audit signal connections in a Python file.
    
    Searches for patterns like:
    - .connect(
    - .disconnect(
    
    Args:
        filepath: Path to Python file
    
    Returns:
        Dictionary with connect/disconnect patterns found
    """
    import re
    
    patterns = {
        'connect': re.compile(r'\.(\w+)\.connect\('),
        'disconnect': re.compile(r'\.(\w+)\.disconnect\('),
    }
    
    results = {'connect': [], 'disconnect': []}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                for pattern_name, pattern in patterns.items():
                    matches = pattern.findall(line)
                    for match in matches:
                        results[pattern_name].append({
                            'signal': match,
                            'line': line_no,
                            'code': line.strip()
                        })
    except Exception as e:
        logger.error(f"Error auditing {filepath}: {e}")
    
    return results
