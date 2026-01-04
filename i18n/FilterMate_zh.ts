<?xml version='1.0' encoding='utf-8'?>
<TS version="2.1" language="zh_CN" sourcelanguage="en_US">
<context>
    <name>FilterMate</name>
    <message>
        <source>&amp;FilterMate</source>
        <translation>&amp;FilterMate</translation>
    </message>
    <message>
        <source>FilterMate</source>
        <translation>FilterMate</translation>
    </message>
    <message>
        <source>Open FilterMate panel</source>
        <translation>打开 FilterMate 面板</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>重置配置和数据库</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>恢复默认配置并删除 SQLite 数据库</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>重置配置</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>您确定要恢复默认配置吗？

这将：
- 重置所有 FilterMate 设置
- 删除所有过滤历史数据库</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>配置重置成功。</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>未找到默认配置文件。</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>数据库已删除：{filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>无法删除 {filename}：{error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>需要重新启动</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>配置已重置。

请重新启动 QGIS 以应用所有更改。</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>重置时出错：{error}</translation>
    </message>
    <message>
        <source>Obsolete configuration detected</source>
        <translation>检测到过时配置</translation>
    </message>
    <message>
        <source>unknown version</source>
        <translation>未知版本</translation>
    </message>
    <message>
        <source>Corrupted configuration detected</source>
        <translation>检测到损坏的配置</translation>
    </message>
    <message>
        <source>Configuration not reset. Some features may not work correctly.</source>
        <translation>配置未重置。某些功能可能无法正常工作。</translation>
    </message>
    <message>
        <source>Configuration created with default values</source>
        <translation>已使用默认值创建配置</translation>
    </message>
    <message>
        <source>Corrupted configuration reset. Default settings have been restored.</source>
        <translation>损坏的配置已重置。默认设置已恢复。</translation>
    </message>
    <message>
        <source>Obsolete configuration reset. Default settings have been restored.</source>
        <translation>过时的配置已重置。默认设置已恢复。</translation>
    </message>
    <message>
        <source>Configuration updated to latest version</source>
        <translation>配置已更新至最新版本</translation>
    </message>
    <message>
        <source>Configuration updated: new settings available ({sections}). Access via Options menu.</source>
        <translation>配置已更新：新设置可用 ({sections})。通过选项菜单访问。</translation>
    </message>
    <message>
        <source>Geometry Simplification</source>
        <translation>几何简化</translation>
    </message>
    <message>
        <source>Optimization Thresholds</source>
        <translation>优化阈值</translation>
    </message>
    <message>
        <source>Geometry validation setting</source>
        <translation>几何验证设置</translation>
    </message>
    <message>
        <source>Invalid geometry filtering disabled successfully.</source>
        <translation>无效几何过滤已成功禁用。</translation>
    </message>
    <message>
        <source>Invalid geometry filtering not modified. Some features may be excluded from exports.</source>
        <translation>无效几何过滤未修改。某些要素可能会从导出中排除。</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive=expand, negative=shrink polygons)</source>
        <translation>缓冲区值（米）（正值=扩展，负值=收缩多边形）</translation>
    </message>
    <message>
        <source>Negative buffer (erosion): shrinks polygons inward</source>
        <translation>负缓冲区（侵蚀）：向内收缩多边形</translation>
    </message>
    <message>
        <source>point</source>
        <translation>点</translation>
    </message>
    <message>
        <source>line</source>
        <translation>线</translation>
    </message>
    <message>
        <source>non-polygon</source>
        <translation>非多边形</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive only when centroids are enabled. Negative buffers cannot be applied to points)</source>
        <translation>缓冲区值（米）（启用质心时仅允许正值。负缓冲区不能应用于点）</translation>
    </message>
    <message>
        <source>Mode batch</source>
        <translation>批处理模式</translation>
    </message>
    <message>
        <source>Number of segments for buffer precision</source>
        <translation>缓冲区精度的段数</translation>
    </message>
    <message>
        <source>Centroids</source>
        <translation>质心</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for distant layers (faster for complex polygons like buildings)</source>
        <translation>使用质心而不是完整几何图形用于远程图层（对于建筑物等复杂多边形更快）</translation>
    </message>
    <message>
        <source>An obsolete configuration ({}) has been detected.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created)
