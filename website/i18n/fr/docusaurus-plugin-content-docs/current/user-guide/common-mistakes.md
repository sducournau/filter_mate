---
sidebar_position: 8
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Erreurs Courantes et Solutions

Évitez les pièges fréquents et résolvez rapidement les problèmes grâce à ce guide de dépannage.

## Vue d'ensemble

Ce guide documente les erreurs les plus courantes rencontrées par les utilisateurs de FilterMate, avec des solutions claires et des stratégies de prévention.

**Navigation Rapide** :
- [Résultats de Filtre Vides](#1-résultats-de-filtre-vides)
- [Backend PostgreSQL Indisponible](#2-backend-postgresql-indisponible)
- [Performances Lentes](#3-performances-lentes-30-secondes)
- [Résultats Spatiaux Incorrects](#4-résultats-spatiaux-incorrects)
- [Erreurs d'Expression](#5-erreurs-de-syntaxe-dexpression)
- [Échecs d'Export](#6-échecs-dexport)
- [Historique des Filtres Perdu](#7-historique-des-filtres-perdu-après-redémarrage)
- [Problèmes de CRS](#8-problèmes-de-décalage-crs)

---

## 1. Résultats de Filtre Vides {#1-résultats-de-filtre-vides}

**Symptôme** : Le filtre retourne 0 entités, alors que vous attendiez des correspondances.

### Causes Courantes

#### Cause A : Décalage de CRS
**Problème** : Les couches ont des systèmes de coordonnées différents qui ne se chevauchent pas géographiquement.

**Exemple** :
```
Couche 1 : EPSG:4326 (WGS84) - Coordonnées mondiales
Couche 2 : EPSG:2154 (Lambert 93) - France uniquement
```

**Solution** :
✅ FilterMate gère automatiquement la reprojection CRS, mais vérifiez que les couches se chevauchent :
1. Clic droit sur chaque couche → **Zoomer sur la Couche**
2. Vérifiez que les deux couches apparaissent dans la même zone géographique
3. Cherchez l'indicateur 🔄 reprojection dans les logs FilterMate

**Prévention** :
- Utilisez des couches de la même région géographique
- Vérifiez l'étendue de la couche dans Propriétés → Information

---

#### Cause B : Géométries Invalides
**Problème** : Géométries corrompues ou auto-intersectantes empêchant les opérations spatiales.

**Symptômes** :
- "Erreur GEOS" dans les logs
- Résultats incohérents
- Certaines entités manquantes de façon inattendue

**Solution** :
✅ Exécutez la réparation des géométries avant le filtrage :
```bash
# Dans la Boîte à Outils de Traitement QGIS
1. Géométrie vectorielle → Réparer les géométries
2. Entrée : Votre couche problématique
3. Sortie : couche_corrigee
4. Utilisez la couche corrigée dans FilterMate
```

**Vérification Rapide** :
```bash
# Boîte à Outils de Traitement
Géométrie vectorielle → Vérifier la validité
```

---

#### Cause C : Distance de Buffer Trop Petite
**Problème** : La zone tampon n'atteint aucune entité.

**Exemple** :
```
Buffer : 10 mètres
Réalité : L'entité la plus proche est à 50 mètres
Résultat : 0 entités trouvées
```

**Solution** :
✅ Augmentez progressivement la distance du buffer :
```
Essayez : 50m → 100m → 500m → 1000m
```

✅ Testez d'abord sans buffer :
- Utilisez le prédicat "Intersects" sans buffer
- Si cela retourne des résultats, la distance du buffer est le problème

---

#### Cause D : Mauvaises Valeurs d'Attributs
**Problème** : Filtrage pour des valeurs qui n'existent pas dans les données.

**Exemple** :
```sql
-- Votre expression :
city = 'Paris'

-- Valeurs réelles dans les données :
city = 'PARIS' (majuscules)
city = 'Paris, France' (inclut le pays)
```

**Solution** :
✅ Vérifiez d'abord les valeurs réelles des champs :
1. Clic droit sur la couche → **Table d'Attributs**
2. Regardez les valeurs réelles dans le champ
3. Ajustez l'expression pour correspondre exactement

✅ Utilisez une correspondance insensible à la casse :
```sql
-- Au lieu de :
city = 'Paris'

-- Utilisez :
upper(city) = 'PARIS'
-- ou
city ILIKE 'paris'
```

---

#### Cause E : Les Couches ne se Chevauchent pas Géographiquement
**Problème** : La couche de référence et la couche cible sont dans des emplacements différents.

**Exemple** :
```
Cible : Bâtiments à New York
Référence : Routes à Londres
Résultat : Pas de chevauchement = 0 résultats
```

**Solution** :
✅ Vérifiez le chevauchement géographique :
1. Sélectionnez les deux couches dans le Panneau des Couches
2. Clic droit → **Zoomer sur les Couches**
3. Les deux devraient apparaître dans la même vue de carte

---

### Workflow de Débogage pour Résultats Vides

**Étape 1** : Testez avec une expression simple
```sql
1 = 1  -- Devrait retourner TOUTES les entités
```
Si cela échoue → Problème de backend ou de couche

**Étape 2** : Testez le filtre attributaire seul
```sql
-- Supprimez le filtre spatial
-- Test : population > 0
```
Si cela fonctionne → Problème de configuration spatiale

**Étape 3** : Testez le filtre spatial seul
```sql
-- Supprimez le filtre attributaire
-- Utilisez un "Intersects" basique sans buffer
```
Si cela fonctionne → Problème d'expression attributaire

**Étape 4** : Vérifiez les logs
```
QGIS → Vue → Panneaux → Messages de Log → FilterMate
Cherchez les messages d'erreur en rouge
```

---

## 2. Backend PostgreSQL Indisponible {#2-backend-postgresql-indisponible}

**Symptôme** : Message d'avertissement : `Backend PostgreSQL indisponible - utilisation du fallback`

### Cause Racine

**Problème** : Le package Python `psycopg2` n'est pas installé dans l'environnement Python de QGIS.

**Impact** :
- Performances 10-50× plus lentes sur les grands jeux de données
- Pas de vues matérialisées ni de traitement côté serveur
- Repli sur le backend Spatialite ou OGR

---

### Solution : Installer psycopg2

<Tabs>
  <TabItem value="windows" label="Windows" default>
    ```bash
    # Méthode A : Shell OSGeo4W (Recommandé)
    # Ouvrez le Shell OSGeo4W en tant qu'Administrateur
    # Exécutez ces commandes :
    py3_env
    pip install psycopg2-binary
    
    # Méthode B : Console Python QGIS
    # QGIS → Extensions → Console Python
    # Exécutez ce code :
    import subprocess
    subprocess.check_call(['python', '-m', 'pip', 'install', 'psycopg2-binary'])
    ```
  </TabItem>
  
  <TabItem value="linux" label="Linux">
    ```bash
    # Ubuntu/Debian
    sudo apt-get install python3-psycopg2
    
    # Ou via pip
    pip3 install psycopg2-binary
    
    # Vérifier l'installation
    python3 -c "import psycopg2; print(psycopg2.__version__)"
    ```
  </TabItem>
  
  <TabItem value="macos" label="macOS">
    ```bash
    # Via pip (Python QGIS)
    /Applications/QGIS.app/Contents/MacOS/bin/pip3 install psycopg2-binary
    
    # Ou via Homebrew
    brew install postgresql
    pip3 install psycopg2-binary
    ```
  </TabItem>
</Tabs>

---

### Vérification

**Vérifiez si psycopg2 est installé** :
```python
# Console Python QGIS
import psycopg2
print(psycopg2.__version__)
# Attendu : '2.9.x (dt dec pq3 ext lo64)'
```

**Vérifiez les logs FilterMate** :
```
✅ Succès : "Backend PostgreSQL disponible"
❌ Avertissement : "psycopg2 non trouvé, utilisation de Spatialite"
```

---

### Quand NE PAS S'Inquiéter

**Vous pouvez ignorer l'installation PostgreSQL si** :
- Jeu de données avec `<10 000` entités (Spatialite est assez rapide)
- Utilisation de couches OGR (Shapefile, GeoPackage) sans possibilité de migration
- Filtrage occasionnel uniquement (performances non critiques)
- Pas de base de données PostgreSQL disponible

---

## 3. Performances Lentes (>30 secondes) {#3-performances-lentes-30-secondes}

**Symptôme** : L'opération de filtre prend plus de 30 secondes.

### Diagnostic

**Vérifiez le backend utilisé** :
```
Panneau FilterMate → Info couche :
Provider : ogr (⚠️ Plus lent)
Provider : spatialite (⏱️ Moyen)
Provider : postgresql (⚡ Plus rapide)
```

---

### Solutions par Backend

#### Backend OGR (Shapefile, GeoPackage)

**Problème** : Pas d'index spatiaux natifs, traitement en mémoire.

**Solution 1** : Migrer vers PostgreSQL
```bash
# Optimal pour jeux de données >50k entités
1. Configurez PostgreSQL+PostGIS
2. Gestionnaire BD → Importer la couche
3. Reconnectez dans QGIS
4. Accélération 10-50×
```

**Solution 2** : Migrer vers Spatialite
```bash
# Bon pour jeux de données 10k-50k entités
1. Boîte à Outils de Traitement → Vecteur général → Empaqueter les couches
2. Choisissez le format Spatialite
3. Accélération 3-5× vs Shapefile
```

**Solution 3** : Optimiser la requête
```sql
-- Ajoutez le filtre attributaire EN PREMIER (réduit la portée de la requête spatiale)
population > 10000 AND ...requête spatiale...

-- Au lieu de :
...requête spatiale... AND population > 10000
```

---

#### Backend Spatialite

**Problème** : Grand jeu de données (>50k entités).

**Solution** : Migrer vers PostgreSQL
- Amélioration attendue : 5-10× plus rapide
- Requêtes en moins d'une seconde sur 100k+ entités

**Contournement** : Réduire la portée de la requête
```sql
-- Pré-filtrer avec une emprise
bbox($geometry, 
     $xmin, $ymin, 
     $xmax, $ymax)
AND ...votre filtre...
```

---

#### Backend PostgreSQL (Déjà Rapide)

**Problème** : Lent malgré l'utilisation de PostgreSQL (rare).

**Causes Possibles** :
1. ❌ Index spatial manquant
2. ❌ Géométries invalides
3. ❌ Latence réseau (base de données distante)

**Solutions** :
```sql
-- 1. Vérifiez que l'index spatial existe
SELECT * FROM pg_indexes 
WHERE tablename = 'votre_table' 
  AND indexdef LIKE '%GIST%';

-- 2. Créez l'index si manquant
CREATE INDEX idx_geom ON votre_table USING GIST(geom);

-- 3. Réparez les géométries
UPDATE votre_table SET geom = ST_MakeValid(geom);
```

---

### Benchmarks de Performance

| Backend | 10k entités | 50k entités | 100k entités |
|---------|-------------|-------------|--------------|
| PostgreSQL | 0.1s ⚡ | 0.3s ⚡ | 0.8s ⚡ |
| Spatialite | 0.4s ✓ | 4.5s ⏱️ | 18s ⏱️ |
| OGR (GPKG) | 2.1s | 25s ⚠️ | 95s 🐌 |
| OGR (SHP) | 3.8s | 45s 🐌 | 180s 🐌 |

**Recommandation** : Utilisez PostgreSQL pour >50k entités.

---

## 4. Résultats Spatiaux Incorrects {#4-résultats-spatiaux-incorrects}

**Symptôme** : Des entités éloignées de la géométrie de référence sont incluses dans les résultats.

### Causes Courantes

#### Cause A : Distance de Buffer dans les Mauvaises Unités

**Problème** : Utilisation de degrés quand vous avez besoin de mètres (ou vice versa).

**Exemple** :
```
Buffer : 500 (supposé en mètres)
CRS de la couche : EPSG:4326 (degrés !)
Résultat : Buffer de 500 degrés (~55 000 km !)
```

**Solution** :
✅ FilterMate convertit automatiquement les CRS géographiques en EPSG:3857 pour les buffers métriques
- Cherchez l'indicateur 🌍 dans les logs
- Vérification manuelle : Propriétés de la Couche → Information → Unités CRS

✅ Utilisez un CRS approprié :
```
Degrés : EPSG:4326 (WGS84) - Auto-converti ✓
Mètres : EPSG:3857 (Web Mercator)
Mètres : Zones UTM locales (plus précis)
```

---

#### Cause B : Mauvais Prédicat Spatial

**Problème** : Utilisation de "Contains" quand vous avez besoin de "Intersects".

**Signification des Prédicats** :
```
Intersects : Touche ou chevauche (plus permissif)
Contains : A englobe complètement B (strict)
Within : A complètement à l'intérieur de B (opposé de Contains)
Crosses : Intersection linéaire uniquement
```

**Exemple** :
```
❌ Faux : Contains
   - Trouve les parcelles qui CONTIENNENT les routes (opposé !)
   
✅ Correct : Intersects
   - Trouve les parcelles qui TOUCHENT les routes
```

**Solution** :
Voir le [Guide des Prédicats Spatiaux](../reference/cheat-sheets/spatial-predicates.md) pour un guide visuel.

---

#### Cause C : La Couche de Référence est Fausse

**Problème** : Mauvaise couche sélectionnée comme référence spatiale.

**Exemple** :
```
Objectif : Bâtiments près des ROUTES
Réel : Couche de référence = RIVIÈRES
Résultat : Mauvaises entités sélectionnées
```

**Solution** :
✅ Vérifiez la liste déroulante de la couche de référence :
- Le nom de la couche doit correspondre à votre intention
- L'icône montre le type de géométrie (point/ligne/polygone)

---

### Étapes de Vérification

**Vérification Manuelle** :
1. Utilisez l'**Outil de Mesure** QGIS (Ctrl+Shift+M)
2. Mesurez la distance de l'entité filtrée à l'entité de référence la plus proche
3. La distance devrait être ≤ votre paramètre de buffer

**Vérification Visuelle** :
1. **Outil d'Identification** → Cliquez sur l'entité de référence
2. Clic droit → **Zoomer sur l'Entité**
3. Regardez les entités filtrées environnantes
4. Elles devraient former un anneau autour de l'entité de référence (si buffer utilisé)

---

## 5. Erreurs de Syntaxe d'Expression {#5-erreurs-de-syntaxe-dexpression}

**Symptôme** : ✗ rouge dans le constructeur d'expression avec un message d'erreur.

### Erreurs de Syntaxe Courantes

#### Guillemets Manquants Autour du Texte

```sql
❌ Faux :
city = Paris

✅ Correct :
city = 'Paris'
```

---

#### Noms de Champs Sensibles à la Casse (Spatialite)

```sql
❌ Faux (Spatialite) :
name = 'test'  -- Le champ est 'NAME', pas 'name'

✅ Correct :
"NAME" = 'test'  -- Guillemets doubles pour les champs sensibles à la casse
```

---

#### Utilisation de = avec NULL

```sql
❌ Faux :
population = NULL

✅ Correct :
population IS NULL
```

---

#### Concaténation de Chaînes

```sql
❌ Faux :
city + ', ' + country

✅ Correct :
city || ', ' || country
```

---

#### Comparaisons de Dates

```sql
❌ Faux :
date_field > '2024-01-01'  -- Comparaison de chaînes

✅ Correct :
date_field > to_date('2024-01-01')
-- ou
year(date_field) = 2024
```

---

### Débogage d'Expression

**Étape 1** : Testez dans le Constructeur d'Expression
```
Couche QGIS → Ouvrir la Table d'Attributs → 
Calculatrice de Champs → Testez l'expression
```

**Étape 2** : Utilisez l'Aperçu d'Expression
```
Cliquez sur le bouton "Aperçu" pour voir le résultat sur la première entité
```

**Étape 3** : Simplifiez l'Expression
```sql
-- Commencez simple :
1 = 1  -- Toujours vrai

-- Ajoutez de la complexité graduellement :
city = 'Paris'
city = 'Paris' AND population > 100000
```

---

## 6. Échecs d'Export {#6-échecs-dexport}

**Symptôme** : Le bouton d'export ne fait rien ou affiche une erreur.

### Causes Courantes

#### Cause A : Permission Refusée

**Problème** : Impossible d'écrire dans le dossier de destination.

**Solution** :
```bash
# Windows : Choisissez un dossier utilisateur
C:\Users\VotreNom\Documents\

# Linux/macOS : Vérifiez les permissions
chmod 755 /chemin/vers/dossier/sortie
```

---

#### Cause B : Caractères Invalides dans le Nom de Fichier

**Problème** : Caractères spéciaux non autorisés par le système de fichiers.

```bash
❌ Faux :
exports/data:2024.gpkg  -- Deux-points non autorisé (Windows)

✅ Correct :
exports/data_2024.gpkg
```

---

#### Cause C : CRS Cible Invalide

**Problème** : Le CRS sélectionné n'existe pas ou n'est pas reconnu.

**Solution** :
✅ Utilisez des codes CRS courants :
```
EPSG:4326 - WGS84 (mondial)
EPSG:3857 - Web Mercator (cartes web)
EPSG:2154 - Lambert 93 (France)
```

---

#### Cause D : Le Nom de Couche Contient des Espaces (export PostgreSQL)

**Problème** : Les noms de tables PostgreSQL avec espaces nécessitent des guillemets.

**Solution** :
```sql
❌ Faux : mon nom de couche

✅ Correct : mon_nom_de_couche
```

---

## 7. Historique des Filtres Perdu Après Redémarrage {#7-historique-des-filtres-perdu-après-redémarrage}

**Symptôme** : L'historique Annuler/Rétablir est vide après la fermeture de QGIS.

### Comportement Attendu

**L'historique des filtres est basé sur la session** - il n'est pas sauvegardé dans le fichier de projet QGIS.

**Pourquoi** :
- L'historique peut devenir volumineux (100+ opérations)
- Peut contenir des critères de filtre sensibles
- Optimisation des performances

---

### Contournement : Utilisez les Favoris

**Sauvegardez les filtres importants** :
1. Appliquez votre filtre
2. Cliquez sur le bouton **"Ajouter aux Favoris"** (icône ⭐)
3. Donnez-lui un nom descriptif
4. Les favoris SONT sauvegardés dans le fichier de projet

**Rappelez les filtres favoris** :
1. Cliquez sur le menu déroulant **"Favoris"**
2. Sélectionnez le filtre sauvegardé
3. Cliquez sur **"Appliquer"**

---

## 8. Problèmes de Décalage CRS {#8-problèmes-de-décalage-crs}

**Symptôme** : Les entités apparaissent au mauvais endroit ou les requêtes spatiales échouent.

### Gestion Automatique des CRS

**FilterMate reprojette automatiquement les couches** pendant les opérations spatiales.

**Vous verrez** :
```
🔄 Reprojection de la couche de EPSG:4326 vers EPSG:3857
```

**C'est NORMAL et attendu** - aucune action nécessaire.

---

### Quand le CRS Cause des Problèmes

#### Problème : CRS Géographique Utilisé pour les Buffers

**Problème** : Distance de buffer interprétée comme des degrés au lieu de mètres.

**Solution FilterMate** :
✅ Convertit automatiquement EPSG:4326 → EPSG:3857 pour les opérations métriques
- L'indicateur 🌍 apparaît dans les logs
- Aucune intervention manuelle nécessaire

**Remplacement Manuel** (si nécessaire) :
1. Clic droit sur la couche → **Exporter** → **Sauvegarder les Entités Sous**
2. Définissez le CRS sur un système projeté local (UTM, State Plane, etc.)
3. Utilisez la couche exportée dans FilterMate

---

#### Problème : La Couche Affiche un Mauvais Emplacement

**Problème** : La couche a un mauvais CRS assigné.

**Symptômes** :
- La couche apparaît loin de l'emplacement attendu
- Peut être de l'autre côté du monde
- Saute à 0°,0° (Golfe de Guinée)

**Solution** :
```bash
# Corrigez le CRS de la couche
1. Clic droit sur la couche → Définir le CRS de la Couche
2. Sélectionnez le bon CRS (vérifiez la documentation des données)
3. N'utilisez pas "Définir le CRS du Projet depuis la Couche" - corrige uniquement l'affichage
```

**Identifier le Bon CRS** :
- Vérifiez le fichier de métadonnées (.xml, .prj, .qmd)
- Regardez les valeurs de coordonnées dans la table d'attributs
  - Grands nombres (ex: 500 000) → CRS Projeté
  - Petits nombres (-180 à 180) → CRS Géographique
- Cherchez sur Google la source des données pour les informations CRS

---

## Liste de Vérification de Prévention

Avant de filtrer, vérifiez :

### Qualité des Données
- [ ] Les couches se chargent et s'affichent correctement
- [ ] Les géométries sont valides (exécutez Vérifier les Géométries)
- [ ] La table d'attributs a les valeurs attendues
- [ ] Les couches se chevauchent géographiquement

### Configuration
- [ ] Bonne couche cible sélectionnée
- [ ] Bonne couche de référence (pour les requêtes spatiales)
- [ ] L'expression affiche une coche verte ✓
- [ ] Distance et unités de buffer appropriées
- [ ] Le prédicat spatial correspond à l'intention

### Performance
- [ ] Le type de backend est approprié pour la taille du jeu de données
- [ ] psycopg2 installé si utilisation de PostgreSQL
- [ ] Les index spatiaux existent (PostgreSQL)

---

## Obtenir de l'Aide

### Ressources en Libre-Service

1. **Vérifiez les Logs** : QGIS → Vue → Panneaux → Messages de Log → FilterMate
2. **Lisez le Message d'Erreur** : Il dit souvent exactement ce qui ne va pas
3. **Cherchez dans la Documentation** : Utilisez la barre de recherche (Ctrl+K)
4. **Essayez une Version Simplifiée** : Supprimez la complexité pour isoler le problème

### Support Communautaire

- 🐛 **Rapports de Bugs** : [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Questions** : [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 📧 **Contact** : Incluez la version QGIS, la version FilterMate et les logs d'erreur

---

## Résumé

**Erreurs les Plus Courantes** :
1. Résultats vides → Vérifiez les valeurs d'attributs et la distance de buffer
2. PostgreSQL indisponible → Installez psycopg2
3. Performances lentes → Utilisez PostgreSQL pour les grands jeux de données
4. Mauvais résultats spatiaux → Vérifiez les unités de buffer et le prédicat
5. Erreurs d'expression → Vérifiez la syntaxe et les noms de champs

**Points Clés** :
- FilterMate gère les CRS automatiquement (cherchez les indicateurs)
- Testez toujours avec des expressions simplifiées d'abord
- Vérifiez les logs pour des messages d'erreur détaillés
- PostgreSQL offre les meilleures performances pour >50k entités
- L'historique des filtres est basé sur la session (utilisez les Favoris pour la persistance)

---

**Toujours bloqué ?** Consultez le [Guide de Dépannage](../advanced/troubleshooting.md) ou posez votre question sur [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions).
