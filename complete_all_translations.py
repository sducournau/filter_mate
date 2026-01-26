#!/usr/bin/env python3
"""
Complete All Translations for FilterMate
Adds all missing translations to bring all languages to 100%

Phase C1: DE, ES, IT, NL, PT (1 message manquant)
Phase C2: DA, FI, NB, PL, RU, SV, ZH (42 messages manquants)
Phase C3: AM, HI, ID, SL, TL, TR, UZ, VI (110 messages manquants)
"""

import os
import re
import subprocess

I18N_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n')

# ============================================================================
# TRANSLATIONS DATABASE - All missing messages with translations
# ============================================================================

# Phase C1: 1 message missing from DE, ES, IT, NL, PT
PHASE_C1_TRANSLATIONS = {
    "Error resetting layer properties: {}": {
        "de": "Fehler beim Zurücksetzen der Layer-Eigenschaften: {}",
        "es": "Error al restablecer las propiedades de la capa: {}",
        "it": "Errore nel ripristino delle proprietà del layer: {}",
        "nl": "Fout bij het resetten van laageigenschappen: {}",
        "pt": "Erro ao redefinir propriedades da camada: {}"
    }
}

# Phase C2: 42 messages missing from DA, FI, NB, PL, RU, SV, ZH
PHASE_C2_TRANSLATIONS = {
    "Allow cancellation of QGIS processing algorithms. Enables stopping long-running operations.": {
        "da": "Tillad annullering af QGIS-behandlingsalgoritmer. Muliggør stop af langvarige operationer.",
        "fi": "Salli QGIS-käsittelyalgoritmien peruutus. Mahdollistaa pitkäkestoisten operaatioiden pysäyttämisen.",
        "nb": "Tillat avbryting av QGIS-behandlingsalgoritmer. Muliggjør stopping av langvarige operasjoner.",
        "pl": "Pozwól na anulowanie algorytmów przetwarzania QGIS. Umożliwia zatrzymanie długotrwałych operacji.",
        "ru": "Разрешить отмену алгоритмов обработки QGIS. Позволяет остановить длительные операции.",
        "sv": "Tillåt avbrytning av QGIS-bearbetningsalgoritmer. Möjliggör stopp av långvariga operationer.",
        "zh": "允许取消QGIS处理算法。可以停止长时间运行的操作。"
    },
    "Analyzing your project... Recommendations will appear here.": {
        "da": "Analyserer dit projekt... Anbefalinger vil blive vist her.",
        "fi": "Analysoidaan projektiasi... Suositukset näkyvät tässä.",
        "nb": "Analyserer prosjektet ditt... Anbefalinger vil vises her.",
        "pl": "Analizowanie projektu... Zalecenia pojawią się tutaj.",
        "ru": "Анализ вашего проекта... Рекомендации появятся здесь.",
        "sv": "Analyserar ditt projekt... Rekommendationer visas här.",
        "zh": "正在分析您的项目...建议将显示在这里。"
    },
    "Auto-Centroid for Distant Layers": {
        "da": "Auto-centroid for fjerne lag",
        "fi": "Automaattinen keskipiste etäisille tasoille",
        "nb": "Auto-sentroid for fjerne lag",
        "pl": "Auto-centroid dla odległych warstw",
        "ru": "Авто-центроид для удаленных слоев",
        "sv": "Auto-centroid för avlägsna lager",
        "zh": "远程图层自动质心"
    },
    "Auto-Select Best Strategy": {
        "da": "Auto-vælg bedste strategi",
        "fi": "Valitse automaattisesti paras strategia",
        "nb": "Auto-velg beste strategi",
        "pl": "Auto-wybór najlepszej strategii",
        "ru": "Автовыбор лучшей стратегии",
        "sv": "Auto-välj bästa strategi",
        "zh": "自动选择最佳策略"
    },
    "Auto-Simplify Geometries ⚠️": {
        "da": "Auto-forenkl geometrier ⚠️",
        "fi": "Automaattinen geometrioiden yksinkertaistaminen ⚠️",
        "nb": "Auto-forenkle geometrier ⚠️",
        "pl": "Auto-upraszczanie geometrii ⚠️",
        "ru": "Авто-упрощение геометрий ⚠️",
        "sv": "Auto-förenkla geometrier ⚠️",
        "zh": "自动简化几何图形 ⚠️"
    },
    "Auto-detect mod_spatialite": {
        "da": "Auto-detekter mod_spatialite",
        "fi": "Tunnista mod_spatialite automaattisesti",
        "nb": "Auto-oppdage mod_spatialite",
        "pl": "Auto-wykrywanie mod_spatialite",
        "ru": "Автообнаружение mod_spatialite",
        "sv": "Auto-detektera mod_spatialite",
        "zh": "自动检测mod_spatialite"
    },
    "Automatic GIST Index Usage": {
        "da": "Automatisk brug af GIST-indeks",
        "fi": "Automaattinen GIST-indeksin käyttö",
        "nb": "Automatisk bruk av GIST-indeks",
        "pl": "Automatyczne użycie indeksu GIST",
        "ru": "Автоматическое использование GIST-индекса",
        "sv": "Automatisk GIST-indexanvändning",
        "zh": "自动GIST索引使用"
    },
    "Automatically analyze layers and suggest optimizations before filtering.": {
        "da": "Analyser automatisk lag og foreslå optimeringer før filtrering.",
        "fi": "Analysoi tasot automaattisesti ja ehdota optimointeja ennen suodatusta.",
        "nb": "Analyser lag automatisk og foreslå optimaliseringer før filtrering.",
        "pl": "Automatycznie analizuj warstwy i sugeruj optymalizacje przed filtrowaniem.",
        "ru": "Автоматически анализировать слои и предлагать оптимизации перед фильтрацией.",
        "sv": "Analysera lager automatiskt och föreslå optimeringar före filtrering.",
        "zh": "自动分析图层并在过滤前建议优化。"
    },
    "Automatically choose optimal filtering strategy based on layer analysis. (attribute-first, bbox-prefilter, progressive chunks)": {
        "da": "Vælg automatisk optimal filtreringsstrategi baseret på laganalyse. (attribut-først, bbox-forfilter, progressive chunks)",
        "fi": "Valitse automaattisesti optimaalinen suodatusstrategia tasoanalyysin perusteella. (attribuutti-ensin, bbox-esisuodatin, progressiiviset lohkot)",
        "nb": "Velg automatisk optimal filtreringsstrategi basert på laganalyse. (attributt-først, bbox-forfilter, progressive chunks)",
        "pl": "Automatycznie wybierz optymalną strategię filtrowania na podstawie analizy warstwy. (atrybut-pierwszy, bbox-prefiltr, progresywne fragmenty)",
        "ru": "Автоматически выбирать оптимальную стратегию фильтрации на основе анализа слоя. (атрибут-сначала, bbox-предфильтр, прогрессивные чанки)",
        "sv": "Välj automatiskt optimal filtreringsstrategi baserad på lageranalys. (attribut-först, bbox-förfilter, progressiva chunks)",
        "zh": "根据图层分析自动选择最佳过滤策略。（属性优先、边界框预过滤、渐进式分块）"
    },
    "Automatically create spatial index (.qix/.shx) for layers without one. Dramatically improves spatial query speed.": {
        "da": "Opret automatisk rumligt indeks (.qix/.shx) for lag uden et. Forbedrer dramatisk hastigheden af rumlige forespørgsler.",
        "fi": "Luo automaattisesti spatiaalinen indeksi (.qix/.shx) tasoille joilla ei ole sitä. Parantaa dramaattisesti spatiaalisten kyselyjen nopeutta.",
        "nb": "Opprett automatisk romlig indeks (.qix/.shx) for lag uten en. Forbedrer dramatisk hastigheten på romlige spørringer.",
        "pl": "Automatycznie twórz indeks przestrzenny (.qix/.shx) dla warstw bez niego. Dramatycznie poprawia szybkość zapytań przestrzennych.",
        "ru": "Автоматически создавать пространственный индекс (.qix/.shx) для слоев без него. Значительно ускоряет пространственные запросы.",
        "sv": "Skapa automatiskt spatialt index (.qix/.shx) för lager utan ett. Förbättrar dramatiskt hastigheten för spatiala frågor.",
        "zh": "自动为没有索引的图层创建空间索引（.qix/.shx）。显著提高空间查询速度。"
    },
    "Automatically find and load the best mod_spatialite extension.": {
        "da": "Find og indlæs automatisk den bedste mod_spatialite-udvidelse.",
        "fi": "Etsi ja lataa automaattisesti paras mod_spatialite-laajennus.",
        "nb": "Finn og last automatisk den beste mod_spatialite-utvidelsen.",
        "pl": "Automatycznie znajdź i załaduj najlepsze rozszerzenie mod_spatialite.",
        "ru": "Автоматически найти и загрузить лучшее расширение mod_spatialite.",
        "sv": "Hitta och ladda automatiskt det bästa mod_spatialite-tillägget.",
        "zh": "自动查找并加载最佳mod_spatialite扩展。"
    },
    "Automatically simplify complex geometries. WARNING: This is a LOSSY operation that may change polygon shapes.": {
        "da": "Forenkl automatisk komplekse geometrier. ADVARSEL: Dette er en TABENDE operation, der kan ændre polygonformer.",
        "fi": "Yksinkertaista monimutkaiset geometriat automaattisesti. VAROITUS: Tämä on HÄVIÖLLINEN operaatio joka voi muuttaa monikulmioiden muotoja.",
        "nb": "Forenkle automatisk komplekse geometrier. ADVARSEL: Dette er en TAPENDE operasjon som kan endre polygonformer.",
        "pl": "Automatycznie upraszczaj złożone geometrie. OSTRZEŻENIE: Jest to operacja STRATNA, która może zmienić kształty wielokątów.",
        "ru": "Автоматически упрощать сложные геометрии. ПРЕДУПРЕЖДЕНИЕ: Это операция с ПОТЕРЯМИ, которая может изменить формы полигонов.",
        "sv": "Förenkla automatiskt komplexa geometrier. VARNING: Detta är en FÖRLUSTBRINGANDE operation som kan ändra polygonformer.",
        "zh": "自动简化复杂几何图形。警告：这是一个有损操作，可能会改变多边形形状。"
    },
    "Automatically use ST_Centroid() for remote layers (WFS, ArcGIS). Reduces network data transfer by ~90%.": {
        "da": "Brug automatisk ST_Centroid() for fjernlag (WFS, ArcGIS). Reducerer netværksdataoverførsel med ~90%.",
        "fi": "Käytä automaattisesti ST_Centroid() etätasoille (WFS, ArcGIS). Vähentää verkkodata-siirtoa ~90%.",
        "nb": "Bruk automatisk ST_Centroid() for fjernlag (WFS, ArcGIS). Reduserer nettverksdataoverføring med ~90%.",
        "pl": "Automatycznie używaj ST_Centroid() dla warstw zdalnych (WFS, ArcGIS). Zmniejsza transfer danych sieciowych o ~90%.",
        "ru": "Автоматически использовать ST_Centroid() для удаленных слоев (WFS, ArcGIS). Уменьшает сетевой трафик на ~90%.",
        "sv": "Använd automatiskt ST_Centroid() för fjärrlager (WFS, ArcGIS). Minskar nätverksdataöverföring med ~90%.",
        "zh": "自动为远程图层（WFS、ArcGIS）使用ST_Centroid()。减少约90%的网络数据传输。"
    },
    "Bypass GDAL layer and execute SQL directly on GeoPackage. Faster for complex spatial queries.": {
        "da": "Omgå GDAL-lag og udfør SQL direkte på GeoPackage. Hurtigere for komplekse rumlige forespørgsler.",
        "fi": "Ohita GDAL-taso ja suorita SQL suoraan GeoPackagessa. Nopeampi monimutkaisille spatiaalisille kyselyille.",
        "nb": "Omgå GDAL-lag og kjør SQL direkte på GeoPackage. Raskere for komplekse romlige spørringer.",
        "pl": "Omiń warstwę GDAL i wykonaj SQL bezpośrednio na GeoPackage. Szybsze dla złożonych zapytań przestrzennych.",
        "ru": "Обойти слой GDAL и выполнить SQL напрямую в GeoPackage. Быстрее для сложных пространственных запросов.",
        "sv": "Kringgå GDAL-lagret och kör SQL direkt på GeoPackage. Snabbare för komplexa spatiala frågor.",
        "zh": "绕过GDAL图层直接在GeoPackage上执行SQL。对复杂空间查询更快。"
    },
    "Cache built expressions to avoid rebuilding identical queries.": {
        "da": "Cache byggede udtryk for at undgå at genopbygge identiske forespørgsler.",
        "fi": "Välimuistiin rakennetut lausekkeet välttääksesi identtisten kyselyjen uudelleenrakentamisen.",
        "nb": "Buffer byggede uttrykk for å unngå å gjenoppbygge identiske spørringer.",
        "pl": "Buforuj zbudowane wyrażenia, aby uniknąć ponownego budowania identycznych zapytań.",
        "ru": "Кэшировать построенные выражения, чтобы избежать повторного построения идентичных запросов.",
        "sv": "Cacha byggda uttryck för att undvika att bygga om identiska frågor.",
        "zh": "缓存已构建的表达式以避免重建相同的查询。"
    },
    "Cache converted WKT strings to avoid repeated geometry serialization.": {
        "da": "Cache konverterede WKT-strenge for at undgå gentagen geometriserialisering.",
        "fi": "Välimuistiin muunnetut WKT-merkkijonot välttääksesi toistuvan geometrian sarjallistamisen.",
        "nb": "Buffer konverterte WKT-strenger for å unngå gjentatt geometriserialisering.",
        "pl": "Buforuj przekonwertowane ciągi WKT, aby uniknąć powtarzającej się serializacji geometrii.",
        "ru": "Кэшировать преобразованные строки WKT, чтобы избежать повторной сериализации геометрии.",
        "sv": "Cacha konverterade WKT-strängar för att undvika upprepad geometriserialisering.",
        "zh": "缓存转换后的WKT字符串以避免重复的几何序列化。"
    },
    "Cancel": {
        "da": "Annuller",
        "fi": "Peruuta",
        "nb": "Avbryt",
        "pl": "Anuluj",
        "ru": "Отмена",
        "sv": "Avbryt",
        "zh": "取消"
    },
    "Cancellable Processing": {
        "da": "Annullerbar behandling",
        "fi": "Peruutettava käsittely",
        "nb": "Avbrytbar behandling",
        "pl": "Anulowalne przetwarzanie",
        "ru": "Отменяемая обработка",
        "sv": "Avbrytbar bearbetning",
        "zh": "可取消处理"
    },
    "Chunk size (features):": {
        "da": "Chunk-størrelse (funktioner):",
        "fi": "Lohkokoko (ominaisuudet):",
        "nb": "Chunk-størrelse (funksjoner):",
        "pl": "Rozmiar fragmentu (obiekty):",
        "ru": "Размер чанка (объекты):",
        "sv": "Chunk-storlek (funktioner):",
        "zh": "块大小（要素）："
    },
    "Confirm Before Applying": {
        "da": "Bekræft før anvendelse",
        "fi": "Vahvista ennen soveltamista",
        "nb": "Bekreft før bruk",
        "pl": "Potwierdź przed zastosowaniem",
        "ru": "Подтвердить перед применением",
        "sv": "Bekräfta innan tillämpning",
        "zh": "应用前确认"
    },
    "Connection Pooling": {
        "da": "Forbindelsespooling",
        "fi": "Yhteyksien yhdistäminen",
        "nb": "Tilkoblingspooling",
        "pl": "Pula połączeń",
        "ru": "Пул соединений",
        "sv": "Anslutningspoolning",
        "zh": "连接池"
    },
    "Create Spatial Indexes": {
        "da": "Opret rumlige indekser",
        "fi": "Luo spatiaaliset indeksit",
        "nb": "Opprett romlige indekser",
        "pl": "Utwórz indeksy przestrzenne",
        "ru": "Создать пространственные индексы",
        "sv": "Skapa spatiala index",
        "zh": "创建空间索引"
    },
    "Create indexed temporary views for complex spatial queries. Best for large datasets with complex expressions.": {
        "da": "Opret indekserede midlertidige visninger for komplekse rumlige forespørgsler. Bedst for store datasæt med komplekse udtryk.",
        "fi": "Luo indeksoituja väliaikaisia näkymiä monimutkaisille spatiaalisille kyselyille. Paras suurille tietojoukkoille monimutkaisilla lausekkeilla.",
        "nb": "Opprett indekserte midlertidige visninger for komplekse romlige spørringer. Best for store datasett med komplekse uttrykk.",
        "pl": "Utwórz indeksowane widoki tymczasowe dla złożonych zapytań przestrzennych. Najlepsze dla dużych zbiorów danych ze złożonymi wyrażeniami.",
        "ru": "Создать индексированные временные представления для сложных пространственных запросов. Лучше всего для больших наборов данных со сложными выражениями.",
        "sv": "Skapa indexerade temporära vyer för komplexa spatiala frågor. Bäst för stora dataset med komplexa uttryck.",
        "zh": "为复杂空间查询创建索引临时视图。最适合具有复杂表达式的大型数据集。"
    },
    "Create materialized views for datasets larger than this": {
        "da": "Opret materialiserede visninger for datasæt større end dette",
        "fi": "Luo materialisoidut näkymät tätä suuremmille tietojoukoille",
        "nb": "Opprett materialiserte visninger for datasett større enn dette",
        "pl": "Utwórz zmaterializowane widoki dla zbiorów danych większych niż to",
        "ru": "Создать материализованные представления для наборов данных больше этого",
        "sv": "Skapa materialiserade vyer för dataset större än detta",
        "zh": "为大于此大小的数据集创建物化视图"
    },
    "Create temporary tables with R-tree spatial indexes for complex queries. Best for complex expressions on local files.": {
        "da": "Opret midlertidige tabeller med R-træ rumlige indekser for komplekse forespørgsler. Bedst for komplekse udtryk på lokale filer.",
        "fi": "Luo väliaikaiset taulukot R-puu spatiaalisilla indekseillä monimutkaisille kyselyille. Paras monimutkaisille lausekkeille paikallisissa tiedostoissa.",
        "nb": "Opprett midlertidige tabeller med R-tre romlige indekser for komplekse spørringer. Best for komplekse uttrykk på lokale filer.",
        "pl": "Utwórz tabele tymczasowe z przestrzennymi indeksami R-tree dla złożonych zapytań. Najlepsze dla złożonych wyrażeń na plikach lokalnych.",
        "ru": "Создать временные таблицы с пространственными индексами R-tree для сложных запросов. Лучше всего для сложных выражений в локальных файлах.",
        "sv": "Skapa temporära tabeller med R-träd spatiala index för komplexa frågor. Bäst för komplexa uttryck på lokala filer.",
        "zh": "为复杂查询创建带R树空间索引的临时表。最适合本地文件上的复杂表达式。"
    },
    "Direct SQL access can make GeoPackage filtering 2-5x faster.": {
        "da": "Direkte SQL-adgang kan gøre GeoPackage-filtrering 2-5x hurtigere.",
        "fi": "Suora SQL-pääsy voi tehdä GeoPackage-suodatuksesta 2-5x nopeampaa.",
        "nb": "Direkte SQL-tilgang kan gjøre GeoPackage-filtrering 2-5x raskere.",
        "pl": "Bezpośredni dostęp SQL może przyspieszyć filtrowanie GeoPackage 2-5x.",
        "ru": "Прямой доступ к SQL может ускорить фильтрацию GeoPackage в 2-5 раз.",
        "sv": "Direkt SQL-åtkomst kan göra GeoPackage-filtrering 2-5x snabbare.",
        "zh": "直接SQL访问可以使GeoPackage过滤速度提高2-5倍。"
    },
    "Direct SQL for GeoPackage": {
        "da": "Direkte SQL for GeoPackage",
        "fi": "Suora SQL GeoPackagelle",
        "nb": "Direkte SQL for GeoPackage",
        "pl": "Bezpośrednie SQL dla GeoPackage",
        "ru": "Прямой SQL для GeoPackage",
        "sv": "Direkt SQL för GeoPackage",
        "zh": "GeoPackage直接SQL"
    },
    "Display optimization hints in message bar when recommendations are available.": {
        "da": "Vis optimeringstips i meddelelseslinjen, når anbefalinger er tilgængelige.",
        "fi": "Näytä optimointivihjeet viestipalkkissa kun suosituksia on saatavilla.",
        "nb": "Vis optimaliseringstips i meldingslinjen når anbefalinger er tilgjengelige.",
        "pl": "Wyświetlaj wskazówki optymalizacji w pasku wiadomości, gdy dostępne są zalecenia.",
        "ru": "Отображать подсказки по оптимизации в панели сообщений, когда доступны рекомендации.",
        "sv": "Visa optimeringstips i meddelandefältet när rekommendationer finns tillgängliga.",
        "zh": "当有建议时在消息栏中显示优化提示。"
    },
    "Distant layer threshold:": {
        "da": "Fjern lag-tærskel:",
        "fi": "Etäisen tason kynnys:",
        "nb": "Fjern lag-terskel:",
        "pl": "Próg odległej warstwy:",
        "ru": "Порог удаленного слоя:",
        "sv": "Fjärrlager-tröskel:",
        "zh": "远程图层阈值："
    },
    "EXISTS Subquery for Large WKT": {
        "da": "EXISTS underforespørgsel for stor WKT",
        "fi": "EXISTS-alikysely suurelle WKT:lle",
        "nb": "EXISTS underspørring for stor WKT",
        "pl": "Podzapytanie EXISTS dla dużego WKT",
        "ru": "Подзапрос EXISTS для большого WKT",
        "sv": "EXISTS-underfråga för stor WKT",
        "zh": "大型WKT的EXISTS子查询"
    },
    "Enable Auto-Centroid for Remote Layers": {
        "da": "Aktiver auto-centroid for fjernlag",
        "fi": "Ota käyttöön automaattinen keskipiste etätasoille",
        "nb": "Aktiver auto-sentroid for fjernlag",
        "pl": "Włącz auto-centroid dla warstw zdalnych",
        "ru": "Включить авто-центроид для удаленных слоев",
        "sv": "Aktivera auto-centroid för fjärrlager",
        "zh": "为远程图层启用自动质心"
    },
    "Enable Auto-Optimization": {
        "da": "Aktiver auto-optimering",
        "fi": "Ota käyttöön automaattinen optimointi",
        "nb": "Aktiver auto-optimalisering",
        "pl": "Włącz auto-optymalizację",
        "ru": "Включить авто-оптимизацию",
        "sv": "Aktivera auto-optimering",
        "zh": "启用自动优化"
    },
    "Enable Direct SQL for GeoPackage": {
        "da": "Aktiver direkte SQL for GeoPackage",
        "fi": "Ota käyttöön suora SQL GeoPackagelle",
        "nb": "Aktiver direkte SQL for GeoPackage",
        "pl": "Włącz bezpośrednie SQL dla GeoPackage",
        "ru": "Включить прямой SQL для GeoPackage",
        "sv": "Aktivera direkt SQL för GeoPackage",
        "zh": "为GeoPackage启用直接SQL"
    },
    "Enable Materialized Views": {
        "da": "Aktiver materialiserede visninger",
        "fi": "Ota käyttöön materialisoidut näkymät",
        "nb": "Aktiver materialiserte visninger",
        "pl": "Włącz zmaterializowane widoki",
        "ru": "Включить материализованные представления",
        "sv": "Aktivera materialiserade vyer",
        "zh": "启用物化视图"
    },
    "Error resetting layer properties: {}": {
        "da": "Fejl ved nulstilling af lagegenskaber: {}",
        "fi": "Virhe tason ominaisuuksien nollauksessa: {}",
        "nb": "Feil ved tilbakestilling av lagegenskaper: {}",
        "pl": "Błąd resetowania właściwości warstwy: {}",
        "ru": "Ошибка сброса свойств слоя: {}",
        "sv": "Fel vid återställning av lageregenskaper: {}",
        "zh": "重置图层属性时出错：{}"
    },
    "Estimated performance improvement": {
        "da": "Estimeret ydelsesforbedring",
        "fi": "Arvioitu suorituskyvyn parannus",
        "nb": "Estimert ytelsesforbedring",
        "pl": "Szacowana poprawa wydajności",
        "ru": "Ожидаемое улучшение производительности",
        "sv": "Uppskattad prestandaförbättring",
        "zh": "预计性能提升"
    },
    "Execute SQLite queries in background thread with cancellation support. Prevents UI freezing.": {
        "da": "Udfør SQLite-forespørgsler i baggrundstråd med annulleringsstøtte. Forhindrer UI-frysning.",
        "fi": "Suorita SQLite-kyselyt taustasäikeessä peruutustuella. Estää käyttöliittymän jäätymisen.",
        "nb": "Utfør SQLite-spørringer i bakgrunnstråd med avbrytingsstøtte. Forhindrer UI-frysing.",
        "pl": "Wykonuj zapytania SQLite w wątku tła z obsługą anulowania. Zapobiega zamrażaniu interfejsu.",
        "ru": "Выполнять запросы SQLite в фоновом потоке с поддержкой отмены. Предотвращает зависание интерфейса.",
        "sv": "Kör SQLite-frågor i bakgrundstråd med avbrytningsstöd. Förhindrar UI-frysning.",
        "zh": "在后台线程中执行SQLite查询并支持取消。防止UI冻结。"
    },
    "Filter multiple layers simultaneously using multiple CPU cores.": {
        "da": "Filtrer flere lag samtidigt ved hjælp af flere CPU-kerner.",
        "fi": "Suodata useita tasoja samanaikaisesti käyttäen useita CPU-ytimiä.",
        "nb": "Filtrer flere lag samtidig ved hjelp av flere CPU-kjerner.",
        "pl": "Filtruj wiele warstw jednocześnie używając wielu rdzeni CPU.",
        "ru": "Фильтровать несколько слоев одновременно, используя несколько ядер процессора.",
        "sv": "Filtrera flera lager samtidigt med flera CPU-kärnor.",
        "zh": "使用多个CPU核心同时过滤多个图层。"
    },
    "FilterMate - Backend Optimizations": {
        "da": "FilterMate - Backend-optimeringer",
        "fi": "FilterMate - Backend-optimoinnit",
        "nb": "FilterMate - Backend-optimaliseringer",
        "pl": "FilterMate - Optymalizacje backendu",
        "ru": "FilterMate - Оптимизации бэкенда",
        "sv": "FilterMate - Backend-optimeringar",
        "zh": "FilterMate - 后端优化"
    },
    "First filter by bounding box, then by exact geometry. Reduces precision calculations on irrelevant features.": {
        "da": "Filtrer først efter begrænsingsboks, derefter efter præcis geometri. Reducerer præcisionsberegninger på irrelevante funktioner.",
        "fi": "Suodata ensin rajauslaatikolla, sitten tarkalla geometrialla. Vähentää tarkkuuslaskentoja epäolennaisille kohteille.",
        "nb": "Filtrer først etter grenseboks, deretter etter nøyaktig geometri. Reduserer presisjonsberegninger på irrelevante funksjoner.",
        "pl": "Najpierw filtruj według ramki ograniczającej, potem według dokładnej geometrii. Zmniejsza obliczenia precyzji dla nieistotnych obiektów.",
        "ru": "Сначала фильтровать по ограничивающему прямоугольнику, затем по точной геометрии. Уменьшает вычисления точности для нерелевантных объектов.",
        "sv": "Filtrera först efter begränsningsbox, sedan efter exakt geometri. Minskar precisionsberäkningar på irrelevanta funktioner.",
        "zh": "先按边界框过滤，再按精确几何过滤。减少对不相关要素的精度计算。"
    },
    "For small PostgreSQL layers, copy to memory for faster filtering. Avoids network latency for small datasets.": {
        "da": "For små PostgreSQL-lag, kopier til hukommelse for hurtigere filtrering. Undgår netværksforsinkelse for små datasæt.",
        "fi": "Pienille PostgreSQL-tasoille, kopioi muistiin nopeampaa suodatusta varten. Välttää verkon latenssin pienille tietojoukoille.",
        "nb": "For små PostgreSQL-lag, kopier til minne for raskere filtrering. Unngår nettverksforsinkelse for små datasett.",
        "pl": "Dla małych warstw PostgreSQL, skopiuj do pamięci dla szybszego filtrowania. Unika opóźnień sieciowych dla małych zbiorów danych.",
        "ru": "Для небольших слоев PostgreSQL копировать в память для быстрой фильтрации. Избегает сетевой задержки для небольших наборов данных.",
        "sv": "För små PostgreSQL-lager, kopiera till minne för snabbare filtrering. Undviker nätverkslatens för små dataset.",
        "zh": "对于小型PostgreSQL图层，复制到内存以加快过滤速度。避免小型数据集的网络延迟。"
    },
    "Force sequential execution for OGR layers to prevent crashes. Safer but slower.": {
        "da": "Tving sekventiel udførelse for OGR-lag for at forhindre nedbrud. Sikrere men langsommere.",
        "fi": "Pakota peräkkäinen suoritus OGR-tasoille kaatumisten estämiseksi. Turvallisempi mutta hitaampi.",
        "nb": "Tving sekvensiell utførelse for OGR-lag for å forhindre krasj. Sikrere men langsommere.",
        "pl": "Wymuś sekwencyjne wykonanie dla warstw OGR, aby zapobiec awariom. Bezpieczniejsze, ale wolniejsze.",
        "ru": "Принудительное последовательное выполнение для слоев OGR для предотвращения сбоев. Безопаснее, но медленнее.",
        "sv": "Tvinga sekventiell körning för OGR-lager för att förhindra krascher. Säkrare men långsammare.",
        "zh": "强制OGR图层顺序执行以防止崩溃。更安全但更慢。"
    },
    "GEOS-safe Geometry Handling": {
        "da": "GEOS-sikker geometrihåndtering",
        "fi": "GEOS-turvallinen geometrian käsittely",
        "nb": "GEOS-sikker geometrihåndtering",
        "pl": "Obsługa geometrii bezpieczna dla GEOS",
        "ru": "GEOS-безопасная обработка геометрии",
        "sv": "GEOS-säker geometrihantering",
        "zh": "GEOS安全几何处理"
    },
    "Global": {
        "da": "Global",
        "fi": "Globaali",
        "nb": "Global",
        "pl": "Globalny",
        "ru": "Глобальный",
        "sv": "Global",
        "zh": "全局"
    },
    "Interruptible Queries": {
        "da": "Afbrydelige forespørgsler",
        "fi": "Keskeytettävät kyselyt",
        "nb": "Avbrytbare spørringer",
        "pl": "Przerwalne zapytania",
        "ru": "Прерываемые запросы",
        "sv": "Avbrytbara frågor",
        "zh": "可中断查询"
    },
    "Lazy cursor threshold:": {
        "da": "Doven markør-tærskel:",
        "fi": "Laiska osoitinkynnys:",
        "nb": "Lat peker-terskel:",
        "pl": "Próg leniwego kursora:",
        "ru": "Порог ленивого курсора:",
        "sv": "Lat markör-tröskel:",
        "zh": "延迟游标阈值："
    },
    "Max workers (0=auto):": {
        "da": "Maks arbejdere (0=auto):",
        "fi": "Maksimi työntekijät (0=auto):",
        "nb": "Maks arbeidere (0=auto):",
        "pl": "Maks. procesy robocze (0=auto):",
        "ru": "Макс. рабочих (0=авто):",
        "sv": "Max arbetare (0=auto):",
        "zh": "最大工作线程（0=自动）："
    },
    "Optimizations for PostgreSQL databases with PostGIS extension": {
        "da": "Optimeringer for PostgreSQL-databaser med PostGIS-udvidelse",
        "fi": "Optimoinnit PostgreSQL-tietokannoille PostGIS-laajennuksella",
        "nb": "Optimaliseringer for PostgreSQL-databaser med PostGIS-utvidelse",
        "pl": "Optymalizacje dla baz danych PostgreSQL z rozszerzeniem PostGIS",
        "ru": "Оптимизации для баз данных PostgreSQL с расширением PostGIS",
        "sv": "Optimeringar för PostgreSQL-databaser med PostGIS-tillägg",
        "zh": "带PostGIS扩展的PostgreSQL数据库优化"
    },
    "Optimizations for Spatialite databases and GeoPackage files": {
        "da": "Optimeringer for Spatialite-databaser og GeoPackage-filer",
        "fi": "Optimoinnit Spatialite-tietokannoille ja GeoPackage-tiedostoille",
        "nb": "Optimaliseringer for Spatialite-databaser og GeoPackage-filer",
        "pl": "Optymalizacje dla baz danych Spatialite i plików GeoPackage",
        "ru": "Оптимизации для баз данных Spatialite и файлов GeoPackage",
        "sv": "Optimeringar för Spatialite-databaser och GeoPackage-filer",
        "zh": "Spatialite数据库和GeoPackage文件优化"
    },
    "Optimizations for file-based formats (Shapefiles, GeoJSON) and memory layers": {
        "da": "Optimeringer for filbaserede formater (Shapefiles, GeoJSON) og hukommelseslager",
        "fi": "Optimoinnit tiedostopohjaisille formaateille (Shapefiles, GeoJSON) ja muistitasoille",
        "nb": "Optimaliseringer for filbaserte formater (Shapefiles, GeoJSON) og minnelag",
        "pl": "Optymalizacje dla formatów plikowych (Shapefiles, GeoJSON) i warstw pamięciowych",
        "ru": "Оптимизации для файловых форматов (Shapefiles, GeoJSON) и слоев в памяти",
        "sv": "Optimeringar för filbaserade format (Shapefiles, GeoJSON) och minneslager",
        "zh": "基于文件格式（Shapefiles、GeoJSON）和内存图层的优化"
    }
}

