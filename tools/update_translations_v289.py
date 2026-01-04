#!/usr/bin/env python3
"""
Update translation files with new strings from v2.8.9

This script adds new translatable strings to all language .ts files.
New strings are added with English fallback text.

Usage:
    python3 tools/update_translations_v289.py [--translate-fr]
"""

import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
I18N_DIR = os.path.join(PLUGIN_DIR, 'i18n')

# New strings for v2.8.9 - MV Management & Simplified Popup
# Format: "source": {"fr": "translation", "de": "translation", ...}
NEW_STRINGS_V289 = {
    # ========================================
    # MV Status Widget
    # ========================================
    "MV Status: Checking...": {
        "fr": "État MV : Vérification...",
        "de": "MV-Status: Prüfe...",
        "es": "Estado MV: Verificando...",
        "it": "Stato MV: Verifica...",
        "pt": "Estado MV: Verificando...",
    },
    "MV Status: Error": {
        "fr": "État MV : Erreur",
        "de": "MV-Status: Fehler",
        "es": "Estado MV: Error",
        "it": "Stato MV: Errore",
        "pt": "Estado MV: Erro",
    },
    "MV Status: Clean": {
        "fr": "État MV : Propre",
        "de": "MV-Status: Sauber",
        "es": "Estado MV: Limpio",
        "it": "Stato MV: Pulito",
        "pt": "Estado MV: Limpo",
    },
    "MV Status:": {
        "fr": "État MV :",
        "de": "MV-Status:",
        "es": "Estado MV:",
        "it": "Stato MV:",
        "pt": "Estado MV:",
    },
    "active": {
        "fr": "actives",
        "de": "aktiv",
        "es": "activas",
        "it": "attive",
        "pt": "ativas",
    },
    "No active materialized views": {
        "fr": "Aucune vue matérialisée active",
        "de": "Keine aktiven materialisierten Ansichten",
        "es": "Sin vistas materializadas activas",
        "it": "Nessuna vista materializzata attiva",
        "pt": "Nenhuma visualização materializada ativa",
    },
    "Session:": {
        "fr": "Session :",
        "de": "Sitzung:",
        "es": "Sesión:",
        "it": "Sessione:",
        "pt": "Sessão:",
    },
    "Other sessions:": {
        "fr": "Autres sessions :",
        "de": "Andere Sitzungen:",
        "es": "Otras sesiones:",
        "it": "Altre sessioni:",
        "pt": "Outras sessões:",
    },
    
    # Cleanup buttons
    "🧹 Session": {
        "fr": "🧹 Session",
        "de": "🧹 Sitzung",
        "es": "🧹 Sesión",
        "it": "🧹 Sessione",
        "pt": "🧹 Sessão",
    },
    "Cleanup MVs from this session": {
        "fr": "Nettoyer les MV de cette session",
        "de": "MVs dieser Sitzung bereinigen",
        "es": "Limpiar MVs de esta sesión",
        "it": "Pulisci MV di questa sessione",
        "pt": "Limpar MVs desta sessão",
    },
    "🗑️ Orphaned": {
        "fr": "🗑️ Orphelines",
        "de": "🗑️ Verwaist",
        "es": "🗑️ Huérfanas",
        "it": "🗑️ Orfane",
        "pt": "🗑️ Órfãs",
    },
    "Cleanup orphaned MVs (>24h old)": {
        "fr": "Nettoyer les MV orphelines (>24h)",
        "de": "Verwaiste MVs bereinigen (>24h alt)",
        "es": "Limpiar MVs huérfanas (>24h)",
        "it": "Pulisci MV orfane (>24h)",
        "pt": "Limpar MVs órfãs (>24h)",
    },
    "⚠️ All": {
        "fr": "⚠️ Toutes",
        "de": "⚠️ Alle",
        "es": "⚠️ Todas",
        "it": "⚠️ Tutte",
        "pt": "⚠️ Todas",
    },
    "Cleanup ALL MVs (affects other sessions)": {
        "fr": "Nettoyer TOUTES les MV (affecte les autres sessions)",
        "de": "ALLE MVs bereinigen (betrifft andere Sitzungen)",
        "es": "Limpiar TODAS las MVs (afecta otras sesiones)",
        "it": "Pulisci TUTTE le MV (influisce su altre sessioni)",
        "pt": "Limpar TODAS as MVs (afeta outras sessões)",
    },
    "Confirm Cleanup": {
        "fr": "Confirmer le nettoyage",
        "de": "Bereinigung bestätigen",
        "es": "Confirmar limpieza",
        "it": "Conferma pulizia",
        "pt": "Confirmar limpeza",
    },
    "Drop ALL materialized views?\nThis affects other FilterMate sessions!": {
        "fr": "Supprimer TOUTES les vues matérialisées ?\nCela affecte les autres sessions FilterMate !",
        "de": "ALLE materialisierten Ansichten löschen?\nDies betrifft andere FilterMate-Sitzungen!",
        "es": "¿Eliminar TODAS las vistas materializadas?\n¡Esto afecta otras sesiones de FilterMate!",
        "it": "Eliminare TUTTE le viste materializzate?\nQuesto influisce su altre sessioni FilterMate!",
        "pt": "Excluir TODAS as visualizações materializadas?\nIsso afeta outras sessões do FilterMate!",
    },
    "Refresh MV status": {
        "fr": "Actualiser l'état des MV",
        "de": "MV-Status aktualisieren",
        "es": "Actualizar estado de MV",
        "it": "Aggiorna stato MV",
        "pt": "Atualizar status de MV",
    },
    
    # MV Settings
    "Threshold:": {
        "fr": "Seuil :",
        "de": "Schwellenwert:",
        "es": "Umbral:",
        "it": "Soglia:",
        "pt": "Limite:",
    },
    "features": {
        "fr": "entités",
        "de": "Features",
        "es": "entidades",
        "it": "elementi",
        "pt": "feições",
    },
    "Auto-cleanup on exit": {
        "fr": "Nettoyage auto à la sortie",
        "de": "Auto-Bereinigung beim Beenden",
        "es": "Limpieza auto al salir",
        "it": "Pulizia auto all'uscita",
        "pt": "Limpeza auto ao sair",
    },
    "Automatically drop session MVs when plugin unloads": {
        "fr": "Supprimer automatiquement les MV de session à la fermeture du plugin",
        "de": "Session-MVs automatisch löschen wenn Plugin entladen wird",
        "es": "Eliminar automáticamente MVs de sesión al descargar plugin",
        "it": "Elimina automaticamente MV di sessione quando il plugin si chiude",
        "pt": "Excluir automaticamente MVs da sessão quando o plugin descarregar",
    },
    "Create MVs for datasets larger than this": {
        "fr": "Créer des MV pour les jeux de données plus grands que ça",
        "de": "MVs für Datensätze größer als dies erstellen",
        "es": "Crear MVs para conjuntos de datos mayores que esto",
        "it": "Crea MV per dataset più grandi di questo",
        "pt": "Criar MVs para conjuntos de dados maiores que isso",
    },
    
    # ========================================
    # Simplified Optimization Popup
    # ========================================
    "faster possible": {
        "fr": "plus rapide possible",
        "de": "schneller möglich",
        "es": "más rápido posible",
        "it": "più veloce possibile",
        "pt": "mais rápido possível",
    },
    "Optimizations available": {
        "fr": "Optimisations disponibles",
        "de": "Optimierungen verfügbar",
        "es": "Optimizaciones disponibles",
        "it": "Ottimizzazioni disponibili",
        "pt": "Otimizações disponíveis",
    },
    "FilterMate - Apply Optimizations?": {
        "fr": "FilterMate - Appliquer les optimisations ?",
        "de": "FilterMate - Optimierungen anwenden?",
        "es": "FilterMate - ¿Aplicar optimizaciones?",
        "it": "FilterMate - Applicare ottimizzazioni?",
        "pt": "FilterMate - Aplicar otimizações?",
    },
    "Skip": {
        "fr": "Ignorer",
        "de": "Überspringen",
        "es": "Omitir",
        "it": "Salta",
        "pt": "Pular",
    },
    "✓ Apply": {
        "fr": "✓ Appliquer",
        "de": "✓ Anwenden",
        "es": "✓ Aplicar",
        "it": "✓ Applica",
        "pt": "✓ Aplicar",
    },
    "Don't ask for this session": {
        "fr": "Ne plus demander pour cette session",
        "de": "Diese Sitzung nicht mehr fragen",
        "es": "No preguntar en esta sesión",
        "it": "Non chiedere per questa sessione",
        "pt": "Não perguntar nesta sessão",
    },
    
    # Optimization tags
    "Centroids": {
        "fr": "Centroïdes",
        "de": "Zentroide",
        "es": "Centroides",
        "it": "Centroidi",
        "pt": "Centróides",
    },
    "Simplify": {
        "fr": "Simplifier",
        "de": "Vereinfachen",
        "es": "Simplificar",
        "it": "Semplifica",
        "pt": "Simplificar",
    },
    "Pre-simplify": {
        "fr": "Pré-simplifier",
        "de": "Vorvereinfachen",
        "es": "Pre-simplificar",
        "it": "Pre-semplifica",
        "pt": "Pré-simplificar",
    },
    "Fewer segments": {
        "fr": "Moins de segments",
        "de": "Weniger Segmente",
        "es": "Menos segmentos",
        "it": "Meno segmenti",
        "pt": "Menos segmentos",
    },
    "Flat buffer": {
        "fr": "Buffer plat",
        "de": "Flacher Puffer",
        "es": "Buffer plano",
        "it": "Buffer piatto",
        "pt": "Buffer plano",
    },
    "BBox filter": {
        "fr": "Filtre BBox",
        "de": "BBox-Filter",
        "es": "Filtro BBox",
        "it": "Filtro BBox",
        "pt": "Filtro BBox",
    },
    "Attr-first": {
        "fr": "Attribut d'abord",
        "de": "Attribut zuerst",
        "es": "Atributo primero",
        "it": "Attributo prima",
        "pt": "Atributo primeiro",
    },
    
    # ========================================
    # PostgreSQL not available errors
    # ========================================
    "PostgreSQL not available": {
        "fr": "PostgreSQL non disponible",
        "de": "PostgreSQL nicht verfügbar",
        "es": "PostgreSQL no disponible",
        "it": "PostgreSQL non disponibile",
        "pt": "PostgreSQL não disponível",
    },
    "No connection": {
        "fr": "Pas de connexion",
        "de": "Keine Verbindung",
        "es": "Sin conexión",
        "it": "Nessuna connessione",
        "pt": "Sem conexão",
    },
    
    # ========================================
    # Missing strings from verification
    # ========================================
    "Auto-zoom when feature changes": {
        "fr": "Zoom auto lors du changement d'entité",
        "de": "Auto-Zoom bei Feature-Änderung",
        "es": "Zoom automático al cambiar entidad",
        "it": "Zoom automatico al cambio di elemento",
        "pt": "Zoom automático ao mudar feição",
    },
    "Backend optimization settings saved": {
        "fr": "Paramètres d'optimisation backend enregistrés",
        "de": "Backend-Optimierungseinstellungen gespeichert",
        "es": "Configuración de optimización del backend guardada",
        "it": "Impostazioni ottimizzazione backend salvate",
        "pt": "Configurações de otimização do backend salvas",
    },
    "Backend optimizations configured": {
        "fr": "Optimisations backend configurées",
        "de": "Backend-Optimierungen konfiguriert",
        "es": "Optimizaciones de backend configuradas",
        "it": "Ottimizzazioni backend configurate",
        "pt": "Otimizações de backend configuradas",
    },
    "Expression Evaluation": {
        "fr": "Évaluation d'expression",
        "de": "Ausdrucksauswertung",
        "es": "Evaluación de expresión",
        "it": "Valutazione espressione",
        "pt": "Avaliação de expressão",
    },
    "Identify selected feature": {
        "fr": "Identifier l'entité sélectionnée",
        "de": "Ausgewähltes Feature identifizieren",
        "es": "Identificar entidad seleccionada",
        "it": "Identifica elemento selezionato",
        "pt": "Identificar feição selecionada",
    },
    "Layer properties reset to defaults": {
        "fr": "Propriétés du layer réinitialisées par défaut",
        "de": "Layer-Eigenschaften auf Standard zurückgesetzt",
        "es": "Propiedades de capa restablecidas a valores predeterminados",
        "it": "Proprietà layer ripristinate ai valori predefiniti",
        "pt": "Propriedades da camada redefinidas para padrões",
    },
    "Link exploring widgets together": {
        "fr": "Lier les widgets d'exploration ensemble",
        "de": "Erkundungs-Widgets verknüpfen",
        "es": "Vincular widgets de exploración",
        "it": "Collega widget esplorazione insieme",
        "pt": "Vincular widgets de exploração",
    },
    "Optimization settings saved": {
        "fr": "Paramètres d'optimisation enregistrés",
        "de": "Optimierungseinstellungen gespeichert",
        "es": "Configuración de optimización guardada",
        "it": "Impostazioni ottimizzazione salvate",
        "pt": "Configurações de otimização salvas",
    },
    "Reset all layer exploring properties": {
        "fr": "Réinitialiser toutes les propriétés d'exploration du layer",
        "de": "Alle Layer-Erkundungseigenschaften zurücksetzen",
        "es": "Restablecer todas las propiedades de exploración de capa",
        "it": "Ripristina tutte le proprietà esplorazione layer",
        "pt": "Redefinir todas as propriedades de exploração da camada",
    },
    "Toggle feature selection on map": {
        "fr": "Activer/désactiver la sélection d'entités sur la carte",
        "de": "Feature-Auswahl auf Karte umschalten",
        "es": "Alternar selección de entidades en el mapa",
        "it": "Attiva/disattiva selezione elementi sulla mappa",
        "pt": "Alternar seleção de feições no mapa",
    },
    "Use centroids instead of full geometries for distant layers (faster for complex polygons)": {
        "fr": "Utiliser les centroïdes au lieu des géométries complètes pour les couches distantes (plus rapide pour les polygones complexes)",
        "de": "Zentroide statt voller Geometrien für entfernte Layer verwenden (schneller für komplexe Polygone)",
        "es": "Usar centroides en lugar de geometrías completas para capas distantes (más rápido para polígonos complejos)",
        "it": "Usa centroidi invece delle geometrie complete per layer distanti (più veloce per poligoni complessi)",
        "pt": "Usar centróides em vez de geometrias completas para camadas distantes (mais rápido para polígonos complexos)",
    },
    "Use centroids instead of full geometries for source layer (faster for complex polygons)": {
        "fr": "Utiliser les centroïdes au lieu des géométries complètes pour la couche source (plus rapide pour les polygones complexes)",
        "de": "Zentroide statt voller Geometrien für Quell-Layer verwenden (schneller für komplexe Polygone)",
        "es": "Usar centroides en lugar de geometrías completas para capa fuente (más rápido para polígonos complejos)",
        "it": "Usa centroidi invece delle geometrie complete per layer sorgente (più veloce per poligoni complessi)",
        "pt": "Usar centróides em vez de geometrias completas para camada de origem (mais rápido para polígonos complexos)",
    },
    "Zoom to selected feature": {
        "fr": "Zoomer sur l'entité sélectionnée",
        "de": "Auf ausgewähltes Feature zoomen",
        "es": "Zoom a entidad seleccionada",
        "it": "Zoom su elemento selezionato",
        "pt": "Zoom para feição selecionada",
    },
}


