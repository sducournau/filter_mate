#!/usr/bin/env python3
"""
FilterMate - Delegation Regression Verification Script
Vérifie que toutes les délégations du dockwidget vers les controllers et
de l'app vers les services sont correctes.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field

@dataclass
class MethodCall:
    """Représente un appel de méthode délégué."""
    line: int
    object_name: str  # _backend_ctrl, _exploring_ctrl, etc.
    method_name: str
    context: str  # Ligne de code complète

@dataclass
class AttributeAccess:
    """Représente un accès d'attribut délégué."""
    line: int
    object_name: str
    attribute_name: str
    context: str

@dataclass
class AnalysisResult:
    """Résultats de l'analyse de régression."""
    file_path: str
    method_calls: List[MethodCall] = field(default_factory=list)
    attribute_accesses: List[AttributeAccess] = field(default_factory=list)
    missing_methods: List[Tuple[str, str, int]] = field(default_factory=list)  # (object, method, line)
    missing_attributes: List[Tuple[str, str, int]] = field(default_factory=list)  # (object, attr, line)
    broken_imports: List[Tuple[str, int]] = field(default_factory=list)  # (import, line)

class DelegationAnalyzer(ast.NodeVisitor):
    """Analyse AST pour détecter les délégations et vérifier leur validité."""
    
    def __init__(self, source_code: str):
        self.source_lines = source_code.splitlines()
        self.method_calls: List[MethodCall] = []
        self.attribute_accesses: List[AttributeAccess] = []
        self.current_line = 0
        
    def visit_Attribute(self, node):
        """Visite les accès d'attributs (self._exploring_ctrl.method())."""
        if hasattr(node, 'lineno'):
            self.current_line = node.lineno
            
        # Détecte les accès aux controllers (self._xxx_ctrl)
        if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name):
            if node.value.value.id == 'self' and '_ctrl' in node.value.attr:
                context = self.source_lines[self.current_line - 1] if self.current_line > 0 else ""
                self.attribute_accesses.append(
                    AttributeAccess(
                        line=self.current_line,
                        object_name=node.value.attr,
                        attribute_name=node.attr,
                        context=context.strip()
                    )
                )
        
        self.generic_visit(node)
        
    def visit_Call(self, node):
        """Visite les appels de méthodes."""
        if hasattr(node, 'lineno'):
            self.current_line = node.lineno
            
        # Détecte les appels de méthodes sur les controllers
        if isinstance(node.func, ast.Attribute):
            # Pattern: self._exploring_ctrl.method()
            if isinstance(node.func.value, ast.Attribute):
                if (isinstance(node.func.value.value, ast.Name) and 
                    node.func.value.value.id == 'self' and 
                    '_ctrl' in node.func.value.attr):
                    
                    context = self.source_lines[self.current_line - 1] if self.current_line > 0 else ""
                    self.method_calls.append(
                        MethodCall(
                            line=self.current_line,
                            object_name=node.func.value.attr,
                            method_name=node.func.attr,
                            context=context.strip()
                        )
                    )
            
            # Pattern: self._get_xxx_service().method()
            elif isinstance(node.func.value, ast.Call):
                if isinstance(node.func.value.func, ast.Attribute):
                    if (isinstance(node.func.value.func.value, ast.Name) and 
                        node.func.value.func.value.id == 'self' and 
                        '_get_' in node.func.value.func.attr and 
                        '_service' in node.func.value.func.attr):
                        
                        context = self.source_lines[self.current_line - 1] if self.current_line > 0 else ""
                        self.method_calls.append(
                            MethodCall(
                                line=self.current_line,
                                object_name=node.func.value.func.attr,  # _get_layer_service
                                method_name=node.func.attr,
                                context=context.strip()
                            )
                        )
        
        self.generic_visit(node)

