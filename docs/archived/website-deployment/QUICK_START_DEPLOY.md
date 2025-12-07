# 🚀 Quick Start - Déploiement Docusaurus

## Étapes Rapides (5 minutes)

### 1️⃣ Activer GitHub Pages

1. Allez sur : https://github.com/sducournau/filter_mate/settings/pages
2. Dans **"Source"**, sélectionnez : `Deploy from a branch`
3. Dans **"Branch"**, sélectionnez : `gh-pages` / `/ (root)`
4. Cliquez **Save**

### 2️⃣ Commiter et Pousser

```bash
cd /windows/c/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate

# Vérifier les fichiers créés
git status

# Ajouter tous les nouveaux fichiers
git add website/ .github/workflows/deploy-docs.yml .gitignore DOCUSAURUS_IMPLEMENTATION.md

# Commiter
git commit -m "feat: Add Docusaurus documentation website

- Complete website structure with 45+ files
- 6 fully documented pages (intro, installation, tutorials, backends)
- 24 placeholder pages for future expansion
- Custom React homepage with features and video
- GitHub Actions CI/CD for automatic deployment
- Comprehensive developer documentation

Sprint 1 MVP completed ✅"

# Pousser vers GitHub
git push origin main
```

### 3️⃣ Vérifier le Déploiement

1. **Suivre le build** : https://github.com/sducournau/filter_mate/actions
   - Le workflow "Deploy Documentation" devrait démarrer automatiquement
   - Durée : ~2-3 minutes

2. **Vérifier les logs** :
   - Cliquez sur le workflow en cours
   - Vérifiez que toutes les étapes passent ✅

3. **Accéder au site** :
   - URL : https://sducournau.github.io/filter_mate/
   - Le site sera live après le build !

### 4️⃣ Vérification Post-Déploiement

Une fois le site déployé, vérifiez :

- ✅ La homepage s'affiche correctement
- ✅ La navigation fonctionne (sidebar)
- ✅ Les pages complètes sont accessibles
- ✅ Le logo s'affiche
- ✅ Le thème dark/light fonctionne
- ✅ La recherche fonctionne
- ✅ Les liens internes fonctionnent

## 🔧 Troubleshooting

### Le workflow GitHub Actions échoue ?

**Vérifier les permissions** :
1. Settings → Actions → General
2. Workflow permissions : "Read and write permissions"
3. Sauvegarder

**Re-déclencher le workflow** :
```bash
git commit --allow-empty -m "chore: trigger deployment"
git push origin main
```

### La page GitHub Pages n'est pas accessible ?

**Attendre quelques minutes** - Le premier déploiement peut prendre 5-10 min

**Vérifier les settings** :
- Settings → Pages
- Source doit être : `gh-pages` branch
- URL affichée : https://sducournau.github.io/filter_mate/

**Forcer le redéploiement** :
1. Settings → Pages
2. Changez temporairement la source vers `None`
3. Sauvegardez
4. Rechangez vers `gh-pages`
5. Sauvegardez

### Les liens sont cassés ?

**Vérifier le baseUrl** :
- Le fichier `website/docusaurus.config.ts` a `baseUrl: '/filter_mate/'`
- C'est correct pour GitHub Pages

## 📊 Commandes Git Utiles

```bash
# Voir le statut
git status

# Voir les fichiers modifiés
git diff --name-only

# Voir les changements d'un fichier
git diff website/package.json

# Annuler un commit (avant push)
git reset --soft HEAD~1

# Voir l'historique
git log --oneline -5
```

## 🎯 Après le Déploiement

### Partager le Site

Une fois déployé, vous pouvez :

1. **Mettre à jour le README principal** avec le lien :
   ```markdown
   📚 **Documentation** : https://sducournau.github.io/filter_mate/
   ```

2. **Ajouter le badge** au README :
   ```markdown
   [![Documentation](https://img.shields.io/badge/docs-docusaurus-blue.svg)](https://sducournau.github.io/filter_mate/)
   ```

3. **Annoncer sur QGIS Plugin Repository** :
   - Mettre à jour la description du plugin
   - Ajouter le lien vers la documentation

### Mettre à Jour le Contenu

Pour ajouter ou modifier une page :

```bash
# Éditer un fichier
nano website/docs/user-guide/filtering-basics.md

# Commiter et pousser
git add website/docs/user-guide/filtering-basics.md
git commit -m "docs: Complete filtering basics guide"
git push origin main

# GitHub Actions redéploiera automatiquement !
```

## 🎨 Personnalisation Future

### Changer les Couleurs

Éditez `website/src/css/custom.css` :

```css
:root {
  --ifm-color-primary: #2e8555;  /* Changez cette couleur */
  /* ... */
}
```

### Ajouter des Images

```bash
# Copier une image
cp screenshot.png website/static/img/docs/

# Utiliser dans un doc
![Screenshot](../../static/img/docs/screenshot.png)
```

### Modifier le Footer

Éditez `website/docusaurus.config.ts` → section `footer`

## 📈 Métriques de Succès

Après déploiement, vous aurez :

- ✅ Un site professionnel à https://sducournau.github.io/filter_mate/
- ✅ Documentation recherchable et navigable
- ✅ Support dark/light mode
- ✅ Responsive (mobile/desktop)
- ✅ SEO optimisé
- ✅ Déploiement automatique sur chaque push

## 🚀 Prêt ?

Exécutez les commandes de la section 2️⃣ et votre documentation sera live en quelques minutes !

---

**Besoin d'aide ?** Consultez :
- `website/README.md` - Guide développeur complet
- `website/DEPLOYMENT.md` - Instructions détaillées
- `DOCUSAURUS_IMPLEMENTATION.md` - Vue d'ensemble du projet