def prettify_xml(elem):
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")


def add_strings_to_ts(ts_file, lang_code, new_strings):
    """Add new strings to a .ts translation file."""
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"  ERROR parsing {ts_file}: {e}")
        return 0
    
    # Find or create BackendOptimizationWidget context
    context = None
    for ctx in root.findall('context'):
        name = ctx.find('name')
        if name is not None and name.text == 'BackendOptimizationWidget':
            context = ctx
            break
    
    if context is None:
        context = ET.SubElement(root, 'context')
        name = ET.SubElement(context, 'name')
        name.text = 'BackendOptimizationWidget'
    
    # Get existing source strings in this context
    existing_sources = set()
    for msg in context.findall('message'):
        src = msg.find('source')
        if src is not None and src.text:
            existing_sources.add(src.text)
    
    # Add new messages
    added_count = 0
    for source, translations in new_strings.items():
        if source in existing_sources:
            continue  # Skip existing strings
        
        message = ET.SubElement(context, 'message')
        src_elem = ET.SubElement(message, 'source')
        src_elem.text = source
        
        trans_elem = ET.SubElement(message, 'translation')
        # Get translation for this language, fallback to English (source)
        trans_text = translations.get(lang_code, source)
        trans_elem.text = trans_text
        
        # Mark as unfinished if using fallback
        if lang_code not in translations:
            trans_elem.set('type', 'unfinished')
        
        added_count += 1
    
    # Write back
    tree.write(ts_file, encoding='utf-8', xml_declaration=True)
    
    return added_count


