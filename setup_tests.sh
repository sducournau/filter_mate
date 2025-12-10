#!/bin/bash
# Installation script for FilterMate test environment

set -e  # Exit on error

echo "🚀 FilterMate Test Environment Setup"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running in QGIS Python environment
if command -v qgis &> /dev/null; then
    echo -e "${GREEN}✓${NC} QGIS found"
    PYTHON_CMD="python3"
else
    echo -e "${YELLOW}⚠${NC} QGIS not found in PATH, using system Python"
    PYTHON_CMD="python3"
fi

# Check Python version
echo ""
echo "Checking Python version..."
$PYTHON_CMD --version

# Install test dependencies
echo ""
echo "Installing test dependencies..."
echo "-------------------------------"

if $PYTHON_CMD -m pip install --version &> /dev/null; then
    echo -e "${GREEN}✓${NC} pip is available"
    
    echo ""
    echo "Installing pytest and related packages..."
    $PYTHON_CMD -m pip install pytest pytest-cov pytest-mock --user
    
    echo ""
    echo "Installing code quality tools..."
    $PYTHON_CMD -m pip install black flake8 --user
    
    echo ""
    echo -e "${GREEN}✓${NC} Dependencies installed successfully"
else
    echo -e "${RED}✗${NC} pip not found. Please install pip first."
    exit 1
fi

# Verify installation
echo ""
echo "Verifying installation..."
echo "------------------------"

if $PYTHON_CMD -m pytest --version &> /dev/null; then
    echo -e "${GREEN}✓${NC} pytest installed"
    $PYTHON_CMD -m pytest --version
else
    echo -e "${RED}✗${NC} pytest installation failed"
    exit 1
fi

# Run tests
echo ""
echo "Running tests..."
echo "---------------"

cd "$(dirname "$0")"

if [ -d "tests" ]; then
    echo "Found tests directory"
    
    # Count test files
    TEST_COUNT=$(find tests -name "test_*.py" -type f | wc -l)
    echo "Found $TEST_COUNT test files"
    
    echo ""
    echo "Running test suite..."
    $PYTHON_CMD -m pytest tests/ -v || true
    
    echo ""
    echo -e "${GREEN}✓${NC} Test run complete"
else
    echo -e "${RED}✗${NC} tests/ directory not found"
    exit 1
fi

# Summary
echo ""
echo "Setup Summary"
echo "============="
echo -e "${GREEN}✓${NC} Test framework installed"
echo -e "${GREEN}✓${NC} $TEST_COUNT test files created"
echo -e "${GREEN}✓${NC} Code quality tools installed"
echo ""
echo "Next steps:"
echo "1. Review test results above"
echo "2. Install any missing dependencies for failing tests"
echo "3. Run tests manually: pytest tests/ -v"
echo "4. Check coverage: pytest tests/ --cov=. --cov-report=html"
echo ""
echo -e "${GREEN}✓${NC} Phase 1 setup complete!"
