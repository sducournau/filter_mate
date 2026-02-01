# FilteredLayerListItem - Usage Guide

**Created:** 2026-02-03 (Sprint 1, Day 3)  
**Author:** Sally (UX Designer)

---

## Overview

`FilteredLayerListItem` is a custom Qt widget for displaying filtered raster layers in the Active Filtered Layers list. It provides integrated controls for visibility, opacity, and deletion.

## Features

- **Visibility Toggle**: Checkbox + eye icon indicator
- **Opacity Control**: Slider with real-time value display (0-100%)
- **Delete Action**: Button to remove layer
- **Layer Info**: Name display with truncation for long names
- **Signal Emission**: All actions emit signals for controller handling

## Usage in Controller

### Basic Usage

```python
from qgis.PyQt.QtWidgets import QListWidget, QListWidgetItem
from ui.widgets import FilteredLayerListItem

class RasterFilterController:
    def __init__(self, dockwidget):
        self.dockwidget = dockwidget
        self.list_widget = dockwidget.listWidget_active_filtered_layers
    
    def add_filtered_layer_to_list(self, layer):
        """
        Add a new filtered layer to the active layers list.
        
        Args:
            layer: QgsMapLayer - The filtered raster layer
        """
        # Create list item
        item = QListWidgetItem(self.list_widget)
        item.setSizeHint(QSize(0, 60))  # Fixed height
        
        # Create custom widget
        widget = FilteredLayerListItem(layer)
        
        # Connect signals
        widget.visibility_toggled.connect(self.on_visibility_toggled)
        widget.opacity_changed.connect(self.on_opacity_changed)
        widget.delete_clicked.connect(self.on_delete_clicked)
        
        # Set widget as list item
        self.list_widget.setItemWidget(item, widget)
        
        # Store reference for later access
        # Option 1: Store in dict
        self.layer_widgets[layer.id()] = (item, widget)
        
        # Option 2: Store in item data
        item.setData(Qt.UserRole, layer.id())
```

### Signal Handlers

```python
def on_visibility_toggled(self, layer_id, is_visible):
    """
    Handle visibility checkbox toggle from list item.
    
    Args:
        layer_id: str - ID of the layer
        is_visible: bool - New visibility state
    """
    # Update QGIS layer tree
    layer_tree_root = QgsProject.instance().layerTreeRoot()
    layer_tree_layer = layer_tree_root.findLayer(layer_id)
    
    if layer_tree_layer:
        # Temporarily disconnect to prevent signal loop
        layer_tree_root.visibilityChanged.disconnect(
            self.on_layer_tree_visibility_changed
        )
        
        try:
            layer_tree_layer.setItemVisibilityChecked(is_visible)
        finally:
            layer_tree_root.visibilityChanged.connect(
                self.on_layer_tree_visibility_changed
            )
    
    # Trigger canvas repaint
    layer = QgsProject.instance().mapLayer(layer_id)
    if layer:
        layer.triggerRepaint()


def on_opacity_changed(self, layer_id, opacity_percent):
    """
    Handle opacity slider change from list item.
    
    Args:
        layer_id: str - ID of the layer
        opacity_percent: int - New opacity value (0-100)
    """
    # Update layer opacity
    layer = QgsProject.instance().mapLayer(layer_id)
    if layer:
        layer.setOpacity(opacity_percent / 100.0)
        layer.triggerRepaint()


def on_delete_clicked(self, layer_id):
    """
    Handle delete button click from list item.
    
    Args:
        layer_id: str - ID of the layer to remove
    """
    # Show confirmation dialog
    from qgis.PyQt.QtWidgets import QMessageBox
    
    layer = QgsProject.instance().mapLayer(layer_id)
    if not layer:
        return
    
    reply = QMessageBox.question(
        None,
        "FilterMate",
        f"Remove filtered layer '{layer.name()}'?",
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply == QMessageBox.Yes:
        # Remove from project
        QgsProject.instance().removeMapLayer(layer_id)
        
        # Remove from list widget
        self.remove_layer_from_list(layer_id)


def remove_layer_from_list(self, layer_id):
    """
    Remove layer from active layers list widget.
    
    Args:
        layer_id: str - ID of layer to remove
    """
    # Find item in list
    for i in range(self.list_widget.count()):
        item = self.list_widget.item(i)
        widget = self.list_widget.itemWidget(item)
        
        if widget and widget.layer_id == layer_id:
            # Remove item from list
            self.list_widget.takeItem(i)
            break
    
    # Clean up reference
    if layer_id in self.layer_widgets:
        del self.layer_widgets[layer_id]
```

