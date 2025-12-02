@echo off
REM Clear FilterMate Plugin Cache for QGIS
REM Double-click this file to run

echo ====================================
echo FilterMate Cache Cleaner
echo ====================================
echo.

set "QGIS_PLUGIN_DIR=%APPDATA%\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate"
set "SOURCE_DIR=%~dp0"

echo 1. Clearing cache from source directory...
if exist "%SOURCE_DIR%__pycache__" (
    rmdir /s /q "%SOURCE_DIR%__pycache__"
    echo    Removed __pycache__ from root
)

if exist "%SOURCE_DIR%modules\__pycache__" (
    rmdir /s /q "%SOURCE_DIR%modules\__pycache__"
    echo    Removed modules\__pycache__
)

if exist "%SOURCE_DIR%config\__pycache__" (
    rmdir /s /q "%SOURCE_DIR%config\__pycache__"
    echo    Removed config\__pycache__
)

echo    Done!
echo.

if exist "%QGIS_PLUGIN_DIR%" (
    echo 2. Clearing cache from QGIS plugin directory...
    
    if exist "%QGIS_PLUGIN_DIR%\__pycache__" (
        rmdir /s /q "%QGIS_PLUGIN_DIR%\__pycache__"
        echo    Removed __pycache__ from root
    )
    
    if exist "%QGIS_PLUGIN_DIR%\modules\__pycache__" (
        rmdir /s /q "%QGIS_PLUGIN_DIR%\modules\__pycache__"
        echo    Removed modules\__pycache__
    )
    
    if exist "%QGIS_PLUGIN_DIR%\config\__pycache__" (
        rmdir /s /q "%QGIS_PLUGIN_DIR%\config\__pycache__"
        echo    Removed config\__pycache__
    )
    
    echo    Done!
) else (
    echo 2. QGIS plugin directory not found (plugin may not be installed)
)

echo.
echo ====================================
echo Cache cleared successfully!
echo ====================================
echo.
echo NEXT STEPS:
echo 1. Close QGIS completely (if running)
echo 2. Reopen QGIS
echo 3. Go to Plugin Manager ^> Installed
echo 4. Uncheck and re-check FilterMate
echo.
echo If the error persists, manually delete:
echo %QGIS_PLUGIN_DIR%
echo Then reinstall the plugin.
echo.
pause
