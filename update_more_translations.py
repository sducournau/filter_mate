#!/usr/bin/env python3
"""Update additional language translations for FilterMate"""

import xml.etree.ElementTree as ET
import subprocess
import os

# Additional translations for more languages
ADDITIONAL_TRANSLATIONS = {
    'sv': {  # Swedish
        "All layers using auto-selection": "Alla lager använder automatiskt urval",
        "Applied to '{0}':\n{1}": "Tillämpat på '{0}':\n{1}",
        "Auto-centroid {0}": "Auto-centroid {0}",
        "Auto-optimization {0}": "Auto-optimering {0}",
        "Auto-optimizer module not available": "Auto-optimeringsmodul inte tillgänglig",
        "Auto-optimizer not available: {0}": "Auto-optimerare inte tillgänglig: {0}",
        "Auto-selected backends for {0} layer(s)": "Automatiskt valda backends för {0} lager",
        "Backend controller not available": "Backend-kontroller inte tillgänglig",
        "Backend forced to {0} for '{1}'": "Backend tvingad till {0} för '{1}'",
        "Backend optimization unavailable": "Backend-optimering inte tillgänglig",
        "Backend set to Auto for '{0}'": "Backend inställd på Auto för '{0}'",
        "Clear ALL FilterMate temporary tables from all databases": "Rensa ALLA FilterMate temporära tabeller från alla databaser",
        "Clear temporary tables for the current project only": "Rensa temporära tabeller endast för aktuellt projekt",
        "Cleared {0} temporary table(s) for current project": "Rensade {0} temporära tabell(er) för aktuellt projekt",
        "Cleared {0} temporary table(s) globally": "Rensade {0} temporära tabell(er) globalt",
        "Confirmation {0}": "Bekräftelse {0}",
        "Could not analyze layer '{0}'": "Kunde inte analysera lager '{0}'",
        "Could not reload plugin automatically.": "Kunde inte ladda om plugin automatiskt.",
        "Dark mode": "Mörkt läge",
        "Description (auto-generated, you can modify it)": "Beskrivning (automatiskt genererad, du kan ändra den)",
        "Dialog not available: {0}": "Dialog inte tillgänglig: {0}",
        "Enter a name for this filter": "Ange ett namn för detta filter",
        "Error analyzing layer: {0}": "Fel vid analys av lager: {0}",
        "Error cancelling changes: {0}": "Fel vid avbrytande av ändringar: {0}",
        "Error reloading plugin: {0}": "Fel vid omladdning av plugin: {0}",
        "Error: {0}": "Fel: {0}",
        "Favorites manager not available": "Favorithanterare inte tillgänglig",
        "Filter history position": "Position i filterhistorik",
        "FilterMate - Add to Favorites": "FilterMate - Lägg till i favoriter",
        "Forced {0} backend for {1} layer(s)": "Tvingad {0} backend för {1} lager",
        "Initialization error: {}": "Initieringsfel: {}",
        "Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}": "Lager '{0}' är redan optimalt konfigurerat.\nTyp: {1}\nObjekt: {2:,}",
        "Light mode": "Ljust läge",
        "No PostgreSQL connection available": "Ingen PostgreSQL-anslutning tillgänglig",
        "No alternative backends available for this layer": "Inga alternativa backends tillgängliga för detta lager",
        "No layer selected. Please select a layer first.": "Inget lager valt. Vänligen välj ett lager först.",
        "No optimizations selected to apply.": "Inga optimeringar valda att tillämpa.",
        "No temporary tables found": "Inga temporära tabeller hittades",
        "No temporary tables found for current project": "Inga temporära tabeller hittades för aktuellt projekt",
        "No views to clean or cleanup failed": "Inga vyer att rensa eller rensning misslyckades",
        "Optimized {0} layer(s)": "Optimerade {0} lager",
        "Other Sessions Active": "Andra sessioner aktiva",
        "Plugin activated with {0} vector layer(s)": "Plugin aktiverat med {0} vektorlager",
        "PostgreSQL auto-cleanup disabled": "PostgreSQL auto-rensning inaktiverad",
        "PostgreSQL auto-cleanup enabled": "PostgreSQL auto-rensning aktiverad",
        "PostgreSQL session views cleaned up": "PostgreSQL sessionsvyer rensade",
        "Redo filter (Ctrl+Y)": "Gör om filter (Ctrl+Y)",
        "Schema '{0}' dropped successfully": "Schema '{0}' togs bort framgångsrikt",
        "Schema cleanup cancelled": "Schemarensning avbruten",
        "Schema cleanup failed": "Schemarensning misslyckades",
        "Schema has {0} view(s) from other sessions.\nDrop anyway?": "Schema har {0} vy(er) från andra sessioner.\nTa bort ändå?",
        "The selected layer is invalid or its source cannot be found.": "Det valda lagret är ogiltigt eller dess källa kan inte hittas.",
        "Theme adapted: {0}": "Tema anpassat: {0}",
        "UI configuration incomplete - check logs": "UI-konfiguration ofullständig - kontrollera loggar",
        "UI dimension error: {}": "UI-dimensionsfel: {}",
        "Undo last filter (Ctrl+Z)": "Ångra senaste filter (Ctrl+Z)",
        "disabled": "inaktiverad",
        "enabled": "aktiverad",
        "★ No favorites saved\nClick to add current filter": "★ Inga favoriter sparade\nKlicka för att lägga till aktuellt filter",
        "★ {0} Favorites saved\nClick to apply or manage": "★ {0} favoriter sparade\nKlicka för att tillämpa eller hantera",
        "⚙️ Manage favorites...": "⚙️ Hantera favoriter...",
        "⭐ Add Current Filter (no filter active)": "⭐ Lägg till aktuellt filter (inget filter aktivt)",
        "⭐ Add Current Filter to Favorites": "⭐ Lägg till aktuellt filter i favoriter",
        "⭐ Add current filter to favorites": "⭐ Lägg till aktuellt filter i favoriter",
        "⭐ Add filter (no active filter)": "⭐ Lägg till filter (inget aktivt filter)",
        "🌐 All Projects (Global)": "🌐 Alla projekt (Globalt)",
        "📁 Current Project": "📁 Aktuellt projekt",
        "📤 Export...": "📤 Exportera...",
        "📥 Import...": "📥 Importera...",
    },
    'da': {  # Danish
        "All layers using auto-selection": "Alle lag bruger automatisk valg",
        "Applied to '{0}':\n{1}": "Anvendt på '{0}':\n{1}",
        "Auto-centroid {0}": "Auto-centroid {0}",
        "Auto-optimization {0}": "Auto-optimering {0}",
        "Auto-optimizer module not available": "Auto-optimeringsmodul ikke tilgængelig",
        "Auto-optimizer not available: {0}": "Auto-optimering ikke tilgængelig: {0}",
        "Auto-selected backends for {0} layer(s)": "Automatisk valgte backends for {0} lag",
        "Backend controller not available": "Backend-controller ikke tilgængelig",
        "Backend forced to {0} for '{1}'": "Backend tvunget til {0} for '{1}'",
        "Backend optimization unavailable": "Backend-optimering ikke tilgængelig",
        "Backend set to Auto for '{0}'": "Backend sat til Auto for '{0}'",
        "Clear ALL FilterMate temporary tables from all databases": "Ryd ALLE FilterMate midlertidige tabeller fra alle databaser",
        "Clear temporary tables for the current project only": "Ryd midlertidige tabeller kun for det aktuelle projekt",
        "Cleared {0} temporary table(s) for current project": "Ryddede {0} midlertidig(e) tabel(ler) for aktuelt projekt",
        "Cleared {0} temporary table(s) globally": "Ryddede {0} midlertidig(e) tabel(ler) globalt",
        "Confirmation {0}": "Bekræftelse {0}",
        "Could not analyze layer '{0}'": "Kunne ikke analysere lag '{0}'",
        "Could not reload plugin automatically.": "Kunne ikke genindlæse plugin automatisk.",
        "Dark mode": "Mørk tilstand",
        "Description (auto-generated, you can modify it)": "Beskrivelse (auto-genereret, du kan ændre den)",
        "Dialog not available: {0}": "Dialog ikke tilgængelig: {0}",
        "Enter a name for this filter": "Indtast et navn til dette filter",
        "Error analyzing layer: {0}": "Fejl ved analyse af lag: {0}",
        "Error cancelling changes: {0}": "Fejl ved annullering af ændringer: {0}",
        "Error reloading plugin: {0}": "Fejl ved genindlæsning af plugin: {0}",
        "Error: {0}": "Fejl: {0}",
        "Favorites manager not available": "Favoritmanager ikke tilgængelig",
        "Filter history position": "Position i filterhistorik",
        "FilterMate - Add to Favorites": "FilterMate - Tilføj til favoritter",
        "Forced {0} backend for {1} layer(s)": "Tvunget {0} backend for {1} lag",
        "Initialization error: {}": "Initialiseringsfejl: {}",
        "Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}": "Lag '{0}' er allerede optimalt konfigureret.\nType: {1}\nFunktioner: {2:,}",
        "Light mode": "Lys tilstand",
        "No PostgreSQL connection available": "Ingen PostgreSQL-forbindelse tilgængelig",
        "No alternative backends available for this layer": "Ingen alternative backends tilgængelige for dette lag",
        "No layer selected. Please select a layer first.": "Intet lag valgt. Vælg venligst et lag først.",
        "No optimizations selected to apply.": "Ingen optimeringer valgt at anvende.",
        "No temporary tables found": "Ingen midlertidige tabeller fundet",
        "No temporary tables found for current project": "Ingen midlertidige tabeller fundet for aktuelt projekt",
        "No views to clean or cleanup failed": "Ingen visninger at rydde eller oprydning mislykkedes",
        "Optimized {0} layer(s)": "Optimerede {0} lag",
        "Other Sessions Active": "Andre sessioner aktive",
        "Plugin activated with {0} vector layer(s)": "Plugin aktiveret med {0} vektorlag",
        "PostgreSQL auto-cleanup disabled": "PostgreSQL auto-oprydning deaktiveret",
        "PostgreSQL auto-cleanup enabled": "PostgreSQL auto-oprydning aktiveret",
        "PostgreSQL session views cleaned up": "PostgreSQL-sessionsvisninger ryddet op",
        "Redo filter (Ctrl+Y)": "Gentag filter (Ctrl+Y)",
        "Schema '{0}' dropped successfully": "Schema '{0}' fjernet med succes",
        "Schema cleanup cancelled": "Skema-oprydning annulleret",
        "Schema cleanup failed": "Skema-oprydning mislykkedes",
        "Schema has {0} view(s) from other sessions.\nDrop anyway?": "Schema har {0} visning(er) fra andre sessioner.\nFjern alligevel?",
        "The selected layer is invalid or its source cannot be found.": "Det valgte lag er ugyldigt, eller dets kilde kan ikke findes.",
        "Theme adapted: {0}": "Tema tilpasset: {0}",
        "UI configuration incomplete - check logs": "UI-konfiguration ufuldstændig - tjek logfiler",
        "UI dimension error: {}": "UI-dimensionsfejl: {}",
        "Undo last filter (Ctrl+Z)": "Fortryd sidste filter (Ctrl+Z)",
        "disabled": "deaktiveret",
        "enabled": "aktiveret",
        "★ No favorites saved\nClick to add current filter": "★ Ingen favoritter gemt\nKlik for at tilføje aktuelt filter",
        "★ {0} Favorites saved\nClick to apply or manage": "★ {0} favoritter gemt\nKlik for at anvende eller administrere",
        "⚙️ Manage favorites...": "⚙️ Administrer favoritter...",
        "⭐ Add Current Filter (no filter active)": "⭐ Tilføj aktuelt filter (intet filter aktivt)",
        "⭐ Add Current Filter to Favorites": "⭐ Tilføj aktuelt filter til favoritter",
        "⭐ Add current filter to favorites": "⭐ Tilføj aktuelt filter til favoritter",
        "⭐ Add filter (no active filter)": "⭐ Tilføj filter (intet aktivt filter)",
        "🌐 All Projects (Global)": "🌐 Alle projekter (Globalt)",
        "📁 Current Project": "📁 Aktuelt projekt",
        "📤 Export...": "📤 Eksporter...",
        "📥 Import...": "📥 Importer...",
    },
    'zh': {  # Chinese (Simplified)
        "All layers using auto-selection": "所有图层使用自动选择",
        "Applied to '{0}':\n{1}": "应用于 '{0}':\n{1}",
        "Auto-centroid {0}": "自动质心 {0}",
        "Auto-optimization {0}": "自动优化 {0}",
        "Auto-optimizer module not available": "自动优化模块不可用",
        "Auto-optimizer not available: {0}": "自动优化器不可用: {0}",
        "Auto-selected backends for {0} layer(s)": "为 {0} 个图层自动选择后端",
        "Backend controller not available": "后端控制器不可用",
        "Backend forced to {0} for '{1}'": "'{1}' 的后端强制设为 {0}",
        "Backend optimization unavailable": "后端优化不可用",
        "Backend set to Auto for '{0}'": "'{0}' 的后端设为自动",
        "Clear ALL FilterMate temporary tables from all databases": "从所有数据库中清除所有 FilterMate 临时表",
        "Clear temporary tables for the current project only": "仅清除当前项目的临时表",
        "Cleared {0} temporary table(s) for current project": "已清除当前项目的 {0} 个临时表",
        "Cleared {0} temporary table(s) globally": "已全局清除 {0} 个临时表",
        "Confirmation {0}": "确认 {0}",
        "Could not analyze layer '{0}'": "无法分析图层 '{0}'",
        "Could not reload plugin automatically.": "无法自动重新加载插件。",
        "Dark mode": "深色模式",
        "Description (auto-generated, you can modify it)": "描述（自动生成，您可以修改）",
        "Dialog not available: {0}": "对话框不可用: {0}",
        "Enter a name for this filter": "输入此过滤器的名称",
        "Error analyzing layer: {0}": "分析图层时出错: {0}",
        "Error cancelling changes: {0}": "取消更改时出错: {0}",
        "Error reloading plugin: {0}": "重新加载插件时出错: {0}",
        "Error: {0}": "错误: {0}",
        "Favorites manager not available": "收藏夹管理器不可用",
        "Filter history position": "过滤器历史记录位置",
        "FilterMate - Add to Favorites": "FilterMate - 添加到收藏夹",
        "Forced {0} backend for {1} layer(s)": "为 {1} 个图层强制使用 {0} 后端",
        "Initialization error: {}": "初始化错误: {}",
        "Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}": "图层 '{0}' 已经是最优配置。\n类型: {1}\n要素: {2:,}",
        "Light mode": "浅色模式",
        "No PostgreSQL connection available": "没有可用的 PostgreSQL 连接",
        "No alternative backends available for this layer": "此图层没有可用的替代后端",
        "No layer selected. Please select a layer first.": "未选择图层。请先选择一个图层。",
        "No optimizations selected to apply.": "未选择要应用的优化。",
        "No temporary tables found": "未找到临时表",
        "No temporary tables found for current project": "未找到当前项目的临时表",
        "No views to clean or cleanup failed": "没有要清理的视图或清理失败",
        "Optimized {0} layer(s)": "已优化 {0} 个图层",
        "Other Sessions Active": "其他会话处于活动状态",
        "Plugin activated with {0} vector layer(s)": "插件已激活，包含 {0} 个矢量图层",
        "PostgreSQL auto-cleanup disabled": "PostgreSQL 自动清理已禁用",
        "PostgreSQL auto-cleanup enabled": "PostgreSQL 自动清理已启用",
        "PostgreSQL session views cleaned up": "PostgreSQL 会话视图已清理",
        "Redo filter (Ctrl+Y)": "重做过滤器 (Ctrl+Y)",
        "Schema '{0}' dropped successfully": "模式 '{0}' 已成功删除",
        "Schema cleanup cancelled": "模式清理已取消",
        "Schema cleanup failed": "模式清理失败",
        "Schema has {0} view(s) from other sessions.\nDrop anyway?": "模式有 {0} 个来自其他会话的视图。\n仍要删除吗？",
        "The selected layer is invalid or its source cannot be found.": "所选图层无效或找不到其源。",
        "Theme adapted: {0}": "主题已适配: {0}",
        "UI configuration incomplete - check logs": "UI 配置不完整 - 请检查日志",
        "UI dimension error: {}": "UI 尺寸错误: {}",
        "Undo last filter (Ctrl+Z)": "撤消上次过滤器 (Ctrl+Z)",
        "disabled": "已禁用",
        "enabled": "已启用",
        "★ No favorites saved\nClick to add current filter": "★ 未保存收藏夹\n点击添加当前过滤器",
        "★ {0} Favorites saved\nClick to apply or manage": "★ 已保存 {0} 个收藏夹\n点击应用或管理",
        "⚙️ Manage favorites...": "⚙️ 管理收藏夹...",
        "⭐ Add Current Filter (no filter active)": "⭐ 添加当前过滤器（无活动过滤器）",
        "⭐ Add Current Filter to Favorites": "⭐ 将当前过滤器添加到收藏夹",
        "⭐ Add current filter to favorites": "⭐ 将当前过滤器添加到收藏夹",
        "⭐ Add filter (no active filter)": "⭐ 添加过滤器（无活动过滤器）",
        "🌐 All Projects (Global)": "🌐 所有项目（全局）",
        "📁 Current Project": "📁 当前项目",
        "📤 Export...": "📤 导出...",
        "📥 Import...": "📥 导入...",
    },
}

