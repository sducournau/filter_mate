@echo off
REM Script complet pour rebuild UI FilterMate
REM 1. Modifie le .ui avec update_ui_properties.py
REM 2. Compile le .ui en .py avec OSGeo4W

echo ============================================================
echo FilterMate UI - Rebuild Complet
echo ============================================================
echo.

REM Chemin vers OSGeo4W
set OSGEO4W_BAT="C:\Program Files\QGIS 3.44.2\OSGeo4W.bat"

REM Vérification OSGeo4W
if not exist %OSGEO4W_BAT% (
    echo ERREUR: OSGeo4W.bat introuvable
    pause
    exit /b 1
)

cd /d "%~dp0"
echo Repertoire: %CD%
echo.

REM ============================================================
REM ETAPE 1: Mise a jour du .ui avec Python
REM ============================================================
echo ETAPE 1/2: Mise a jour des proprietes UI...
echo.

if exist "update_ui_properties.py" (
    python update_ui_properties.py
    
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ERREUR: Echec mise a jour proprietes
        pause
        exit /b 1
    )
) else (
    echo WARNING: update_ui_properties.py introuvable, passage a compilation...
)

echo.
echo ============================================================
REM ETAPE 2: Compilation .ui -> .py
REM ============================================================
echo ETAPE 2/2: Compilation avec pyuic5...
echo.

if not exist "filter_mate_dockwidget_base.ui" (
    echo ERREUR: filter_mate_dockwidget_base.ui introuvable
    pause
    exit /b 1
)

REM Backup du .py
if exist "filter_mate_dockwidget_base.py" (
    echo Creation backup .py...
    copy /Y "filter_mate_dockwidget_base.py" "filter_mate_dockwidget_base.py.backup" >nul
)

REM Compilation
call %OSGEO4W_BAT% pyuic5 -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCES: UI rebuild complete!
    echo ============================================================
    echo.
    echo Fichiers generes:
    echo   - filter_mate_dockwidget_base.py (compile)
    echo   - filter_mate_dockwidget_base.ui.backup (backup UI)
    echo   - filter_mate_dockwidget_base.py.backup (backup PY)
    echo.
) else (
    echo.
    echo ============================================================
    echo ERREUR: Echec compilation
    echo ============================================================
    echo.
    if exist "filter_mate_dockwidget_base.py.backup" (
        echo Restauration backup...
        copy /Y "filter_mate_dockwidget_base.py.backup" "filter_mate_dockwidget_base.py" >nul
    )
)

pause
