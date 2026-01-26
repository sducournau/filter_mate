#!/usr/bin/env python3
"""Add missing translations to FilterMate_fr.ts from FilterMate_en.ts"""

import xml.etree.ElementTree as ET

# French translations for missing messages
TRANSLATIONS = {
    "All layers using auto-selection": "Toutes les couches utilisent la sélection automatique",
    "Applied to '{0}':\n{1}": "Appliqué à '{0}':\n{1}",
    "Auto-centroid {0}": "Centroïde automatique {0}",
    "Auto-optimization {0}": "Optimisation automatique {0}",
    "Auto-optimizer module not available": "Module d'optimisation automatique non disponible",
    "Auto-optimizer not available: {0}": "Optimiseur automatique non disponible : {0}",
    "Auto-selected backends for {0} layer(s)": "Backends sélectionnés automatiquement pour {0} couche(s)",
    "Backend controller not available": "Contrôleur de backend non disponible",
    "Backend forced to {0} for '{1}'": "Backend forcé à {0} pour '{1}'",
    "Backend optimization unavailable": "Optimisation du backend non disponible",
    "Backend set to Auto for '{0}'": "Backend défini sur Auto pour '{0}'",
    "Clear ALL FilterMate temporary tables from all databases": "Effacer TOUTES les tables temporaires FilterMate de toutes les bases de données",
    "Clear temporary tables for the current project only": "Effacer les tables temporaires pour le projet actuel uniquement",
    "Cleared {0} temporary table(s) for current project": "{0} table(s) temporaire(s) effacée(s) pour le projet actuel",
    "Cleared {0} temporary table(s) globally": "{0} table(s) temporaire(s) effacée(s) globalement",
    "Confirmation {0}": "Confirmation {0}",
    "Could not analyze layer '{0}'": "Impossible d'analyser la couche '{0}'",
    "Could not reload plugin automatically.": "Impossible de recharger le plugin automatiquement.",
    "Dark mode": "Mode sombre",
    "Description (auto-generated, you can modify it)": "Description (générée automatiquement, vous pouvez la modifier)",
    "Dialog not available: {0}": "Dialogue non disponible : {0}",
    "Enter a name for this filter": "Entrez un nom pour ce filtre",
    "Error analyzing layer: {0}": "Erreur lors de l'analyse de la couche : {0}",
    "Error cancelling changes: {0}": "Erreur lors de l'annulation des modifications : {0}",
    "Error reloading plugin: {0}": "Erreur lors du rechargement du plugin : {0}",
    "Error: {0}": "Erreur : {0}",
    "Favorites manager not available": "Gestionnaire de favoris non disponible",
    "Filter history position": "Position dans l'historique des filtres",
    "FilterMate - Add to Favorites": "FilterMate - Ajouter aux favoris",
    "Forced {0} backend for {1} layer(s)": "Backend {0} forcé pour {1} couche(s)",
    "Initialization error: {}": "Erreur d'initialisation : {}",
    "Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}": "La couche '{0}' est déjà configurée de manière optimale.\nType : {1}\nEntités : {2:,}",
    "Light mode": "Mode clair",
    "No PostgreSQL connection available": "Aucune connexion PostgreSQL disponible",
    "No alternative backends available for this layer": "Aucun backend alternatif disponible pour cette couche",
    "No layer selected. Please select a layer first.": "Aucune couche sélectionnée. Veuillez d'abord sélectionner une couche.",
    "No optimizations selected to apply.": "Aucune optimisation sélectionnée à appliquer.",
    "No temporary tables found": "Aucune table temporaire trouvée",
    "No temporary tables found for current project": "Aucune table temporaire trouvée pour le projet actuel",
    "No views to clean or cleanup failed": "Aucune vue à nettoyer ou échec du nettoyage",
    "Optimized {0} layer(s)": "{0} couche(s) optimisée(s)",
    "Other Sessions Active": "Autres sessions actives",
    "Plugin activated with {0} vector layer(s)": "Plugin activé avec {0} couche(s) vectorielle(s)",
    "PostgreSQL auto-cleanup disabled": "Nettoyage automatique PostgreSQL désactivé",
    "PostgreSQL auto-cleanup enabled": "Nettoyage automatique PostgreSQL activé",
    "PostgreSQL session views cleaned up": "Vues de session PostgreSQL nettoyées",
    "Redo filter (Ctrl+Y)": "Refaire le filtre (Ctrl+Y)",
    "Schema '{0}' dropped successfully": "Schéma '{0}' supprimé avec succès",
    "Schema cleanup cancelled": "Nettoyage du schéma annulé",
    "Schema cleanup failed": "Échec du nettoyage du schéma",
    "Schema has {0} view(s) from other sessions.\nDrop anyway?": "Le schéma a {0} vue(s) d'autres sessions.\nSupprimer quand même ?",
    "The selected layer is invalid or its source cannot be found.": "La couche sélectionnée est invalide ou sa source est introuvable.",
    "Theme adapted: {0}": "Thème adapté : {0}",
    "UI configuration incomplete - check logs": "Configuration de l'interface utilisateur incomplète - vérifier les logs",
    "UI dimension error: {}": "Erreur de dimension de l'interface : {}",
    "Undo last filter (Ctrl+Z)": "Annuler le dernier filtre (Ctrl+Z)",
    "disabled": "désactivé",
    "enabled": "activé",
    "★ No favorites saved\nClick to add current filter": "★ Aucun favori enregistré\nCliquez pour ajouter le filtre actuel",
    "★ {0} Favorites saved\nClick to apply or manage": "★ {0} favoris enregistrés\nCliquez pour appliquer ou gérer",
    "⚙️ Manage favorites...": "⚙️ Gérer les favoris...",
    "⭐ Add Current Filter (no filter active)": "⭐ Ajouter le filtre actuel (aucun filtre actif)",
    "⭐ Add Current Filter to Favorites": "⭐ Ajouter le filtre actuel aux favoris",
    "⭐ Add current filter to favorites": "⭐ Ajouter le filtre actuel aux favoris",
    "⭐ Add filter (no active filter)": "⭐ Ajouter un filtre (aucun filtre actif)",
    "🌐 All Projects (Global)": "🌐 Tous les projets (Global)",
    "📁 Current Project": "📁 Projet actuel",
    "📤 Export...": "📤 Exporter...",
    "📥 Import...": "📥 Importer...",
}

