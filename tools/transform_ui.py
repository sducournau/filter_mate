#!/usr/bin/env python3
"""
Script to transform FilterMate UI:
- Replace QgsCollapsibleGroupBox with QToolBox tabs
- Create toolBox_exploring with EXPLORING_VECTOR and EXPLORING_RASTER pages
- Keep toolBox_tabTools with FILTERING, EXPORTING, CONFIGURATION
"""
import xml.etree.ElementTree as ET
import os
import copy
import re

# Get paths
script_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(script_dir)
filepath = os.path.join(plugin_dir, 'filter_mate_dockwidget_base.ui')

print(f"Processing: {filepath}")

# Parse with namespace handling
tree = ET.parse(filepath)
root = tree.getroot()

# Helper to find elements by attribute
def find_by_name(parent, name, tag='widget'):
    for elem in parent.iter(tag):
        name_elem = elem.find("property[@name='name']")
        if name_elem is not None and name_elem.text == name:
            return elem
        # Also check attribute directly
        if elem.get('name') == name:
            return elem
    return None

# Find scrollAreaWidgetContents
scroll_area_contents = None
for widget in root.iter('widget'):
    if widget.get('name') == 'scrollAreaWidgetContents':
        scroll_area_contents = widget
        break

if not scroll_area_contents:
    print("ERROR: scrollAreaWidgetContents not found")
    exit(1)

print("Found scrollAreaWidgetContents")

# Find mGroupBox_exploring_vector
vector_groupbox = None
for widget in root.iter('widget'):
    if widget.get('name') == 'mGroupBox_exploring_vector':
        vector_groupbox = widget
        break

# Find mGroupBox_exploring_raster  
raster_groupbox = None
for widget in root.iter('widget'):
    if widget.get('name') == 'mGroupBox_exploring_raster':
        raster_groupbox = widget
        break

# Find widget_exploring_keys
keys_widget = None
for widget in root.iter('widget'):
    if widget.get('name') == 'widget_exploring_keys':
        keys_widget = widget
        break

print(f"Found vector_groupbox: {vector_groupbox is not None}")
print(f"Found raster_groupbox: {raster_groupbox is not None}")
print(f"Found keys_widget: {keys_widget is not None}")

# Extract inner content from vector groupbox
vector_content = []
if vector_groupbox is not None:
    layout = vector_groupbox.find('layout')
    if layout is not None:
        for item in layout.findall('item'):
            for child in item:
                vector_content.append(copy.deepcopy(child))

# Extract inner content from raster groupbox
raster_content = []
if raster_groupbox is not None:
    layout = raster_groupbox.find('layout')
    if layout is not None:
        for item in layout.findall('item'):
            for child in item:
                raster_content.append(copy.deepcopy(child))

# Copy keys widget
keys_copy = copy.deepcopy(keys_widget) if keys_widget else None

print(f"Extracted {len(vector_content)} items from vector groupbox")
print(f"Extracted {len(raster_content)} items from raster groupbox")

# Create the new toolBox_exploring structure
toolbox_exploring = ET.Element('widget', {'class': 'QToolBox', 'name': 'toolBox_exploring'})

# Add properties to toolbox
props = [
    ('sizePolicy', {'hsizetype': 'Preferred', 'vsizetype': 'Expanding'}),
    ('minimumSize', {'width': '0', 'height': '100'}),
    ('font', {'family': 'Segoe UI Semibold', 'pointsize': '10', 'weight': '75', 'bold': 'true'}),
    ('cursor', 'PointingHandCursor'),
    ('frameShape', 'QFrame::Panel'),
    ('currentIndex', '0'),
]

# sizePolicy
prop_sp = ET.SubElement(toolbox_exploring, 'property', {'name': 'sizePolicy'})
sp = ET.SubElement(prop_sp, 'sizepolicy', {'hsizetype': 'Preferred', 'vsizetype': 'Expanding'})
ET.SubElement(sp, 'horstretch').text = '0'
ET.SubElement(sp, 'verstretch').text = '0'

# minimumSize
prop_ms = ET.SubElement(toolbox_exploring, 'property', {'name': 'minimumSize'})
size = ET.SubElement(prop_ms, 'size')
ET.SubElement(size, 'width').text = '0'
ET.SubElement(size, 'height').text = '100'

