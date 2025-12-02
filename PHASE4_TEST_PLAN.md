# FilterMate Phase 4 - Plan de Test et Validation

## 🎯 Objectif Phase 4

Valider que FilterMate v1.9.0 fonctionne correctement avec tous les backends (PostgreSQL, Spatialite, OGR) dans un environnement QGIS réel.

**Critères de succès** :
- ✅ Tous les backends fonctionnent sans erreur
- ✅ Performances acceptables (voir benchmarks ci-dessous)
- ✅ Aucune régression PostgreSQL (v1.9 = v1.8 pour PostgreSQL)
- ✅ Messages utilisateur clairs et pertinents
- ✅ Export des données filtrées fonctionne

---

## 📋 Checklist Pré-Tests

### Environnement QGIS

- [ ] QGIS 3.x installé (version ≥ 3.22 recommandée)
- [ ] Plugin FilterMate v1.9.0 installé
- [ ] Console Python QGIS accessible (Plugins > Console Python)

### Données de Test Requises

Préparer au minimum :

#### 1. Couche PostgreSQL/PostGIS (si psycopg2 disponible)
- [ ] Base de données PostGIS accessible
- [ ] Couche avec ≥ 10,000 features
- [ ] Géométrie : Point, Line ou Polygon
- [ ] Au moins 2-3 attributs (nom, population, etc.)

#### 2. Couche Spatialite
- [ ] Fichier .sqlite avec extension Spatialite
- [ ] Couche avec ≥ 5,000 features
- [ ] Géométrie : Point, Line ou Polygon
- [ ] Au moins 2-3 attributs

#### 3. Couches OGR (Shapefile/GeoPackage)
- [ ] 1 Shapefile (.shp) avec ≥ 1,000 features
- [ ] 1 GeoPackage (.gpkg) avec ≥ 5,000 features
- [ ] Géométrie variée

#### 4. Données de Performance (optionnel mais recommandé)
- [ ] 1 couche avec 50,000-100,000 features (tester limites)
- [ ] 1 couche avec > 500,000 features (si PostgreSQL disponible)

### Scripts de Test

- [ ] `test_qgis_interactive.py` présent dans le répertoire plugin
- [ ] `benchmark_performance.py` présent dans le répertoire plugin
- [ ] Permissions d'exécution configurées

---

## 🧪 Tests Fonctionnels

### Test 1 : Vérification Disponibilité Backends

**Objectif** : Confirmer quels backends sont disponibles

**Procédure** :
1. Ouvrir QGIS
2. Console Python > copier-coller `test_qgis_interactive.py`
3. Observer les messages de vérification

**Résultats attendus** :
```
✅ psycopg2 installé - PostgreSQL disponible (ou ⚠️ non installé)
✅ Extension Spatialite chargée
✅ OGR disponible (toujours)
```

**Validation** :
- [ ] PostgreSQL : Installé ou message clair si absent
- [ ] Spatialite : Extension chargée sans erreur
- [ ] OGR : Toujours disponible

---

### Test 2 : Filtrage Simple (1=1)

**Objectif** : Tester filtrage basique sur chaque backend

**Procédure** :
1. Charger les couches de test dans QGIS
2. Lancer `test_qgis_interactive.py`
3. Confirmer tests (répondre 'o')

**Critères de succès** :

| Backend    | Condition                          | Temps attendu         |
|------------|------------------------------------|-----------------------|
| PostgreSQL | < 50k features                     | < 3s                  |
| PostgreSQL | 50k-100k features                  | < 5s                  |
| Spatialite | < 10k features                     | < 3s                  |
| Spatialite | 10k-50k features                   | < 10s                 |
| OGR        | < 5k features                      | < 5s                  |
| OGR        | 5k-10k features                    | < 15s                 |

**Validation** :
- [ ] Tous les backends testés fonctionnent sans erreur
- [ ] Temps de réponse dans les limites acceptables
- [ ] Nombre de features filtrées = nombre total (pour 1=1)
- [ ] Couche réinitialisée après test (setSubsetString(""))

---

### Test 3 : Filtrage Attributaire

**Objectif** : Tester expressions avec attributs

