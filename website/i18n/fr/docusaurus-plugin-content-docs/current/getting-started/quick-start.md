---
sidebar_position: 2
---

# Démarrage rapide

Démarrez avec FilterMate en 5 minutes ! Ce guide couvre le flux de travail essentiel.

## Étape 1 : Ouvrir FilterMate

1. Dans QGIS, chargez une couche vectorielle (n'importe quel format : Shapefile, GeoPackage, PostGIS, etc.)

<img src="/filter_mate/img/quickstart-1.png" alt="quickstart-1" width="500"/>

*QGIS avec une couche vectorielle chargée et prête pour le filtrage*

2. Cliquez sur l'icône **FilterMate** dans la barre d'outils, ou allez dans **Extensions** → **FilterMate**

<img src="/filter_mate/img/install-4.png" alt="install-4" width="500"/>

*Ouverture de FilterMate depuis la barre d'outils*

3. Le panneau ancrable FilterMate apparaîtra

<img src="/filter_mate/img/quickstart-3.png" alt="quickstart-3" width="500"/>

*Panneau FilterMate ancré sur le côté droit de QGIS*

:::tip Première fois ?
FilterMate détectera automatiquement le type de votre couche et sélectionnera le backend optimal (PostgreSQL, Spatialite ou OGR).
:::

## Étape 2 : Sélectionnez votre couche

1. Dans le menu déroulant **Sélection de couche** en haut du panneau
2. Choisissez la couche que vous souhaitez filtrer
3. FilterMate chargera les paramètres spécifiques à la couche et affichera les champs pertinents

*Couche sélectionnée avec expression de filtre prête à être appliquée*

## Étape 3 : Créer un filtre

### Option A : Filtre d'attributs

Pour filtrer par attributs (par ex., population > 10 000) :

1. Allez dans l'onglet **Filtre d'attributs**
2. Entrez une expression QGIS comme :
   ```
   "population" > 10000
   ```
3. Cliquez sur **Appliquer le filtre**

### Option B : Filtre géométrique

Pour le filtrage spatial (par ex., bâtiments à moins de 100m d'une route) :

1. Allez dans l'onglet **Filtre géométrique**
2. Sélectionnez une **couche de référence** (par ex., routes)
3. Choisissez un **prédicat spatial** (par ex., "à distance de")
4. Définissez une **distance de tampon** (par ex., 100 mètres)
5. Cliquez sur **Appliquer le filtre**

:::info Sélection du backend
FilterMate utilise automatiquement le meilleur backend pour vos données :
- **PostgreSQL** : Pour les couches PostGIS (le plus rapide, nécessite psycopg2)
- **Spatialite** : Pour les bases de données Spatialite
- **OGR** : Pour les Shapefiles, GeoPackage, etc.
:::

## Étape 4 : Examiner les résultats

Après avoir appliqué le filtre :

- Les entités filtrées sont **mises en surbrillance** sur la carte
- Le **nombre d'entités** se met à jour dans le panneau
- Utilisez l'onglet **Historique** pour annuler/rétablir les filtres

## Étape 5 : Exporter (Optionnel)

Pour exporter les entités filtrées :

1. Allez dans l'onglet **Export**
2. Choisissez le **format d'export** (GeoPackage, Shapefile, PostGIS, etc.)
3. Configurez le **SCR** et autres options
4. Cliquez sur **Exporter**

## Flux de travail courants

### Filtrer par plusieurs critères

Combinez les filtres d'attributs et géométriques :

```python
# Filtre d'attributs
"population" > 10000 AND "type" = 'residential'

# Puis appliquer le filtre géométrique
# à moins de 500m du centre-ville
```

### Annuler/Rétablir les filtres

1. Allez dans l'onglet **Historique**
2. Cliquez sur **Annuler** pour annuler le dernier filtre
3. Cliquez sur **Rétablir** pour réappliquer

### Enregistrer les paramètres de filtre

FilterMate enregistre automatiquement les paramètres par couche :
- Expressions de filtre
- Distances de tampon
- Préférences d'export

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
- ✅ La couche est modifiable (déverrouillez si nécessaire)
- ✅ Aucun autre filtre n'est déjà appliqué

### Performances lentes ?

Solutions :
- ⚡ Passez à une couche PostGIS avec psycopg2 installé
- 🔧 Simplifiez les expressions de filtre complexes
- 📊 Créez des index spatiaux sur vos couches
- 💾 Réduisez la taille du jeu de données si possible

## Besoin d'aide ?

- 📖 [Guide utilisateur complet](../user-guide/introduction.md)
- 🐛 [Signaler un bug](https://github.com/sducournau/filter_mate/issues)
- 💬 [Poser une question](https://github.com/sducournau/filter_mate/discussions)