### External Sync (from QGIS Layer Tree)

```python
def on_layer_tree_visibility_changed(self, node):
    """
    Handle visibility change from QGIS layer tree.
    Sync to FilterMate UI.
    
    Args:
        node: QgsLayerTreeNode that changed
    """
    if node.nodeType() != QgsLayerTreeNode.NodeLayer:
        return
    
    layer_id = node.layerId()
    
    # Check if it's a FilterMate temp layer
    if layer_id not in self.layer_widgets:
        return
    
    # Get new visibility state
    is_visible = node.isVisible()
    
    # Update widget checkbox (without triggering signal)
    item, widget = self.layer_widgets[layer_id]
    widget.set_visibility_checked(is_visible)
```

---

## Widget API Reference

### Constructor

```python
FilteredLayerListItem(layer, parent=None)
```

**Args:**
- `layer` (QgsMapLayer): The raster layer this item represents
- `parent` (QWidget, optional): Parent widget

### Signals

```python
visibility_toggled(str, bool)
```
Emitted when visibility checkbox is toggled.
- **Args:** `layer_id` (str), `is_visible` (bool)

```python
opacity_changed(str, int)
```
Emitted when opacity slider is moved.
- **Args:** `layer_id` (str), `opacity_percent` (int, 0-100)

```python
delete_clicked(str)
```
Emitted when delete button is clicked.
- **Args:** `layer_id` (str)

### Methods

```python
update_from_layer()
```
Update widget state from the actual QGIS layer.

```python
set_visibility_checked(checked: bool)
```
Set visibility checkbox state programmatically (for external sync).

```python
set_opacity_value(value: int)
```
Set opacity slider value programmatically (for external sync).

---

## Styling

