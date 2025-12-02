#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate Phase 4 - Performance Benchmark Script

Ce script doit être exécuté dans la console Python QGIS.
Il mesure les performances réelles de filtrage pour différents backends et tailles de données.

Usage dans QGIS:
    1. Ouvrir QGIS avec des couches de test chargées
    2. Plugins > Console Python
    3. exec(open('benchmark_performance.py').read())
    4. Ou copier-coller le contenu

Author: Simon Ducournau + GitHub Copilot
Date: Décembre 2025
"""

import sys
import time
import json
from datetime import datetime
from collections import defaultdict

try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsExpression
    from qgis.utils import iface
    print("✅ Modules QGIS importés")
except ImportError:
    print("❌ Ce script doit être exécuté dans QGIS")
    sys.exit(1)


class FilterMatePerformanceBenchmark:
    """Benchmark des performances FilterMate"""
    
    def __init__(self):
        self.project = QgsProject.instance()
        self.benchmarks = []
        self.start_time = datetime.now()
        
    def print_header(self, title):
        """En-tête formaté"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    
    def print_section(self, title):
        """Section formatée"""
        print(f"\n{'─' * 80}")
        print(f"  {title}")
        print(f"{'─' * 80}")
    
    def get_provider_type(self, layer):
        """Détermine le type de provider normalisé"""
        provider = layer.providerType()
        if provider == 'postgres':
            return 'postgresql'
        elif provider == 'spatialite':
            return 'spatialite'
        elif provider == 'ogr':
            return 'ogr'
        else:
            return 'unknown'
    
    def categorize_layer_size(self, count):
        """Catégorise la taille d'une couche"""
        if count < 1000:
            return 'tiny', '< 1k'
        elif count < 10000:
            return 'small', '1k-10k'
        elif count < 50000:
            return 'medium', '10k-50k'
        elif count < 100000:
            return 'large', '50k-100k'
        elif count < 500000:
            return 'xlarge', '100k-500k'
        else:
            return 'huge', '> 500k'
    
    def benchmark_simple_filter(self, layer, expression="1=1", label="Simple filter"):
        """Benchmark un filtrage simple"""
        layer_name = layer.name()
        provider = self.get_provider_type(layer)
        initial_count = layer.featureCount()
        size_cat, size_label = self.categorize_layer_size(initial_count)
        
        print(f"\n  Testing: {layer_name}")
        print(f"    Provider: {provider}")
        print(f"    Features: {initial_count:,} ({size_label})")
        print(f"    Expression: {expression}")
        
        # Mesurer le temps
        start = time.time()
        
        try:
            layer.setSubsetString(expression)
            filtered_count = layer.featureCount()
            
            end = time.time()
            duration = end - start
            
            # Réinitialiser
            layer.setSubsetString("")
            
            # Calculer métriques
            rate = filtered_count / duration if duration > 0 else 0
            
            result = {
                'layer': layer_name,
                'provider': provider,
                'size_category': size_cat,
                'size_label': size_label,
                'initial_count': initial_count,
                'filtered_count': filtered_count,
                'expression': expression,
                'label': label,
                'duration': duration,
                'rate': rate,
                'success': True,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"    ✅ Duration: {duration:.3f}s")
            print(f"    ✅ Rate: {rate:,.0f} features/s")
            print(f"    ✅ Filtered: {filtered_count:,} features")
            
            self.benchmarks.append(result)
            return result
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            
            result = {
                'layer': layer_name,
                'provider': provider,
                'size_category': size_cat,
                'initial_count': initial_count,
                'expression': expression,
                'label': label,
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
            self.benchmarks.append(result)
            return result
    
    def benchmark_spatial_filter(self, layer):
        """Benchmark un filtrage spatial"""
        # Tester avec un buffer (opération spatiale courante)
        # Note: l'expression doit être adaptée selon la géométrie de la couche
        geom_type = layer.geometryType()
        
        if geom_type == 0:  # Point
            expr = "ST_Buffer(geometry, 100) IS NOT NULL"
        elif geom_type == 1:  # Line
            expr = "ST_Length(geometry) > 0"
        elif geom_type == 2:  # Polygon
            expr = "ST_Area(geometry) > 0"
        else:
            expr = "1=1"
        
        return self.benchmark_simple_filter(layer, expr, "Spatial filter")
    
    def benchmark_complex_filter(self, layer):
        """Benchmark un filtrage complexe (attributaire + spatial)"""
        # Expression combinée (adapter selon les attributs disponibles)
        fields = [f.name() for f in layer.fields()]
        
        # Essayer de construire une expression intelligente
        if any('pop' in f.lower() for f in fields):
            attr_part = "1=1"  # Fallback simple
            for f in fields:
                if 'pop' in f.lower():
                    attr_part = f'"{f}" > 0'
                    break
        else:
            attr_part = "1=1"
        
        # Partie spatiale selon géométrie
        geom_type = layer.geometryType()
        if geom_type == 2:  # Polygon
            spatial_part = "ST_Area(geometry) > 1"
        elif geom_type == 1:  # Line
            spatial_part = "ST_Length(geometry) > 1"
        else:
            spatial_part = "1=1"
        
        expr = f"({attr_part}) AND ({spatial_part})"
        
        return self.benchmark_simple_filter(layer, expr, "Complex filter")
    
    def run_comprehensive_benchmarks(self):
        """Lance une batterie complète de benchmarks"""
        self.print_header("FilterMate Performance Benchmarks")
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        layers = list(self.project.mapLayers().values())
        
        if not layers:
            print("\n⚠️  No layers in project. Please load test layers.")
            return
        
        # Grouper par provider
        layers_by_provider = defaultdict(list)
        for layer in layers:
            provider = self.get_provider_type(layer)
            layers_by_provider[provider].append(layer)
        
        # Afficher résumé
        self.print_section("Layers Summary")
        for provider, provider_layers in layers_by_provider.items():
            print(f"\n{provider.upper()}:")
            for layer in provider_layers:
                count = layer.featureCount()
                _, size_label = self.categorize_layer_size(count)
                print(f"  - {layer.name()}: {count:,} features ({size_label})")
        
        # Demander confirmation
        print("\n" + "=" * 80)
        response = input("Run benchmarks on all layers? (y/n): ")
        if response.lower() != 'y':
            print("Benchmarks cancelled")
            return
        
        # Exécuter benchmarks
        for provider, provider_layers in sorted(layers_by_provider.items()):
            self.print_section(f"Benchmarking {provider.upper()}")
            
            for layer in provider_layers:
                # Test 1: Simple filter
                self.benchmark_simple_filter(layer, "1=1", "Simple (1=1)")
                
                # Test 2: Spatial filter
                self.benchmark_spatial_filter(layer)
                
                # Test 3: Complex filter
                self.benchmark_complex_filter(layer)
        
        # Générer rapport
        self.generate_report()
    
    def generate_report(self):
        """Génère un rapport détaillé des benchmarks"""
        self.print_header("BENCHMARK REPORT")
        
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        print(f"\nTotal duration: {total_duration:.1f}s")
        print(f"Total tests: {len(self.benchmarks)}")
        
        # Grouper par provider
        by_provider = defaultdict(list)
        for b in self.benchmarks:
            if b['success']:
                by_provider[b['provider']].append(b)
        
        # Rapport par provider
        self.print_section("Results by Backend")
        
        for provider in sorted(by_provider.keys()):
            results = by_provider[provider]
            print(f"\n{provider.upper()}:")
            
            # Grouper par taille
            by_size = defaultdict(list)
            for r in results:
                by_size[r['size_category']].append(r)
            
            for size_cat in ['tiny', 'small', 'medium', 'large', 'xlarge', 'huge']:
                if size_cat not in by_size:
                    continue
                
                size_results = by_size[size_cat]
                avg_duration = sum(r['duration'] for r in size_results) / len(size_results)
                avg_rate = sum(r['rate'] for r in size_results) / len(size_results)
                size_label = size_results[0]['size_label']
                
                print(f"\n  {size_label}:")
                print(f"    Tests: {len(size_results)}")
                print(f"    Avg duration: {avg_duration:.3f}s")
                print(f"    Avg rate: {avg_rate:,.0f} features/s")
                
                # Détails par test
                for r in size_results:
                    print(f"      - {r['label']}: {r['duration']:.3f}s ({r['rate']:,.0f} f/s)")
        
        # Comparaison entre backends
        self.print_section("Backend Comparison")
        
        # Comparer pour chaque catégorie de taille
        size_categories = ['tiny', 'small', 'medium', 'large', 'xlarge', 'huge']
        
        comparison_data = defaultdict(lambda: defaultdict(list))
        
        for b in self.benchmarks:
            if b['success']:
                comparison_data[b['size_category']][b['provider']].append(b['duration'])
        
        print("\nAverage duration by size and backend:")
        print(f"\n{'Size':<15} {'PostgreSQL':<15} {'Spatialite':<15} {'OGR':<15}")
        print("─" * 60)
        
        for size_cat in size_categories:
            if size_cat not in comparison_data:
                continue
            
            size_data = comparison_data[size_cat]
            
            # Obtenir le label de taille
            size_label = next((b['size_label'] for b in self.benchmarks 
                             if b['success'] and b['size_category'] == size_cat), size_cat)
            
            row = [size_label]
            
            for provider in ['postgresql', 'spatialite', 'ogr']:
                if provider in size_data and size_data[provider]:
                    avg = sum(size_data[provider]) / len(size_data[provider])
                    row.append(f"{avg:.3f}s")
                else:
                    row.append("N/A")
            
            print(f"{row[0]:<15} {row[1]:<15} {row[2]:<15} {row[3]:<15}")
        
        # Recommandations
        self.print_section("Recommendations")
        
        print("\nBased on benchmark results:")
        
        # Analyser les résultats pour donner recommandations
        for provider, results in by_provider.items():
            if not results:
                continue
            
            # Trouver limite de performance (où le temps dépasse un seuil)
            large_results = [r for r in results if r['size_category'] in ['large', 'xlarge', 'huge']]
            
            if large_results:
                avg_large_duration = sum(r['duration'] for r in large_results) / len(large_results)
                
                if avg_large_duration > 10:
                    print(f"\n⚠️  {provider.upper()}: Performance degrades with large datasets (avg {avg_large_duration:.1f}s)")
                    print(f"    Consider using PostgreSQL for datasets > 50k features")
                elif avg_large_duration > 5:
                    print(f"\n✓ {provider.upper()}: Acceptable performance for large datasets ({avg_large_duration:.1f}s)")
                else:
                    print(f"\n✅ {provider.upper()}: Excellent performance for large datasets ({avg_large_duration:.1f}s)")
        
        # Sauvegarder résultats JSON
        self.save_results_json()
        
        print("\n" + "=" * 80)
        print("Benchmarks completed!")
        print("=" * 80)
    
    def save_results_json(self):
        """Sauvegarde les résultats en JSON"""
        try:
            output_file = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            report = {
                'metadata': {
                    'start_time': self.start_time.isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'total_tests': len(self.benchmarks)
                },
                'benchmarks': self.benchmarks
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Results saved to: {output_file}")
            
        except Exception as e:
            print(f"\n⚠️  Could not save JSON results: {e}")


def main():
    """Point d'entrée"""
    benchmark = FilterMatePerformanceBenchmark()
    benchmark.run_comprehensive_benchmarks()


if __name__ == '__main__':
    main()
else:
    print("\n" + "=" * 80)
    print("Benchmark script loaded! To run:")
    print("  >>> main()")
    print("=" * 80)