def get_class_methods(source_code: str, class_name: str) -> Set[str]:
    """Extrait tous les noms de méthodes d'une classe."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"⚠️  Erreur de syntaxe lors du parsing pour {class_name}: {e}")
        return set()
    
    methods = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.add(item.name)
    
    return methods

def verify_delegation(root_path: Path) -> Dict[str, AnalysisResult]:
    """Vérifie toutes les délégations dans le projet."""
    results = {}
    
    # 1. Analyser filter_mate_dockwidget.py -> controllers
    dockwidget_path = root_path / "filter_mate_dockwidget.py"
    if dockwidget_path.exists():
        print(f"\n🔍 Analyse des délégations: {dockwidget_path.name}")
        result = analyze_dockwidget_delegations(dockwidget_path, root_path)
        results['dockwidget'] = result
    
    # 2. Analyser filter_mate_app.py -> services
    app_path = root_path / "filter_mate_app.py"
    if app_path.exists():
        print(f"\n🔍 Analyse des délégations: {app_path.name}")
        result = analyze_app_delegations(app_path, root_path)
        results['app'] = result
    
    # 3. Analyser les controllers entre eux
    controllers_path = root_path / "ui" / "controllers"
    if controllers_path.exists():
        print(f"\n🔍 Analyse des délégations inter-controllers")
        result = analyze_controller_cross_delegations(controllers_path, root_path)
        results['controllers'] = result
    
    return results

def analyze_dockwidget_delegations(dockwidget_path: Path, root_path: Path) -> AnalysisResult:
    """Analyse les délégations du dockwidget vers les controllers."""
    result = AnalysisResult(file_path=str(dockwidget_path))
    
    with open(dockwidget_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    # Parse AST pour trouver les appels
    analyzer = DelegationAnalyzer(source_code)
    try:
        tree = ast.parse(source_code)
        analyzer.visit(tree)
    except SyntaxError as e:
        print(f"⚠️  Erreur de syntaxe: {e}")
        return result
    
    result.method_calls = analyzer.method_calls
    result.attribute_accesses = analyzer.attribute_accesses
    
    # Charger les méthodes des controllers
    controller_methods = {
        '_backend_ctrl': get_class_methods(
            (root_path / "ui/controllers/backend_controller.py").read_text(encoding='utf-8'),
            "BackendController"
        ),
        '_favorites_ctrl': get_class_methods(
            (root_path / "ui/controllers/favorites_controller.py").read_text(encoding='utf-8'),
            "FavoritesController"
        ),
        '_exploring_ctrl': get_class_methods(
            (root_path / "ui/controllers/exploring_controller.py").read_text(encoding='utf-8'),
            "ExploringController"
        ),
        '_layer_sync_ctrl': get_class_methods(
            (root_path / "ui/controllers/layer_sync_controller.py").read_text(encoding='utf-8'),
            "LayerSyncController"
        ),
        '_property_ctrl': get_class_methods(
            (root_path / "ui/controllers/property_controller.py").read_text(encoding='utf-8'),
            "PropertyController"
        ),
    }
    
    # Vérifier les appels de méthodes
    for call in result.method_calls:
        if call.object_name in controller_methods:
            if call.method_name not in controller_methods[call.object_name]:
                # Ignorer si hasattr() est utilisé (pattern de compatibilité)
                if 'hasattr' not in call.context:
                    result.missing_methods.append((call.object_name, call.method_name, call.line))
                    print(f"  ❌ Ligne {call.line}: {call.object_name}.{call.method_name}() manquante")
    
    print(f"  ✅ {len(result.method_calls)} appels de méthodes analysés")
    print(f"  ✅ {len(result.attribute_accesses)} accès d'attributs analysés")
    
    if result.missing_methods:
        print(f"  ⚠️  {len(result.missing_methods)} méthodes manquantes détectées")
    else:
        print(f"  ✅ Aucune méthode manquante")
    
    return result

def analyze_app_delegations(app_path: Path, root_path: Path) -> AnalysisResult:
    """Analyse les délégations de l'app vers les services."""
    result = AnalysisResult(file_path=str(app_path))
    
    with open(app_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    # Parse AST
    analyzer = DelegationAnalyzer(source_code)
    try:
        tree = ast.parse(source_code)
        analyzer.visit(tree)
    except SyntaxError as e:
        print(f"⚠️  Erreur de syntaxe: {e}")
        return result
    
    result.method_calls = analyzer.method_calls
    
    # Charger les méthodes des services principaux
    service_methods = {}
    services_to_check = [
        ('_get_layer_lifecycle_service', 'core/services/layer_lifecycle_service.py', 'LayerLifecycleService'),
        ('_get_task_management_service', 'core/services/task_management_service.py', 'TaskManagementService'),
        ('_get_filter_service', 'core/services/filter_service.py', 'FilterService'),
        ('_get_layer_service', 'core/services/layer_service.py', 'LayerService'),
    ]
    
    for service_getter, service_file, class_name in services_to_check:
        service_path = root_path / service_file
        if service_path.exists():
            service_methods[service_getter] = get_class_methods(
                service_path.read_text(encoding='utf-8'),
                class_name
            )
    
    # Vérifier les appels
    for call in result.method_calls:
        if call.object_name in service_methods:
            if call.method_name not in service_methods[call.object_name]:
                result.missing_methods.append((call.object_name, call.method_name, call.line))
                print(f"  ❌ Ligne {call.line}: {call.object_name}().{call.method_name}() manquante")
    
    print(f"  ✅ {len(result.method_calls)} appels de services analysés")
    
    if result.missing_methods:
        print(f"  ⚠️  {len(result.missing_methods)} méthodes manquantes détectées")
    else:
        print(f"  ✅ Aucune méthode manquante")
    
    return result

def analyze_controller_cross_delegations(controllers_path: Path, root_path: Path) -> AnalysisResult:
    """Analyse les délégations entre controllers."""
    result = AnalysisResult(file_path=str(controllers_path))
    
    # Liste des controllers à analyser
    controllers = [
        'backend_controller.py',
        'favorites_controller.py',
        'exploring_controller.py',
        'layer_sync_controller.py',
        'property_controller.py',
        'filtering_controller.py',
    ]
    
    total_calls = 0
    for controller_file in controllers:
        controller_path = controllers_path / controller_file
        if not controller_path.exists():
            continue
        
        with open(controller_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        analyzer = DelegationAnalyzer(source_code)
        try:
            tree = ast.parse(source_code)
            analyzer.visit(tree)
            total_calls += len(analyzer.method_calls)
        except SyntaxError as e:
            print(f"  ⚠️  Erreur de syntaxe dans {controller_file}: {e}")
    
    print(f"  ✅ {total_calls} délégations inter-controllers analysées")
    
    return result

def generate_report(results: Dict[str, AnalysisResult], output_path: Path):
    """Génère un rapport détaillé des régressions."""
    timestamp = "20260116"
    report_path = output_path / f"DELEGATION-REGRESSION-REPORT-{timestamp}.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Rapport de Vérification des Délégations - FilterMate v4.0-alpha\n\n")
        f.write(f"**Date**: 2026-01-16\n")
        f.write(f"**Version**: v4.0-alpha (Migration Hexagonale)\n\n")
        
        f.write("## 📊 Résumé Exécutif\n\n")
        
        total_missing = sum(len(r.missing_methods) for r in results.values())
        total_calls = sum(len(r.method_calls) for r in results.values())
        
        if total_missing == 0:
            f.write("✅ **Aucune régression de délégation détectée**\n\n")
            f.write(f"- **Total d'appels vérifiés**: {total_calls}\n")
            f.write(f"- **Méthodes manquantes**: 0\n")
            f.write(f"- **Taux de réussite**: 100%\n\n")
        else:
            f.write(f"⚠️  **{total_missing} régressions détectées**\n\n")
            f.write(f"- **Total d'appels vérifiés**: {total_calls}\n")
            f.write(f"- **Méthodes manquantes**: {total_missing}\n")
            f.write(f"- **Taux de réussite**: {((total_calls - total_missing) / total_calls * 100):.1f}%\n\n")
        
        # Détails par fichier
        f.write("## 📁 Analyse Détaillée\n\n")
        
        for name, result in results.items():
            f.write(f"### {name.upper()}\n\n")
            f.write(f"**Fichier**: `{result.file_path}`\n\n")
            
            f.write(f"- Appels de méthodes: {len(result.method_calls)}\n")
            f.write(f"- Accès d'attributs: {len(result.attribute_accesses)}\n")
            f.write(f"- Méthodes manquantes: {len(result.missing_methods)}\n\n")
            
            if result.missing_methods:
                f.write("#### ❌ Méthodes Manquantes\n\n")
                for obj, method, line in result.missing_methods:
                    f.write(f"- Ligne {line}: `{obj}.{method}()`\n")
                f.write("\n")
            else:
                f.write("✅ Aucune méthode manquante\n\n")
        
        # Recommandations
        if total_missing > 0:
            f.write("## 🔧 Recommandations\n\n")
            f.write("### Actions Immédiates\n\n")
            
            for name, result in results.items():
                if result.missing_methods:
                    f.write(f"**{name}**:\n\n")
                    for obj, method, line in result.missing_methods:
                        f.write(f"1. Implémenter `{method}()` dans la classe correspondant à `{obj}`\n")
                        f.write(f"   - OU supprimer l'appel ligne {line} si obsolète\n")
                        f.write(f"   - OU ajouter une vérification `hasattr()` pour compatibilité\n\n")
        
        f.write("## ✅ Conclusion\n\n")
        if total_missing == 0:
            f.write("Toutes les délégations sont correctement implémentées. ")
            f.write("La migration hexagonale n'a introduit aucune régression au niveau des délégations.\n")
        else:
            f.write(f"{total_missing} régressions détectées nécessitent une correction. ")
            f.write("Voir les recommandations ci-dessus.\n")
    
    print(f"\n📄 Rapport généré: {report_path}")
    return report_path

def main():
    """Point d'entrée principal."""
    print("=" * 80)
    print("FilterMate - Vérification des Délégations (Régressions)")
    print("=" * 80)
    
    # Déterminer le chemin racine
    script_path = Path(__file__).resolve()
    root_path = script_path.parent.parent
    
    print(f"\n📂 Répertoire du projet: {root_path}")
    
    # Exécuter l'analyse
    results = verify_delegation(root_path)
    
    # Générer le rapport
    output_path = root_path / "_bmad-output"
    output_path.mkdir(exist_ok=True)
    report_path = generate_report(results, output_path)
    
    # Résumé final
    print("\n" + "=" * 80)
    total_missing = sum(len(r.missing_methods) for r in results.values())
    if total_missing == 0:
        print("✅ SUCCÈS: Aucune régression de délégation détectée")
        return 0
    else:
        print(f"⚠️  ATTENTION: {total_missing} régressions détectées - voir {report_path}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
