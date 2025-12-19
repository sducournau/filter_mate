---
sidebar_position: 1
---

# Premiers pas

Bienvenue sur FilterMate ! Ces tutoriels vous aideront à devenir productif rapidement.

## Tutoriels de cette section

### [Démarrage rapide](/docs/getting-started/quick-start)
**Durée : 5 minutes**

Apprenez le flux de travail essentiel :
- Ouvrir FilterMate et sélectionner des couches
- Créer votre premier filtre d'attributs
- Comprendre la sélection du backend
- Exporter les résultats filtrés

### [Votre premier filtre](/docs/getting-started/first-filter)
**Durée : 10-15 minutes**

Tutoriel complet étape par étape :
- Configurer un filtre géométrique
- Utiliser les opérations de tampon
- Travailler avec les prédicats spatiaux
- Réviser et exporter les résultats

## Avant de commencer

Assurez-vous d'avoir :

- ✅ **QGIS 3.x** installé
- ✅ **Plugin FilterMate** installé ([Guide d'installation](/docs/installation))
- ✅ **Couche vectorielle** chargée dans votre projet

## Conseils de performance

Pour de meilleurs résultats avec de grands jeux de données :

- 📦 **Jeux de données moyens** (&lt;50k entités) : Spatialite/OGR fonctionnent bien
- ⚡ **Grands jeux de données** (&gt;50k entités) : Installez `psycopg2` pour le support PostgreSQL
- 🗄️ **Très grands jeux de données** (&gt;1M entités) : Utilisez des couches PostGIS

## Tutoriel vidéo

Vous préférez la vidéo ? Regardez notre présentation complète :

[![Démo FilterMate](https://img.youtube.com/vi/2gOEPrdl2Bo/0.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Prochaines étapes

Après avoir terminé ces tutoriels :

1. **[Aperçu de l'interface](/docs/user-guide/interface-overview)** - Explorez tous les composants de l'interface
2. **[Bases du filtrage](/docs/user-guide/filtering-basics)** - Maîtrisez le filtrage d'attributs
3. **[Filtrage géométrique](/docs/user-guide/geometric-filtering)** - Opérations spatiales avancées
4. **[Aperçu des backends](/docs/backends/overview)** - Comprendre l'optimisation des performances

:::tip Besoin d'aide ?
Visitez [GitHub Issues](https://github.com/sducournau/filter_mate/issues) pour signaler des problèmes.
:::