# font
prop_font = ET.SubElement(toolbox_exploring, 'property', {'name': 'font'})
font = ET.SubElement(prop_font, 'font')
ET.SubElement(font, 'family').text = 'Segoe UI Semibold'
ET.SubElement(font, 'pointsize').text = '10'
ET.SubElement(font, 'weight').text = '75'
ET.SubElement(font, 'bold').text = 'true'

# cursor
prop_cursor = ET.SubElement(toolbox_exploring, 'property', {'name': 'cursor'})
ET.SubElement(prop_cursor, 'cursorShape').text = 'PointingHandCursor'

# frameShape
prop_frame = ET.SubElement(toolbox_exploring, 'property', {'name': 'frameShape'})
ET.SubElement(prop_frame, 'enum').text = 'QFrame::Panel'

# currentIndex
prop_idx = ET.SubElement(toolbox_exploring, 'property', {'name': 'currentIndex'})
ET.SubElement(prop_idx, 'number').text = '0'

# Create EXPLORING_VECTOR page
page_vector = ET.SubElement(toolbox_exploring, 'widget', {'class': 'QWidget', 'name': 'EXPLORING_VECTOR'})
prop_geom = ET.SubElement(page_vector, 'property', {'name': 'geometry'})
rect = ET.SubElement(prop_geom, 'rect')
ET.SubElement(rect, 'x').text = '0'
ET.SubElement(rect, 'y').text = '0'
ET.SubElement(rect, 'width').text = '429'
ET.SubElement(rect, 'height').text = '280'

attr_icon = ET.SubElement(page_vector, 'attribute', {'name': 'icon'})
iconset = ET.SubElement(attr_icon, 'iconset')
ET.SubElement(iconset, 'normaloff').text = 'icons/mIconPointLayer.svg'
iconset.text = 'icons/mIconPointLayer.svg'

attr_label = ET.SubElement(page_vector, 'attribute', {'name': 'label'})
ET.SubElement(attr_label, 'string').text = 'EXPLORING VECTOR'

# Layout for vector page (horizontal to include keys)
layout_vec = ET.SubElement(page_vector, 'layout', {'class': 'QHBoxLayout', 'name': 'horizontalLayout_exploring_vector_toolbox'})
prop_spacing = ET.SubElement(layout_vec, 'property', {'name': 'spacing'})
ET.SubElement(prop_spacing, 'number').text = '4'
for margin in ['leftMargin', 'topMargin', 'rightMargin', 'bottomMargin']:
    prop_m = ET.SubElement(layout_vec, 'property', {'name': margin})
    ET.SubElement(prop_m, 'number').text = '2'

# Add keys widget
if keys_copy is not None:
    item_keys = ET.SubElement(layout_vec, 'item')
    item_keys.append(keys_copy)

# Add vertical layout for vector content
item_content = ET.SubElement(layout_vec, 'item')
vlayout = ET.SubElement(item_content, 'layout', {'class': 'QVBoxLayout', 'name': 'verticalLayout_exploring_vector_toolbox_content'})
prop_sp2 = ET.SubElement(vlayout, 'property', {'name': 'spacing'})
ET.SubElement(prop_sp2, 'number').text = '4'

# Add vector content items
for widget in vector_content:
    item = ET.SubElement(vlayout, 'item')
    item.append(widget)

# Add spacer at bottom
item_spacer = ET.SubElement(vlayout, 'item')
spacer = ET.SubElement(item_spacer, 'spacer', {'name': 'verticalSpacer_exploring_vector_bottom'})
prop_orient = ET.SubElement(spacer, 'property', {'name': 'orientation'})
ET.SubElement(prop_orient, 'enum').text = 'Qt::Vertical'
prop_hint = ET.SubElement(spacer, 'property', {'name': 'sizeHint', 'stdset': '0'})
size_hint = ET.SubElement(prop_hint, 'size')
ET.SubElement(size_hint, 'width').text = '20'
ET.SubElement(size_hint, 'height').text = '10'

# Create EXPLORING_RASTER page
page_raster = ET.SubElement(toolbox_exploring, 'widget', {'class': 'QWidget', 'name': 'EXPLORING_RASTER'})
prop_geom2 = ET.SubElement(page_raster, 'property', {'name': 'geometry'})
rect2 = ET.SubElement(prop_geom2, 'rect')
ET.SubElement(rect2, 'x').text = '0'
ET.SubElement(rect2, 'y').text = '0'
ET.SubElement(rect2, 'width').text = '429'
ET.SubElement(rect2, 'height').text = '200'

