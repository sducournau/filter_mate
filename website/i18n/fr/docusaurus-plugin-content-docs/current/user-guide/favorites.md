---
sidebar_position: 8
---

# Favoris de filtres

Enregistrez, organisez et appliquez rapidement des configurations de filtres fréquemment utilisées avec le système de favoris intégré de FilterMate.

:::info Version 2.0+
Le système de favoris est disponible dans FilterMate v2.0 et ultérieur, avec persistance SQLite et capacités d'export/import.
:::

## Aperçu

Les **Favoris de filtres** vous permettent d'enregistrer des configurations de filtres complexes—incluant expressions, prédicats spatiaux, paramètres de tampon et sélections multi-couches—pour une réutilisation rapide entre les sessions.

### Fonctionnalités clés

- ⭐ **Enregistrer des filtres complexes** avec des noms et notes descriptifs
- 📊 **Suivre les statistiques d'utilisation** (nombre d'applications, dernière utilisation)
- 💾 **Persistance SQLite** - favoris enregistrés en base de données
- 📤 **Export/Import** - partager les favoris via des fichiers JSON
- 🔍 **Rechercher & organiser** - trouver des favoris par nom ou tags
- 🎯 **Support multi-couches** - enregistrer des configurations affectant plusieurs couches

## Indicateur de favoris

L'**indicateur ★ Favoris** est situé dans la barre d'en-tête en haut du panneau FilterMate, à côté de l'indicateur de backend.

### États de l'indicateur

| Affichage | Signification | Infobulle |
|-----------|---------------|-----------|
| **★** (gris) | Aucun favori enregistré | Cliquer pour ajouter le filtre actuel |
| **★ 5** (doré) | 5 favoris enregistrés | Cliquer pour appliquer ou gérer |

**Cliquer sur l'indicateur** ouvre le menu contextuel des favoris.

---

## Ajouter des favoris

### Méthode 1 : À partir du filtre actuel

1. **Configurez votre filtre** dans l'onglet FILTRAGE :
   - Définir l'expression
   - Choisir les prédicats spatiaux
   - Configurer la distance du tampon
   - Sélectionner les couches à filtrer

2. **Cliquez sur l'indicateur ★** dans l'en-tête

3. **Sélectionnez "⭐ Ajouter le filtre actuel aux favoris"**

4. **Entrez les détails** dans la boîte de dialogue :
   - **Nom** : Nom court et descriptif (ex : "Grandes parcelles résidentielles")
   - **Description** (optionnelle) : Notes détaillées sur le filtre
   - **Tags** (optionnels) : Mots-clés pour la recherche (séparés par des virgules)

5. **Cliquez sur OK** pour enregistrer

:::tip Convention de nommage
Utilisez des noms clairs et orientés action :
- ✅ "Bâtiments à 200m du métro"
- ✅ "Propriétés de haute valeur > 500k"
- ❌ "filtre1", "test", "requête"
:::

### Ce qui est enregistré

Un favori capture :

- **Expression de filtre** : Le texte de l'expression QGIS
- **Couche source** : Nom et ID de la couche de référence
- **Couches distantes** : Liste des couches filtrées (si multi-couches)
- **Prédicats spatiaux** : Relations géométriques sélectionnées
- **Paramètres de tampon** : Distance, unité, type
- **Opérateur de combinaison** : AND/OR/AND NOT
- **Métadonnées** : Date de création, nombre d'utilisations, dernière utilisation

---

## Appliquer des favoris

### Depuis le menu ★

1. **Cliquez sur l'indicateur ★**

