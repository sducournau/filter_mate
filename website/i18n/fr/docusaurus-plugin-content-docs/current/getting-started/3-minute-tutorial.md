---
sidebar_position: 1.5
---

# Démarrage Rapide en 3 Minutes

Créez votre premier filtre en seulement 3 minutes !

:::info Ce Que Vous Allez Apprendre
- Comment ouvrir FilterMate
- Comment appliquer un filtre attributaire
- Comment voir les résultats sur la carte
:::

**Durée** : ⏱️ 3 minutes  
**Difficulté** : ⭐ Débutant absolu  
**Prérequis** : QGIS installé + une couche vectorielle chargée

---

## L'Objectif

**Filtrer une couche de villes pour n'afficher que les grandes villes** (population > 100 000)

---

## Étape 1 : Ouvrir FilterMate (30 secondes)

1. Recherchez l'icône FilterMate dans votre barre d'outils QGIS :

   <img src="/filter_mate/icons/logo.png" alt="Icône FilterMate" width="32"/>

2. Cliquez dessus, ou allez dans **Vecteur** → **FilterMate**
3. Le panneau FilterMate apparaît (généralement sur le côté droit)

:::tip Position du Panneau
Vous pouvez faire glisser le panneau vers n'importe quel bord de votre fenêtre QGIS, ou le rendre flottant.
:::

---

## Étape 2 : Sélectionner Votre Couche (30 secondes)

Dans le menu déroulant **Sélection de couche** en haut du panneau FilterMate :

1. Cliquez sur le menu déroulant
2. Choisissez votre couche de villes/communes
3. FilterMate analyse la couche et affiche :
   - Type de backend (PostgreSQL⚡ / Spatialite / OGR)
   - Nombre d'entités (ex. : « 450 entités »)
   - Champs disponibles