def update_translations_for_language(lang_code, translations):
    """Update translations for a specific language"""
    
    ts_file = f'i18n/FilterMate_{lang_code}.ts'
    
    try:
        # Parse files
        en_tree = ET.parse('i18n/FilterMate_en.ts')
        lang_tree = ET.parse(ts_file)
        
        en_root = en_tree.getroot()
        lang_root = lang_tree.getroot()
        
        # Get existing sources
        lang_sources = {msg.find('source').text for msg in lang_root.findall('.//message')}
        
        # Get the context element
        lang_context = lang_root.find('context')
        
        # Find and add missing messages
        added = 0
        for en_msg in en_root.findall('.//message'):
            source_text = en_msg.find('source').text
            
            if source_text not in lang_sources and source_text in translations:
                # Create new message element
                new_msg = ET.Element('message')
                
                # Add source
                source = ET.SubElement(new_msg, 'source')
                source.text = source_text
                
                # Add translation
                translation = ET.SubElement(new_msg, 'translation')
                translation.text = translations[source_text]
                
                # Add to context
                lang_context.append(new_msg)
                added += 1
        
        if added > 0:
            # Write back to file with proper formatting
            ET.indent(lang_tree, space='    ')
            lang_tree.write(ts_file, encoding='utf-8', xml_declaration=True)
            
            # Compile the .qm file
            qm_file = ts_file.replace('.ts', '.qm')
            result = subprocess.run(
                ['/home/simon/anaconda3/bin/lrelease', ts_file, '-qm', qm_file],
                capture_output=True,
                text=True
            )
            
            print(f"✅ {lang_code.upper()}: Added {added} translations")
            if result.stdout:
                print(f"   {result.stdout.strip()}")
        else:
            print(f"✅ {lang_code.upper()}: Already complete!")
            
    except Exception as e:
        print(f"❌ {lang_code.upper()}: Error - {e}")

def main():
    """Update all additional translation files"""
    
    print("=== FilterMate Additional Translation Updater ===\n")
    
    # Change to plugin directory
    os.chdir('/mnt/c/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate')
    
    # Update all languages
    for lang_code, translations in ADDITIONAL_TRANSLATIONS.items():
        update_translations_for_language(lang_code, translations)
    
    print("\n=== Additional translation update complete! ===")

if __name__ == '__main__':
    main()
