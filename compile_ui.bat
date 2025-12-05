@echo off
REM Script pour compiler le fichier .ui avec l'environnement QGIS OSGeo4W
REM Usage: compile_ui.bat

echo ============================================================
echo Compilation UI FilterMate avec OSGeo4W
echo ============================================================
echo.

REM Chemin vers OSGeo4W.bat
set OSGEO4W_BAT="C:\Program Files\QGIS 3.44.2\OSGeo4W.bat"

REM Vérifier que OSGeo4W.bat existe
if not exist %OSGEO4W_BAT% (
    echo ERREUR: OSGeo4W.bat introuvable a l'emplacement:
    echo %OSGEO4W_BAT%
    echo.
    echo Veuillez ajuster le chemin dans le script.
    pause
    exit /b 1
)

REM Répertoire du plugin
cd /d "%~dp0"

echo Repertoire actuel: %CD%
echo.

REM Vérifier que le fichier .ui existe
if not exist "filter_mate_dockwidget_base.ui" (
    echo ERREUR: filter_mate_dockwidget_base.ui introuvable
    pause
    exit /b 1
)

echo Fichier source: filter_mate_dockwidget_base.ui
echo Fichier cible: filter_mate_dockwidget_base.py
echo.

REM Créer un backup du .py existant si présent
if exist "filter_mate_dockwidget_base.py" (
    echo Creation backup: filter_mate_dockwidget_base.py.backup
    copy /Y "filter_mate_dockwidget_base.py" "filter_mate_dockwidget_base.py.backup" >nul
)

echo.
echo Lancement de pyuic5 via OSGeo4W...
echo.

REM Exécuter pyuic5 dans l'environnement OSGeo4W
call %OSGEO4W_BAT% pyuic5 -x filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py

REM Vérifier le résultat
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCES: Fichier compile avec succes!
    echo ============================================================
    echo.
    echo Fichier genere: filter_mate_dockwidget_base.py
    echo.
) else (
    echo.
    echo ============================================================
    echo ERREUR: La compilation a echoue
    echo ============================================================
    echo.
    if exist "filter_mate_dockwidget_base.py.backup" (
        echo Restauration du backup...
        copy /Y "filter_mate_dockwidget_base.py.backup" "filter_mate_dockwidget_base.py" >nul
        echo Backup restaure.
    )
)

pause
