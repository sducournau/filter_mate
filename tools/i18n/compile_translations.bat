@echo off
REM Script pour compiler les fichiers de traduction .ts en .qm
REM Usage: compile_translations.bat

echo ============================================================
echo Compilation des traductions FilterMate
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

REM Compiler chaque fichier .ts
echo Compilation des fichiers de traduction...
echo.

for %%f in (i18n\FilterMate_*.ts) do (
    echo Compilation de %%f...
    call %OSGEO4W_BAT% lrelease "%%f"
    if %ERRORLEVEL% EQU 0 (
        echo   [OK] %%f
    ) else (
        echo   [ERREUR] %%f
    )
    echo.
)

echo.
echo ============================================================
echo Compilation terminee!
echo ============================================================
echo.
echo Les fichiers .qm ont ete generes dans le dossier i18n/
echo.

pause
