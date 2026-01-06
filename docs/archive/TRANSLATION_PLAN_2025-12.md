# Plan d'Intégration des Nouvelles Traductions - FilterMate v2.4.0

**Date**: 22 décembre 2025  
**Version cible**: 2.4.0  
**Statut**: En cours d'implémentation

---

## 📊 Analyse des Téléchargements par Pays

### Données brutes (Décembre 2025)

| Pays              | Téléchargements | Langue principale     | Statut traduction |
| ----------------- | --------------- | --------------------- | ----------------- |
| 🇺🇸 United States  | 285             | English               | ✅ Supportée      |
| 🇧🇷 Brazil         | 35              | Portuguese            | ✅ Supportée      |
| 🇫🇷 France         | 29              | French                | ✅ Supportée      |
| 🇩🇪 Germany        | 27              | German                | ✅ Supportée      |
| 🇬🇧 United Kingdom | 22              | English               | ✅ Supportée      |
| 🇸🇬 Singapore      | 18              | English               | ✅ Supportée      |
| 🇵🇱 **Poland**     | 16              | Polish                | 🆕 À ajouter      |
| 🇿🇦 South Africa   | 11              | English               | ✅ Supportée      |
| 🇧🇪 Belgium        | 9               | French/Dutch          | ✅ Supportée      |
| 🇨🇳 **China**      | 9               | Chinese               | 🆕 À ajouter      |
| 🇮🇩 **Indonesia**  | 9               | Indonesian            | 🆕 À ajouter      |
| 🇦🇺 Australia      | 8               | English               | ✅ Supportée      |
| 🇲🇽 Mexico         | 8               | Spanish               | ✅ Supportée      |
| 🇻🇳 **Vietnam**    | 8               | Vietnamese            | 🆕 À ajouter      |
| 🇨🇦 Canada         | 7               | English/French        | ✅ Supportée      |
| 🇮🇹 Italy          | 7               | Italian               | ✅ Supportée      |
| 🇷🇺 **Russia**     | 7               | Russian               | 🆕 À ajouter      |
| 🇨🇭 Switzerland    | 7               | German/French/Italian | ✅ Supportée      |
| 🇲🇦 Morocco        | 6               | Arabic/French         | ⚠️ Partiel (FR)   |
| 🇹🇷 **Türkiye**    | 6               | Turkish               | 🆕 À ajouter      |
| 🇮🇳 **India**      | 5               | Hindi                 | 🆕 À ajouter      |
| 🇫🇮 **Finland**    | 5               | Finnish               | 🆕 À ajouter      |
| 🇩🇰 **Denmark**    | 4               | Danish                | 🆕 À ajouter      |
| 🇸🇪 **Sweden**     | 4               | Swedish               | 🆕 À ajouter      |
| 🇳🇴 **Norway**     | 4               | Norwegian             | 🆕 À ajouter      |

---

## 🎯 Nouvelles Traductions à Implémenter

### Priorité Haute (Phase 1 - v2.4.0)

| Langue                | Code ISO | Téléchargements | Notes                         |
| --------------------- | -------- | --------------- | ----------------------------- |
| **Polonais**          | `pl`     | 16              | 3ème marché non couvert       |
| **Chinois simplifié** | `zh_CN`  | 9               | Grand potentiel de croissance |
| **Russe**             | `ru`     | 7               | Large communauté QGIS         |

### Priorité Moyenne (Phase 2 - v2.5.0)

| Langue         | Code ISO | Téléchargements | Notes                    |
| -------------- | -------- | --------------- | ------------------------ |
| **Indonésien** | `id`     | 9               | Marché GIS émergent      |
| **Vietnamien** | `vi`     | 8               | Marché GIS émergent      |
| **Turc**       | `tr`     | 6               | Croissance rapide        |
| **Hindi**      | `hi`     | 5               | Large population GIS     |
| **Finnois**    | `fi`     | 5               | Pays nordique actif      |
| **Danois**     | `da`     | 4               | Communauté QGIS nordique |
| **Suédois**    | `sv`     | 4               | Communauté QGIS nordique |
| **Norvégien**  | `nb`     | 4               | Communauté QGIS nordique |

### Priorité Basse (Phase 3 - Future)

| Langue       | Code ISO | Notes                 |
| ------------ | -------- | --------------------- |
| **Arabe**    | `ar`     | Nécessite support RTL |
| **Japonais** | `ja`     | Marché potentiel      |
| **Coréen**   | `ko`     | Marché potentiel      |

---

## 📁 Structure des Fichiers

### Fichiers de traduction existants

