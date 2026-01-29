"""
EPIC-3: Workflow Templates Widget.

UI widget for managing workflow templates - save, load, and apply filter workflows.
"""
import logging
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QFont, QCursor
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
    QMenu, QAction, QFileDialog, QDialog, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QGroupBox, QSizePolicy
)

logger = logging.getLogger('FilterMate.UI.WorkflowTemplatesWidget')


class WorkflowTemplateItem(QListWidgetItem):
    """Custom list item for workflow templates."""
    
    def __init__(
        self,
        template_id: str,
        name: str,
        description: str = "",
        source_type: str = "raster",
        parent: Optional[QListWidget] = None
    ):
        super().__init__(parent)
        self.template_id = template_id
        self.template_name = name
        self.description = description
        self.source_type = source_type
        
        # Display with icon
        icon = "🏔️" if source_type == "raster" else "📍"
        self.setText(f"{icon} {name}")
        self.setToolTip(description if description else name)


class SaveTemplateDialog(QDialog):
    """Dialog for saving a new workflow template."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Save Workflow Template")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Form
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter template name...")
        form_layout.addRow("Name:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Optional description...")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_edit)
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Tags (comma-separated)...")
        form_layout.addRow("Tags:", self.tags_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self._save_btn = QPushButton("💾 Save")
        self._save_btn.clicked.connect(self.accept)
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def get_values(self) -> Dict:
        """Get entered values."""
        tags_text = self.tags_edit.text().strip()
        tags = [t.strip() for t in tags_text.split(',')] if tags_text else []
        
        return {
            'name': self.name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'tags': tags
        }


class LoadTemplateDialog(QDialog):
    """Dialog for selecting and loading a workflow template."""
    
    def __init__(
        self,
        templates: List[Dict],
        parent: Optional[QWidget] = None
    ):
        """
        Initialize dialog with available templates.
        
        Args:
            templates: List of template dicts with 'template_id', 'name', 'description', etc.
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Load Workflow Template")
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)
        
        self._templates = templates
        self._selected_template_id: Optional[str] = None
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "Select a template to apply to your current project.\n"
            "Templates will attempt to match layers by name patterns."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Template list
        self._template_list = QListWidget()
        self._template_list.setAlternatingRowColors(True)
        self._template_list.itemDoubleClicked.connect(self.accept)
        self._template_list.currentItemChanged.connect(self._on_selection_changed)
        
        for tmpl in templates:
            item = WorkflowTemplateItem(
                template_id=tmpl.get('template_id', ''),
                name=tmpl.get('name', 'Untitled'),
                description=tmpl.get('description', ''),
                source_type=tmpl.get('source_type', 'raster')
            )
            self._template_list.addItem(item)
        
        layout.addWidget(self._template_list, 1)
        
        # Details group
        details_group = QGroupBox("Template Details")
        details_layout = QVBoxLayout(details_group)
        
        self._details_label = QLabel("Select a template to view details")
        self._details_label.setWordWrap(True)
        self._details_label.setStyleSheet("color: palette(mid);")
        details_layout.addWidget(self._details_label)
        
        layout.addWidget(details_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self._apply_btn = QPushButton("▶️ Apply Template")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self.accept)
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self._apply_btn)
        btn_layout.addWidget(self._cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # Select first item if available
        if self._template_list.count() > 0:
            self._template_list.setCurrentRow(0)
    
    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle template selection change."""
        if current and isinstance(current, WorkflowTemplateItem):
            self._selected_template_id = current.template_id
            self._apply_btn.setEnabled(True)
            
            # Find template details
            for tmpl in self._templates:
                if tmpl.get('template_id') == current.template_id:
                    # Build details text
                    details = []
                    if tmpl.get('description'):
                        details.append(tmpl['description'])
                    details.append(f"\n📂 Source: {tmpl.get('source_type', 'raster').title()}")
                    if tmpl.get('source_name_pattern'):
                        details.append(f"📝 Pattern: {tmpl['source_name_pattern']}")
                    if tmpl.get('tags'):
                        details.append(f"🏷️ Tags: {', '.join(tmpl['tags'])}")
                    if tmpl.get('raster_rules'):
                        rules = tmpl['raster_rules']
                        if rules:
                            rule = rules[0]
                            details.append(
                                f"📊 Value Range: {rule.get('min_value', '?')} - {rule.get('max_value', '?')}"
                            )
                    
                    self._details_label.setText('\n'.join(details))
                    self._details_label.setStyleSheet("")
                    break
        else:
            self._selected_template_id = None
            self._apply_btn.setEnabled(False)
            self._details_label.setText("Select a template to view details")
            self._details_label.setStyleSheet("color: palette(mid);")
    
    @property
    def selected_template_id(self) -> Optional[str]:
        """Get the selected template ID."""
        return self._selected_template_id


class WorkflowTemplatesWidget(QWidget):
    """
    Widget for managing workflow templates.
    
    Provides UI to:
    - View saved templates
    - Save current filter configuration as template
    - Load and apply templates
    - Import/export templates
    - Delete templates
    
    Signals:
        template_selected: When user selects a template
        template_apply_requested: When user wants to apply a template
        save_requested: When user wants to save current config as template
    """
    
    # Signals
    template_selected = pyqtSignal(str)  # template_id
    template_apply_requested = pyqtSignal(str)  # template_id
    save_requested = pyqtSignal(str, str, list)  # name, description, tags
    
    def __init__(
        self,
        service: Optional['WorkflowTemplateService'] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the widget.
        
        Args:
            service: WorkflowTemplateService instance
            parent: Parent widget
        """
        super().__init__(parent)
        self._service = service
        self._setup_ui()
        self._setup_connections()
        
        # Load templates if service available
        if self._service:
            self._refresh_template_list()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Header
        header_layout = QHBoxLayout()
        
        header_label = QLabel("📋 Workflow Templates")
        header_font = QFont()
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        # Save current button
        self._save_btn = QPushButton("💾 Save Current")
        self._save_btn.setToolTip("Save current filter configuration as template")
        self._save_btn.setMaximumWidth(110)
        header_layout.addWidget(self._save_btn)
        
        layout.addLayout(header_layout)
        
        # Template list
        self._template_list = QListWidget()
        self._template_list.setMinimumHeight(100)
        self._template_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._template_list.setAlternatingRowColors(True)
        layout.addWidget(self._template_list, 1)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self._apply_btn = QPushButton("▶️ Apply")
        self._apply_btn.setToolTip("Apply selected template")
        self._apply_btn.setEnabled(False)
        btn_layout.addWidget(self._apply_btn)
        
        self._import_btn = QPushButton("📥 Import")
        self._import_btn.setToolTip("Import template from file")
        btn_layout.addWidget(self._import_btn)
        
        self._export_btn = QPushButton("📤 Export")
        self._export_btn.setToolTip("Export selected template")
        self._export_btn.setEnabled(False)
        btn_layout.addWidget(self._export_btn)
        
        self._delete_btn = QPushButton("🗑️")
        self._delete_btn.setToolTip("Delete selected template")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setMaximumWidth(32)
        btn_layout.addWidget(self._delete_btn)
        
        layout.addLayout(btn_layout)
        
        # Status label
        self._status_label = QLabel("No templates")
        self._status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._status_label)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        self._import_btn.clicked.connect(self._on_import_clicked)
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        
        self._template_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._template_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._template_list.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect to service signals if available
        if self._service:
            self._service.templates_changed.connect(self._refresh_template_list)
    
    def set_service(self, service: 'WorkflowTemplateService') -> None:
        """Set the workflow template service."""
        self._service = service
        self._service.templates_changed.connect(self._refresh_template_list)
        self._refresh_template_list()
    
    def _refresh_template_list(self) -> None:
        """Refresh the template list from service."""
        self._template_list.clear()
        
        if not self._service:
            self._status_label.setText("No service connected")
            return
        
        templates = self._service.get_all_templates()
        
        for template in templates:
            item = WorkflowTemplateItem(
                template_id=template.template_id,
                name=template.name,
                description=template.description,
                source_type=template.source_type,
                parent=self._template_list
            )
        
        count = len(templates)
        self._status_label.setText(f"{count} template{'s' if count != 1 else ''}")
    
    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        has_selection = len(self._template_list.selectedItems()) > 0
        self._apply_btn.setEnabled(has_selection)
        self._export_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        
        if has_selection:
            item = self._template_list.currentItem()
            if isinstance(item, WorkflowTemplateItem):
                self.template_selected.emit(item.template_id)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click to apply template."""
        if isinstance(item, WorkflowTemplateItem):
            self._apply_template(item.template_id)
    
    def _on_save_clicked(self) -> None:
        """Handle save current button."""
        dialog = SaveTemplateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            if values['name']:
                self.save_requested.emit(
                    values['name'],
                    values['description'],
                    values['tags']
                )
    
    def _on_apply_clicked(self) -> None:
        """Handle apply button."""
        item = self._template_list.currentItem()
        if isinstance(item, WorkflowTemplateItem):
            self._apply_template(item.template_id)
    
    def _apply_template(self, template_id: str) -> None:
        """Apply a template."""
        if not self._service:
            return
        
        # Check for unmatched layers
        match_result = self._service.match_template_to_project(template_id)
        if match_result and match_result.warnings:
            warning_text = "\n".join(match_result.warnings)
            reply = QMessageBox.question(
                self,
                "Template Match Warnings",
                f"Some layers were not found:\n\n{warning_text}\n\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.No:
                return
        
        self.template_apply_requested.emit(template_id)
    
    def _on_import_clicked(self) -> None:
        """Handle import button."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Workflow Template",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path and self._service:
            template = self._service.import_template(file_path)
            if template:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Template '{template.name}' imported successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "Failed to import template. Check the file format."
                )
    
    def _on_export_clicked(self) -> None:
        """Handle export button."""
        item = self._template_list.currentItem()
        if not isinstance(item, WorkflowTemplateItem) or not self._service:
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
        if not isinstance(item, WorkflowTemplateItem) or not self._service:
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
    
    def _show_context_menu(self, position) -> None:
        """Show context menu for template list."""
        item = self._template_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        apply_action = QAction("▶️ Apply", self)
        apply_action.triggered.connect(self._on_apply_clicked)
        menu.addAction(apply_action)
        
        menu.addSeparator()
        
        export_action = QAction("📤 Export", self)
        export_action.triggered.connect(self._on_export_clicked)
        menu.addAction(export_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ Delete", self)
        delete_action.triggered.connect(self._on_delete_clicked)
        menu.addAction(delete_action)
        
        menu.exec_(self._template_list.mapToGlobal(position))
