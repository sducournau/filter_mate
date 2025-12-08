#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de Contraste pour les Couleurs Harmonisées de FilterMate

Ce script vérifie que les ratios de contraste respectent les normes WCAG 2.1
pour les thèmes 'default' et 'light' après harmonisation.

Usage:
    python tests/test_color_contrast.py
"""

import json
import os
import sys
from typing import Dict, Tuple


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """
    Convertir une couleur hexadécimale en RGB.
    
    Args:
        hex_color: Couleur au format #RRGGBB
    
    Returns:
        tuple: (R, G, B) valeurs entre 0-255
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """
    Calculer la luminance relative d'une couleur RGB selon WCAG.
    
    Args:
        rgb: Tuple (R, G, B) valeurs 0-255
    
    Returns:
        float: Luminance relative (0.0 - 1.0)
    """
    # Normaliser 0-255 vers 0-1
    r, g, b = [x / 255.0 for x in rgb]
    
    # Appliquer la formule WCAG
    def adjust(c):
        if c <= 0.03928:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4
    
    r_adj = adjust(r)
    g_adj = adjust(g)
    b_adj = adjust(b)
    
    return 0.2126 * r_adj + 0.7152 * g_adj + 0.0722 * b_adj


def contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculer le ratio de contraste entre deux couleurs selon WCAG.
    
    Args:
        color1: Couleur hex #RRGGBB
        color2: Couleur hex #RRGGBB
    
    Returns:
        float: Ratio de contraste (1.0 - 21.0)
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    
    lum1 = relative_luminance(rgb1)
    lum2 = relative_luminance(rgb2)
    
    # Le plus clair doit être au numérateur
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    
    return (lighter + 0.05) / (darker + 0.05)


def evaluate_contrast(ratio: float, context: str = "text") -> Dict[str, any]:
    """
    Évaluer si un ratio de contraste respecte les normes WCAG.
    
    Args:
        ratio: Ratio de contraste
        context: Type de contenu ("text", "large_text", "ui")
    
    Returns:
        dict: Évaluation avec niveau WCAG et statut
    """
    result = {
        "ratio": round(ratio, 2),
        "wcag_aa": False,
        "wcag_aaa": False,
        "level": "FAIL"
    }
    
    if context == "text":
        # Texte normal : AA=4.5:1, AAA=7:1
        if ratio >= 7.0:
            result["wcag_aaa"] = True
            result["wcag_aa"] = True
            result["level"] = "AAA"
        elif ratio >= 4.5:
            result["wcag_aa"] = True
            result["level"] = "AA"
    elif context == "large_text":
        # Texte large : AA=3:1, AAA=4.5:1
        if ratio >= 4.5:
            result["wcag_aaa"] = True
            result["wcag_aa"] = True
            result["level"] = "AAA"
        elif ratio >= 3.0:
            result["wcag_aa"] = True
            result["level"] = "AA"
    elif context == "ui":
        # Éléments UI : AA=3:1
        if ratio >= 3.0:
            result["wcag_aa"] = True
            result["level"] = "AA"
    
    return result


def load_config_colors() -> Dict[str, Dict[str, list]]:
    """
    Charger les couleurs depuis config.json.
    
    Returns:
        dict: Thèmes avec leurs couleurs
    """
    # Chemin du fichier config.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_dir = os.path.dirname(script_dir)
    config_path = os.path.join(plugin_dir, 'config', 'config.json')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    themes = config["APP"]["DOCKWIDGET"]["COLORS"]["THEMES"]
    return themes


