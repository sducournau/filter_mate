@echo off
REM Test runner for FilterMate using QGIS Python environment
REM Phase 14.1 - BackendExpressionBuilder tests

echo Running FilterMate tests with QGIS Python environment...
echo.

cd /d "%~dp0"

REM Set QGIS path
set OSGEO4W_ROOT=C:\Program Files\QGIS 3.44.2
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT%\apps\qgis

REM Initialize QGIS environment
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

REM Add QGIS Python modules to path
set PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis\python;%PYTHONPATH%
set PYTHONPATH=%OSGEO4W_ROOT%\apps\Python312\Lib\site-packages;%PYTHONPATH%
set PYTHONPATH=%CD%;%PYTHONPATH%

REM Debug: Show Python version and paths
echo Python executable:
where python3
echo.
python3 --version
echo.
echo PYTHONPATH:
echo %PYTHONPATH%
echo.

REM Test QGIS import
echo Testing QGIS import...
python3 -c "import sys; import qgis.core; print('QGIS version:', qgis.core.Qgis.QGIS_VERSION)"
echo.

REM Run tests
echo Testing BackendExpressionBuilder service...
python3 -m unittest tests.test_backend_expression_builder -v

echo.
echo Tests complete. Press any key to exit...
pause > nul