```
i18n/
├── FilterMate_de.ts    # Allemand ✅
├── FilterMate_de.qm    # Compilé
├── FilterMate_en.ts    # Anglais ✅
├── FilterMate_en.qm    # Compilé
├── FilterMate_es.ts    # Espagnol ✅
├── FilterMate_es.qm    # Compilé
├── FilterMate_fr.ts    # Français ✅
├── FilterMate_fr.qm    # Compilé
├── FilterMate_it.ts    # Italien ✅
├── FilterMate_it.qm    # Compilé
├── FilterMate_nl.ts    # Néerlandais ✅
├── FilterMate_nl.qm    # Compilé
└── FilterMate_pt.ts    # Portugais ✅
    FilterMate_pt.qm    # Compilé
```

### Nouveaux fichiers à créer

```
i18n/
├── FilterMate_pl.ts    # Polonais 🆕
├── FilterMate_zh.ts    # Chinois simplifié 🆕
├── FilterMate_ru.ts    # Russe 🆕
├── FilterMate_id.ts    # Indonésien 🆕
├── FilterMate_vi.ts    # Vietnamien 🆕
├── FilterMate_tr.ts    # Turc 🆕
├── FilterMate_hi.ts    # Hindi 🆕
├── FilterMate_fi.ts    # Finnois 🆕
├── FilterMate_da.ts    # Danois 🆕
├── FilterMate_sv.ts    # Suédois 🆕
└── FilterMate_nb.ts    # Norvégien 🆕
```

---

## 🔧 Modifications Requises

### 1. Fichiers de Configuration

#### config/config.default.json

```json
"LANGUAGE": {
    "value": "auto",
    "choices": [
        "auto",
        "en", "fr", "de", "es", "it", "nl", "pt",
        "pl", "zh", "ru", "id", "vi", "tr",
        "hi", "fi", "da", "sv", "nb"
    ],
    "available_translations": [
        "en (English)",
        "fr (Français)",
        "de (Deutsch)",
        "es (Español)",
        "it (Italiano)",
        "nl (Nederlands)",
        "pt (Português)",
        "pl (Polski)",
        "zh (中文)",
        "ru (Русский)",
        "id (Bahasa Indonesia)",
        "vi (Tiếng Việt)",
        "tr (Türkçe)",
        "hi (हिन्दी)",
        "fi (Suomi)",
        "da (Dansk)",
        "sv (Svenska)",
        "nb (Norsk)"
    ]
}
```

#### config/config_schema.json

Ajouter les nouveaux codes de langue à l'enum de validation.

### 2. Fichier metadata.txt

Pas de modification requise - les traductions sont détectées automatiquement.

### 3. Script compile_translations.py

Aucune modification - compile tous les fichiers .ts du répertoire i18n.

---

## 📝 Processus de Traduction

### Étape 1: Création des fichiers .ts

1. Copier `FilterMate_en.ts` comme base
2. Modifier l'en-tête avec le code langue correct
3. Laisser les traductions vides ou identiques à la source

### Étape 2: Traduction

**Options de traduction:**

| Méthode                        | Avantages                          | Inconvénients                  |
| ------------------------------ | ---------------------------------- | ------------------------------ |
| **Communauté QGIS**            | Qualité, gratuit, terminologie GIS | Lent, disponibilité incertaine |
| **Traducteurs professionnels** | Qualité garantie                   | Coût                           |
| **IA + Révision**              | Rapide, économique                 | Nécessite vérification humaine |
| **Crowdsourcing (Transifex)**  | Évolutif                           | Setup initial                  |

**Recommandation**: IA (Claude/GPT) + révision par native speaker de la communauté QGIS.

### Étape 3: Compilation

```bash
python compile_translations.py
```

### Étape 4: Test

1. Lancer QGIS
2. Configurer la langue dans FilterMate > Configuration
3. Redémarrer QGIS
4. Vérifier l'interface

---

## 📋 Checklist d'Implémentation

### Phase 1 - Préparation (✅ En cours)

- [x] Analyse des données de téléchargement
- [x] Identification des langues prioritaires
- [x] Création du document de planification
- [ ] Création des fichiers .ts de base
  - [ ] FilterMate_pl.ts (Polonais)
  - [ ] FilterMate_zh.ts (Chinois)
  - [ ] FilterMate_ru.ts (Russe)
  - [ ] FilterMate_id.ts (Indonésien)
  - [ ] FilterMate_vi.ts (Vietnamien)
  - [ ] FilterMate_tr.ts (Turc)
  - [ ] FilterMate_hi.ts (Hindi)
  - [ ] FilterMate_fi.ts (Finnois)
  - [ ] FilterMate_da.ts (Danois)
  - [ ] FilterMate_sv.ts (Suédois)
  - [ ] FilterMate_nb.ts (Norvégien)

