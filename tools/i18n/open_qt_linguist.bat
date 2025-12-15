@echo off
rem Open Qt Linguist from OSGeo4W environment
rem This script launches Qt Linguist for editing FilterMate translation files (.ts)

rem Set OSGEO4W_ROOT - adjust this path if your OSGeo4W installation is different
set OSGEO4W_ROOT=C:\OSGeo4W

rem Check if OSGeo4W exists
if not exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" (
    echo ERROR: OSGeo4W not found at %OSGEO4W_ROOT%
    echo Please edit this script and set the correct OSGEO4W_ROOT path.
    pause
    exit /b 1
)

rem Initialize OSGeo4W environment
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

rem Launch Qt Linguist
echo Starting Qt Linguist...
start "" "%OSGEO4W_ROOT%\apps\Qt5\bin\linguist.exe" "%~dp0i18n\FilterMate_fr.ts"
