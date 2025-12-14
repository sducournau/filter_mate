---
sidebar_position: 2
---

# Démarrage rapide

Démarrez avec FilterMate en 5 minutes ! Ce guide couvre le flux de travail essentiel.

:::info Version 2.3.0
Ce guide est mis à jour pour FilterMate v2.3.0 avec Annuler/Rétablir intelligent et préservation automatique des filtres.
:::

## Étape 1 : Ouvrir FilterMate

1. Dans QGIS, chargez une couche vectorielle (n'importe quel format : Shapefile, GeoPackage, PostGIS, etc.)

<img src="/filter_mate/img/quickstart-1.png" alt="quickstart-1" width="500"/>

*QGIS avec une couche vectorielle chargée et prête pour le filtrage*

2. Cliquez sur l'icône **FilterMate** dans la barre d'outils, ou allez dans **Extensions** → **FilterMate**

<img src="/filter_mate/img/install-4.png" alt="install-4" width="500"/>

*Ouverture de FilterMate depuis la barre d'outils*

3. Le panneau ancrable FilterMate apparaîtra (s'active automatiquement quand des couches sont ajoutées !)

<img src="/filter_mate/img/quickstart-3.png" alt="quickstart-3" width="500"/>

*Panneau FilterMate ancré sur le côté droit de QGIS*

:::tip Première fois ?
FilterMate détectera automatiquement le type de votre couche et sélectionnera le backend optimal (PostgreSQL, Spatialite ou OGR). Pour les SCR géographiques (EPSG:4326), les opérations métriques sont automatiquement converties en EPSG:3857 pour plus de précision.
:::

## Étape 2 : Sélectionnez votre couche

1. Dans le menu déroulant **Sélection de couche** en haut du panneau
2. Choisissez la couche que vous souhaitez filtrer
3. FilterMate chargera les paramètres spécifiques à la couche et affichera les champs pertinents

*Couche sélectionnée avec expression de filtre prête à être appliquée*

## Étape 3 : Explorer et sélectionner des entités

FilterMate offre plusieurs méthodes de sélection dans la section **Exploration** :

### Sélection simple
Utilisez le widget **Sélecteur d'entités** pour sélectionner des entités individuelles en cliquant sur la carte ou en choisissant dans un menu déroulant.

### Sélection multiple
Développez le groupe **Sélection multiple** pour sélectionner plusieurs entités à la fois à l'aide de cases à cocher.

### Expression personnalisée
Développez le groupe **Expression personnalisée** pour créer des expressions QGIS complexes pour le filtrage :

```sql
"population" > 10000 AND "type" = 'residential'
```

## Étape 4 : Appliquer les filtres

### Options de filtrage

Dans la section **Filtrage**, configurez votre filtre :

1. **Couches à filtrer** : Sélectionnez les couches qui seront filtrées (source + couches distantes)
2. **Opérateur de combinaison** : Choisissez comment les nouveaux filtres interagissent avec les existants :
   - **AND** (par défaut) : Combine les filtres (intersection)
   - **OR** : Union des filtres
   - **AND NOT** : Filtre d'exclusion
3. **Prédicats géométriques** : Sélectionnez les relations spatiales (intersecte, à l'intérieur, contient, etc.)
4. **Tampon** : Ajoutez une distance de tampon à votre filtre géométrique

### Appliquer le filtre

Cliquez sur le bouton **Filtrer** (icône entonnoir) dans la barre d'actions. Le filtre est appliqué à toutes les couches sélectionnées.

:::info Préservation automatique des filtres ⭐ NOUVEAU dans v2.3.0
FilterMate préserve maintenant automatiquement les filtres existants ! Lorsque vous appliquez un nouveau filtre, il est combiné avec les filtres précédents en utilisant l'opérateur sélectionné (AND par défaut). Plus de filtres perdus lors du passage entre filtrage par attributs et géométrique.
:::

:::info Sélection du backend
FilterMate utilise automatiquement le meilleur backend pour vos données :
- **PostgreSQL** : Pour les couches PostGIS (le plus rapide, nécessite psycopg2)
- **Spatialite** : Pour les bases de données Spatialite
- **OGR** : Pour les Shapefiles, GeoPackage, etc.
:::

## Étape 5 : Examiner les résultats

Après avoir appliqué le filtre :

- Les entités filtrées sont **affichées** sur la carte
- Le **nombre d'entités** se met à jour dans la liste des couches
- Les **boutons Annuler/Rétablir** deviennent actifs dans la barre d'actions

## Étape 6 : Annuler/Rétablir les filtres

:::tip Annuler/Rétablir intelligent ⭐ NOUVEAU dans v2.3.0
FilterMate v2.3.0 propose un annuler/rétablir contextuel :
- **Couche source uniquement** : Sans couches distantes sélectionnées, annuler/rétablir n'affecte que la couche source
- **Mode global** : Avec des couches distantes filtrées, annuler/rétablir restaure l'état complet de toutes les couches simultanément
:::

Utilisez les boutons **Annuler** (↩️) et **Rétablir** (↪️) dans la barre d'actions pour naviguer dans l'historique de vos filtres. Les boutons s'activent/désactivent automatiquement selon la disponibilité de l'historique.

## Étape 7 : Exporter (Optionnel)

Pour exporter les entités filtrées :

1. Allez dans la section **Export**
2. Choisissez le **format d'export** (GeoPackage, Shapefile, PostGIS, etc.)
3. Configurez le **SCR** et autres options
4. Cliquez sur **Exporter**

## Flux de travail courants

### Filtrage progressif (Préservation des filtres)

Construisez des filtres complexes étape par étape :

```python
# Étape 1 : Filtre géométrique - sélection par polygone
# Résultat : 150 entités

# Étape 2 : Ajouter un filtre d'attributs avec opérateur AND
"population" > 10000
# Résultat : 23 entités (intersection préservée !)
```

### Filtrage multi-couches

1. Sélectionnez des entités dans votre couche source
2. Activez **Couches à filtrer** et sélectionnez les couches distantes
3. Appliquez le filtre - toutes les couches sélectionnées sont filtrées simultanément
4. Utilisez **Annuler global** pour restaurer toutes les couches en une fois

### Réinitialiser les filtres

Cliquez sur le bouton **Réinitialiser** pour effacer tous les filtres des couches sélectionnées.

## Conseils de performance

### Pour les grands jeux de données (>50 000 entités)

:::tip Utilisez PostgreSQL
Installez psycopg2 et utilisez des couches PostGIS pour un **filtrage 10 à 50× plus rapide** :
```bash
pip install psycopg2-binary
```
:::

### Pour les jeux de données moyens (10 000-50 000 entités)

- Le backend Spatialite fonctionne bien
- Aucune installation supplémentaire nécessaire

### Pour les petits jeux de données (Moins de 10 000 entités)

- N'importe quel backend fonctionnera bien
- Le backend OGR est suffisant

## Feedback configurable

FilterMate v2.3.0 inclut un système de feedback configurable pour réduire la fatigue des notifications :
- **Minimal** : Erreurs critiques uniquement (production)
- **Normal** (par défaut) : Équilibré, infos essentielles
- **Verbose** : Tous les messages (développement)

Configurez dans `config.json` → `APP.DOCKWIDGET.FEEDBACK_LEVEL`

## Prochaines étapes

- **[Tutoriel premier filtre](./first-filter.md)** - Exemple détaillé étape par étape
- **[Bases du filtrage](../user-guide/filtering-basics.md)** - Apprenez les expressions et prédicats
- **[Filtrage géométrique](../user-guide/geometric-filtering.md)** - Opérations spatiales avancées
- **[Comparaison des backends](../backends/performance-benchmarks.md)** - Comprendre les performances des backends

## Dépannage

### Le filtre ne s'applique pas ?

Vérifiez :
- ✅ La syntaxe de l'expression est correcte (utilisez le constructeur d'expressions QGIS)
- ✅ Les noms de champs sont correctement entre guillemets : `"nom_champ"`
- ✅ La couche contient des entités correspondant aux critères

### Performances lentes ?

- Pour les grands jeux de données, envisagez d'[installer le backend PostgreSQL](../installation.md#optional-postgresql-backend-recommended-for-large-datasets)
- Consultez le guide [Optimisation des performances](../advanced/performance-tuning.md)

### Backend non détecté ?

FilterMate affichera quel backend est utilisé. Si PostgreSQL n'est pas disponible :
1. Vérifiez si psycopg2 est installé : `import psycopg2`
2. Vérifiez que la source de la couche est PostgreSQL/PostGIS
3. Voir [Dépannage de l'installation](../installation.md#troubleshooting)

## Besoin d'aide ?

- 📖 [Guide utilisateur complet](../user-guide/introduction.md)
- 🐛 [Signaler un bug](https://github.com/sducournau/filter_mate/issues)
- 💬 [Poser une question](https://github.com/sducournau/filter_mate/discussions)