**Expressions à tester** :

1. **Simple** : `"population" > 10000`
2. **Texte** : `"name" ILIKE '%paris%'` (insensible à la casse)
3. **Numérique** : `"area" BETWEEN 100 AND 1000`
4. **Logique** : `("population" > 5000) AND ("type" = 'city')`

**Procédure** :
1. Ouvrir FilterMate dans QGIS
2. Sélectionner une couche
3. Saisir l'expression dans le champ de filtre
4. Cliquer "Filter"
5. Observer résultats et messages

**Validation pour chaque backend** :
- [ ] Expression appliquée sans erreur
- [ ] Nombre de features filtrées cohérent
- [ ] Message de confirmation affiché
- [ ] Temps de traitement acceptable
- [ ] Export des résultats possible

**Attention Spatialite** :
- [ ] Vérifier conversion `ILIKE` → `LOWER() LIKE LOWER()`
- [ ] Vérifier message info "Filtering with Spatialite backend..."

---

### Test 4 : Filtrage Spatial

**Objectif** : Tester fonctions spatiales

**Expressions à tester** :

1. **Buffer** : `ST_Buffer(geometry, 1000) IS NOT NULL`
2. **Aire** : `ST_Area(geometry) > 100000` (pour Polygones)
3. **Longueur** : `ST_Length(geometry) > 1000` (pour Lignes)
4. **Intersection** : `ST_Intersects(geometry, ST_GeomFromText('POLYGON(...)', 4326))`

**Procédure** :
Même que Test 3, mais avec expressions spatiales

**Validation** :
- [ ] PostgreSQL : Toutes fonctions PostGIS fonctionnent
- [ ] Spatialite : Fonctions Spatialite équivalentes fonctionnent (~90% compatibilité)
- [ ] OGR : Filtrage local fonctionne (peut être lent)

**Notes** :
- Spatialite utilise syntaxe similaire à PostGIS
- Certaines fonctions avancées peuvent différer légèrement

---

### Test 5 : Type Casting

**Objectif** : Vérifier conversion types de données

**Expressions à tester** :

1. **PostgreSQL** : `"population"::real / "area"::real > 100`
2. **Spatialite** (conversion attendue) : `CAST("population" AS REAL) / CAST("area" AS REAL) > 100`

**Procédure** :
1. Tester expression PostgreSQL sur couche PostgreSQL
2. Tester même expression sur couche Spatialite
3. Vérifier conversion automatique

**Validation** :
- [ ] PostgreSQL : Syntaxe `::` fonctionne
- [ ] Spatialite : Conversion automatique `::` → `CAST()` fonctionne
- [ ] Résultats équivalents entre backends

---

### Test 6 : Actions Reset et Unfilter

**Objectif** : Tester autres actions FilterMate

**Procédure** :
1. Appliquer un filtre sur une couche
2. Cliquer "Reset" → devrait réinitialiser le filtre
3. Appliquer à nouveau un filtre
4. Cliquer "Unfilter" → devrait supprimer le filtre

**Validation** :
- [ ] Reset : Filtre supprimé, couche affiche toutes les features
- [ ] Unfilter : Même comportement
- [ ] Messages de confirmation affichés
- [ ] Fonctionne pour tous les backends

---

### Test 7 : Messages Utilisateur

**Objectif** : Vérifier pertinence des messages

**Scénarios** :

1. **Performance warning (Spatialite > 50k)** :
   - Charger couche Spatialite > 50,000 features
   - Appliquer filtre
   - **Attendu** : Message info suggérant PostgreSQL pour grandes données

2. **Backend information** :
   - Filtrer couche Spatialite
   - **Attendu** : "Filtering with Spatialite backend..."
   
3. **Erreur extension Spatialite** :
   - Simuler absence extension (difficile)
   - **Attendu** : Message d'erreur clair avec instructions

**Validation** :
- [ ] Messages apparaissent dans la barre de message QGIS
- [ ] Messages clairs et informatifs (pas de jargon technique excessif)
- [ ] Durée d'affichage appropriée (3-8s selon importance)
- [ ] Niveau de message correct (Info/Warning/Error)

---

