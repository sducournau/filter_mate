#!/usr/bin/env python3
"""
Script de vérification post-correction des suffixes
Vérifie que tous les widgets attendus sont présents dans le fichier .py généré
"""
import re

# Widgets attendus (échantillon des plus importants)
expected_widgets = [
    'comboBox_filtering_current_layer',
    'toolBox_tabTools',
    'widget_filtering_keys',
    'widget_exporting_keys',
    'verticalLayout_filtering_keys',
    'verticalLayout_filtering_values',
    'verticalLayout_exporting_keys',
    'pushButton_checkable_filtering_auto_current_layer',
    'pushButton_checkable_filtering_layers_to_filter',
    'pushButton_checkable_exporting_layers',
    'comboBox_filtering_geometric_predicates',
    'comboBox_exporting_styles',
    'mQgsDoubleSpinBox_filtering_buffer_value',
    'lineEdit_exporting_output_folder',
    'checkBox_batch_exporting_zip',
]

# Lire le fichier .py généré
with open('filter_mate_dockwidget_base.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("Vérification des widgets dans filter_mate_dockwidget_base.py\n")
print("=" * 60)

# Vérifier chaque widget
all_found = True
for widget in expected_widgets:
    pattern = f'self.{widget}\\s*='
    if re.search(pattern, content):
        print(f"✓ {widget}")
    else:
        print(f"✗ MANQUANT: {widget}")
        all_found = False

print("=" * 60)

# Vérifier qu'il ne reste aucun suffixe "_3"
suffixes_found = re.findall(r'self\.\w+_3\s*=', content)
if suffixes_found:
    print(f"\n⚠️  ATTENTION: {len(suffixes_found)} suffixes '_3' trouvés:")
    for match in suffixes_found[:5]:  # Afficher les 5 premiers
        print(f"  - {match}")
else:
    print("\n✅ Aucun suffixe '_3' restant trouvé")

if all_found:
    print("\n✅ SUCCÈS: Tous les widgets attendus sont présents!")
    print("\n📋 Prochaines étapes:")
    print("  1. Recharger le plugin dans QGIS")
    print("  2. Vérifier que l'erreur a disparu")
    print("  3. Tester les fonctionnalités du plugin")
else:
    print("\n⚠️  ATTENTION: Certains widgets sont manquants!")
    print("Vérifiez le fichier .ui et recompilez si nécessaire")