The widget uses inline styles for the delete button:
- Normal: Transparent background, gray text
- Hover: Red text (#d32f2f), light red background (#ffebee)

Eye icon changes color based on visibility:
- Visible: Blue (#1976d2)
- Hidden: Gray (#bdbdbd)

---

## Layout Structure

```
┌────────────────────────────────────────────────────┐
│ [☑] [👁] Layer Name                           [×] │ ← Row 1 (25px height)
│     Opacity: ████████░░░ 70%                      │ ← Row 2 (25px height)
└────────────────────────────────────────────────────┘
    5px  20px  Flexible                         20px
   checkbox eye  layer name                    delete
   
Total height: 60px (5px top + 25px row1 + 3px gap + 25px row2 + 5px bottom)
```

---

## Example: Full Integration

```python
class RasterFilterController:
    def __init__(self, dockwidget, app):
        self.dockwidget = dockwidget
        self.app = app
        self.layer_widgets = {}  # layer_id → (item, widget)
        
        # Setup layer tree sync
        self.setup_layer_tree_sync()
    
    def setup_layer_tree_sync(self):
        """Setup bidirectional sync with QGIS layer tree."""
        layer_tree_root = QgsProject.instance().layerTreeRoot()
        layer_tree_root.visibilityChanged.connect(
            self.on_layer_tree_visibility_changed
        )
    
    def on_filter_task_completed(self, result_layer):
        """
        Called when filter task completes.
        Add new layer to active list.
        
        Args:
            result_layer: QgsMapLayer - Newly created filtered layer
        """
        # Add to project (already done in task.finished())
        # Add to UI list
        self.add_filtered_layer_to_list(result_layer)
    
    def add_filtered_layer_to_list(self, layer):
        """Add layer to active filtered layers list."""
        list_widget = self.dockwidget.listWidget_active_filtered_layers
        
        # Create list item
        item = QListWidgetItem(list_widget)
        item.setSizeHint(QSize(0, 60))
        
        # Create custom widget
        widget = FilteredLayerListItem(layer)
        widget.visibility_toggled.connect(self.on_visibility_toggled)
        widget.opacity_changed.connect(self.on_opacity_changed)
        widget.delete_clicked.connect(self.on_delete_clicked)
        
        # Set widget
        list_widget.setItemWidget(item, widget)
        
        # Store reference
        self.layer_widgets[layer.id()] = (item, widget)
    
    def on_visibility_toggled(self, layer_id, is_visible):
        """Handle visibility toggle from widget."""
        # Update QGIS layer tree
        layer_tree_root = QgsProject.instance().layerTreeRoot()
        layer_tree_layer = layer_tree_root.findLayer(layer_id)
        
        if layer_tree_layer:
            layer_tree_layer.setItemVisibilityChecked(is_visible)
        
        # Trigger repaint
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            layer.triggerRepaint()
    
    def on_opacity_changed(self, layer_id, opacity_percent):
        """Handle opacity change from widget."""
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            layer.setOpacity(opacity_percent / 100.0)
            layer.triggerRepaint()
    
    def on_delete_clicked(self, layer_id):
        """Handle delete click from widget."""
        from qgis.PyQt.QtWidgets import QMessageBox
        
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer:
            return
        
        reply = QMessageBox.question(
            None,
            "FilterMate",
            f"Remove '{layer.name()}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            QgsProject.instance().removeMapLayer(layer_id)
            self.remove_layer_from_list(layer_id)
    
    def remove_layer_from_list(self, layer_id):
        """Remove layer from list widget."""
        list_widget = self.dockwidget.listWidget_active_filtered_layers
        
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            
            if widget and widget.layer_id == layer_id:
                list_widget.takeItem(i)
                break
        
        if layer_id in self.layer_widgets:
            del self.layer_widgets[layer_id]
    
    def on_layer_tree_visibility_changed(self, node):
        """Sync visibility from QGIS TOC to FilterMate UI."""
        if node.nodeType() != QgsLayerTreeNode.NodeLayer:
            return
        
        layer_id = node.layerId()
        if layer_id not in self.layer_widgets:
            return
        
        is_visible = node.isVisible()
        item, widget = self.layer_widgets[layer_id]
        widget.set_visibility_checked(is_visible)
```

---

## Testing

```python
# Manual test in QGIS Python console
from qgis.core import QgsProject
from ui.widgets import FilteredLayerListItem
from qgis.PyQt.QtWidgets import QListWidget, QListWidgetItem, QDialog, QVBoxLayout
from qgis.PyQt.QtCore import QSize

# Get a raster layer
layer = iface.activeLayer()

# Create test dialog
dialog = QDialog()
dialog.setWindowTitle("Test FilteredLayerListItem")
dialog.resize(400, 200)

layout = QVBoxLayout(dialog)

# Create list widget
list_widget = QListWidget()
layout.addWidget(list_widget)

# Create list item
item = QListWidgetItem(list_widget)
item.setSizeHint(QSize(0, 60))

# Create custom widget
widget = FilteredLayerListItem(layer)

# Connect signals for testing
widget.visibility_toggled.connect(
    lambda lid, vis: print(f"Visibility: {lid} → {vis}")
)
widget.opacity_changed.connect(
    lambda lid, op: print(f"Opacity: {lid} → {op}%")
)
widget.delete_clicked.connect(
    lambda lid: print(f"Delete: {lid}")
)

# Set widget
list_widget.setItemWidget(item, widget)

# Show dialog
dialog.show()
```

---

**End of Usage Guide**

For controller implementation, see `ui/controllers/raster_filter_controller.py` (to be created in Sprint 2).