• No: Keep current configuration (may cause issues)</source>
        <translation>检测到过时的配置 ({})。

是否要重置为默认设置？

• 是：重置（将创建备份）
• 否：保留当前配置（可能导致问题）</translation>
    </message>
    <message>
        <source>The configuration file is corrupted and cannot be read.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created if possible)
• No: Cancel (the plugin may not work correctly)</source>
        <translation>配置文件已损坏，无法读取。

是否要重置为默认设置？

• 是：重置（如果可能，将创建备份）
• 否：取消（插件可能无法正常工作）</translation>
    </message>
    <message>
        <source>Configuration reset</source>
        <translation>重置配置</translation>
    </message>
    <message>
        <source>The configuration needs to be reset.

Do you want to continue?</source>
        <translation>配置需要重置。

是否要继续？</translation>
    </message>
    <message>
        <source>Error during configuration migration: {}</source>
        <translation>配置迁移时出错：{}</translation>
    </message>
    <message>
        <source>The QGIS setting 'Invalid features filtering' is currently set to '{mode}'.

FilterMate recommends disabling this setting (value 'Off') for the following reasons:

• Features with invalid geometries could be silently excluded from exports and filters
• FilterMate handles geometry validation internally with automatic repair options
• Some legitimate data may have geometries considered as 'invalid' according to strict OGC rules

Do you want to disable this setting now?

• Yes: Disable filtering (recommended for FilterMate)
• No: Keep current setting</source>
        <translation>The QGIS setting 'Invalid features filtering' is currently set to '{mode}'.

FilterMate recommends disabling this setting (value 'Off') for the following reasons:

• Features with invalid geometries could be silently excluded from exports and filters
• FilterMate handles geometry validation internally with automatic repair options
• Some legitimate data may have geometries considered as 'invalid' according to strict OGC rules

Do you want to disable this setting now?

• Yes: Disable filtering (recommended for FilterMate)
• No: Keep current setting</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Restore default settings
- Delete the layer database

QGIS must be restarted to apply the changes.</source>
        <translation>您确定要重置为默认配置吗？

这将：
- 恢复默认设置
- 删除图层数据库

必须重启 QGIS 才能应用更改。</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply the changes.</source>
        <translation>配置已重置。

