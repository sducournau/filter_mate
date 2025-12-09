---
sidebar_position: 2
---

# Installation

FilterMate est disponible via le dépôt de plugins QGIS et fonctionne directement avec n'importe quelle installation QGIS.

## Installation de base

1. Ouvrez QGIS
2. Allez dans **Extensions** → **Installer/Gérer les extensions**

 <img src="/filter_mate/img/install-1.png" alt="install-1" width="500"/>
 
*Gestionnaire d'extensions QGIS - Recherche de FilterMate*

3. Recherchez **"FilterMate"**

 <img src="/filter_mate/img/install-2.png" alt="install-2" width="500"/>

*Résultats de recherche affichant le plugin FilterMate*

4. Cliquez sur **Installer l'extension**

*FilterMate installé avec succès et prêt à l'emploi*

C'est tout ! FilterMate est maintenant prêt à être utilisé avec les backends OGR et Spatialite.

## Optionnel : Backend PostgreSQL (Recommandé pour les grands jeux de données)

Pour des performances optimales avec les couches PostgreSQL/PostGIS, installez le package `psycopg2`.

:::tip Amélioration des performances
Le backend PostgreSQL offre un **filtrage 10 à 50× plus rapide** sur les grands jeux de données (>50 000 entités) par rapport aux autres backends.
:::

### Méthode 1 : pip (Recommandé)

```bash
pip install psycopg2-binary
```

### Méthode 2 : Console Python de QGIS

1. Ouvrez la Console Python de QGIS (**Extensions** → **Console Python**)
2. Exécutez :

```python
import pip
pip.main(['install', 'psycopg2-binary'])
```

### Méthode 3 : Shell OSGeo4W (Windows)

1. Ouvrez le **Shell OSGeo4W** en tant qu'Administrateur
2. Exécutez :

```bash
py3_env
pip install psycopg2-binary
```

### Vérifier l'installation

Vérifiez si le backend PostgreSQL est disponible :

```python
from modules.appUtils import POSTGRESQL_AVAILABLE
print(f"PostgreSQL disponible : {POSTGRESQL_AVAILABLE}")
```

Si `True`, vous êtes prêt ! Le backend PostgreSQL sera utilisé automatiquement pour les couches PostGIS.

## Sélection du backend

FilterMate sélectionne automatiquement le backend optimal en fonction de votre source de données :

| Source de données | Backend utilisé | Installation requise |
|-------------------|-----------------|---------------------|
| PostgreSQL/PostGIS | PostgreSQL (si psycopg2 installé) | Optionnel : psycopg2 |
| Spatialite | Spatialite | Aucune (intégré) |
| Shapefile, GeoPackage, etc. | OGR | Aucune (intégré) |

En savoir plus sur les backends dans [Aperçu des backends](./backends/overview.md).

## Dépannage

### PostgreSQL n'est pas utilisé ?

**Vérifiez si psycopg2 est installé :**

```python
try:
    import psycopg2
    print("✅ psycopg2 installé")
except ImportError:
    print("❌ psycopg2 non installé")
```

**Problèmes courants :**
- La couche ne provient pas d'une source PostgreSQL → Utilisez des couches PostGIS
- psycopg2 n'est pas dans l'environnement Python de QGIS → Réinstallez dans le bon environnement
- Les informations d'identification de connexion ne sont pas enregistrées → Vérifiez les paramètres de la source de données de la couche

## Prochaines étapes

- [Tutoriel de démarrage rapide](./getting-started/quick-start.md) - Apprenez les bases
- [Premier filtre](./getting-started/first-filter.md) - Créez votre premier filtre
- [Benchmarks de performance](./backends/performance-benchmarks.md) - Comprendre les performances des backends
