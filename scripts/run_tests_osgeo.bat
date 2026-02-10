@echo off
REM Script pour exécuter les tests avec l'environnement QGIS OSGeo4W
REM Usage: run_tests_osgeo.bat [test_path]

set OSGEO4W_ROOT=C:\Program Files\QGIS 3.44.6
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT%\apps\qgis

REM Setup OSGeo4W environment
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

REM Add QGIS Python to path
set PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis\python;%OSGEO4W_ROOT%\apps\qgis\python\plugins;%CD%;%PYTHONPATH%

REM Set test path (default to tests/unit/)
set TEST_PATH=%1
if "%TEST_PATH%"=="" set TEST_PATH=tests/unit/

echo.
echo ===================================================
echo Running FilterMate Tests with QGIS Environment
echo ===================================================
echo OSGEO4W_ROOT: %OSGEO4W_ROOT%
echo PYTHONPATH includes: %OSGEO4W_ROOT%\apps\qgis\python
echo Test path: %TEST_PATH%
echo.

REM Run pytest
python -m pytest %TEST_PATH% -v --tb=short

echo.
echo Tests completed.
pause