**Vous n'avez pas de couche de villes ?**
- Utilisez n'importe quelle couche avec un champ numérique
- Ou téléchargez notre [jeu de données exemple](https://github.com/sducournau/filter_mate/releases) (5 Mo)

---

## Étape 3 : Écrire une Expression de Filtre (1 minute)

Filtrons maintenant pour n'afficher que les entités où la population est supérieure à 100 000.

### Trouver la Boîte d'Expression

Dans le panneau FilterMate, recherchez le **constructeur d'expressions** - c'est la zone de saisie de texte dans l'onglet FILTRAGE ou EXPLORATION.

### Tapez Votre Expression

```sql
"population" > 100000
```

:::caution Noms de Champs
- Les noms de champs sont **sensibles à la casse**
- Utilisez des **guillemets doubles** autour des noms de champs : `"population"`
- Utilisez des **guillemets simples** pour les valeurs textuelles : `'Paris'`
:::

**Expressions Alternatives** (adaptez à vos données) :

<details>
<summary>Pour une couche avec des noms de champs différents</summary>

```sql
-- Si votre champ s'appelle "POPULATION" (majuscules)
"POPULATION" > 100000

-- Si votre champ s'appelle "pop" ou "habitants"
"pop" > 100000
"habitants" > 100000

-- Conditions multiples
"population" > 100000 AND "pays" = 'France'
```

</details>

---

## Étape 4 : Appliquer le Filtre (30 secondes)

1. Recherchez le bouton **Appliquer le filtre** (généralement avec une icône d'entonnoir 🔽)
2. Cliquez dessus
3. **Admirez la magie !** ✨

**Ce que vous devriez voir :**
- La carte se met à jour pour n'afficher que les entités filtrées
- Le nombre d'entités se met à jour (ex. : « Affichage de 42 sur 450 entités »)
- Les entités filtrées sont mises en évidence sur la carte

---

## ✅ Succès ! Que S'est-il Passé ?

FilterMate a appliqué votre expression à chaque entité de la couche :
- Entités avec `population > 100000` : ✅ **Affichées**
- Entités avec `population ≤ 100000` : ❌ **Masquées**

Les données d'origine sont **inchangées** - FilterMate crée une vue filtrée temporaire.

---

## 🎓 Et Maintenant ?

### Apprendre d'Autres Techniques de Filtrage

**Filtrage Géométrique** (10 min)  
Trouvez des entités en fonction de leur localisation et de leurs relations spatiales  
[▶️ Votre Premier Filtre Géométrique](./first-filter)

**Exporter Vos Résultats** (5 min)  
Enregistrez les entités filtrées au format GeoPackage, Shapefile ou PostGIS  
[▶️ Guide d'Export](../user-guide/export-features)

**Annuler/Rétablir** (3 min)  
Naviguez dans votre historique de filtres avec annulation/rétablissement intelligent  
[▶️ Historique des Filtres](../user-guide/filter-history)

### Explorer les Workflows du Monde Réel

**Urbanisme** (10 min)  
Trouvez des propriétés à proximité des stations de transport  
[▶️ Développement Axé sur le Transit](../workflows/urban-planning-transit)

**Immobilier** (8 min)  
Filtrage de propriétés multi-critères  
[▶️ Analyse de Marché](../workflows/real-estate-analysis)

---

## 🆘 Dépannage

### « Aucune entité ne correspond »

**Causes possibles :**
1. **Erreur de syntaxe d'expression** - Vérifiez les fautes de frappe
2. **Nom de champ incorrect** - Clic droit sur la couche → Ouvrir la table d'attributs pour vérifier les noms de champs
3. **Seuil trop élevé** - Essayez une valeur inférieure : `"population" > 10000`

**Solution rapide :**
```sql
-- Essayez d'abord cette expression plus simple
"population" IS NOT NULL
```

Cela devrait afficher toutes les entités avec une valeur de population.

---

### Erreur « Champ introuvable »

**Cause** : Le nom du champ ne correspond pas exactement

**Solution :**
1. Clic droit sur votre couche → **Ouvrir la table d'attributs**
2. Trouvez la colonne avec les données de population
3. Notez le nom **exact** du champ (y compris les majuscules/minuscules)
4. Utilisez ce nom exact entre guillemets : `"VotreNomDeChamp"`

---

### Impossible de trouver le bouton Appliquer

**L'emplacement du bouton Appliquer le filtre dépend de votre configuration :**
- **Bas du panneau** (par défaut)
- **Haut près du sélecteur de couche**
- **Côté gauche ou droit** (si configuré)

Recherchez un bouton avec une icône d'entonnoir (🔽) ou le texte « Appliquer le filtre ».

---

## 💡 Astuces Pro

### 1. Utiliser la Liste des Champs
La plupart des interfaces FilterMate affichent une liste des champs disponibles. Cliquez sur un nom de champ pour l'insérer automatiquement dans votre expression.

### 2. Vérifier la Validité de l'Expression
FilterMate valide votre expression en temps réel :
- ✅ Coche verte = Valide
- ❌ X rouge = Erreur de syntaxe (survolez pour plus de détails)

### 3. Combiner avec la Sélection Manuelle
Vous pouvez combiner les filtres FilterMate avec l'outil de sélection manuelle de QGIS :
1. Appliquez le filtre FilterMate
2. Utilisez l'outil Sélectionner pour affiner davantage
3. Seules les entités filtrées sont sélectionnables

---

## 🎉 Félicitations !

Vous avez appliqué avec succès votre premier filtre ! Vous êtes maintenant prêt à explorer les fonctionnalités plus avancées de FilterMate.

**Continuer l'Apprentissage :**
- [Bases du Filtrage](../user-guide/filtering-basics) - Maîtrisez les expressions QGIS
- [Filtrage Géométrique](../user-guide/geometric-filtering) - Relations spatiales
- [Tous les Workflows](../workflows/index) - Scénarios du monde réel

**Besoin d'Aide ?**
- 📖 [Guide Utilisateur](../user-guide/introduction)
- 🐛 [Signaler des Problèmes](https://github.com/sducournau/filter_mate/issues)
- 💬 [Poser des Questions](https://github.com/sducournau/filter_mate/discussions)
