# -*- coding: utf-8 -*-
"""
FilterMate Raster Templates GroupBox Widget.

EPIC-3: Raster-Vector Integration
GroupBox 5: 📋 WORKFLOW TEMPLATES

Provides UI for managing workflow templates within the raster exploring accordion.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFileDialog,
)
from qgis.PyQt.QtGui import QFont

# Try to import QgsCollapsibleGroupBox
try:
    from qgis.gui import QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = True
except ImportError:
    from qgis.PyQt.QtWidgets import QGroupBox as QgsCollapsibleGroupBox
    QGIS_GUI_AVAILABLE = False

if TYPE_CHECKING:
    from core.services.workflow_template_service import WorkflowTemplateService

logger = logging.getLogger('FilterMate.UI.RasterTemplatesGB')


class TemplateListItem(QListWidgetItem):
    """Custom list item for workflow templates."""
    
    def __init__(
        self,
        template_id: str,
        name: str,
        description: str = "",
        source_type: str = "raster"
    ):
        super().__init__()
        self.template_id = template_id
        self.template_name = name
        self.description = description
        self.source_type = source_type
        
        # Display with icon
        icon = "🏔️" if source_type == "raster" else "📍"
        self.setText(f"{icon} {name}")
        self.setToolTip(description if description else name)


class RasterTemplatesGroupBox(QWidget):
    """
    Collapsible GroupBox for workflow templates management.
    
    EPIC-3: GroupBox 5 - 📋 WORKFLOW TEMPLATES
    
    Features:
    - List of saved templates
    - Apply template button
    - Import/Export templates
    - Delete templates
    
    Signals:
        collapsed_changed: Emitted when collapse state changes
        activated: Emitted when this GroupBox becomes active (expanded)
        template_apply_requested: Emitted when user wants to apply a template
        save_current_requested: Emitted when user wants to save current config
    """
    
    # Signals
    collapsed_changed = pyqtSignal(bool)  # is_collapsed
    activated = pyqtSignal()  # This GroupBox became active
    template_apply_requested = pyqtSignal(str)  # template_id
    save_current_requested = pyqtSignal()  # Save current filter config as template
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the templates GroupBox.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._service: Optional['WorkflowTemplateService'] = None
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create collapsible groupbox
        self._groupbox = QgsCollapsibleGroupBox("📋 WORKFLOW TEMPLATES")
        self._groupbox.setObjectName("groupBox_raster_templates")
        self._groupbox.setCheckable(False)
        
        # Style for accordion look
        self._groupbox.setStyleSheet("""
            QgsCollapsibleGroupBox::title, QGroupBox::title {
                font-weight: bold;
                color: palette(text);
                padding: 4px 8px;
            }
            QgsCollapsibleGroupBox, QGroupBox {
                border: 1px solid palette(mid);
                border-radius: 4px;
                margin-top: 8px;
            }
        """)
        
        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)
        
        # Template list
        self._template_list = QListWidget()
        self._template_list.setMinimumHeight(80)
        self._template_list.setMaximumHeight(150)
        self._template_list.setAlternatingRowColors(True)
        content_layout.addWidget(self._template_list)
        
        # Action buttons row 1
        btn_layout1 = QHBoxLayout()
        
        self._apply_btn = QPushButton("▶️ Apply")
        self._apply_btn.setToolTip("Apply selected template")
        self._apply_btn.setEnabled(False)
        btn_layout1.addWidget(self._apply_btn)
        
        self._save_btn = QPushButton("💾 Save Current")
        self._save_btn.setToolTip("Save current filter as template")
        btn_layout1.addWidget(self._save_btn)
        
        content_layout.addLayout(btn_layout1)
        
        # Action buttons row 2
        btn_layout2 = QHBoxLayout()
        
        self._import_btn = QPushButton("📥 Import")
        self._import_btn.setToolTip("Import template from file")
        btn_layout2.addWidget(self._import_btn)
        
        self._export_btn = QPushButton("📤 Export")
        self._export_btn.setToolTip("Export selected template")
        self._export_btn.setEnabled(False)
        btn_layout2.addWidget(self._export_btn)
        
        self._delete_btn = QPushButton("🗑️")
        self._delete_btn.setToolTip("Delete selected template")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setMaximumWidth(40)
        btn_layout2.addWidget(self._delete_btn)
        
        content_layout.addLayout(btn_layout2)
        
        # Status label
        self._status_label = QLabel("No templates")
        self._status_label.setStyleSheet("color: palette(mid); font-size: 10px;")
        content_layout.addWidget(self._status_label)
        
        # Set content to groupbox
        self._groupbox.setLayout(QVBoxLayout())
        self._groupbox.layout().setContentsMargins(0, 0, 0, 0)
        self._groupbox.layout().addWidget(content)
        
        main_layout.addWidget(self._groupbox)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # GroupBox collapse
        if hasattr(self._groupbox, 'collapsedStateChanged'):
            self._groupbox.collapsedStateChanged.connect(
                self._on_collapse_changed
            )
        
        # Buttons
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._import_btn.clicked.connect(self._on_import_clicked)
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        
        # List selection
        self._template_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._template_list.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def _on_collapse_changed(self, collapsed: bool) -> None:
        """Handle collapse state change."""
        self.collapsed_changed.emit(collapsed)
        
        if not collapsed:
            self.activated.emit()
            # Refresh list when expanded
            self._refresh_template_list()
    
    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        has_selection = len(self._template_list.selectedItems()) > 0
        self._apply_btn.setEnabled(has_selection)
        self._export_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click to apply template."""
        if isinstance(item, TemplateListItem):
            self.template_apply_requested.emit(item.template_id)
    
    def _on_apply_clicked(self) -> None:
        """Handle apply button."""
        item = self._template_list.currentItem()
        if isinstance(item, TemplateListItem):
            self.template_apply_requested.emit(item.template_id)
    
    def _on_save_clicked(self) -> None:
        """Handle save current button."""
        self.save_current_requested.emit()
    
    def _on_import_clicked(self) -> None:
        """Handle import button."""
        if not self._service:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Workflow Template",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            template = self._service.import_template(file_path)
            if template:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Template '{template.name}' imported successfully."
                )
                self._refresh_template_list()
            else:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "Failed to import template. Check the file format."
                )
    
    def _on_export_clicked(self) -> None:
        """Handle export button."""
        item = self._template_list.currentItem()
        if not isinstance(item, TemplateListItem) or not self._service:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Workflow Template",
            f"{item.template_name}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            if self._service.export_template(item.template_id, file_path):
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Template exported to:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Failed to export template."
                )
    
    def _on_delete_clicked(self) -> None:
        """Handle delete button."""
        item = self._template_list.currentItem()
        if not isinstance(item, TemplateListItem) or not self._service:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Template",
            f"Delete template '{item.template_name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._service.delete_template(item.template_id)
            self._refresh_template_list()
    
    def _refresh_template_list(self) -> None:
        """Refresh the template list from service."""
        self._template_list.clear()
        
        if not self._service:
            self._status_label.setText("No service connected")
            return
        
        templates = self._service.get_all_templates()
        
        for template in templates:
            item = TemplateListItem(
                template_id=template.template_id,
                name=template.name,
                description=template.description,
                source_type=template.source_type
            )
            self._template_list.addItem(item)
        
        count = len(templates)
        self._status_label.setText(f"{count} template{'s' if count != 1 else ''}")
    
    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    
    def set_service(self, service: 'WorkflowTemplateService') -> None:
        """
        Set the workflow template service.
        
        Args:
            service: WorkflowTemplateService instance
        """
        self._service = service
        
        # Connect to service signals
        if self._service:
            self._service.templates_changed.connect(self._refresh_template_list)
        
        self._refresh_template_list()
    
    def set_collapsed(self, collapsed: bool) -> None:
        """
        Set the collapsed state of the groupbox.
        
        Args:
            collapsed: True to collapse, False to expand
        """
        if hasattr(self._groupbox, 'setCollapsed'):
            self._groupbox.setCollapsed(collapsed)
    
    def is_collapsed(self) -> bool:
        """
        Check if the groupbox is collapsed.
        
        Returns:
            True if collapsed
        """
        if hasattr(self._groupbox, 'isCollapsed'):
            return self._groupbox.isCollapsed()
        return False
    
    def refresh(self) -> None:
        """Refresh the template list."""
        self._refresh_template_list()
