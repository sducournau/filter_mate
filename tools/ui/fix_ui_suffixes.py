#!/usr/bin/env python3
"""
Script pour supprimer les suffixes "_3" des noms de widgets dans le fichier .ui
Procède méthodiquement en remplaçant tous les noms de widgets, layouts et spacers.
"""
import re
import os

# Chemin du fichier .ui
ui_file = 'filter_mate_dockwidget_base.ui'

# Lire le contenu
with open(ui_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Liste des patterns à remplacer
# Format: (pattern regex, fonction de remplacement ou chaîne)
replacements = [
    # Layouts
    (r'name="verticalLayout_filtering_section_3"', 'name="verticalLayout_filtering_section"'),
    (r'name="verticalLayout_filtering_container_3"', 'name="verticalLayout_filtering_container"'),
    (r'name="verticalLayout_filtering_keys_container_3"', 'name="verticalLayout_filtering_keys_container"'),
    (r'name="verticalLayout_filtering_keys_3"', 'name="verticalLayout_filtering_keys"'),
    (r'name="verticalLayout_filtering_values_3"', 'name="verticalLayout_filtering_values"'),
    (r'name="horizontalLayout_filtering_main_3"', 'name="horizontalLayout_filtering_main"'),
    (r'name="horizontalLayout_filtering_content_3"', 'name="horizontalLayout_filtering_content"'),
    (r'name="horizontalLayout_filtering_values_search_3"', 'name="horizontalLayout_filtering_values_search"'),
    (r'name="horizontalLayout_filtering_values_buttons_3"', 'name="horizontalLayout_filtering_values_buttons"'),
    
    # Exporting layouts
    (r'name="verticalLayout_exporting_keys_container_3"', 'name="verticalLayout_exporting_keys_container"'),
    (r'name="verticalLayout_exporting_keys_3"', 'name="verticalLayout_exporting_keys"'),
    (r'name="verticalLayout_config_section_3"', 'name="verticalLayout_config_section"'),
    (r'name="verticalLayout_configurationPanel_3"', 'name="verticalLayout_configurationPanel"'),
    
    # Widgets
    (r'name="toolBox_tabTools_3"', 'name="toolBox_tabTools"'),
    (r'name="FILTERING_3"', 'name="FILTERING"'),
    (r'name="EXPORTING_3"', 'name="EXPORTING"'),
    (r'name="CONFIGURATION_3"', 'name="CONFIGURATION"'),
    (r'name="widget_filtering_keys_3"', 'name="widget_filtering_keys"'),
    (r'name="widget_exporting_keys_3"', 'name="widget_exporting_keys"'),
    
    # Filtering buttons
    (r'name="pushButton_checkable_filtering_auto_current_layer_3"', 'name="pushButton_checkable_filtering_auto_current_layer"'),
    (r'name="pushButton_checkable_filtering_layers_to_filter_3"', 'name="pushButton_checkable_filtering_layers_to_filter"'),
    (r'name="pushButton_checkable_filtering_current_layer_combine_operator_3"', 'name="pushButton_checkable_filtering_current_layer_combine_operator"'),
    (r'name="pushButton_checkable_filtering_geometric_predicates_3"', 'name="pushButton_checkable_filtering_geometric_predicates"'),
    (r'name="pushButton_checkable_filtering_buffer_value_3"', 'name="pushButton_checkable_filtering_buffer_value"'),
    (r'name="pushButton_checkable_filtering_buffer_type_3"', 'name="pushButton_checkable_filtering_buffer_type"'),
    
    # Filtering comboboxes
    (r'name="comboBox_filtering_current_layer_3"', 'name="comboBox_filtering_current_layer"'),
    (r'name="comboBox_filtering_source_layer_combine_operator_3"', 'name="comboBox_filtering_source_layer_combine_operator"'),
    (r'name="comboBox_filtering_other_layers_combine_operator_3"', 'name="comboBox_filtering_other_layers_combine_operator"'),
    (r'name="comboBox_filtering_geometric_predicates_3"', 'name="comboBox_filtering_geometric_predicates"'),
    (r'name="comboBox_filtering_buffer_type_3"', 'name="comboBox_filtering_buffer_type"'),
    
    # Filtering other widgets
    (r'name="mQgsDoubleSpinBox_filtering_buffer_value_3"', 'name="mQgsDoubleSpinBox_filtering_buffer_value"'),
    (r'name="mPropertyOverrideButton_filtering_buffer_value_property_3"', 'name="mPropertyOverrideButton_filtering_buffer_value_property"'),
    
    # Exporting buttons
    (r'name="pushButton_checkable_exporting_layers_3"', 'name="pushButton_checkable_exporting_layers"'),
    (r'name="pushButton_checkable_exporting_projection_3"', 'name="pushButton_checkable_exporting_projection"'),
    (r'name="pushButton_checkable_exporting_styles_3"', 'name="pushButton_checkable_exporting_styles"'),
    (r'name="pushButton_checkable_exporting_datatype_3"', 'name="pushButton_checkable_exporting_datatype"'),
    (r'name="pushButton_checkable_exporting_output_folder_3"', 'name="pushButton_checkable_exporting_output_folder"'),
    (r'name="pushButton_checkable_exporting_zip_3"', 'name="pushButton_checkable_exporting_zip"'),
    
    # Exporting comboboxes and widgets
    (r'name="mQgsProjectionSelectionWidget_exporting_projection_3"', 'name="mQgsProjectionSelectionWidget_exporting_projection"'),
    (r'name="comboBox_exporting_styles_3"', 'name="comboBox_exporting_styles"'),
    (r'name="comboBox_exporting_datatype_3"', 'name="comboBox_exporting_datatype"'),
    (r'name="checkBox_batch_exporting_output_folder_3"', 'name="checkBox_batch_exporting_output_folder"'),
    (r'name="lineEdit_exporting_output_folder_3"', 'name="lineEdit_exporting_output_folder"'),
    (r'name="checkBox_batch_exporting_zip_3"', 'name="checkBox_batch_exporting_zip"'),
    (r'name="lineEdit_exporting_zip_3"', 'name="lineEdit_exporting_zip"'),
    
    # Configuration
    (r'name="buttonBox_3"', 'name="buttonBox"'),
    
    # Spacers - Filtering
    (r'name="verticalSpacer_filtering_keys_field_top_3"', 'name="verticalSpacer_filtering_keys_field_top"'),
    (r'name="verticalSpacer_filtering_keys_field_middle1_3"', 'name="verticalSpacer_filtering_keys_field_middle1"'),
    (r'name="verticalSpacer_filtering_keys_field_middle2_3"', 'name="verticalSpacer_filtering_keys_field_middle2"'),
    (r'name="verticalSpacer_filtering_keys_field_middle3_3"', 'name="verticalSpacer_filtering_keys_field_middle3"'),
    (r'name="verticalSpacer_filtering_keys_field_bottom_3"', 'name="verticalSpacer_filtering_keys_field_bottom"'),
    (r'name="verticalSpacer_filtering_values_top_3"', 'name="verticalSpacer_filtering_values_top"'),
    (r'name="verticalSpacer_filtering_values_search_top_3"', 'name="verticalSpacer_filtering_values_search_top"'),
    (r'name="verticalSpacer_filtering_values_search_bottom_3"', 'name="verticalSpacer_filtering_values_search_bottom"'),
    (r'name="verticalSpacer_filtering_values_buttons_top_3"', 'name="verticalSpacer_filtering_values_buttons_top"'),
    (r'name="verticalSpacer_filtering_values_buttons_middle_3"', 'name="verticalSpacer_filtering_values_buttons_middle"'),
    (r'name="verticalSpacer_filtering_values_buttons_bottom1_3"', 'name="verticalSpacer_filtering_values_buttons_bottom1"'),
    (r'name="verticalSpacer_filtering_values_buttons_bottom2_3"', 'name="verticalSpacer_filtering_values_buttons_bottom2"'),
    
    # Spacers - Exporting
    (r'name="verticalSpacer_exporting_keys_field_top_3"', 'name="verticalSpacer_exporting_keys_field_top"'),
    (r'name="verticalSpacer_exporting_keys_field_middle1_3"', 'name="verticalSpacer_exporting_keys_field_middle1"'),
    (r'name="verticalSpacer_exporting_keys_field_middle2_3"', 'name="verticalSpacer_exporting_keys_field_middle2"'),
    (r'name="verticalSpacer_exporting_keys_field_middle3_3"', 'name="verticalSpacer_exporting_keys_field_middle3"'),
    (r'name="verticalSpacer_exporting_keys_field_bottom_3"', 'name="verticalSpacer_exporting_keys_field_bottom"'),
    (r'name="verticalSpacer_exporting_values_top_3"', 'name="verticalSpacer_exporting_values_top"'),
    (r'name="verticalSpacer_exporting_values_crs_top_3"', 'name="verticalSpacer_exporting_values_crs_top"'),
    (r'name="verticalSpacer_exporting_values_crs_middle_3"', 'name="verticalSpacer_exporting_values_crs_middle"'),
    (r'name="verticalSpacer_exporting_values_format_top_3"', 'name="verticalSpacer_exporting_values_format_top"'),
    (r'name="verticalSpacer_exporting_values_format_middle_3"', 'name="verticalSpacer_exporting_values_format_middle"'),
    (r'name="verticalSpacer_exporting_values_destination_top_3"', 'name="verticalSpacer_exporting_values_destination_top"'),
    (r'name="verticalSpacer_exporting_values_destination_bottom_3"', 'name="verticalSpacer_exporting_values_destination_bottom"'),
]

# Appliquer les remplacements
original_content = content
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Compter les changements
changes = sum(1 for i, (a, b) in enumerate(zip(original_content, content)) if a != b)
print(f"Nombre de caractères modifiés: {changes}")

# Afficher un échantillon des remplacements
print("\nÉchantillon des remplacements effectués:")
for pattern, replacement in replacements[:10]:
    if re.search(pattern, original_content):
        print(f"  ✓ {pattern} -> {replacement}")

# Écrire le fichier modifié
with open(ui_file, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ Fichier {ui_file} mis à jour avec succès!")
print("Prochaines étapes:")
print("  1. Recompiler le fichier .ui: python compile_ui.bat (ou sur Linux: sh compile_ui.sh)")
print("  2. Recharger le plugin dans QGIS")