2. Les **favoris récents** sont affichés (jusqu'à 10 plus récents)

3. **Cliquez sur un favori** pour l'appliquer :
   - Expression restaurée
   - Couches sélectionnées
   - Paramètres spatiaux configurés
   - Prêt à appliquer avec le bouton **Filtrer**

4. **Cliquez sur "Filtrer"** pour exécuter la configuration enregistrée

:::warning Disponibilité des couches
Si une couche enregistrée n'existe plus dans le projet, FilterMate :
- Ignorera la couche manquante avec un message d'avertissement
- Appliquera le filtre aux couches disponibles uniquement
:::

### Format d'affichage des favoris

\`\`\`
★ Proximité des bâtiments (3 couches)
  Utilisé 12 fois • Dernière : 18 déc.
\`\`\`

**Affiche** :
- Nom
- Nombre de couches impliquées
- Nombre d'utilisations
- Date de dernière utilisation

---

## Gérer les favoris

### Boîte de dialogue Gestionnaire de favoris

**Accès** : Cliquer sur l'indicateur ★ → **"⚙️ Gérer les favoris..."**

Le gestionnaire fournit :

#### Panneau gauche : Liste des favoris
- Tous les favoris enregistrés
- Affiche nom, nombre de couches, statistiques d'utilisation
- Cliquer pour voir les détails

#### Panneau droit : Détails & Édition

**Onglet 1 : Général**
- **Nom** : Modifier le nom du favori
- **Expression** : Voir/modifier l'expression de filtre
- **Description** : Ajouter des notes

**Onglet 2 : Couches**
- **Couche source** : Informations de la couche de référence
- **Couches distantes** : Liste des couches filtrées

**Onglet 3 : Paramètres**
- **Prédicats spatiaux** : Relations géométriques
- **Tampon** : Distance et type
- **Opérateur de combinaison** : AND/OR/AND NOT

**Onglet 4 : Statistiques d'utilisation**
- Nombre d'utilisations
- Date de création
- Date de dernière utilisation

#### Actions

- **Enregistrer les modifications** : Mettre à jour le favori sélectionné
- **Supprimer** : Retirer le favori (avec confirmation)
- **Appliquer** : Fermer la boîte de dialogue et appliquer le favori

---

## Export & Import

### Exporter des favoris

Partagez vos filtres favoris avec des collègues ou sauvegardez dans un fichier :

1. **Cliquez sur l'indicateur ★** → **"📤 Exporter les favoris..."**

2. **Choisissez l'emplacement** et le nom du fichier (ex : \`filtermate_favorites.json\`)

3. **Tous les favoris exportés** au format JSON

**Cas d'usage** :
- Partager avec les membres de l'équipe
- Sauvegarder avant les mises à jour du plugin
- Transférer entre projets

---

### Importer des favoris

Charger des favoris depuis un fichier JSON :

1. **Cliquez sur l'indicateur ★** → **"📥 Importer les favoris..."**

2. **Sélectionnez le fichier JSON**

3. **Choisissez le mode d'import** :
   - **Fusionner** : Ajouter aux favoris existants
   - **Remplacer** : Supprimer tous et importer les nouveaux

4. **Favoris chargés** et prêts à utiliser

:::tip Flux de travail d'équipe
Établissez une bibliothèque de favoris d'équipe :
1. L'utilisateur expert crée des filtres optimisés
2. Exporte vers un lecteur/dépôt partagé
3. Les membres de l'équipe importent les filtres standardisés
4. Assure la cohérence entre les analyses
:::

---

## Recherche & Filtre

### Trouver des favoris

**Dans le Gestionnaire de favoris** :
- Tapez dans la zone de recherche pour filtrer par :
  - Nom
  - Texte d'expression
  - Tags
  - Description

**Insensible à la casse** et correspond au texte partiel.

---

## Fonctionnalités avancées

### Statistiques d'utilisation

FilterMate suit :
- **Nombre d'applications** : Combien de fois vous avez utilisé ce favori
- **Dernière utilisation** : Horodatage de l'utilisation la plus récente
- **Créé** : Quand le favori a été enregistré pour la première fois

**Avantage** : Identifier vos filtres les plus précieux et optimiser les flux de travail.

---

### Favoris multi-couches

Lorsque vous enregistrez un favori avec des **couches distantes** (Couches à filtrer activé) :

**Enregistré** :
- Configuration de la couche source
- Tous les ID de couches distantes
- Prédicats géométriques
- Paramètres de tampon

**À l'application** :
- Toutes les couches enregistrées re-sélectionnées (si disponibles)
- Relations spatiales restaurées
- Prêt pour le filtrage multi-couches

**Exemple** : "Parcelles urbaines près des transports"
- Source : stations_metro
- Couches distantes : parcelles, bâtiments, routes
- Prédicat : intersecte
- Tampon : 500m

---

## Persistance des favoris

### Emplacement de stockage

Les favoris sont enregistrés dans :
\`\`\`
<profil QGIS>/python/plugins/filter_mate/config/filterMate_db.sqlite
\`\`\`

**Table** : \`fm_favorites\`

**Par projet** : Les favoris sont organisés par UUID de projet, de sorte que différents projets QGIS peuvent avoir des collections de favoris séparées.

---

### Stratégie de sauvegarde

Les favoris sont automatiquement sauvegardés lorsque :
- La configuration du plugin est enregistrée
- Le projet est fermé
- FilterMate est déchargé

**Sauvegarde manuelle** : Utilisez **Exporter les favoris** pour créer des sauvegardes JSON.

---

## Bonnes pratiques

### Nommer les favoris

✅ **Bons noms** :
- "Propriétés > 500k près des écoles"
- "Zones industrielles à 1km de l'eau"
- "Routes à fort trafic (TMJA > 10k)"

❌ **À éviter** :
- "Test", "Requête1", "Temp"
- Mots simples sans contexte
- Jargon trop technique

---

### Organiser avec des tags

Utilisez des **tags** pour catégoriser :
- Par objectif : \`analyse\`, \`export\`, \`reporting\`
- Par géographie : \`centre-ville\`, \`banlieue\`, \`région-nord\`
- Par type de données : \`parcelles\`, \`routes\`, \`bâtiments\`

**Exemple** :
\`\`\`
Nom : Grandes parcelles résidentielles
Tags : parcelles, résidentiel, analyse, urbanisme
\`\`\`

---

### Maintenance

**Régulièrement** :
- ✅ Supprimer les favoris inutilisés
- ✅ Mettre à jour les descriptions à mesure que les flux de travail évoluent
- ✅ Exporter des sauvegardes avant les changements majeurs
- ✅ Réviser et consolider les favoris similaires

**Garder le nombre de favoris** : ~20-50 favoris actifs est optimal (éviter l'encombrement).

---

## Dépannage

### Le favori ne s'applique pas correctement

**Symptômes** : Le filtre s'applique mais les résultats diffèrent de ceux attendus.

**Causes & Solutions** :

1. **Couche renommée ou déplacée**
   - Solution : Modifier le favori, mettre à jour les références de couche

2. **SCR modifié**
   - Solution : Re-enregistrer le favori avec le SCR actuel

3. **Structure de données modifiée** (nouveaux champs, etc.)
   - Solution : Modifier l'expression pour correspondre au schéma actuel

---

### Les favoris ne persistent pas

**Symptôme** : Les favoris disparaissent après le redémarrage.

**Solutions** :

1. **Vérifier le fichier de base de données** :
   \`\`\`bash
   # Vérifier l'existence :
   ls <profil>/python/plugins/filter_mate/config/filterMate_db.sqlite
   \`\`\`

2. **Permissions de fichier** : Assurer l'accès en écriture au répertoire de configuration

3. **Exporter une sauvegarde** : Utiliser l'export JSON comme stockage de secours

---

### L'import échoue

**Erreur** : "Aucun favori importé"

**Causes** :
- Format JSON invalide
- Fichier corrompu
- Version incompatible

**Solution** : 
- Vérifier la structure JSON
- Essayer de ré-exporter depuis la source
- Vérifier que les versions de FilterMate correspondent (v2.0+)

---

## Exemples de flux de travail

### Flux de travail 1 : Filtres d'équipe standardisés

**Scénario** : Équipe SIG de 5 personnes nécessitant un filtrage cohérent

**Configuration** :
1. Le chef d'équipe crée 10 favoris de base
2. Exporte vers \`filtres_equipe.json\`
3. Partage via dépôt/lecteur
4. Les membres de l'équipe importent lors de la première utilisation

**Résultat** : Tout le monde utilise une logique de filtre identique

---

### Flux de travail 2 : Analyse progressive

**Tâche** : Analyse urbaine en plusieurs étapes

**Favoris** :
1. "Étape 1 : Parcelles résidentielles"
2. "Étape 2 : Près des transports (500m)"
3. "Étape 3 : Haute valeur (>300k)"
4. "Étape 4 : Sélection finale"

**Processus** : Appliquer chaque favori en séquence, exporter les résultats à chaque étape.

---

### Flux de travail 3 : Assurance qualité

**Cas d'usage** : Valider les imports de données

**Favoris** :
- "QA : Attributs manquants"
- "QA : Géométries invalides"
- "QA : Enregistrements dupliqués"
- "QA : Hors limites"

**Processus** : Appliquer chaque filtre QA, réviser les entités signalées, corriger les problèmes.

---

## Référence API

### Classe FilterFavorite

Emplacement : \`modules/filter_favorites.py\`

**Propriétés** :
- \`id\` : UUID unique
- \`name\` : Nom d'affichage
- \`expression\` : Expression de filtre
- \`description\` : Notes optionnelles
- \`tags\` : Liste de mots-clés
- \`source_layer_id\` : Couche de référence
- \`remote_layers\` : Liste des couches filtrées
- \`created_at\` : Horodatage
- \`last_used\` : Horodatage
- \`use_count\` : Compteur d'applications

**Méthodes** :
- \`mark_used()\` : Incrémenter le compteur d'utilisation
- \`to_dict()\` : Sérialiser en JSON
- \`from_dict()\` : Désérialiser depuis JSON

---

### Classe FavoritesManager

Emplacement : \`modules/filter_favorites.py\`

**Méthodes** :
- \`add_favorite(fav)\` : Ajouter à la collection
- \`remove_favorite(id)\` : Supprimer par ID
- \`get_favorite(id)\` : Récupérer par ID
- \`get_all_favorites()\` : Lister tous (triés par nom)
- \`get_recent_favorites(limit)\` : Plus récemment utilisés
- \`search_favorites(query)\` : Rechercher par mot-clé
- \`export_to_file(path)\` : Enregistrer en JSON
- \`import_from_file(path)\` : Charger depuis JSON

---

## Documentation connexe

- **[Historique des filtres](./filter-history)** - Système Annuler/Rétablir
- **[Bases du filtrage](./filtering-basics)** - Créer des filtres
- **[Aperçu de l'interface](./interface-overview)** - Composants de l'interface
- **[Pourquoi FilterMate ?](../getting-started/why-filtermate)** - Comparaison des fonctionnalités

---

## Résumé

Les Favoris de filtres dans FilterMate fournissent :

✅ **Enregistrer des configurations complexes** pour réutilisation  
✅ **Organiser les flux de travail** avec noms, descriptions, tags  
✅ **Suivre l'utilisation** pour identifier les filtres précieux  
✅ **Partager avec l'équipe** via export/import JSON  
✅ **Persister entre les sessions** avec stockage SQLite  

**Prochaines étapes** :
1. Créer votre premier favori à partir d'un filtre utile
2. Ajouter un nom et des tags descriptifs
3. L'appliquer dans différents projets
4. Exporter pour partage d'équipe
