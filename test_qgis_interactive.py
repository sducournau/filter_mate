#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate Phase 4 - QGIS Interactive Test Script

Ce script doit être exécuté dans la console Python QGIS (pas en standalone).
Il teste tous les backends (PostgreSQL, Spatialite, OGR) avec différentes tailles de données.

Usage dans QGIS:
    1. Ouvrir QGIS
    2. Plugins > Console Python
    3. Copier-coller ce script dans la console
    4. Suivre les instructions à l'écran

Author: Simon Ducournau + GitHub Copilot
Date: Décembre 2025
"""

import sys
import os
from datetime import datetime

# Vérifier qu'on est dans QGIS
try:
    from qgis.core import (
        QgsProject, QgsVectorLayer, QgsApplication,
        QgsCoordinateReferenceSystem, QgsExpression
    )
    from qgis.utils import iface
    print("✅ Modules QGIS importés avec succès")
except ImportError as e:
    print("❌ ERREUR: Ce script doit être exécuté dans QGIS (console Python)")
    print(f"   Détails: {e}")
    sys.exit(1)


class FilterMateQGISTest:
    """Classe de test interactive pour FilterMate dans QGIS"""
    
    def __init__(self):
        self.project = QgsProject.instance()
        self.results = {
            'postgresql': [],
            'spatialite': [],
            'ogr': []
        }
        self.test_start_time = datetime.now()
        
    def print_header(self, title):
        """Affiche un en-tête formaté"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    
    def print_section(self, title):
        """Affiche une section"""
        print(f"\n{'─' * 70}")
        print(f"  {title}")
        print(f"{'─' * 70}")
    
    def check_postgresql_available(self):
        """Vérifie si PostgreSQL est disponible"""
        self.print_section("Vérification disponibilité PostgreSQL")
        try:
            import psycopg2
            print("✅ psycopg2 installé - PostgreSQL disponible")
            return True
        except ImportError:
            print("⚠️  psycopg2 non installé - PostgreSQL non disponible")
            print("   Les tests PostgreSQL seront ignorés")
            return False
    
    def check_spatialite_available(self):
        """Vérifie si Spatialite est disponible"""
        self.print_section("Vérification disponibilité Spatialite")
        try:
            import sqlite3
            conn = sqlite3.connect(':memory:')
            conn.enable_load_extension(True)
            try:
                conn.load_extension('mod_spatialite')
                print("✅ Extension Spatialite chargée (mod_spatialite)")
                conn.close()
                return True
            except Exception:
                try:
                    conn.load_extension('mod_spatialite.dll')
                    print("✅ Extension Spatialite chargée (mod_spatialite.dll)")
                    conn.close()
                    return True
                except Exception as e:
                    print(f"⚠️  Extension Spatialite non disponible: {e}")
                    conn.close()
                    return False
        except Exception as e:
            print(f"❌ Erreur sqlite3: {e}")
            return False
    
    def list_project_layers(self):
        """Liste toutes les couches du projet avec leurs providers"""
        self.print_section("Couches disponibles dans le projet")
        layers = self.project.mapLayers().values()
        
        if not layers:
            print("⚠️  Aucune couche dans le projet QGIS")
            print("   Veuillez charger des couches de test avant de lancer les tests")
            return []
        
        layer_info = []
        for i, layer in enumerate(layers, 1):
            provider = layer.providerType()
            count = layer.featureCount()
            crs = layer.crs().authid()
            
            # Déterminer le type de provider normalisé
            if provider == 'postgres':
                provider_type = 'postgresql'
            elif provider == 'spatialite':
                provider_type = 'spatialite'
            elif provider == 'ogr':
                provider_type = 'ogr'
            else:
                provider_type = 'unknown'
            
            print(f"\n{i}. {layer.name()}")
            print(f"   Provider: {provider} ({provider_type})")
            print(f"   Features: {count:,}")
            print(f"   CRS: {crs}")
            print(f"   Géométrie: {layer.geometryType()}")
            
            layer_info.append({
                'index': i,
                'layer': layer,
                'provider': provider_type,
                'count': count,
                'name': layer.name()
            })
        
        return layer_info
    
    def test_layer_filtering(self, layer_info):
        """Teste le filtrage sur une couche"""
        layer = layer_info['layer']
        provider = layer_info['provider']
        count = layer_info['count']
        name = layer_info['name']
        
        self.print_section(f"Test filtrage: {name}")
        print(f"Provider: {provider}")
        print(f"Features totales: {count:,}")
        
        # Tester une expression simple
        test_expression = "1=1"  # Expression qui retourne tout
        
        print(f"\nApplication filtre test: {test_expression}")
        start_time = datetime.now()
        
        try:
            # Appliquer le filtre
            layer.setSubsetString(test_expression)
            filtered_count = layer.featureCount()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"✅ Filtre appliqué en {duration:.3f}s")
            print(f"   Features filtrées: {filtered_count:,}")
            
            # Réinitialiser
            layer.setSubsetString("")
            
            # Enregistrer résultats
            result = {
                'layer': name,
                'count': count,
                'duration': duration,
                'success': True
            }
            self.results[provider].append(result)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors du filtrage: {e}")
            result = {
                'layer': name,
                'count': count,
                'error': str(e),
                'success': False
            }
            self.results[provider].append(result)
            return False
    
    def test_expression_conversion(self):
        """Teste la conversion d'expressions QGIS"""
        self.print_section("Test conversion expressions")
        
        # Importer les fonctions FilterMate
        try:
            plugin_path = os.path.dirname(os.path.abspath(__file__))
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            from modules.appTasks import FilterTask
            
            # Expressions de test
            test_expressions = [
                ("population > 10000", "Expression simple"),
                ("name ILIKE '%paris%'", "ILIKE (insensible casse)"),
                ("ST_Area(geometry) > 1000", "Fonction spatiale"),
                ("population::real / area::real > 100", "Type casting"),
            ]
            
            print("\nTest conversion QGIS → Spatialite:")
            for expr, description in test_expressions:
                print(f"\n  {description}")
                print(f"  QGIS:      {expr}")
                
                # Note: Cette méthode nécessite une instance FilterTask
                # Pour un test complet, il faudrait créer une vraie tâche
                print(f"  Spatialite: (conversion nécessite instance FilterTask)")
            
            print("\n✅ Module FilterTask importé avec succès")
            return True
            
        except Exception as e:
            print(f"❌ Erreur import FilterTask: {e}")
            return False
    
    def print_summary(self):
        """Affiche le résumé des tests"""
        self.print_header("RÉSUMÉ DES TESTS")
        
        end_time = datetime.now()
        total_duration = (end_time - self.test_start_time).total_seconds()
        
        print(f"\nDurée totale des tests: {total_duration:.1f}s")
        
        for provider, results in self.results.items():
            if not results:
                continue
            
            print(f"\n{provider.upper()}:")
            success_count = sum(1 for r in results if r['success'])
            total_count = len(results)
            
            print(f"  Tests réussis: {success_count}/{total_count}")
            
            for result in results:
                status = "✅" if result['success'] else "❌"
                print(f"\n  {status} {result['layer']}")
                print(f"     Features: {result['count']:,}")
                if result['success']:
                    print(f"     Durée: {result['duration']:.3f}s")
                    if result['count'] > 0:
                        rate = result['count'] / result['duration']
                        print(f"     Vitesse: {rate:,.0f} features/s")
                else:
                    print(f"     Erreur: {result['error']}")
    
    def run_interactive_tests(self):
        """Lance les tests interactifs"""
        self.print_header("FilterMate Phase 4 - Tests QGIS Interactifs")
        print(f"Date: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Vérifier disponibilité des backends
        postgresql_available = self.check_postgresql_available()
        spatialite_available = self.check_spatialite_available()
        
        print("\n")
        print("Backends disponibles:")
        print(f"  PostgreSQL: {'✅ Oui' if postgresql_available else '❌ Non'}")
        print(f"  Spatialite: {'✅ Oui' if spatialite_available else '❌ Non'}")
        print(f"  OGR (local): ✅ Oui (toujours disponible)")
        
        # Lister les couches
        layer_info = self.list_project_layers()
        
        if not layer_info:
            print("\n" + "=" * 70)
            print("INSTRUCTIONS:")
            print("  1. Chargez des couches de test dans QGIS")
            print("  2. Idéalement, ayez au moins:")
            print("     - 1 couche PostgreSQL/PostGIS (si disponible)")
            print("     - 1 couche Spatialite")
            print("     - 1 couche Shapefile ou GeoPackage (OGR)")
            print("  3. Relancez ce script")
            print("=" * 70)
            return
        
        # Demander confirmation
        print("\n" + "=" * 70)
        response = input("\nLancer les tests sur ces couches ? (o/n): ")
        if response.lower() != 'o':
            print("Tests annulés par l'utilisateur")
            return
        
        # Tester chaque couche
        for info in layer_info:
            self.test_layer_filtering(info)
        
        # Tester conversion d'expressions
        self.test_expression_conversion()
        
        # Afficher résumé
        self.print_summary()
        
        # Recommandations
        self.print_header("RECOMMANDATIONS")
        print("\nTests manuels complémentaires à effectuer:")
        print("  1. Ouvrir le plugin FilterMate dans QGIS")
        print("  2. Tester filtrage avec expressions complexes:")
        print("     - Filtres attributaires (population > 10000)")
        print("     - Filtres spatiaux (ST_Intersects, ST_Buffer)")
        print("     - Combinaisons (AND, OR, NOT)")
        print("  3. Tester actions Reset et Unfilter")
        print("  4. Vérifier messages utilisateur (barre de message QGIS)")
        print("  5. Tester avec grandes données (>50k features)")
        print("  6. Vérifier export des résultats filtrés")
        
        print("\n" + "=" * 70)
        print("Tests terminés !")
        print("=" * 70)


def main():
    """Point d'entrée principal"""
    tester = FilterMateQGISTest()
    tester.run_interactive_tests()


# Exécution automatique si dans la console QGIS
if __name__ == '__main__':
    main()
else:
    # Si importé dans la console, permettre exécution manuelle
    print("\n" + "=" * 70)
    print("Script chargé ! Pour lancer les tests, exécutez:")
    print("  >>> main()")
    print("=" * 70)