### Phase 2 - Configuration

- [ ] Mise à jour de config.default.json
- [ ] Mise à jour de config_schema.json
- [ ] Test du sélecteur de langue

### Phase 3 - Traduction (Haute priorité)

- [ ] Traduction Polonais (pl)
- [ ] Traduction Chinois (zh)
- [ ] Traduction Russe (ru)

### Phase 4 - Traduction (Priorité moyenne)

- [ ] Traduction Indonésien (id)
- [ ] Traduction Vietnamien (vi)
- [ ] Traduction Turc (tr)
- [ ] Traduction Hindi (hi)
- [ ] Traduction Finnois (fi)
- [ ] Traduction Danois (da)
- [ ] Traduction Suédois (sv)
- [ ] Traduction Norvégien (nb)

### Phase 5 - Validation

- [ ] Compilation de tous les fichiers .qm
- [ ] Tests fonctionnels
- [ ] Révision par locuteurs natifs

---

## 📊 Statistiques de Messages

Basé sur `FilterMate_en.ts`:

| Contexte                 | Nombre de messages |
| ------------------------ | ------------------ |
| FilterMate               | 13                 |
| FilterMateDockWidgetBase | 54                 |
| FilterMateDockWidget     | 15                 |
| FeedbackUtils            | 10                 |
| **Total**                | **~92 messages**   |

---

## 🌐 Ressources pour Traducteurs

### Terminologie GIS Standard

| Anglais       | Polonais     | Chinois | Russe        | Indonésien  | Vietnamien | Turc         | Hindi        | Finnois   | Danois        | Suédois       | Norvégien     |
| ------------- | ------------ | ------- | ------------ | ----------- | ---------- | ------------ | ------------ | --------- | ------------- | ------------- | ------------- |
| Filter        | Filtr        | 过滤    | Фильтр       | Filter      | Bộ lọc     | Filtre       | फ़िल्टर      | Suodatin  | Filter        | Filter        | Filter        |
| Layer         | Warstwa      | 图层    | Слой         | Layer       | Lớp        | Katman       | लेयर         | Taso      | Lag           | Lager         | Lag           |
| Feature       | Obiekt       | 要素    | Объект       | Fitur       | Đối tượng  | Özellik      | फ़ीचर        | Kohde     | Objekt        | Objekt        | Objekt        |
| Expression    | Wyrażenie    | 表达式  | Выражение    | Ekspresi    | Biểu thức  | İfade        | एक्सप्रेशन   | Lauseke   | Udtryk        | Uttryck       | Uttrykk       |
| Buffer        | Bufor        | 缓冲区  | Буфер        | Buffer      | Vùng đệm   | Tampon       | बफ़र         | Puskuri   | Buffer        | Buffert       | Buffer        |
| Export        | Eksport      | 导出    | Экспорт      | Ekspor      | Xuất       | Dışa Aktar   | निर्यात      | Vie       | Eksporter     | Exportera     | Eksporter     |
| Configuration | Konfiguracja | 配置    | Конфигурация | Konfigurasi | Cấu hình   | Yapılandırma | कॉन्फ़िगरेशन | Asetukset | Konfiguration | Konfiguration | Konfigurasjon |

### Références QGIS

- [QGIS Translation Guidelines](https://qgis.org/en/site/getinvolved/translate.html)
- [Transifex QGIS Project](https://www.transifex.com/qgis/)
- [QGIS Terminology Glossary](https://docs.qgis.org/)

---

## 📅 Calendrier Prévisionnel

| Phase              | Début       | Fin         | Livrable                       |
| ------------------ | ----------- | ----------- | ------------------------------ |
| Préparation        | 22 déc 2025 | 23 déc 2025 | Fichiers .ts de base           |
| Traduction P1      | 24 déc 2025 | 15 jan 2026 | pl, zh, ru                     |
| Traduction P2      | 16 jan 2026 | 15 fév 2026 | id, vi, tr, hi, fi, da, sv, nb |
| Validation         | 16 fév 2026 | 28 fév 2026 | Tests complets                 |
| **Release v2.4.0** | 1 mar 2026  | -           | 11 nouvelles langues           |

---

## 📞 Contacts Communauté

Pour recruter des traducteurs volontaires:

- **Forum QGIS**: https://lists.osgeo.org/mailman/listinfo/qgis-community-team
- **Discord QGIS**: #translations
- **GitHub Issues**: Créer des issues "Help Wanted" par langue

---

_Document créé automatiquement - FilterMate Translation Management_
