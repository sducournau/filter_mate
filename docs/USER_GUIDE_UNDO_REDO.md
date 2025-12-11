# Guide Utilisateur : Undo/Redo Intelligent

## Vue d'ensemble

FilterMate propose désormais un système d'annulation/rétablissement (Undo/Redo) intelligent qui s'adapte automatiquement à votre contexte de travail.

## Boutons d'action

![Boutons Undo/Redo](icons/undo_redo_buttons.png)

- **Bouton Undo** (↶) : Annuler la dernière action de filtrage
- **Bouton Redo** (↷) : Rétablir une action annulée

Les boutons sont automatiquement activés/désactivés selon la disponibilité de l'historique.

## Modes de fonctionnement

### Mode 1 : Couche source uniquement

**Quand ?** Vous travaillez uniquement sur une couche, sans couches distantes sélectionnées.

**Comportement :**
- ✅ Undo annule le dernier filtre sur cette couche
- ✅ Redo rétablit le filtre annulé
- ✅ L'historique est indépendant pour chaque couche

**Exemple :**
```
1. Sélectionner la couche "Communes"
2. Appliquer le filtre : population > 50000
   → 42 communes affichées
3. Clic Undo
   → Retour à l'état précédent (toutes les communes)
4. Clic Redo
   → Réapplique le filtre (42 communes)
```

### Mode 2 : Filtrage global (source + couches distantes)

**Quand ?** Vous avez sélectionné des couches distantes dans "Layers to filter" et ces couches sont filtrées.

**Comportement :**
- ✅ Undo annule le filtre sur TOUTES les couches simultanément
- ✅ Redo rétablit le filtre sur TOUTES les couches
- ✅ L'état complet (source + distantes) est restauré atomiquement

**Exemple :**
```
1. Sélectionner la couche "Départements" (source)
2. Ajouter "Communes" et "Routes" dans "Layers to filter"
3. Appliquer le filtre : région = 'Bretagne'
   → Départements : 4 filtrés
   → Communes : 1 268 filtrées
   → Routes : 8 543 filtrées
4. Clic Undo
   → Les 3 couches reviennent à l'état précédent
5. Clic Redo
   → Les 3 couches réappliquent le filtre simultanément
```

## Détection automatique du mode

FilterMate détecte automatiquement le mode approprié :

| Situation | Mode utilisé | Effet de Undo/Redo |
|-----------|--------------|-------------------|
| Aucune couche distante sélectionnée | Source seule | Affecte uniquement la couche source |
| Couches distantes sélectionnées MAIS non filtrées | Source seule | Affecte uniquement la couche source |
| Couches distantes sélectionnées ET filtrées | Global | Affecte toutes les couches |

## Messages utilisateur

FilterMate affiche des messages clairs pour vous informer :

### Messages de succès
- **Mode source** : `"Undo: <description du filtre>"`
- **Mode global** : `"Global undo successful (3 layers)"` ← indique le nombre de couches

### Messages d'avertissement
- `"No more undo history"` : Vous êtes au début de l'historique
- `"No more redo history"` : Vous êtes à la fin de l'historique

## Limitations et comportement

### Taille de l'historique
- **Maximum** : 100 états par défaut
- Lorsque la limite est atteinte, les états les plus anciens sont supprimés automatiquement
- Vous pouvez toujours annuler les 100 dernières actions

### Changement de couche
- L'historique est conservé pour chaque couche
- Passer d'une couche à l'autre change l'historique disponible
- Les boutons Undo/Redo se mettent à jour automatiquement

### Reset complet
- Le bouton "Reset" efface complètement l'historique
- Aucun Undo possible après un Reset

### Nouveau projet
- L'historique est réinitialisé à l'ouverture/création d'un projet
- Non persistant entre les sessions QGIS

## Raccourcis clavier (à venir)

Fonctionnalité prévue dans une future version :
- `Ctrl+Z` : Undo
- `Ctrl+Y` ou `Ctrl+Shift+Z` : Redo

## Cas d'usage pratiques

### Cas 1 : Affiner progressivement un filtre
```
1. Filtrer : population > 10000
2. Trop de résultats → Affiner : population > 50000
3. Pas assez → Undo
4. Ré-affiner : population > 30000
```

### Cas 2 : Comparer des états
```
1. Filtrer : année_construction < 1950
2. Analyser le résultat
3. Undo pour revenir à la vue complète
4. Filtrer : année_construction >= 2000
5. Comparer les deux périodes
```

### Cas 3 : Sauvegarder un travail en cours
```
1. Appliquer plusieurs filtres successifs
2. Besoin de revenir en arrière temporairement
3. Undo plusieurs fois
4. Analyser un état intermédiaire
5. Redo pour revenir à l'état final
```

## FAQ

**Q : Puis-je annuler un export ?**
R : Non, l'Undo/Redo ne concerne que les opérations de filtrage, pas les exports.

**Q : L'historique est-il sauvegardé avec le projet ?**
R : Non, l'historique est en mémoire uniquement pour la session en cours.

**Q : Que se passe-t-il si je supprime une couche filtrée ?**
R : Son historique est automatiquement nettoyé.

**Q : Puis-je annuler après avoir quitté et rouvert QGIS ?**
R : Non, l'historique est réinitialisé à chaque nouvelle session.

**Q : Combien de fois puis-je faire Undo ?**
R : Jusqu'à 100 actions en arrière (limite configurable).

## Dépannage

### Les boutons Undo/Redo sont grisés
- ✅ Vérifiez qu'un filtre a été appliqué sur la couche courante
- ✅ Si vous venez de changer de couche, l'historique peut être vide
- ✅ Après un Reset, l'historique est effacé

### Undo ne restaure qu'une seule couche au lieu de toutes
- ✅ Vérifiez que les couches distantes ont un filtre actif
- ✅ Si elles ne sont pas filtrées, seul le mode "source" est actif

### Message "No more undo history" inattendu
- ✅ Vous êtes au début de l'historique pour cette couche
- ✅ L'historique peut avoir été nettoyé par un Reset

## Retour d'expérience

Vos retours sont importants ! Si vous rencontrez un comportement inattendu ou avez des suggestions d'amélioration, n'hésitez pas à :
- Ouvrir une issue sur GitHub
- Contacter l'équipe de développement
- Consulter la documentation technique dans `docs/UNDO_REDO_IMPLEMENTATION.md`

---

**Version** : FilterMate 2.2.6+
**Dernière mise à jour** : Décembre 2025