请重启 QGIS 以应用更改。</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidgetBase</name>
    <message>
        <source>FilterMate</source>
        <translation>FilterMate</translation>
    </message>
    <message>
        <source>SINGLE SELECTION</source>
        <translation>单选</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>多选</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>自定义选择</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>过滤</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>导出</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>配置</translation>
    </message>
    <message>
        <source>Identify feature - Display feature attributes</source>
        <translation>识别要素 - 显示要素属性</translation>
    </message>
    <message>
        <source>Zoom to feature - Center the map on the selected feature</source>
        <translation>缩放到要素 - 将地图居中到选定的要素</translation>
    </message>
    <message>
        <source>Enable selection - Select features on map</source>
        <translation>启用选择 - 在地图上选择要素</translation>
    </message>
    <message>
        <source>Enable tracking - Follow the selected feature on the map</source>
        <translation>启用追踪 - 在地图上跟踪选定的要素</translation>
    </message>
    <message>
        <source>Link widgets - Synchronize selection between widgets</source>
        <translation>链接部件 - 同步部件之间的选择</translation>
    </message>
    <message>
        <source>Reset layer properties - Restore default layer settings</source>
        <translation>重置图层属性 - 恢复默认图层设置</translation>
    </message>
    <message>
        <source>Auto-sync with current layer - Automatically update when layer changes</source>
        <translation>与当前图层自动同步 - 图层更改时自动更新</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>启用多图层过滤 - 同时将过滤应用于多个图层</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>启用叠加过滤 - 在当前图层上组合多个过滤</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>启用空间过滤 - 使用几何关系过滤要素</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>启用缓冲区 - 在选定要素周围添加缓冲区</translation>
    </message>
    <message>
        <source>Buffer type - Select the buffer calculation method</source>
        <translation>缓冲区类型 - 选择缓冲区计算方法</translation>
    </message>
    <message>
        <source>Current layer - Select the layer to filter</source>
        <translation>当前图层 - 选择要过滤的图层</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>用于在源图层上组合过滤的逻辑运算符</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on other layers</source>
        <translation>用于在其他图层上组合过滤的逻辑运算符</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>选择用于空间过滤的几何谓词</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>缓冲距离（米）</translation>
    </message>
    <message>
        <source>Buffer type - Define how the buffer is calculated</source>
        <translation>缓冲区类型 - 定义缓冲区的计算方式</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>选择要导出的图层</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>配置输出投影</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>导出图层样式 (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>选择输出格式</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>配置输出位置和文件名</translation>
    </message>
    <message>
        <source>Enable ZIP compression - Create a compressed archive of exported files</source>
        <translation>启用 ZIP 压缩 - 创建导出文件的压缩存档</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>选择导出的坐标参考系</translation>
    </message>
    <message>
        <source>Style format - Select QML or SLD format</source>
        <translation>样式格式 - 选择 QML 或 SLD 格式</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>输出文件格式</translation>
    </message>
    <message>
        <source>Output folder name - Enter the name of the export folder</source>
        <translation>输出文件夹名称 - 输入导出文件夹的名称</translation>
    </message>
    <message>
        <source>Enter folder name...</source>
        <translation>输入文件夹名称...</translation>
    </message>
    <message>
        <source>Batch mode - Export each layer to a separate folder</source>
        <translation>批处理模式 - 将每个图层导出到单独的文件夹</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>批处理模式</translation>
    </message>
    <message>
        <source>ZIP filename - Enter the name for the compressed archive</source>
        <translation>ZIP 文件名 - 输入压缩存档的名称</translation>
    </message>
    <message>
        <source>Enter ZIP filename...</source>
        <translation>输入 ZIP 文件名...</translation>
    </message>
    <message>
        <source>Batch mode - Create a separate ZIP for each layer</source>
        <translation>批处理模式 - 为每个图层创建单独的 ZIP</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>应用过滤 - 在选定图层上执行当前过滤</translation>
    </message>
    <message>
        <source>Apply Filter</source>
        <translation>应用过滤</translation>
    </message>
    <message>
        <source>Apply the current filter expression to filter features on the selected layer(s)</source>
        <translation>应用当前过滤表达式来过滤选定图层上的要素</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>撤销过滤 - 恢复之前的过滤状态</translation>
    </message>
    <message>
        <source>Undo Filter</source>
        <translation>撤销过滤</translation>
    </message>
    <message>
        <source>Undo the last filter operation and restore the previous state</source>
        <translation>撤销上一次过滤操作并恢复之前的状态</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>重做过滤 - 重新应用之前撤销的过滤</translation>
    </message>
    <message>
        <source>Redo Filter</source>
        <translation>重做过滤</translation>
    </message>
    <message>
        <source>Redo the previously undone filter operation</source>
        <translation>重做之前撤销的过滤操作</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>清除所有过滤 - 从所有图层移除所有过滤</translation>
    </message>
    <message>
        <source>Clear All Filters</source>
        <translation>清除所有过滤</translation>
    </message>
    <message>
        <source>Remove all active filters from all layers in the project</source>
        <translation>从项目中的所有图层移除所有活动过滤</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>导出 - 将过滤后的图层保存到指定位置</translation>
    </message>
    <message>
        <source>Export</source>
        <translation>导出</translation>
    </message>
    <message>
        <source>Export the filtered layers to the configured output location and format</source>
        <translation>将过滤后的图层导出到配置的输出位置和格式</translation>
    </message>
    <message>
        <source>About FilterMate - Display plugin information and help</source>
        <translation>关于 FilterMate - 显示插件信息和帮助</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>与</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>与非</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>或</translation>
    </message>
    <message>
        <source>QML</source>
        <translation>QML</translation>
    </message>
    <message>
        <source>SLD</source>
        <translation>SLD</translation>
    </message>
    <message>
        <source> m</source>
        <translation> 米</translation>
    </message>
    <message>
        <source>, </source>
        <translation>，</translation>
    </message>
    <message>
        <source>Multi-layer filtering</source>
        <translation>多图层过滤</translation>
    </message>
    <message>
        <source>Additive filtering for the selected layer</source>
        <translation>选定图层的叠加过滤</translation>
    </message>
    <message>
        <source>Geospatial filtering</source>
        <translation>地理空间过滤</translation>
    </message>
    <message>
        <source>Buffer</source>
        <translation>缓冲区</translation>
    </message>
    <message>
        <source>Expression layer</source>
        <translation>表达式图层</translation>
    </message>
    <message>
        <source>Geometric predicate</source>
        <translation>几何谓词</translation>
    </message>
    <message>
        <source>Value in meters</source>
        <translation>值（米）</translation>
    </message>
    <message>
        <source>Output format</source>
        <translation>输出格式</translation>
    </message>
    <message>
        <source>Filter</source>
        <translation>过滤</translation>
    </message>
    <message>
        <source>Reset</source>
        <translation>重置</translation>
    </message>
    <message>
        <source>Layers to export</source>
        <translation>要导出的图层</translation>
    </message>
    <message>
        <source>Layers projection</source>
        <translation>图层投影</translation>
    </message>
    <message>
        <source>Save styles</source>
        <translation>保存样式</translation>
    </message>
    <message>
        <source>Datatype export</source>
        <translation>数据类型导出</translation>
    </message>
    <message>
        <source>Name of file/directory</source>
        <translation>文件/目录名称</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidget</name>
    <message>
        <source>Reload the plugin to apply layout changes (action bar position)</source>
        <translation>重新加载插件以应用布局更改（操作栏位置）</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>重新加载插件</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>您要重新加载 FilterMate 以应用所有配置更改吗？</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>当前图层：{name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>未选择图层</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>选定的图层：</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>已选择多个图层</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>未选择图层</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>表达式：</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>未定义表达式</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>显示表达式：{expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>要素 ID：{id}</translation>
    </message>
    <message>
        <source>Current layer: {0}</source>
        <translation>当前图层：{0}</translation>
    </message>
    <message>
        <source>Selected layers:
{0}</source>
        <translation>选定的图层：
{0}</translation>
    </message>
    <message>
        <source>Expression:
{0}</source>
        <translation>表达式：
{0}</translation>
    </message>
    <message>
        <source>Expression: {0}</source>
        <translation>表达式：{0}</translation>
    </message>
    <message>
        <source>Display expression: {0}</source>
        <translation>显示表达式：{0}</translation>
    </message>
    <message>
        <source>Feature ID: {0}
First attribute: {1}</source>
        <translation>要素 ID：{0}
第一个属性：{1}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>正在对 {count} 个图层开始过滤</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>正在从 {count} 个图层移除过滤</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>正在重置 {count} 个图层</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>正在导出 {count} 个图层</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>成功过滤 {count} 个图层</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>成功从 {count} 个图层移除过滤</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>成功重置 {count} 个图层</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>成功导出 {count} 个图层</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>大型数据集（{count} 个要素）没有 PostgreSQL。性能可能会降低。</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>建议使用 PostgreSQL 以获得更好的性能。</translation>
    </message>
</context>
<context>
    <name>OptimizationDialogs</name>
    <message>
        <source>FilterMate - Optimizations</source>
        <translation>FilterMate - 优化</translation>
    </message>
    <message>
        <source>Optimizations for:</source>
        <translation>优化：</translation>
    </message>
    <message>
        <source>features</source>
        <translation>个要素</translation>
    </message>
    <message>
        <source>Estimated speedup:</source>
        <translation>预计加速：</translation>
    </message>
    <message>
        <source>faster</source>
        <translation>更快</translation>
    </message>
    <message>
        <source>Use centroids</source>
        <translation>使用质心</translation>
    </message>
    <message>
        <source>Use centroids for distant layers</source>
        <translation>为远程图层使用质心</translation>
    </message>
    <message>
        <source>Enable buffer type</source>
        <translation>启用缓冲区类型</translation>
    </message>
    <message>
        <source>Simplify geometries</source>
        <translation>简化几何</translation>
    </message>
    <message>
        <source>BBox pre-filtering</source>
        <translation>BBox 预过滤</translation>
    </message>
    <message>
        <source>Attribute-first strategy</source>
        <translation>属性优先策略</translation>
    </message>
    <message>
        <source>Remember for this session</source>
        <translation>记住本次会话</translation>
    </message>
    <message>
        <source>Skip</source>
        <translation>跳过</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>应用</translation>
    </message>
    <message>
        <source>Optimization Settings</source>
        <translation>优化设置</translation>
    </message>
    <message>
        <source>Enable optimizations</source>
        <translation>启用优化</translation>
    </message>
    <message>
        <source>Suggest performance optimizations before filtering</source>
        <translation>过滤前建议性能优化</translation>
    </message>
    <message>
        <source>Auto-use centroids for remote layers</source>
        <translation>自动为远程图层使用质心</translation>
    </message>
    <message>
        <source>Use centroids to reduce network transfer (~90% faster)</source>
        <translation>使用质心减少网络传输（约快90%）</translation>
    </message>
    <message>
        <source>Auto-select best strategy</source>
        <translation>自动选择最佳策略</translation>
    </message>
    <message>
        <source>Automatically choose optimal filtering strategy</source>
        <translation>自动选择最佳过滤策略</translation>
    </message>
    <message>
        <source>Auto-simplify geometries</source>
        <translation>自动简化几何</translation>
    </message>
    <message>
        <source>Warning: lossy operation, may change polygon shapes</source>
        <translation>警告：有损操作，可能改变多边形形状</translation>
    </message>
    <message>
        <source>Ask before applying</source>
        <translation>应用前询问</translation>
    </message>
    <message>
        <source>Show confirmation dialog before optimizations</source>
        <translation>优化前显示确认对话框</translation>
    </message>
    <message>
        <source>Centroids enabled for '{0}' (~{1}x {2})</source>
        <translation>已为 '{0}' 启用质心（约{1}倍{2}）</translation>
    </message>
    <message>
        <source>BBox pre-filter enabled for '{0}'</source>
        <translation>已为 '{0}' 启用BBox预过滤</translation>
    </message>
    <message>
        <source>Optimization applied: '{0}' (~{1}x {2})</source>
        <translation>已应用优化：'{0}'（约{1}倍{2}）</translation>
    </message>
    <message>
        <source>Simplify before buffer</source>
        <translation>缓冲前简化</translation>
    </message>
    <message>
        <source>Reduce buffer segments</source>
        <translation>减少缓冲区段数</translation>
    </message>
</context>
<context>
    <name>BackendOptimizationWidget</name>
    <message>
        <source>Quick Setup</source>
        <translation>快速设置</translation>
    </message>
    <message>
        <source>Choose a profile or customize settings below</source>
        <translation>选择配置文件或在下方自定义设置</translation>
    </message>
    <message>
        <source>Smart Recommendations</source>
        <translation>智能推荐</translation>
    </message>
    <message>
        <source>Balanced Profile</source>
        <translation>平衡配置</translation>
    </message>
    <message>
        <source>Maximum Performance</source>
        <translation>最大性能</translation>
    </message>
    <message>
        <source>Minimal Resources</source>
        <translation>最小资源</translation>
    </message>
    <message>
        <source>PostgreSQL/PostGIS Optimizations</source>
        <translation>PostgreSQL/PostGIS 优化</translation>
    </message>
    <message>
        <source>Materialized Views</source>
        <translation>物化视图</translation>
    </message>
    <message>
        <source>Create temporary materialized views for complex filters</source>
        <translation>为复杂过滤器创建临时物化视图</translation>
    </message>
    <message>
        <source>Two-Phase Filtering</source>
        <translation>两阶段过滤</translation>
    </message>
    <message>
        <source>Use bounding box pre-filtering before precise geometry tests</source>
        <translation>在精确几何测试前使用边界框预过滤</translation>
    </message>
    <message>
        <source>Progressive Loading</source>
        <translation>渐进加载</translation>
    </message>
    <message>
        <source>Load data in chunks for very large datasets</source>
        <translation>为超大数据集分块加载数据</translation>
    </message>
    <message>
        <source>Chunk Size</source>
        <translation>块大小</translation>
    </message>
    <message>
        <source>Server-Side Simplification</source>
        <translation>服务端简化</translation>
    </message>
    <message>
        <source>Simplify geometries on server for display purposes</source>
        <translation>在服务器端简化几何图形以用于显示</translation>
    </message>
    <message>
        <source>Simplification Tolerance</source>
        <translation>简化容差</translation>
    </message>
    <message>
        <source>Parallel Query Execution</source>
        <translation>并行查询执行</translation>
    </message>
    <message>
        <source>Execute independent queries in parallel</source>
        <translation>并行执行独立查询</translation>
    </message>
    <message>
        <source>Expression Caching</source>
        <translation>表达式缓存</translation>
    </message>
    <message>
        <source>Cache compiled expressions for reuse</source>
        <translation>缓存编译后的表达式以便重用</translation>
    </message>
    <message>
        <source>Spatialite/GeoPackage Optimizations</source>
        <translation>Spatialite/GeoPackage 优化</translation>
    </message>
    <message>
        <source>R-tree Temp Tables</source>
        <translation>R-tree 临时表</translation>
    </message>
    <message>
        <source>Create temporary tables with R-tree indexes</source>
        <translation>创建带有R-tree索引的临时表</translation>
    </message>
    <message>
        <source>BBox Pre-filtering</source>
        <translation>边界框预过滤</translation>
    </message>
    <message>
        <source>Use bounding box filtering before precise tests</source>
        <translation>在精确测试前使用边界框过滤</translation>
    </message>
    <message>
        <source>Memory-Mapped I/O</source>
        <translation>内存映射I/O</translation>
    </message>
    <message>
        <source>Use memory-mapped I/O for file access</source>
        <translation>使用内存映射I/O进行文件访问</translation>
    </message>
    <message>
        <source>Batch Processing</source>
        <translation>批处理</translation>
    </message>
    <message>
        <source>Process multiple operations in batches</source>
        <translation>批量处理多个操作</translation>
    </message>
    <message>
        <source>Batch Size</source>
        <translation>批处理大小</translation>
    </message>
    <message>
        <source>OGR/Memory Optimizations</source>
        <translation>OGR/内存优化</translation>
    </message>
    <message>
        <source>Automatic Spatial Index</source>
        <translation>自动空间索引</translation>
    </message>
    <message>
        <source>Create temporary spatial indexes automatically</source>
        <translation>自动创建临时空间索引</translation>
    </message>
    <message>
        <source>Progressive Chunking</source>
        <translation>渐进分块</translation>
    </message>
    <message>
        <source>Process large files in progressive chunks</source>
        <translation>以渐进方式分块处理大文件</translation>
    </message>
    <message>
        <source>Memory Feature Caching</source>
        <translation>内存要素缓存</translation>
    </message>
    <message>
        <source>Cache features in memory for faster access</source>
        <translation>在内存中缓存要素以加快访问速度</translation>
    </message>
    <message>
        <source>Cache Size (features)</source>
        <translation>缓存大小（要素数）</translation>
    </message>
    <message>
        <source>Geometry Simplification</source>
        <translation>几何简化</translation>
    </message>
    <message>
        <source>Simplify complex geometries during processing</source>
        <translation>在处理过程中简化复杂几何图形</translation>
    </message>
    <message>
        <source>Global Optimizations</source>
        <translation>全局优化</translation>
    </message>
    <message>
        <source>Auto-Optimization</source>
        <translation>自动优化</translation>
    </message>
    <message>
        <source>Automatically optimize based on data analysis</source>
        <translation>基于数据分析自动优化</translation>
    </message>
    <message>
        <source>Auto-Centroid</source>
        <translation>自动质心</translation>
    </message>
    <message>
        <source>Automatically center view on filter results</source>
        <translation>自动将视图居中到过滤结果</translation>
    </message>
    <message>
        <source>Parallel Layer Filtering</source>
        <translation>并行图层过滤</translation>
    </message>
    <message>
        <source>Filter multiple layers simultaneously</source>
        <translation>同时过滤多个图层</translation>
    </message>
    <message>
        <source>Smart Expression Parsing</source>
        <translation>智能表达式解析</translation>
    </message>
    <message>
        <source>Optimize expression parsing for complex queries</source>
        <translation>为复杂查询优化表达式解析</translation>
    </message>
    <message>
        <source>Deferred Refresh</source>
        <translation>延迟刷新</translation>
    </message>
    <message>
        <source>Delay map refresh until all filters are applied</source>
        <translation>延迟地图刷新直到所有过滤器应用完成</translation>
    </message>
    <message>
        <source>Verbose Logging</source>
        <translation>详细日志</translation>
    </message>
    <message>
        <source>Enable detailed logging for debugging</source>
        <translation>启用详细日志以进行调试</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>应用</translation>
    </message>
    <message>
        <source>Reset to Defaults</source>
        <translation>恢复默认</translation>
    </message>
    <message>
        <source>Settings applied successfully</source>
        <translation>设置已成功应用</translation>
    </message>
    <message>
        <source>Settings reset to defaults</source>
        <translation>设置已恢复为默认值</translation>
    </message>
    <message>
        <source>Profile applied: {}</source>
        <translation>已应用配置文件：{}</translation>
    </message>
    <message>
        <source>Error applying settings</source>
        <translation>应用设置时出错</translation>
    </message>
<message><source>MV Status: Checking...</source><translation type="unfinished">MV Status: Checking...</translation></message><message><source>MV Status: Error</source><translation type="unfinished">MV Status: Error</translation></message><message><source>MV Status: Clean</source><translation type="unfinished">MV Status: Clean</translation></message><message><source>MV Status:</source><translation type="unfinished">MV Status:</translation></message><message><source>active</source><translation type="unfinished">active</translation></message><message><source>No active materialized views</source><translation type="unfinished">No active materialized views</translation></message><message><source>Session:</source><translation type="unfinished">Session:</translation></message><message><source>Other sessions:</source><translation type="unfinished">Other sessions:</translation></message><message><source>🧹 Session</source><translation type="unfinished">🧹 Session</translation></message><message><source>Cleanup MVs from this session</source><translation type="unfinished">Cleanup MVs from this session</translation></message><message><source>🗑️ Orphaned</source><translation type="unfinished">🗑️ Orphaned</translation></message><message><source>Cleanup orphaned MVs (&gt;24h old)</source><translation type="unfinished">Cleanup orphaned MVs (&gt;24h old)</translation></message><message><source>⚠️ All</source><translation type="unfinished">⚠️ All</translation></message><message><source>Cleanup ALL MVs (affects other sessions)</source><translation type="unfinished">Cleanup ALL MVs (affects other sessions)</translation></message><message><source>Confirm Cleanup</source><translation type="unfinished">Confirm Cleanup</translation></message><message><source>Drop ALL materialized views?
This affects other FilterMate sessions!</source><translation type="unfinished">Drop ALL materialized views?
This affects other FilterMate sessions!</translation></message><message><source>Refresh MV status</source><translation type="unfinished">Refresh MV status</translation></message><message><source>Threshold:</source><translation type="unfinished">Threshold:</translation></message><message><source>features</source><translation type="unfinished">features</translation></message><message><source>Auto-cleanup on exit</source><translation type="unfinished">Auto-cleanup on exit</translation></message><message><source>Automatically drop session MVs when plugin unloads</source><translation type="unfinished">Automatically drop session MVs when plugin unloads</translation></message><message><source>Create MVs for datasets larger than this</source><translation type="unfinished">Create MVs for datasets larger than this</translation></message><message><source>faster possible</source><translation type="unfinished">faster possible</translation></message><message><source>Optimizations available</source><translation type="unfinished">Optimizations available</translation></message><message><source>FilterMate - Apply Optimizations?</source><translation type="unfinished">FilterMate - Apply Optimizations?</translation></message><message><source>Skip</source><translation type="unfinished">Skip</translation></message><message><source>✓ Apply</source><translation type="unfinished">✓ Apply</translation></message><message><source>Don't ask for this session</source><translation type="unfinished">Don't ask for this session</translation></message><message><source>Centroids</source><translation type="unfinished">Centroids</translation></message><message><source>Simplify</source><translation type="unfinished">Simplify</translation></message><message><source>Pre-simplify</source><translation type="unfinished">Pre-simplify</translation></message><message><source>Fewer segments</source><translation type="unfinished">Fewer segments</translation></message><message><source>Flat buffer</source><translation type="unfinished">Flat buffer</translation></message><message><source>BBox filter</source><translation type="unfinished">BBox filter</translation></message><message><source>Attr-first</source><translation type="unfinished">Attr-first</translation></message><message><source>PostgreSQL not available</source><translation type="unfinished">PostgreSQL not available</translation></message><message><source>No connection</source><translation type="unfinished">No connection</translation></message><message><source>Auto-zoom when feature changes</source><translation type="unfinished">Auto-zoom when feature changes</translation></message><message><source>Backend optimization settings saved</source><translation type="unfinished">Backend optimization settings saved</translation></message><message><source>Backend optimizations configured</source><translation type="unfinished">Backend optimizations configured</translation></message><message><source>Expression Evaluation</source><translation type="unfinished">Expression Evaluation</translation></message><message><source>Identify selected feature</source><translation type="unfinished">Identify selected feature</translation></message><message><source>Layer properties reset to defaults</source><translation type="unfinished">Layer properties reset to defaults</translation></message><message><source>Link exploring widgets together</source><translation type="unfinished">Link exploring widgets together</translation></message><message><source>Optimization settings saved</source><translation type="unfinished">Optimization settings saved</translation></message><message><source>Reset all layer exploring properties</source><translation type="unfinished">Reset all layer exploring properties</translation></message><message><source>Toggle feature selection on map</source><translation type="unfinished">Toggle feature selection on map</translation></message><message><source>Use centroids instead of full geometries for distant layers (faster for complex polygons)</source><translation type="unfinished">Use centroids instead of full geometries for distant layers (faster for complex polygons)</translation></message><message><source>Use centroids instead of full geometries for source layer (faster for complex polygons)</source><translation type="unfinished">Use centroids instead of full geometries for source layer (faster for complex polygons)</translation></message><message><source>Zoom to selected feature</source><translation type="unfinished">Zoom to selected feature</translation></message></context>
</TS>