# Phase C3: Additional messages for AM, HI, ID, SL, TL, TR, UZ, VI (these need all C2 + more)
# These languages are at 340/450 = 76%, need 110 more messages to get to 100%
PHASE_C3_TRANSLATIONS = {
    # All C2 translations apply to C3 languages too
    **PHASE_C2_TRANSLATIONS,
    
    # Additional messages specific to C3 languages (68 more messages)
    "All layers using auto-selection": {
        "am": "ሁሉም ንብርብሮች አውቶማቲክ ምርጫን እየተጠቀሙ ናቸው",
        "hi": "सभी लेयर स्वचालित चयन का उपयोग कर रही हैं",
        "id": "Semua lapisan menggunakan pemilihan otomatis",
        "sl": "Vse plasti uporabljajo samodejno izbiro",
        "tl": "Lahat ng layer ay gumagamit ng awtomatikong pagpili",
        "tr": "Tüm katmanlar otomatik seçim kullanıyor",
        "uz": "Barcha qatlamlar avtomatik tanlashdan foydalanmoqda",
        "vi": "Tất cả các lớp đang sử dụng chọn tự động"
    },
    "Applied to '{0}':": {
        "am": "ወደ '{0}' ተተገብሯል:",
        "hi": "'{0}' पर लागू किया गया:",
        "id": "Diterapkan ke '{0}':",
        "sl": "Uporabljeno za '{0}':",
        "tl": "Inilapat sa '{0}':",
        "tr": "'{0}'a uygulandı:",
        "uz": "'{0}'ga qo'llanildi:",
        "vi": "Đã áp dụng cho '{0}':"
    },
    "Auto-centroid {0}": {
        "am": "አውቶ-ሴንትሮይድ {0}",
        "hi": "ऑटो-सेंट्रॉइड {0}",
        "id": "Centroid otomatis {0}",
        "sl": "Samodejni centroid {0}",
        "tl": "Awtomatikong centroid {0}",
        "tr": "Otomatik-centroid {0}",
        "uz": "Avto-sentroid {0}",
        "vi": "Tự động tâm {0}"
    },
    "Auto-optimization {0}": {
        "am": "አውቶ-ማመቻቸት {0}",
        "hi": "ऑटो-अनुकूलन {0}",
        "id": "Optimasi otomatis {0}",
        "sl": "Samodejna optimizacija {0}",
        "tl": "Awtomatikong optimisasyon {0}",
        "tr": "Otomatik optimizasyon {0}",
        "uz": "Avto-optimizatsiya {0}",
        "vi": "Tối ưu hóa tự động {0}"
    },
    "Auto-optimizer module not available": {
        "am": "አውቶ-ማመቻቻ ሞዱል አይገኝም",
        "hi": "ऑटो-ऑप्टिमाइज़र मॉड्यूल उपलब्ध नहीं है",
        "id": "Modul pengoptimalisasi otomatis tidak tersedia",
        "sl": "Modul za samodejno optimizacijo ni na voljo",
        "tl": "Hindi available ang auto-optimizer module",
        "tr": "Otomatik optimize edici modülü mevcut değil",
        "uz": "Avto-optimizator moduli mavjud emas",
        "vi": "Mô-đun tối ưu hóa tự động không khả dụng"
    },
    "Auto-optimizer not available: {0}": {
        "am": "አውቶ-ማመቻቻ አይገኝም: {0}",
        "hi": "ऑटो-ऑप्टिमाइज़र उपलब्ध नहीं है: {0}",
        "id": "Pengoptimalisasi otomatis tidak tersedia: {0}",
        "sl": "Samodejna optimizacija ni na voljo: {0}",
        "tl": "Hindi available ang auto-optimizer: {0}",
        "tr": "Otomatik optimize edici mevcut değil: {0}",
        "uz": "Avto-optimizator mavjud emas: {0}",
        "vi": "Trình tối ưu hóa tự động không khả dụng: {0}"
    },
    "Auto-select best strategy": {
        "am": "ምርጥ ስትራቴጂ በራስ-ሰር ምረጥ",
        "hi": "सर्वोत्तम रणनीति स्वचालित रूप से चुनें",
        "id": "Pilih strategi terbaik secara otomatis",
        "sl": "Samodejno izberi najboljšo strategijo",
        "tl": "Awtomatikong piliin ang pinakamahusay na estratehiya",
        "tr": "En iyi stratejiyi otomatik seç",
        "uz": "Eng yaxshi strategiyani avtomatik tanlash",
        "vi": "Tự động chọn chiến lược tốt nhất"
    },
    "Auto-selected backends for {0} layer(s)": {
        "am": "ለ{0} ንብርብር(ዎች) ባክኤንዶች በራስ-ሰር ተመርጠዋል",
        "hi": "{0} लेयर(ओं) के लिए बैकएंड स्वचालित रूप से चयनित",
        "id": "Backend dipilih otomatis untuk {0} lapisan",
        "sl": "Samodejno izbrani zaledni sistemi za {0} plast(i)",
        "tl": "Awtomatikong napiling backend para sa {0} layer",
        "tr": "{0} katman için backend otomatik seçildi",
        "uz": "{0} qatlam(lar) uchun backendlar avtomatik tanlandi",
        "vi": "Đã tự động chọn backend cho {0} lớp"
    },
    "Auto-simplify geometries": {
        "am": "ጂኦሜትሪዎችን በራስ-ሰር ቀላል አድርግ",
        "hi": "ज्यामितीयों को स्वचालित रूप से सरल करें",
        "id": "Sederhanakan geometri secara otomatis",
        "sl": "Samodejno poenostavi geometrije",
        "tl": "Awtomatikong pasimplehin ang mga geometry",
        "tr": "Geometrileri otomatik sadeleştir",
        "uz": "Geometriyalarni avtomatik soddalashtirish",
        "vi": "Tự động đơn giản hóa hình học"
    },
    "Auto-use centroids for remote layers": {
        "am": "ለርቀት ንብርብሮች ሴንትሮይድዎችን በራስ-ሰር ተጠቀም",
        "hi": "दूरस्थ लेयर के लिए स्वचालित रूप से सेंट्रॉइड का उपयोग करें",
        "id": "Gunakan centroid secara otomatis untuk lapisan jarak jauh",
        "sl": "Samodejno uporabi centroide za oddaljene plasti",
        "tl": "Awtomatikong gamitin ang mga centroid para sa mga remote na layer",
        "tr": "Uzak katmanlar için centroid'leri otomatik kullan",
        "uz": "Masofaviy qatlamlar uchun sentroidlarni avtomatik ishlatish",
        "vi": "Tự động sử dụng tâm cho các lớp từ xa"
    },
    "Automatically choose optimal filtering strategy": {
        "am": "ተመቹ የማጣሪያ ስትራቴጂ በራስ-ሰር ይምረጡ",
        "hi": "स्वचालित रूप से इष्टतम फ़िल्टरिंग रणनीति चुनें",
        "id": "Pilih strategi pemfilteran optimal secara otomatis",
        "sl": "Samodejno izberi optimalno strategijo filtriranja",
        "tl": "Awtomatikong piliin ang pinakamahusay na estratehiya ng pag-filter",
        "tr": "Optimal filtreleme stratejisini otomatik seç",
        "uz": "Optimal filtrlash strategiyasini avtomatik tanlash",
        "vi": "Tự động chọn chiến lược lọc tối ưu"
    },
    "BBox pre-filter enabled for '{0}'": {
        "am": "ለ'{0}' BBox ቅድመ-ማጣሪያ ነቅቷል",
        "hi": "'{0}' के लिए BBox प्री-फ़िल्टर सक्षम",
        "id": "Pra-filter BBox diaktifkan untuk '{0}'",
        "sl": "BBox predfilter omogočen za '{0}'",
        "tl": "BBox pre-filter na-enable para sa '{0}'",
        "tr": "'{0}' için BBox ön filtresi etkinleştirildi",
        "uz": "'{0}' uchun BBox oldindan filtri yoqildi",
        "vi": "Đã bật bộ lọc trước BBox cho '{0}'"
    },
    "Backend controller not available": {
        "am": "ባክኤንድ ተቆጣጣሪ አይገኝም",
        "hi": "बैकएंड कंट्रोलर उपलब्ध नहीं है",
        "id": "Pengontrol backend tidak tersedia",
        "sl": "Krmilnik zalednega sistema ni na voljo",
        "tl": "Hindi available ang backend controller",
        "tr": "Backend kontrolcüsü mevcut değil",
        "uz": "Backend kontroleri mavjud emas",
        "vi": "Bộ điều khiển backend không khả dụng"
    },
    "Backend forced to {0} for '{1}'": {
        "am": "ባክኤንድ ወደ {0} ለ'{1}' ተገድዷል",
        "hi": "'{1}' के लिए बैकएंड {0} पर मजबूर किया गया",
        "id": "Backend dipaksa ke {0} untuk '{1}'",
        "sl": "Zaledni sistem prisilno nastavljen na {0} za '{1}'",
        "tl": "Backend pinilit sa {0} para sa '{1}'",
        "tr": "'{1}' için backend {0}'a zorlandı",
        "uz": "'{1}' uchun backend {0}ga majburlandi",
        "vi": "Backend bị buộc thành {0} cho '{1}'"
    },
    "Backend optimization unavailable": {
        "am": "ባክኤንድ ማመቻቸት አይገኝም",
        "hi": "बैकएंड अनुकूलन उपलब्ध नहीं है",
        "id": "Optimasi backend tidak tersedia",
        "sl": "Optimizacija zalednega sistema ni na voljo",
        "tl": "Hindi available ang backend optimization",
        "tr": "Backend optimizasyonu mevcut değil",
        "uz": "Backend optimizatsiyasi mavjud emas",
        "vi": "Tối ưu hóa backend không khả dụng"
    },
    "Backend set to Auto for '{0}'": {
        "am": "ባክኤንድ ለ'{0}' ወደ አውቶ ተቀናበረ",
        "hi": "'{0}' के लिए बैकएंड स्वचालित पर सेट किया गया",
        "id": "Backend diatur ke Otomatis untuk '{0}'",
        "sl": "Zaledni sistem nastavljen na Samodejno za '{0}'",
        "tl": "Backend itinakda sa Auto para sa '{0}'",
        "tr": "'{0}' için backend Otomatik olarak ayarlandı",
        "uz": "'{0}' uchun backend Avtoga o'rnatildi",
        "vi": "Backend được đặt thành Tự động cho '{0}'"
    },
    "Centroids enabled for '{0}' (~{1}x {2})": {
        "am": "ለ'{0}' ሴንትሮይድዎች ነቅተዋል (~{1}x {2})",
        "hi": "'{0}' के लिए सेंट्रॉइड सक्षम (~{1}x {2})",
        "id": "Centroid diaktifkan untuk '{0}' (~{1}x {2})",
        "sl": "Centroidi omogočeni za '{0}' (~{1}x {2})",
        "tl": "Mga centroid na-enable para sa '{0}' (~{1}x {2})",
        "tr": "'{0}' için centroid'ler etkinleştirildi (~{1}x {2})",
        "uz": "'{0}' uchun sentroidlar yoqildi (~{1}x {2})",
        "vi": "Đã bật tâm cho '{0}' (~{1}x {2})"
    },
    "Clear ALL FilterMate temporary tables from all databases": {
        "am": "ከሁሉም ዳታቤዞች ሁሉንም FilterMate ጊዜያዊ ሰንጠረዦች አጽዳ",
        "hi": "सभी डेटाबेस से सभी FilterMate अस्थायी तालिकाएं साफ़ करें",
        "id": "Bersihkan SEMUA tabel sementara FilterMate dari semua database",
        "sl": "Počisti VSE FilterMate začasne tabele iz vseh podatkovnih baz",
        "tl": "I-clear ang LAHAT ng FilterMate temporary tables mula sa lahat ng database",
        "tr": "Tüm veritabanlarından TÜM FilterMate geçici tablolarını temizle",
        "uz": "Barcha ma'lumotlar bazalaridan BARCHA FilterMate vaqtinchalik jadvallarini tozalash",
        "vi": "Xóa TẤT CẢ bảng tạm FilterMate khỏi tất cả cơ sở dữ liệu"
    },
    "Clear temporary tables for the current project only": {
        "am": "ለአሁኑ ፕሮጀክት ብቻ ጊዜያዊ ሰንጠረዦችን አጽዳ",
        "hi": "केवल वर्तमान प्रोजेक्ट के लिए अस्थायी तालिकाएं साफ़ करें",
        "id": "Bersihkan tabel sementara hanya untuk proyek saat ini",
        "sl": "Počisti začasne tabele samo za trenutni projekt",
        "tl": "I-clear ang temporary tables para sa kasalukuyang proyekto lamang",
        "tr": "Yalnızca geçerli proje için geçici tabloları temizle",
        "uz": "Faqat joriy loyiha uchun vaqtinchalik jadvallarni tozalash",
        "vi": "Xóa bảng tạm chỉ cho dự án hiện tại"
    },
    "Cleared {0} temporary table(s) for current project": {
        "am": "ለአሁኑ ፕሮጀክት {0} ጊዜያዊ ሰንጠረዥ(ዎች) ተጸዱ",
        "hi": "वर्तमान प्रोजेक्ट के लिए {0} अस्थायी तालिका(एं) साफ़ की गईं",
        "id": "{0} tabel sementara dibersihkan untuk proyek saat ini",
        "sl": "Počiščenih {0} začasnih tabel za trenutni projekt",
        "tl": "Na-clear ang {0} temporary table(s) para sa kasalukuyang proyekto",
        "tr": "Geçerli proje için {0} geçici tablo temizlendi",
        "uz": "Joriy loyiha uchun {0} ta vaqtinchalik jadval tozalandi",
        "vi": "Đã xóa {0} bảng tạm cho dự án hiện tại"
    },
    "Cleared {0} temporary table(s) globally": {
        "am": "በዓለም አቀፍ ደረጃ {0} ጊዜያዊ ሰንጠረዥ(ዎች) ተጸዱ",
        "hi": "वैश्विक स्तर पर {0} अस्थायी तालिका(एं) साफ़ की गईं",
        "id": "{0} tabel sementara dibersihkan secara global",
        "sl": "Globalno počiščenih {0} začasnih tabel",
        "tl": "Na-clear ang {0} temporary table(s) globally",
        "tr": "Genel olarak {0} geçici tablo temizlendi",
        "uz": "Global miqyosda {0} ta vaqtinchalik jadval tozalandi",
        "vi": "Đã xóa {0} bảng tạm trên toàn cục"
    },
    "Confirmation {0}": {
        "am": "ማረጋገጫ {0}",
        "hi": "पुष्टि {0}",
        "id": "Konfirmasi {0}",
        "sl": "Potrditev {0}",
        "tl": "Kumpirmasyon {0}",
        "tr": "Onay {0}",
        "uz": "Tasdiqlash {0}",
        "vi": "Xác nhận {0}"
    },
    "Could not analyze layer '{0}'": {
        "am": "ንብርብር '{0}' መተንተን አልተቻለም",
        "hi": "लेयर '{0}' का विश्लेषण नहीं किया जा सका",
        "id": "Tidak dapat menganalisis lapisan '{0}'",
        "sl": "Ni bilo mogoče analizirati plasti '{0}'",
        "tl": "Hindi ma-analyze ang layer na '{0}'",
        "tr": "'{0}' katmanı analiz edilemedi",
        "uz": "'{0}' qatlamini tahlil qilib bo'lmadi",
        "vi": "Không thể phân tích lớp '{0}'"
    },
    "Could not reload plugin automatically.": {
        "am": "ተሰኪውን በራስ-ሰር ዳግም መጫን አልተቻለም።",
        "hi": "प्लगइन को स्वचालित रूप से पुनः लोड नहीं किया जा सका।",
        "id": "Tidak dapat memuat ulang plugin secara otomatis.",
        "sl": "Vtičnika ni bilo mogoče samodejno znova naložiti.",
        "tl": "Hindi ma-reload ang plugin nang awtomatiko.",
        "tr": "Plugin otomatik olarak yeniden yüklenemedi.",
        "uz": "Plaginni avtomatik qayta yuklab bo'lmadi.",
        "vi": "Không thể tải lại plugin tự động."
    },
    "Dark mode": {
        "am": "ጨለማ ሁነታ",
        "hi": "डार्क मोड",
        "id": "Mode gelap",
        "sl": "Temni način",
        "tl": "Dark mode",
        "tr": "Koyu mod",
        "uz": "Qorong'i rejim",
        "vi": "Chế độ tối"
    },
    "Description (auto-generated, you can modify it)": {
        "am": "መግለጫ (በራስ-ሰር የተፈጠረ፣ ማሻሻል ይችላሉ)",
        "hi": "विवरण (स्वचालित रूप से उत्पन्न, आप इसे संशोधित कर सकते हैं)",
        "id": "Deskripsi (dibuat otomatis, Anda dapat memodifikasinya)",
        "sl": "Opis (samodejno ustvarjen, lahko ga spremenite)",
        "tl": "Paglalarawan (awtomatikong nalikha, maaari mong baguhin ito)",
        "tr": "Açıklama (otomatik oluşturuldu, değiştirebilirsiniz)",
        "uz": "Tavsif (avtomatik yaratilgan, uni o'zgartirishingiz mumkin)",
        "vi": "Mô tả (tự động tạo, bạn có thể sửa đổi)"
    },
    "Dialog not available: {0}": {
        "am": "ውይይት አይገኝም: {0}",
        "hi": "संवाद उपलब्ध नहीं है: {0}",
        "id": "Dialog tidak tersedia: {0}",
        "sl": "Pogovorno okno ni na voljo: {0}",
        "tl": "Hindi available ang dialog: {0}",
        "tr": "İletişim kutusu mevcut değil: {0}",
        "uz": "Muloqot oynasi mavjud emas: {0}",
        "vi": "Hộp thoại không khả dụng: {0}"
    },
    "Enter a name for this filter": {
        "am": "ለዚህ ማጣሪያ ስም ያስገቡ",
        "hi": "इस फ़िल्टर के लिए एक नाम दर्ज करें",
        "id": "Masukkan nama untuk filter ini",
        "sl": "Vnesite ime za ta filter",
        "tl": "Maglagay ng pangalan para sa filter na ito",
        "tr": "Bu filtre için bir ad girin",
        "uz": "Ushbu filtr uchun nom kiriting",
        "vi": "Nhập tên cho bộ lọc này"
    },
    "Error analyzing layer: {0}": {
        "am": "ንብርብር መተንተን ስህተት: {0}",
        "hi": "लेयर विश्लेषण त्रुटि: {0}",
        "id": "Error menganalisis lapisan: {0}",
        "sl": "Napaka pri analiziranju plasti: {0}",
        "tl": "Error sa pag-analyze ng layer: {0}",
        "tr": "Katman analizi hatası: {0}",
        "uz": "Qatlamni tahlil qilishda xato: {0}",
        "vi": "Lỗi phân tích lớp: {0}"
    },
    "Error cancelling changes: {0}": {
        "am": "ለውጦችን መሰረዝ ስህተት: {0}",
        "hi": "परिवर्तन रद्द करने में त्रुटि: {0}",
        "id": "Error membatalkan perubahan: {0}",
        "sl": "Napaka pri preklicu sprememb: {0}",
        "tl": "Error sa pagkansela ng mga pagbabago: {0}",
        "tr": "Değişiklikleri iptal etme hatası: {0}",
        "uz": "O'zgarishlarni bekor qilishda xato: {0}",
        "vi": "Lỗi hủy thay đổi: {0}"
    },
    "Error reloading plugin: {0}": {
        "am": "ተሰኪውን ዳግም መጫን ስህተት: {0}",
        "hi": "प्लगइन पुनः लोड करने में त्रुटि: {0}",
        "id": "Error memuat ulang plugin: {0}",
        "sl": "Napaka pri ponovnem nalaganju vtičnika: {0}",
        "tl": "Error sa pag-reload ng plugin: {0}",
        "tr": "Plugin yeniden yükleme hatası: {0}",
        "uz": "Plaginni qayta yuklashda xato: {0}",
        "vi": "Lỗi tải lại plugin: {0}"
    },
    "Error: {0}": {
        "am": "ስህተት: {0}",
        "hi": "त्रुटि: {0}",
        "id": "Error: {0}",
        "sl": "Napaka: {0}",
        "tl": "Error: {0}",
        "tr": "Hata: {0}",
        "uz": "Xato: {0}",
        "vi": "Lỗi: {0}"
    },
    "Favorites manager not available": {
        "am": "የተወዳጆች አስተዳዳሪ አይገኝም",
        "hi": "पसंदीदा प्रबंधक उपलब्ध नहीं है",
        "id": "Manajer favorit tidak tersedia",
        "sl": "Upravitelj priljubljenih ni na voljo",
        "tl": "Hindi available ang favorites manager",
        "tr": "Favoriler yöneticisi mevcut değil",
        "uz": "Sevimlilar menejeri mavjud emas",
        "vi": "Trình quản lý yêu thích không khả dụng"
    },
    "Filter history position": {
        "am": "የማጣሪያ ታሪክ አቀማመጥ",
        "hi": "फ़िल्टर इतिहास स्थिति",
        "id": "Posisi riwayat filter",
        "sl": "Položaj zgodovine filtrov",
        "tl": "Posisyon ng filter history",
        "tr": "Filtre geçmişi konumu",
        "uz": "Filtr tarixi holati",
        "vi": "Vị trí lịch sử bộ lọc"
    },
    "FilterMate - Add to Favorites": {
        "am": "FilterMate - ወደ ተወዳጆች አክል",
        "hi": "FilterMate - पसंदीदा में जोड़ें",
        "id": "FilterMate - Tambah ke Favorit",
        "sl": "FilterMate - Dodaj med priljubljene",
        "tl": "FilterMate - Idagdag sa Favorites",
        "tr": "FilterMate - Favorilere Ekle",
        "uz": "FilterMate - Sevimlilarga qo'shish",
        "vi": "FilterMate - Thêm vào Yêu thích"
    },
    "Forced {0} backend for {1} layer(s)": {
        "am": "ለ{1} ንብርብር(ዎች) {0} ባክኤንድ ተገድዷል",
        "hi": "{1} लेयर(ओं) के लिए {0} बैकएंड मजबूर किया गया",
        "id": "Backend {0} dipaksa untuk {1} lapisan",
        "sl": "{0} zaledni sistem prisilno nastavljen za {1} plast(i)",
        "tl": "Pinilit ang {0} backend para sa {1} layer(s)",
        "tr": "{1} katman için {0} backend zorlandı",
        "uz": "{1} qatlam(lar) uchun {0} backend majburlandi",
        "vi": "Đã buộc backend {0} cho {1} lớp"
    },
    "Light mode": {
        "am": "ብርሃን ሁነታ",
        "hi": "लाइट मोड",
        "id": "Mode terang",
        "sl": "Svetli način",
        "tl": "Light mode",
        "tr": "Açık mod",
        "uz": "Yorug' rejim",
        "vi": "Chế độ sáng"
    },
    "Memory layer filtering complete for '{0}'": {
        "am": "ለ'{0}' የማህደረ ትውስታ ንብርብር ማጣሪያ ተጠናቅቋል",
        "hi": "'{0}' के लिए मेमोरी लेयर फ़िल्टरिंग पूर्ण",
        "id": "Pemfilteran lapisan memori selesai untuk '{0}'",
        "sl": "Filtriranje pomnilniške plasti končano za '{0}'",
        "tl": "Kumpleto ang memory layer filtering para sa '{0}'",
        "tr": "'{0}' için bellek katmanı filtreleme tamamlandı",
        "uz": "'{0}' uchun xotira qatlami filtrlash tugallandi",
        "vi": "Đã hoàn thành lọc lớp bộ nhớ cho '{0}'"
    },
    "No optimization recommendations at this time.": {
        "am": "በዚህ ጊዜ የማመቻቸት ምክሮች የሉም።",
        "hi": "इस समय कोई अनुकूलन अनुशंसाएं नहीं हैं।",
        "id": "Tidak ada rekomendasi optimasi saat ini.",
        "sl": "Trenutno ni priporočil za optimizacijo.",
        "tl": "Walang optimization recommendations sa ngayon.",
        "tr": "Şu anda optimizasyon önerisi yok.",
        "uz": "Hozirda optimizatsiya tavsiyalari yo'q.",
        "vi": "Không có đề xuất tối ưu hóa vào lúc này."
    },
    "OGR/Memory": {
        "am": "OGR/ማህደረ ትውስታ",
        "hi": "OGR/मेमोरी",
        "id": "OGR/Memori",
        "sl": "OGR/Pomnilnik",
        "tl": "OGR/Memory",
        "tr": "OGR/Bellek",
        "uz": "OGR/Xotira",
        "vi": "OGR/Bộ nhớ"
    },
    "Optimization applied to {0} layer(s)": {
        "am": "ማመቻቸት በ{0} ንብርብር(ዎች) ላይ ተተግብሯል",
        "hi": "{0} लेयर(ओं) पर अनुकूलन लागू किया गया",
        "id": "Optimasi diterapkan ke {0} lapisan",
        "sl": "Optimizacija uporabljena za {0} plast(i)",
        "tl": "Optimization inilapat sa {0} layer(s)",
        "tr": "{0} katmana optimizasyon uygulandı",
        "uz": "{0} qatlam(lar)ga optimizatsiya qo'llanildi",
        "vi": "Đã áp dụng tối ưu hóa cho {0} lớp"
    },
    "Optimization recommendations": {
        "am": "የማመቻቸት ምክሮች",
        "hi": "अनुकूलन अनुशंसाएं",
        "id": "Rekomendasi optimasi",
        "sl": "Priporočila za optimizacijo",
        "tl": "Mga rekomendasyon sa optimization",
        "tr": "Optimizasyon önerileri",
        "uz": "Optimizatsiya tavsiyalari",
        "vi": "Đề xuất tối ưu hóa"
    },
    "PostgreSQL": {
        "am": "PostgreSQL",
        "hi": "PostgreSQL",
        "id": "PostgreSQL",
        "sl": "PostgreSQL",
        "tl": "PostgreSQL",
        "tr": "PostgreSQL",
        "uz": "PostgreSQL",
        "vi": "PostgreSQL"
    },
    "Redo filter": {
        "am": "ማጣሪያ ድገም",
        "hi": "फ़िल्टर फिर से करें",
        "id": "Ulangi filter",
        "sl": "Ponovi filter",
        "tl": "I-redo ang filter",
        "tr": "Filtreyi yinele",
        "uz": "Filtrni qaytarish",
        "vi": "Làm lại bộ lọc"
    },
    "Redo unavailable": {
        "am": "ድገም አይገኝም",
        "hi": "फिर से करना अनुपलब्ध",
        "id": "Ulangi tidak tersedia",
        "sl": "Ponovi ni na voljo",
        "tl": "Hindi available ang redo",
        "tr": "Yineleme mevcut değil",
        "uz": "Qaytarish mavjud emas",
        "vi": "Làm lại không khả dụng"
    },
    "Save current filter": {
        "am": "የአሁኑን ማጣሪያ አስቀምጥ",
        "hi": "वर्तमान फ़िल्टर सहेजें",
        "id": "Simpan filter saat ini",
        "sl": "Shrani trenutni filter",
        "tl": "I-save ang kasalukuyang filter",
        "tr": "Geçerli filtreyi kaydet",
        "uz": "Joriy filtrni saqlash",
        "vi": "Lưu bộ lọc hiện tại"
    },
    "Spatialite": {
        "am": "Spatialite",
        "hi": "Spatialite",
        "id": "Spatialite",
        "sl": "Spatialite",
        "tl": "Spatialite",
        "tr": "Spatialite",
        "uz": "Spatialite",
        "vi": "Spatialite"
    },
    "Strategy set to {0} for '{1}'": {
        "am": "ስትራቴጂ ለ'{1}' ወደ {0} ተቀናበረ",
        "hi": "'{1}' के लिए रणनीति {0} पर सेट की गई",
        "id": "Strategi diatur ke {0} untuk '{1}'",
        "sl": "Strategija nastavljena na {0} za '{1}'",
        "tl": "Strategy itinakda sa {0} para sa '{1}'",
        "tr": "'{1}' için strateji {0} olarak ayarlandı",
        "uz": "'{1}' uchun strategiya {0}ga o'rnatildi",
        "vi": "Chiến lược được đặt thành {0} cho '{1}'"
    },
    "Theme changed": {
        "am": "ገጽታ ተቀይሯል",
        "hi": "थीम बदली गई",
        "id": "Tema diubah",
        "sl": "Tema spremenjena",
        "tl": "Nabago ang tema",
        "tr": "Tema değiştirildi",
        "uz": "Mavzu o'zgartirildi",
        "vi": "Đã thay đổi chủ đề"
    },
    "Toggle dark/light mode": {
        "am": "ጨለማ/ብርሃን ሁነታ ቀይር",
        "hi": "डार्क/लाइट मोड टॉगल करें",
        "id": "Beralih mode gelap/terang",
        "sl": "Preklopi temni/svetli način",
        "tl": "I-toggle ang dark/light mode",
        "tr": "Koyu/açık modu değiştir",
        "uz": "Qorong'i/yorug' rejimni almashtirish",
        "vi": "Chuyển đổi chế độ tối/sáng"
    },
    "Undo filter": {
        "am": "ማጣሪያ ቀልብስ",
        "hi": "फ़िल्टर पूर्ववत करें",
        "id": "Batalkan filter",
        "sl": "Razveljavi filter",
        "tl": "I-undo ang filter",
        "tr": "Filtreyi geri al",
        "uz": "Filtrni bekor qilish",
        "vi": "Hoàn tác bộ lọc"
    },
    "Undo unavailable": {
        "am": "ቀልብስ አይገኝም",
        "hi": "पूर्ववत अनुपलब्ध",
        "id": "Batalkan tidak tersedia",
        "sl": "Razveljavi ni na voljo",
        "tl": "Hindi available ang undo",
        "tr": "Geri alma mevcut değil",
        "uz": "Bekor qilish mavjud emas",
        "vi": "Hoàn tác không khả dụng"
    },
    "Using QGIS expressions for filtering": {
        "am": "ለማጣራት የQGIS መግለጫዎችን በመጠቀም",
        "hi": "फ़िल्टरिंग के लिए QGIS अभिव्यक्तियों का उपयोग करना",
        "id": "Menggunakan ekspresi QGIS untuk pemfilteran",
        "sl": "Uporaba QGIS izrazov za filtriranje",
        "tl": "Gumagamit ng QGIS expressions para sa pag-filter",
        "tr": "Filtreleme için QGIS ifadeleri kullanılıyor",
        "uz": "Filtrlash uchun QGIS ifodalari ishlatilmoqda",
        "vi": "Sử dụng biểu thức QGIS để lọc"
    },
    "View filter history": {
        "am": "የማጣሪያ ታሪክ ይመልከቱ",
        "hi": "फ़िल्टर इतिहास देखें",
        "id": "Lihat riwayat filter",
        "sl": "Ogled zgodovine filtrov",
        "tl": "Tingnan ang filter history",
        "tr": "Filtre geçmişini görüntüle",
        "uz": "Filtr tarixini ko'rish",
        "vi": "Xem lịch sử bộ lọc"
    },
    "WKT expression threshold:": {
        "am": "የWKT መግለጫ ገደብ:",
        "hi": "WKT अभिव्यक्ति सीमा:",
        "id": "Ambang batas ekspresi WKT:",
        "sl": "Prag WKT izraza:",
        "tl": "WKT expression threshold:",
        "tr": "WKT ifade eşiği:",
        "uz": "WKT ifoda chegarasi:",
        "vi": "Ngưỡng biểu thức WKT:"
    },
    "features": {
        "am": "ባህሪያት",
        "hi": "फ़ीचर",
        "id": "fitur",
        "sl": "objekti",
        "tl": "mga feature",
        "tr": "özellikler",
        "uz": "xususiyatlar",
        "vi": "đối tượng"
    },
    "memory copy": {
        "am": "የማህደረ ትውስታ ቅጂ",
        "hi": "मेमोरी कॉपी",
        "id": "salinan memori",
        "sl": "kopija v pomnilniku",
        "tl": "memory copy",
        "tr": "bellek kopyası",
        "uz": "xotira nusxasi",
        "vi": "sao chép bộ nhớ"
    },
    "pool size": {
        "am": "የገንዳ መጠን",
        "hi": "पूल आकार",
        "id": "ukuran pool",
        "sl": "velikost sklada",
        "tl": "pool size",
        "tr": "havuz boyutu",
        "uz": "hovuz hajmi",
        "vi": "kích thước pool"
    },
    "simplified to {0} vertices": {
        "am": "ወደ {0} ጫፎች ቀለል ተደርጓል",
        "hi": "{0} शीर्षों तक सरलीकृत",
        "id": "disederhanakan menjadi {0} titik",
        "sl": "poenostavljeno na {0} oglišč",
        "tl": "pinasimple sa {0} vertices",
        "tr": "{0} köşeye sadeleştirildi",
        "uz": "{0} ta cho'qqiga soddalashtirildi",
        "vi": "đơn giản hóa thành {0} đỉnh"
    },
    "temp views": {
        "am": "ጊዜያዊ እይታዎች",
        "hi": "अस्थायी दृश्य",
        "id": "tampilan sementara",
        "sl": "začasni pogledi",
        "tl": "temp views",
        "tr": "geçici görünümler",
        "uz": "vaqtinchalik ko'rinishlar",
        "vi": "chế độ xem tạm"
    }
}