def add_missing_translations():
    """Add missing translations to FilterMate_fr.ts"""
    
    # Parse files
    en_tree = ET.parse('i18n/FilterMate_en.ts')
    fr_tree = ET.parse('i18n/FilterMate_fr.ts')
    
    en_root = en_tree.getroot()
    fr_root = fr_tree.getroot()
    
    # Get existing French sources
    fr_sources = {msg.find('source').text for msg in fr_root.findall('.//message')}
    
    # Get the context element
    fr_context = fr_root.find('context')
    
    # Find and add missing messages
    added = 0
    for en_msg in en_root.findall('.//message'):
        source_text = en_msg.find('source').text
        
        if source_text not in fr_sources and source_text in TRANSLATIONS:
            # Create new message element
            new_msg = ET.Element('message')
            
            # Add source
            source = ET.SubElement(new_msg, 'source')
            source.text = source_text
            
            # Add translation
            translation = ET.SubElement(new_msg, 'translation')
            translation.text = TRANSLATIONS[source_text]
            
            # Add to context
            fr_context.append(new_msg)
            added += 1
            print(f"Added: {source_text[:60]}...")
    
    # Write back to file with proper formatting
    ET.indent(fr_tree, space='    ')
    fr_tree.write('i18n/FilterMate_fr.ts', encoding='utf-8', xml_declaration=True)
    
    print(f"\n✅ Added {added} translations to FilterMate_fr.ts")
    
    # Verify
    fr_tree_new = ET.parse('i18n/FilterMate_fr.ts')
    new_count = len(list(fr_tree_new.findall('.//message')))
    print(f"Total messages now: {new_count}")

if __name__ == '__main__':
    add_missing_translations()