def test_theme(theme_name: str, colors: Dict[str, list]) -> Dict[str, Dict]:
    """
    Tester tous les contrastes d'un thème.
    
    Args:
        theme_name: Nom du thème
        colors: Dictionnaire de couleurs
    
    Returns:
        dict: Résultats des tests de contraste
    """
    bg = colors["BACKGROUND"]
    font = colors["FONT"]
    accent = colors["ACCENT"]
    
    results = {}
    
    # Texte primaire sur fond widget
    results["primary_text_widget"] = {
        "description": "Texte primaire / Fond widget",
        "colors": f"{font[0]} on {bg[1]}",
        "context": "text",
        **evaluate_contrast(contrast_ratio(font[0], bg[1]), "text")
    }
    
    # Texte secondaire sur fond widget
    results["secondary_text_widget"] = {
        "description": "Texte secondaire / Fond widget",
        "colors": f"{font[1]} on {bg[1]}",
        "context": "text",
        **evaluate_contrast(contrast_ratio(font[1], bg[1]), "text")
    }
    
    # Texte désactivé sur fond widget
    results["disabled_text_widget"] = {
        "description": "Texte désactivé / Fond widget",
        "colors": f"{font[2]} on {bg[1]}",
        "context": "large_text",
        **evaluate_contrast(contrast_ratio(font[2], bg[1]), "large_text")
    }
    
    # Bordure sur fond widget
    results["border_widget"] = {
        "description": "Bordure / Fond widget",
        "colors": f"{bg[2]} on {bg[1]}",
        "context": "ui",
        **evaluate_contrast(contrast_ratio(bg[2], bg[1]), "ui")
    }
    
    # Frame vs Widget
    results["frame_widget"] = {
        "description": "Frame / Fond widget",
        "colors": f"{bg[0]} on {bg[1]}",
        "context": "ui",
        **evaluate_contrast(contrast_ratio(bg[0], bg[1]), "ui")
    }
    
    # Accent primaire sur fond widget
    results["accent_widget"] = {
        "description": "Accent primaire / Fond widget",
        "colors": f"{accent['PRIMARY']} on {bg[1]}",
        "context": "ui",
        **evaluate_contrast(contrast_ratio(accent['PRIMARY'], bg[1]), "ui")
    }
    
    # Texte sur fond accent (boutons)
    results["text_on_accent"] = {
        "description": "Texte blanc / Fond accent",
        "colors": f"#FFFFFF on {accent['PRIMARY']}",
        "context": "text",
        **evaluate_contrast(contrast_ratio("#FFFFFF", accent['PRIMARY']), "text")
    }
    
    return results


def print_results(theme_name: str, results: Dict[str, Dict]):
    """
    Afficher les résultats des tests pour un thème.
    
    Args:
        theme_name: Nom du thème
        results: Résultats des tests
    """
    print(f"\n{'='*70}")
    print(f"  Thème : {theme_name.upper()}")
    print(f"{'='*70}")
    
    for test_key, result in results.items():
        status_icon = "✅" if result["wcag_aa"] else "❌"
        level = result["level"]
        ratio = result["ratio"]
        desc = result["description"]
        colors = result["colors"]
        
        print(f"\n{status_icon} {desc}")
        print(f"   Couleurs : {colors}")
        print(f"   Ratio    : {ratio}:1")
        print(f"   Niveau   : {level}")
        
        if result["wcag_aaa"]:
            print(f"   Norme    : WCAG AAA ⭐⭐⭐")
        elif result["wcag_aa"]:
            print(f"   Norme    : WCAG AA ⭐⭐")
        else:
            print(f"   Norme    : Non conforme ⚠️")


def print_summary(all_results: Dict[str, Dict[str, Dict]]):
    """
    Afficher un résumé global des tests.
    
    Args:
        all_results: Résultats de tous les thèmes
    """
    print(f"\n{'='*70}")
    print(f"  RÉSUMÉ GLOBAL")
    print(f"{'='*70}")
    
    for theme_name, results in all_results.items():
        total = len(results)
        passed_aa = sum(1 for r in results.values() if r["wcag_aa"])
        passed_aaa = sum(1 for r in results.values() if r["wcag_aaa"])
        
        print(f"\n📊 Thème '{theme_name}':")
        print(f"   Tests totaux   : {total}")
        print(f"   WCAG AA passés : {passed_aa}/{total} ({passed_aa/total*100:.0f}%)")
        print(f"   WCAG AAA passés: {passed_aaa}/{total} ({passed_aaa/total*100:.0f}%)")
        
        if passed_aa == total:
            print(f"   Statut         : ✅ Tous les tests passés!")
        else:
            print(f"   Statut         : ⚠️ {total - passed_aa} test(s) en échec")


def main():
    """
    Point d'entrée principal du script de test.
    """
    print("="*70)
    print("  TEST DE CONTRASTE DES COULEURS - FilterMate")
    print("  Harmonisation v2.2.2+ (2025-12-08)")
    print("="*70)
    
    try:
        # Charger les couleurs depuis config.json
        themes = load_config_colors()
        
        # Tester uniquement les thèmes harmonisés
        themes_to_test = ["default", "light"]
        all_results = {}
        
        for theme_name in themes_to_test:
            if theme_name in themes:
                results = test_theme(theme_name, themes[theme_name])
                all_results[theme_name] = results
                print_results(theme_name, results)
        
        # Afficher le résumé
        print_summary(all_results)
        
        print(f"\n{'='*70}")
        print("✅ Tests de contraste terminés avec succès!")
        print(f"{'='*70}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Erreur lors des tests : {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