attr_icon2 = ET.SubElement(page_raster, 'attribute', {'name': 'icon'})
iconset2 = ET.SubElement(attr_icon2, 'iconset')
ET.SubElement(iconset2, 'normaloff').text = 'icons/mIconRaster.svg'
iconset2.text = 'icons/mIconRaster.svg'

attr_label2 = ET.SubElement(page_raster, 'attribute', {'name': 'label'})
ET.SubElement(attr_label2, 'string').text = 'EXPLORING RASTER'

# Layout for raster page
layout_raster = ET.SubElement(page_raster, 'layout', {'class': 'QVBoxLayout', 'name': 'verticalLayout_exploring_raster_toolbox'})
prop_spacing2 = ET.SubElement(layout_raster, 'property', {'name': 'spacing'})
ET.SubElement(prop_spacing2, 'number').text = '8'
for margin in ['leftMargin', 'topMargin', 'rightMargin', 'bottomMargin']:
    prop_m = ET.SubElement(layout_raster, 'property', {'name': margin})
    ET.SubElement(prop_m, 'number').text = '8'

# Add raster content items
for widget in raster_content:
    item = ET.SubElement(layout_raster, 'item')
    item.append(widget)

# Add spacer at bottom
item_spacer2 = ET.SubElement(layout_raster, 'item')
spacer2 = ET.SubElement(item_spacer2, 'spacer', {'name': 'verticalSpacer_exploring_raster_bottom'})
prop_orient2 = ET.SubElement(spacer2, 'property', {'name': 'orientation'})
ET.SubElement(prop_orient2, 'enum').text = 'Qt::Vertical'
prop_hint2 = ET.SubElement(spacer2, 'property', {'name': 'sizeHint', 'stdset': '0'})
size_hint2 = ET.SubElement(prop_hint2, 'size')
ET.SubElement(size_hint2, 'width').text = '20'
ET.SubElement(size_hint2, 'height').text = '10'

# Now, replace scrollAreaWidgetContents content
# Clear existing content
for child in list(scroll_area_contents):
    scroll_area_contents.remove(child)

# Set new geometry
prop_geom3 = ET.SubElement(scroll_area_contents, 'property', {'name': 'geometry'})
rect3 = ET.SubElement(prop_geom3, 'rect')
ET.SubElement(rect3, 'x').text = '0'
ET.SubElement(rect3, 'y').text = '0'
ET.SubElement(rect3, 'width').text = '433'
ET.SubElement(rect3, 'height').text = '300'

# Create main layout with toolbox
main_layout = ET.SubElement(scroll_area_contents, 'layout', {'class': 'QVBoxLayout', 'name': 'verticalLayout_exploring_main'})
prop_sp3 = ET.SubElement(main_layout, 'property', {'name': 'spacing'})
ET.SubElement(prop_sp3, 'number').text = '0'
for margin in ['leftMargin', 'topMargin', 'rightMargin', 'bottomMargin']:
    prop_m = ET.SubElement(main_layout, 'property', {'name': margin})
    ET.SubElement(prop_m, 'number').text = '0'

# Add toolbox to layout
item_toolbox = ET.SubElement(main_layout, 'item')
item_toolbox.append(toolbox_exploring)

# Save backup
backup_path = filepath + '.backup_before_toolbox'
with open(filepath, 'r', encoding='utf-8') as f:
    original_content = f.read()
with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(original_content)
print(f"Backup saved to: {backup_path}")

# Format and write output
def indent(elem, level=0):
    i = "\n" + level * " "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + " "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent(child, level+1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

indent(root)
tree.write(filepath, encoding='unicode', xml_declaration=True)

# Add DOCTYPE that Qt Designer expects
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix XML declaration and add DOCTYPE
content = content.replace("<?xml version='1.0' encoding='unicode'?>", 
                          '<?xml version="1.0" encoding="UTF-8"?>')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nTransformation complete!")
print("Created two toolboxes:")
print("  1. toolBox_exploring: EXPLORING_VECTOR, EXPLORING_RASTER")
print("  2. toolBox_tabTools: FILTERING, EXPORTING, CONFIGURATION")

# Validate
try:
    ET.parse(filepath)
    print("\n✓ XML validation passed!")
except Exception as e:
    print(f"\n✗ XML validation failed: {e}")
    with open(backup_path, 'r', encoding='utf-8') as f:
        original = f.read()
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(original)
    print("Backup restored due to validation error")