### Test 8 : Non-Régression PostgreSQL

**Objectif** : Garantir aucune régression fonctionnalité PostgreSQL

**Procédure** :
1. Charger couche PostgreSQL/PostGIS
2. Appliquer filtre complexe (attributaire + spatial)
3. Mesurer temps de réponse
4. Comparer avec v1.8 (si disponible)

**Validation** :
- [ ] Performances identiques ou meilleures que v1.8
- [ ] Aucune erreur nouvelle
- [ ] Vues matérialisées créées correctement
- [ ] Export fonctionne

**Critères stricts** :
- Aucune différence de comportement entre v1.8 et v1.9 pour PostgreSQL
- Code PostgreSQL identique (sauf ajout flag `POSTGRESQL_AVAILABLE`)

---

## 📊 Tests de Performance (Benchmarks)

### Exécution Benchmarks

**Procédure** :
1. Charger toutes les couches de test (variété de tailles)
2. Console Python QGIS
3. `exec(open('benchmark_performance.py').read())`
4. Confirmer exécution (répondre 'y')
5. Attendre fin des tests (peut prendre plusieurs minutes)
6. Consulter rapport généré

### Métriques à Collecter

Pour chaque combinaison (Backend × Taille de données) :

- **Durée filtrage** (secondes)
- **Taux** (features/seconde)
- **Type de filtre** : Simple, Spatial, Complexe

### Critères de Performance

#### PostgreSQL (Objectif : Excellence)

| Features  | Simple   | Spatial  | Complexe |
|-----------|----------|----------|----------|
| < 10k     | < 1s     | < 1s     | < 2s     |
| 50k       | < 3s     | < 3s     | < 5s     |
| 100k      | < 5s     | < 5s     | < 10s    |
| 500k      | < 15s    | < 15s    | < 30s    |

**Validation** :
- [ ] Tous les critères respectés
- [ ] Performances comparables à v1.8

#### Spatialite (Objectif : Acceptable)

| Features  | Simple   | Spatial  | Complexe |
|-----------|----------|----------|----------|
| < 5k      | < 2s     | < 3s     | < 5s     |
| 10k       | < 5s     | < 8s     | < 12s    |
| 50k       | < 10s    | < 15s    | < 25s    |
| 100k      | < 20s    | < 30s    | < 45s    |

**Validation** :
- [ ] Performances acceptables < 50k features
- [ ] Warning affiché pour > 50k features
- [ ] Pas de crash/timeout

#### OGR Local (Objectif : Fonctionnel)

| Features  | Simple   | Spatial  | Complexe |
|-----------|----------|----------|----------|
| < 1k      | < 3s     | < 5s     | < 8s     |
| 5k        | < 10s    | < 15s    | < 25s    |
| 10k       | < 20s    | < 30s    | < 60s    |

**Validation** :
- [ ] Fonctionne pour petites données
- [ ] Utilisable en dernier recours
- [ ] Messages informatifs clairs

### Analyse Comparative

**Questions à répondre** :

1. **Quel est le seuil optimal pour chaque backend ?**
   - PostgreSQL : recommandé pour > _____ features
   - Spatialite : acceptable jusqu'à _____ features
   - OGR : limite pratique à _____ features

2. **Quelle dégradation entre backends ?**
   - Spatialite vs PostgreSQL : _____ x plus lent
   - OGR vs PostgreSQL : _____ x plus lent

3. **Recommandations mises à jour** :
   - Mettre à jour INSTALLATION.md si nécessaire
   - Ajuster seuils de warning dans le code

---

## 🐛 Tests de Robustesse

### Test 9 : Gestion Erreurs

**Scénarios à tester** :

1. **Expression invalide** :
   - Saisir `invalid_field > 100`
   - **Attendu** : Message d'erreur clair

2. **Connexion DB perdue** (PostgreSQL) :
   - Déconnecter DB pendant filtrage
   - **Attendu** : Erreur capturée, message informatif

3. **Fichier Spatialite verrouillé** :
   - Ouvrir .sqlite dans autre app
   - Tenter filtrage
   - **Attendu** : Erreur de verrouillage signalée