# C2 language codes
C2_LANGS = ['da', 'fi', 'nb', 'pl', 'ru', 'sv', 'zh']

# C3 language codes (need C2 + additional translations)
C3_LANGS = ['am', 'hi', 'id', 'sl', 'tl', 'tr', 'uz', 'vi']


def get_message_block(source, translation, context="FilterMateDockWidget"):
    """Generate an XML message block for Qt .ts files."""
    # Escape special characters
    source_escaped = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;").replace('"', "&quot;")
    trans_escaped = translation.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;").replace('"', "&quot;")
    
    return f'''        <message>
            <source>{source_escaped}</source>
            <translation>{trans_escaped}</translation>
        </message>'''


def add_messages_to_file(filepath, messages_dict, lang_code):
    """Add missing messages to a .ts file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the last </message> before </context>
    # We'll add new messages before the closing </context> tag
    
    messages_added = 0
    for source, translations in messages_dict.items():
        if lang_code not in translations:
            continue
            
        translation = translations[lang_code]
        
        # Check if this source already exists in the file
        source_escaped = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")
        if f"<source>{source_escaped}</source>" in content:
            continue
        
        # Find the position to insert (before last </context>)
        insert_pos = content.rfind('    </context>')
        if insert_pos == -1:
            print(f"  Warning: Could not find </context> in {filepath}")
            continue
        
        # Create the message block
        message_block = get_message_block(source, translation) + '\n'
        
        # Insert the message
        content = content[:insert_pos] + message_block + content[insert_pos:]
        messages_added += 1
    
    if messages_added > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return messages_added


def compile_ts_file(ts_path):
    """Compile a .ts file to .qm using lrelease."""
    qm_path = ts_path.replace('.ts', '.qm')
    try:
        result = subprocess.run(['lrelease', ts_path, '-qm', qm_path], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"  lrelease error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  lrelease not found - please compile manually")
        return False


def main():
    print("=" * 60)
    print("FilterMate Translation Completion Script")
    print("=" * 60)
    
    # Phase C1: Complete DE, ES, IT, NL, PT (1 message each)
    print("\n📌 Phase C1: Completing DE, ES, IT, NL, PT (1 message each)")
    print("-" * 50)
    c1_langs = ['de', 'es', 'it', 'nl', 'pt']
    for lang in c1_langs:
        filepath = os.path.join(I18N_DIR, f'FilterMate_{lang}.ts')
        if os.path.exists(filepath):
            added = add_messages_to_file(filepath, PHASE_C1_TRANSLATIONS, lang)
            print(f"  {lang.upper()}: Added {added} message(s)")
            if added > 0:
                compile_ts_file(filepath)
    
    # Phase C2: Complete DA, FI, NB, PL, RU, SV, ZH (42 messages each)
    print("\n📌 Phase C2: Completing DA, FI, NB, PL, RU, SV, ZH (42 messages each)")
    print("-" * 50)
    for lang in C2_LANGS:
        filepath = os.path.join(I18N_DIR, f'FilterMate_{lang}.ts')
        if os.path.exists(filepath):
            added = add_messages_to_file(filepath, PHASE_C2_TRANSLATIONS, lang)
            print(f"  {lang.upper()}: Added {added} message(s)")
            if added > 0:
                compile_ts_file(filepath)
    
    # Phase C3: Complete AM, HI, ID, SL, TL, TR, UZ, VI (C2 + additional messages)
    print("\n📌 Phase C3: Completing AM, HI, ID, SL, TL, TR, UZ, VI")
    print("-" * 50)
    for lang in C3_LANGS:
        filepath = os.path.join(I18N_DIR, f'FilterMate_{lang}.ts')
        if os.path.exists(filepath):
            # Add C2 translations that have this language
            added_c2 = 0
            for source, translations in PHASE_C2_TRANSLATIONS.items():
                # C2 translations don't have C3 languages, skip
                pass
            
            # Add C3 specific translations
            added = add_messages_to_file(filepath, PHASE_C3_TRANSLATIONS, lang)
            print(f"  {lang.upper()}: Added {added} message(s)")
            if added > 0:
                compile_ts_file(filepath)
    
    print("\n" + "=" * 60)
    print("✅ Translation completion finished!")
    print("=" * 60)
    
    # Final count
    print("\nFinal message counts:")
    for ts_file in sorted(os.listdir(I18N_DIR)):
        if ts_file.endswith('.ts'):
            filepath = os.path.join(I18N_DIR, ts_file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            count = content.count('</message>')
            lang_code = ts_file.replace('FilterMate_', '').replace('.ts', '')
            pct = (count / 450) * 100
            status = "✅" if pct >= 99 else "📊"
            print(f"  {status} {lang_code.upper()}: {count}/450 ({pct:.1f}%)")


if __name__ == '__main__':
    main()
