---
sidebar_position: 100
title: Déclaration d'Accessibilité
description: Engagement et informations de conformité en matière d'accessibilité de la documentation FilterMate
keywords: [accessibilité, WCAG, lecteur d'écran, navigation clavier, a11y]
---

# Déclaration d'Accessibilité

**Dernière mise à jour** : 9 décembre 2025

La documentation FilterMate s'engage à garantir l'accessibilité numérique pour tous les utilisateurs, y compris ceux utilisant des technologies d'assistance. Nous nous efforçons de respecter ou de dépasser les normes Web Content Accessibility Guidelines (WCAG) 2.1 niveau AA.

## Notre Engagement

Nous croyons que chacun devrait avoir un accès égal aux informations sur FilterMate, quelle que soit sa capacité ou la technologie qu'il utilise. L'accessibilité est un effort continu, et nous travaillons continuellement pour améliorer l'expérience utilisateur de tous les visiteurs.

## Statut de Conformité

**WCAG 2.1 Niveau AA** : Partiellement Conforme

Cela signifie que certaines parties du contenu ne sont pas entièrement conformes à la norme WCAG 2.1 niveau AA, mais nous travaillons activement pour atteindre une conformité complète.

## Fonctionnalités d'Accessibilité

### ✅ Navigation au Clavier
- Tous les éléments interactifs sont accessibles via le clavier
- L'ordre de tabulation suit une séquence logique
- Les indicateurs de focus sont clairement visibles
- Lien de saut de navigation fourni pour un accès rapide au contenu principal

### ✅ Compatibilité avec les Lecteurs d'Écran
- Structure HTML5 sémantique avec des repères appropriés
- Labels ARIA lorsque approprié
- Texte alternatif descriptif pour toutes les images informatives
- La hiérarchie des titres suit une structure logique (h1 → h2 → h3)

### ✅ Accessibilité Visuelle
- **Contraste des Couleurs** : Ratio minimum de 4,5:1 pour le texte normal (WCAG AA)
- **Redimensionnement du Texte** : Contenu lisible à 200% de zoom sans perte de fonctionnalité
- **Indicateurs de Focus** : Contour de 3px avec décalage de 2px sur tous les éléments interactifs
- **Taille de Police** : Taille de police de base de 16px pour une meilleure lisibilité
- **Hauteur de Ligne** : Interligne de 1,65 pour une lecture confortable

### ✅ Design Responsive
- Mises en page adaptées aux mobiles
- Cibles tactiles de minimum 44x44 pixels
- S'adapte aux différentes tailles et orientations d'écran

### ✅ Structure du Contenu
- Titres et repères clairs
- Table des matières pour les pages longues
- Navigation par fil d'Ariane
- Modèles de navigation cohérents

### ✅ Médias
- Blocs de code avec coloration syntaxique
- Les diagrammes incluent des alternatives textuelles
- Les vidéos incluent des sous-titres (lorsque disponible)

### ✅ Mouvement et Animation
- Respecte le paramètre `prefers-reduced-motion`
- Aucun contenu clignotant au-dessus de 3Hz
- Les animations peuvent être désactivées via les paramètres du navigateur

## Limitations Connues

Nous sommes conscients des limitations d'accessibilité suivantes et travaillons à les résoudre :

### 🔨 En Cours
- **Sous-titres Vidéo** : Certaines vidéos intégrées peuvent manquer de sous-titres
- **Accessibilité des PDF** : Les PDF exportés nécessitent un balisage d'accessibilité
- **Alternatives aux Exemples de Code** : Descriptions textuelles pour les exemples de code complexes

### 📋 Améliorations Prévues
- Annonces améliorées par lecteur d'écran pour le contenu dynamique
- Documentation supplémentaire des raccourcis clavier
- Palette de couleurs améliorée pour les utilisateurs daltoniens
- Annonces en région live pour les mises à jour AJAX

## Méthodologie de Test

Nos tests d'accessibilité incluent :

- **Tests Automatisés** :
  - axe-core DevTools
  - pa11y-ci
  - Audit d'Accessibilité Lighthouse

- **Tests Manuels** :
  - Navigation au clavier uniquement
  - Tests avec lecteurs d'écran (NVDA, JAWS, VoiceOver)
  - Analyse du contraste des couleurs
  - Tests de zoom du navigateur (jusqu'à 200%)

- **Tests avec de Vrais Utilisateurs** :
  - Retours d'utilisateurs handicapés
  - Groupes d'utilisateurs de technologies d'assistance

## Support des Navigateurs et Technologies d'Assistance

Cette documentation a été testée avec :

### Navigateurs
- Chrome (dernière version)
- Firefox (dernière version)
- Safari (dernière version)
- Edge (dernière version)

### Lecteurs d'Écran
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS/iOS)
- TalkBack (Android)

### Navigation au Clavier
Toutes les fonctionnalités accessibles via le clavier dans les navigateurs supportés

## Retours et Réclamations

Nous accueillons les retours sur l'accessibilité de la documentation FilterMate. Si vous rencontrez des obstacles d'accessibilité, veuillez nous en informer :

### Signaler un Problème
- **Issues GitHub** : [github.com/sducournau/filter_mate/issues](https://github.com/sducournau/filter_mate/issues)
- **Label** : Utilisez le label `accessibility`
- **Informations à Inclure** :
  - URL de la page
  - Description du problème
  - Navigateur et technologie d'assistance utilisés
  - Étapes pour reproduire

### Délai de Réponse
Nous visons à répondre aux retours d'accessibilité dans les délais suivants :
- Problèmes critiques : 2 jours ouvrables
- Problèmes importants : 1 semaine
- Problèmes mineurs : 2 semaines

## Spécifications Techniques

L'accessibilité de la documentation FilterMate repose sur les technologies suivantes :

- **HTML5** : Balisage sémantique
- **CSS3** : Styles responsive et accessibles
- **JavaScript** : Amélioration progressive (le site fonctionne sans JS)
- **React** : Architecture basée sur les composants
- **Docusaurus** : Framework de documentation

## Normes d'Accessibilité

Nous nous référons aux normes et directives suivantes :

- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/) (Web Content Accessibility Guidelines)
- [Section 508](https://www.section508.gov/) (U.S. Rehabilitation Act)
- [ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/) (Accessible Rich Internet Applications)
- [ATAG 2.0](https://www.w3.org/WAI/standards-guidelines/atag/) (Authoring Tool Accessibility Guidelines)

## Contenu Tiers

Certains contenus sur ce site peuvent provenir de sources tierces (par exemple, vidéos intégrées, liens externes). Nous nous efforçons de garantir que le contenu tiers est accessible mais ne pouvons garantir un contrôle total sur les ressources externes.

## Amélioration Continue

L'accessibilité est un engagement continu. Notre feuille de route inclut :

### Court Terme (3 Prochains Mois)
- Audit complet du texte alternatif pour toutes les images
- Ajout de sous-titres à toutes les vidéos tutorielles
- Mise en place d'un widget de retour sur toutes les pages
- Réalisation de tests complets avec lecteurs d'écran

### Moyen Terme (3-6 Mois)
- Atteindre une conformité WCAG 2.1 AA complète
- Ajout de documentation sur les raccourcis clavier
- Mise en place d'annonces en région live
- Amélioration du contraste des couleurs pour tous les éléments UI

### Long Terme (6-12 Mois)
- Viser une conformité WCAG 2.1 AAA lorsque réalisable
- Fonctionnalités d'accessibilité multilingues
- Support avancé des technologies d'assistance
- Audits d'accessibilité réguliers (trimestriels)

## Ressources

### Pour les Utilisateurs
- [WebAIM : Introduction à l'Accessibilité Web](https://webaim.org/intro/)
- [Lecteur d'Écran NVDA](https://www.nvaccess.org/download/)
- [Vérificateur de Contraste des Couleurs](https://webaim.org/resources/contrastchecker/)

### Pour les Développeurs
- [Guide des Pratiques d'Écriture ARIA](https://www.w3.org/WAI/ARIA/apg/)
- [Bibliothèque de Composants Accessibles](https://www.a11yproject.com/)
- [Référence Rapide WebAIM](https://webaim.org/resources/quickref/)

## Informations Légales

Cette déclaration d'accessibilité s'applique au site web de documentation FilterMate hébergé sur [https://sducournau.github.io/filter_mate/](https://sducournau.github.io/filter_mate/).

Pour les questions concernant le plugin lui-même, veuillez vous référer au [Dépôt Principal de Plugins QGIS](https://plugins.qgis.org/plugins/filter_mate/).

---

**Note** : Cette déclaration a été créée le 9 décembre 2025 et sera révisée et mise à jour trimestriellement pour refléter nos améliorations continues en matière d'accessibilité.

:::tip Aidez-nous à Nous Améliorer
Vos retours nous aident à rendre la documentation FilterMate plus accessible. Si vous utilisez une technologie d'assistance et avez des suggestions, veuillez [ouvrir une issue](https://github.com/sducournau/filter_mate/issues/new?labels=accessibility).
:::
