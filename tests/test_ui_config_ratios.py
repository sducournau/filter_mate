#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de validation des ratios UI COMPACT vs NORMAL

Vérifie que les ratios entre les modes compact et normal sont cohérents
et dans les plages attendues.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ui_config import UIConfig, DisplayProfile


def validate_ratio(compact_val, normal_val, expected_min, expected_max, name):
    """
    Valide qu'un ratio est dans la plage attendue.
    
    Args:
        compact_val: Valeur en mode compact
        normal_val: Valeur en mode normal
        expected_min: Ratio minimum attendu
        expected_max: Ratio maximum attendu
        name: Nom de la propriété testée
        
    Returns:
        tuple: (is_valid, ratio, message)
    """
    if compact_val == 0:
        return False, 0, f"❌ {name}: Valeur compact = 0"
    
    ratio = normal_val / compact_val
    
    if expected_min <= ratio <= expected_max:
        return True, ratio, f"✅ {name}: {compact_val} → {normal_val} (×{ratio:.2f})"
    else:
        return False, ratio, f"⚠️  {name}: {compact_val} → {normal_val} (×{ratio:.2f}) - Attendu: ×{expected_min}-{expected_max}"


def test_button_dimensions():
    """Test des dimensions de boutons."""
    print("\n=== BOUTONS ===")
    
    tests = [
        ("button.height", "button", "height", 1.4, 1.6),
        ("button.icon_size", "button", "icon_size", 1.4, 1.6),
        ("action_button.height", "action_button", "height", 1.4, 1.6),
        ("action_button.icon_size", "action_button", "icon_size", 1.4, 1.6),
        ("tool_button.height", "tool_button", "height", 1.4, 1.6),
        ("tool_button.icon_size", "tool_button", "icon_size", 1.4, 1.6),
    ]
    
    results = []
    for name, component, key, min_ratio, max_ratio in tests:
        compact = UIConfig.get_config(component, key)
        
        # Temporarily switch to normal
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal = UIConfig.get_config(component, key)
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        is_valid, ratio, msg = validate_ratio(compact, normal, min_ratio, max_ratio, name)
        print(msg)
        results.append(is_valid)
    
    return all(results)


def test_input_dimensions():
    """Test des dimensions de champs de saisie."""
    print("\n=== CHAMPS DE SAISIE ===")
    
    tests = [
        ("combobox.height", "combobox", "height", 1.4, 1.6),
        ("combobox.icon_size", "combobox", "icon_size", 1.4, 1.6),
        ("input.height", "input", "height", 1.4, 1.6),
    ]
    
    results = []
    for name, component, key, min_ratio, max_ratio in tests:
        compact = UIConfig.get_config(component, key)
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal = UIConfig.get_config(component, key)
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        is_valid, ratio, msg = validate_ratio(compact, normal, min_ratio, max_ratio, name)
        print(msg)
        results.append(is_valid)
    
    return all(results)


def test_layout_spacing():
    """Test des espacements de layout."""
    print("\n=== LAYOUTS & ESPACEMENTS ===")
    
    tests = [
        ("layout.spacing_main", "layout", "spacing_main", 1.9, 2.1),
        ("layout.spacing_section", "layout", "spacing_section", 1.9, 2.1),
        ("layout.spacing_buttons", "layout", "spacing_buttons", 1.9, 2.1),
        ("layout.margins_main", "layout", "margins_main", 1.9, 2.1),
        ("layout.margins_section", "layout", "margins_section", 1.9, 2.1),
    ]
    
    results = []
    for name, component, key, min_ratio, max_ratio in tests:
        compact = UIConfig.get_config(component, key)
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal = UIConfig.get_config(component, key)
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        is_valid, ratio, msg = validate_ratio(compact, normal, min_ratio, max_ratio, name)
        print(msg)
        results.append(is_valid)
    
    return all(results)


def test_frame_dimensions():
    """Test des dimensions de frames."""
    print("\n=== FRAMES & CONTENEURS ===")
    
    tests = [
        ("frame.min_height", "frame", "min_height", 1.8, 2.5),
        ("frame.padding", "frame", "padding", 3.0, 5.0),
        ("frame_exploring.min_height", "frame_exploring", "min_height", 1.1, 1.4),
        ("frame_filtering.min_height", "frame_filtering", "min_height", 1.1, 1.4),
    ]
    
    results = []
    for name, component, key, min_ratio, max_ratio in tests:
        compact = UIConfig.get_config(component, key)
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal = UIConfig.get_config(component, key)
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        is_valid, ratio, msg = validate_ratio(compact, normal, min_ratio, max_ratio, name)
        print(msg)
        results.append(is_valid)
    
    return all(results)


def test_widget_keys():
    """Test des dimensions de widget_keys."""
    print("\n=== WIDGET KEYS (Colonnes Boutons) ===")
    
    tests = [
        ("widget_keys.min_width", "widget_keys", "min_width", 1.2, 1.6),
        ("widget_keys.max_width", "widget_keys", "max_width", 1.8, 2.2),
    ]
    
    results = []
    for name, component, key, min_ratio, max_ratio in tests:
        compact = UIConfig.get_config(component, key)
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal = UIConfig.get_config(component, key)
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        is_valid, ratio, msg = validate_ratio(compact, normal, min_ratio, max_ratio, name)
        print(msg)
        results.append(is_valid)
    
    return all(results)


def test_text_dimensions():
    """Test des dimensions de texte."""
    print("\n=== TEXTE & TYPOGRAPHIE ===")
    
    tests = [
        ("label.font_size", "label", "font_size", 1.4, 1.6),
        ("label.line_height", "label", "line_height", 1.4, 1.6),
    ]
    
    results = []
    for name, component, key, min_ratio, max_ratio in tests:
        compact = UIConfig.get_config(component, key)
        
        UIConfig.set_profile(DisplayProfile.NORMAL)
        normal = UIConfig.get_config(component, key)
        UIConfig.set_profile(DisplayProfile.COMPACT)
        
        is_valid, ratio, msg = validate_ratio(compact, normal, min_ratio, max_ratio, name)
        print(msg)
        results.append(is_valid)
    
    return all(results)


def run_all_tests():
    """Execute tous les tests de validation."""
    print("=" * 60)
    print("VALIDATION DES RATIOS UI COMPACT vs NORMAL")
    print("=" * 60)
    
    # Ensure we start in compact mode
    UIConfig.set_profile(DisplayProfile.COMPACT)
    
    tests = [
        ("Boutons", test_button_dimensions),
        ("Champs de saisie", test_input_dimensions),
        ("Layouts & Espacements", test_layout_spacing),
        ("Frames & Conteneurs", test_frame_dimensions),
        ("Widget Keys", test_widget_keys),
        ("Texte & Typographie", test_text_dimensions),
    ]
    
    results = []
    for category, test_func in tests:
        result = test_func()
        results.append((category, result))
    
    # Summary
    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    
    all_passed = True
    for category, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHEC"
        print(f"{status}: {category}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 TOUS LES TESTS PASSÉS !")
        return 0
    else:
        print("\n⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        print("Vérifiez les valeurs dans modules/ui_config.py")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