4. **Extension Spatialite manquante** :
   - (Difficile à simuler)
   - **Attendu** : Message détaillé avec lien aide

**Validation** :
- [ ] Aucun crash de QGIS
- [ ] Messages d'erreur clairs et actionnables
- [ ] Logs d'erreur consultables (console Python)

---

### Test 10 : Cas Limites

**Scénarios** :

1. **Couche vide (0 features)** :
   - Appliquer filtre
   - **Attendu** : Fonctionne sans erreur

2. **Filtre qui retourne 0 résultats** :
   - Expression qui ne matche rien
   - **Attendu** : Message "0 features filtrées"

3. **Très grand nombre de features** (> 1M) :
   - PostgreSQL uniquement
   - **Attendu** : Fonctionne, temps acceptable

4. **Géométries invalides** :
   - Couche avec géométries corrompues
   - **Attendu** : Erreur signalée, pas de crash

**Validation** :
- [ ] Tous les cas gérés proprement
- [ ] Aucune exception non capturée

---

## 📝 Documentation Validation

### Vérifier Cohérence Documentation

- [ ] **INSTALLATION.md** :
  - Instructions claires et à jour
  - Tableau comparatif backends précis
  - Procédures installation testées
  
- [ ] **MIGRATION_v1.8_to_v1.9.md** :
  - Guide migration complet
  - Pas d'information obsolète
  
- [ ] **CHANGELOG.md** :
  - Toutes les modifications documentées
  - Benchmarks théoriques cohérents avec résultats réels
  
- [ ] **metadata.txt** :
  - Version 1.9.0
  - Description précise
  - Changelog à jour

---

## ✅ Critères d'Acceptation Phase 4

### Fonctionnalité

- [ ] Tous les backends fonctionnent sans erreur critique
- [ ] Expressions QGIS converties correctement pour Spatialite
- [ ] Actions Filter/Reset/Unfilter opérationnelles
- [ ] Export des données filtrées fonctionne

### Performance

- [ ] PostgreSQL : Performances identiques v1.8
- [ ] Spatialite : Acceptable < 50k features
- [ ] OGR : Fonctionnel < 10k features
- [ ] Warnings performance affichés au bon moment

### Qualité

- [ ] Aucune régression PostgreSQL
- [ ] Messages utilisateur clairs et pertinents
- [ ] Gestion d'erreurs robuste
- [ ] Aucun crash QGIS

### Documentation

- [ ] Documentation complète et précise
- [ ] Benchmarks réels documentés
- [ ] Instructions installation validées

---

## 🚀 Passage en Phase 5

Une fois tous les critères Phase 4 validés :

1. **Mise à jour documentation** avec benchmarks réels
2. **Corrections bugs** découverts pendant tests
3. **Commit final Phase 4** avec résultats benchmarks
4. **Préparation Phase 5** : Beta testing communautaire

---

## 📧 Rapport de Test (Template)

```markdown
# FilterMate v1.9.0 - Rapport de Test Phase 4

**Date** : [Date]
**Testeur** : [Nom]
**Environnement** :
- OS : [Windows/Linux/macOS]
- QGIS : [Version]
- Python : [Version]
- psycopg2 : [Installé/Non installé]

## Résultats Tests Fonctionnels

- [ ] Test 1 : Backends disponibles
- [ ] Test 2 : Filtrage simple
- [ ] Test 3 : Filtrage attributaire
- [ ] Test 4 : Filtrage spatial
- [ ] Test 5 : Type casting
- [ ] Test 6 : Reset/Unfilter
- [ ] Test 7 : Messages utilisateur
- [ ] Test 8 : Non-régression PostgreSQL
- [ ] Test 9 : Gestion erreurs
- [ ] Test 10 : Cas limites

## Benchmarks Performance

[Coller résultats benchmark_performance.py]

## Bugs Découverts

1. [Description bug 1]
2. [Description bug 2]
...

## Recommandations

[Suggestions d'amélioration]

## Conclusion

[✅ Phase 4 validée / ❌ Corrections nécessaires]
```

---

**Note** : Ce plan de test est exhaustif mais flexible. Adapter selon disponibilité des données et du temps.