def main():
    """Main function to update all translation files."""
    print("=" * 60)
    print("FilterMate v2.8.9 Translation Update Tool")
    print("=" * 60)
    print()
    
    if not os.path.exists(I18N_DIR):
        print(f"ERROR: i18n directory not found: {I18N_DIR}")
        return 1
    
    print(f"i18n directory: {I18N_DIR}")
    print(f"New strings to add: {len(NEW_STRINGS_V289)}")
    print()
    
    # Process each .ts file
    ts_files = sorted([f for f in os.listdir(I18N_DIR) if f.endswith('.ts')])
    
    total_added = 0
    for filename in ts_files:
        # Extract language code (e.g., "fr" from "FilterMate_fr.ts")
        lang_code = filename.replace('FilterMate_', '').replace('.ts', '')
        filepath = os.path.join(I18N_DIR, filename)
        
        added = add_strings_to_ts(filepath, lang_code, NEW_STRINGS_V289)
        total_added += added
        
        status = "✓" if added > 0 else "-"
        print(f"  {status} {filename}: {added} strings added")
    
    print()
    print("=" * 60)
    print(f"SUMMARY: {total_added} total strings added across {len(ts_files)} files")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Review translations in Qt Linguist or text editor")
    print("2. Mark 'unfinished' translations as complete when verified")
    print("3. Compile with: python3 tools/compile_translations_simple.py")
    print("4. Test in QGIS with different language settings")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
