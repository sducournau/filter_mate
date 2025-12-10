@echo off
REM Installation script for FilterMate test environment (Windows)

echo ========================================
echo FilterMate Test Environment Setup
echo ========================================
echo.

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH
    echo Please install Python and add it to PATH
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Install test dependencies
echo Installing test dependencies...
echo -------------------------------
echo.

echo Installing pytest and related packages...
python -m pip install pytest pytest-cov pytest-mock --user

echo.
echo Installing code quality tools...
python -m pip install black flake8 --user

echo.
echo [OK] Dependencies installed successfully
echo.

REM Verify installation
echo Verifying installation...
echo ------------------------
echo.

python -m pytest --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] pytest installed
    python -m pytest --version
) else (
    echo [ERROR] pytest installation failed
    pause
    exit /b 1
)

REM Run tests
echo.
echo Running tests...
echo ---------------
echo.

if exist tests\ (
    echo Found tests directory
    
    echo.
    echo Running test suite...
    python -m pytest tests\ -v
    
    echo.
    echo [OK] Test run complete
) else (
    echo [ERROR] tests\ directory not found
    pause
    exit /b 1
)

REM Summary
echo.
echo ========================================
echo Setup Summary
echo ========================================
echo [OK] Test framework installed
echo [OK] Code quality tools installed
echo.
echo Next steps:
echo 1. Review test results above
echo 2. Install any missing dependencies for failing tests
echo 3. Run tests manually: pytest tests\ -v
echo 4. Check coverage: pytest tests\ --cov=. --cov-report=html
echo.
echo [OK] Phase 1 setup complete!
echo.
pause
