@echo off
REM Script to compile .ui files to Python with pyuic5
REM Usage: compile_ui.bat

echo ============================================================
echo FilterMate UI Compilation
echo ============================================================
echo.

REM Get script directory (plugin root)
cd /d "%~dp0"

echo Working directory: %CD%
echo.

REM UI file to compile
set UI_FILE=filter_mate_dockwidget_base.ui
set PY_FILE=filter_mate_dockwidget_base.py

REM Check if .ui file exists
if not exist "%UI_FILE%" (
    echo ERROR: %UI_FILE% not found
    pause
    exit /b 1
)

echo Source file: %UI_FILE%
echo Target file: %PY_FILE%
echo.

REM Create backup of existing .py file
if exist "%PY_FILE%" (
    echo Creating backup: %PY_FILE%.backup
    copy /Y "%PY_FILE%" "%PY_FILE%.backup" >nul
)

echo.
echo Running pyuic5...
echo.

REM Try different paths to find pyuic5

REM Option 1: QGIS OSGeo4W installation
set OSGEO4W_PATHS="C:\Program Files\QGIS 3.44.6\OSGeo4W.bat" ^
                  "C:\Program Files\QGIS 3.44.5\OSGeo4W.bat" ^
                  "C:\Program Files\QGIS 3.44.4\OSGeo4W.bat" ^
                  "C:\Program Files\QGIS 3.44.2\OSGeo4W.bat" ^
                  "C:\Program Files\QGIS 3.38\OSGeo4W.bat" ^
                  "C:\OSGeo4W\OSGeo4W.bat" ^
                  "C:\OSGeo4W64\OSGeo4W.bat"

for %%P in (%OSGEO4W_PATHS%) do (
    if exist %%P (
        echo Found OSGeo4W at: %%P
        call %%P pyuic5 -x "%UI_FILE%" -o "%PY_FILE%"
        goto :check_result
    )
)

REM Option 2: Direct pyuic5 in PATH
where pyuic5 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using pyuic5 from PATH
    pyuic5 -x "%UI_FILE%" -o "%PY_FILE%"
    goto :check_result
)

REM Option 3: Python module
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using Python PyQt5 module
    python -m PyQt5.uic.pyuic -x "%UI_FILE%" -o "%PY_FILE%"
    goto :check_result
)

echo ERROR: pyuic5 not found. Please install QGIS or PyQt5 tools.
pause
exit /b 1

:check_result
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Compilation successful, applying post-processing...
    echo.
    
    REM Clean Python cache to prevent stale bytecode issues
    echo Cleaning Python cache...
    for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
    del /s /q *.pyc 2>nul
    echo   - Cache cleared
    echo.
    
    REM Fix resources_rc import - replace with correct module name
    REM pyuic5 generates "import resources_rc" but our file is "resources.py"
    REM Use regex pattern to match any variation (with/without comments, whitespace)
    powershell -Command "$content = Get-Content '%PY_FILE%' -Raw; $newContent = $content -replace '(?m)^import resources_rc.*$', 'from . import resources  # Qt resources (was: import resources_rc)'; if ($content -ne $newContent) { $newContent | Set-Content '%PY_FILE%' -NoNewline; Write-Host 'Post-processing: Fixed import resources_rc to from . import resources'; exit 0 } else { Write-Host 'Note: No resources_rc import found (may already be correct)'; exit 0 }"
    
    REM Verify the fix was applied
    findstr /C:"import resources_rc" "%PY_FILE%" >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo WARNING: 'import resources_rc' still present! Attempting alternative fix...
        powershell -Command "(Get-Content '%PY_FILE%') | ForEach-Object { $_ -replace '^import resources_rc.*$', 'from . import resources  # Qt resources (was: import resources_rc)' } | Set-Content '%PY_FILE%'"
        echo Alternative fix attempted.
    ) else (
        echo Post-processing completed successfully.
    )
    
    echo.
    echo ============================================================
    echo SUCCESS: File compiled and patched successfully!
    echo ============================================================
    echo.
    echo Generated file: %PY_FILE%
    echo.
) else (
    echo.
    echo ============================================================
    echo ERROR: Compilation failed
    echo ============================================================
    echo.
    if exist "%PY_FILE%.backup" (
        echo Restoring backup...
        copy /Y "%PY_FILE%.backup" "%PY_FILE%" >nul
        echo Backup restored.
    )
    pause
    exit /b 1
)

pause
