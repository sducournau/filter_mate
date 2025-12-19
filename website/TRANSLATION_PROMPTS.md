# Prompts de Traduction pour FilterMate Documentation

## Prompt de Base (Copier-Coller dans ChatGPT/Claude)

```
Je vais te donner un fichier markdown de documentation technique QGIS en anglais.
Traduis-le en [FRANÇAIS/PORTUGAIS] en respectant ces règles:

GLOSSAIRE TECHNIQUE (à utiliser systématiquement):
- Layer → Couche (FR) / Camada (PT)
- Feature → Entité (FR) / Feição (PT)
- Buffer → Tampon (FR) / Buffer (PT)
- CRS/Coordinate System → SCR (FR) / SRC (PT)
- Backend → Backend (garder en anglais)
- Attribute → Attribut (FR) / Atributo (PT)

RÈGLES:
1. Garder le front matter YAML intact (---...---)
2. Garder les blocs de code intacts (```...```)
3. Garder les URLs et chemins de fichiers intacts
4. Traduire les commentaires dans le code
5. Garder les noms de variables/fonctions en anglais
6. Adapter les exemples de noms (Paris → Lyon pour FR, São Paulo pour PT)
7. Utiliser un ton professionnel mais accessible
8. Garder la mise en forme markdown (##, -, **, etc.)

Voici le fichier à traduire:
```

## Prompt Workflow Spécifique

```
CONTEXTE: Ceci est un tutoriel pratique FilterMate pour [DOMAINE].
Le ton doit être pédagogique et encourageant.

ADAPTATIONS CULTURELLES:
- Adapter les exemples géographiques (villes, régions) au contexte local
- Adapter les unités si nécessaire (km, m² sont OK pour FR et PT)
- Adapter les références réglementaires (mentionner que c'est un exemple)

Voici le workflow à traduire:
```

## Vérification Post-Traduction

Après traduction, vérifier:
- [ ] Front matter intact
- [ ] Blocs de code intacts
- [ ] Glossaire SIG utilisé correctement
- [ ] Liens internes fonctionnels
- [ ] Ton professionnel maintenu
- [ ] Pas de termes techniques anglais non nécessaires
