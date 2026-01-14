#!/bin/bash
# UI Dimensions Validation Script (Bash version)
# Validates that combobox and input heights are set to 20px in UIConfig

echo "======================================================================"
echo "UI DIMENSIONS VALIDATION - 20px Standard"
echo "======================================================================"

CONFIG_FILE="ui/config/__init__.py"
EXPECTED=20
ERRORS=0
VALIDATED=0

# Check if file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: UIConfig file not found at $CONFIG_FILE"
    exit 1
fi

echo ""
echo "🔍 Checking NORMAL profile..."
echo ""

# Check NORMAL combobox (lines 95-100)
NORMAL_COMBO_HEIGHT=$(sed -n "96p" $CONFIG_FILE | grep -oP "'height':\s*\K\d+")
NORMAL_COMBO_MIN=$(sed -n "97p" $CONFIG_FILE | grep -oP "'min_height':\s*\K\d+")
NORMAL_COMBO_MAX=$(sed -n "98p" $CONFIG_FILE | grep -oP "'max_height':\s*\K\d+")

if [ "$NORMAL_COMBO_HEIGHT" == "$EXPECTED" ]; then
    echo "✅ NORMAL ComboBox height = ${NORMAL_COMBO_HEIGHT}px"
    ((VALIDATED++))
else
    echo "❌ NORMAL ComboBox height = ${NORMAL_COMBO_HEIGHT}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$NORMAL_COMBO_MIN" == "$EXPECTED" ]; then
    echo "✅ NORMAL ComboBox min_height = ${NORMAL_COMBO_MIN}px"
    ((VALIDATED++))
else
    echo "❌ NORMAL ComboBox min_height = ${NORMAL_COMBO_MIN}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$NORMAL_COMBO_MAX" == "$EXPECTED" ]; then
    echo "✅ NORMAL ComboBox max_height = ${NORMAL_COMBO_MAX}px"
    ((VALIDATED++))
else
    echo "❌ NORMAL ComboBox max_height = ${NORMAL_COMBO_MAX}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

# Check NORMAL input (lines 103-107)
NORMAL_INPUT_HEIGHT=$(sed -n "104p" $CONFIG_FILE | grep -oP "'height':\s*\K\d+")
NORMAL_INPUT_MIN=$(sed -n "105p" $CONFIG_FILE | grep -oP "'min_height':\s*\K\d+")
NORMAL_INPUT_MAX=$(sed -n "106p" $CONFIG_FILE | grep -oP "'max_height':\s*\K\d+")

if [ "$NORMAL_INPUT_HEIGHT" == "$EXPECTED" ]; then
    echo "✅ NORMAL Input height = ${NORMAL_INPUT_HEIGHT}px"
    ((VALIDATED++))
else
    echo "❌ NORMAL Input height = ${NORMAL_INPUT_HEIGHT}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$NORMAL_INPUT_MIN" == "$EXPECTED" ]; then
    echo "✅ NORMAL Input min_height = ${NORMAL_INPUT_MIN}px"
    ((VALIDATED++))
else
    echo "❌ NORMAL Input min_height = ${NORMAL_INPUT_MIN}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$NORMAL_INPUT_MAX" == "$EXPECTED" ]; then
    echo "✅ NORMAL Input max_height = ${NORMAL_INPUT_MAX}px"
    ((VALIDATED++))
else
    echo "❌ NORMAL Input max_height = ${NORMAL_INPUT_MAX}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

echo ""
echo "🔍 Checking COMPACT profile..."
echo ""

# Check COMPACT combobox (lines 267-271)
COMPACT_COMBO_HEIGHT=$(sed -n "268p" $CONFIG_FILE | grep -oP "'height':\s*\K\d+")
COMPACT_COMBO_MIN=$(sed -n "269p" $CONFIG_FILE | grep -oP "'min_height':\s*\K\d+")
COMPACT_COMBO_MAX=$(sed -n "270p" $CONFIG_FILE | grep -oP "'max_height':\s*\K\d+")

if [ "$COMPACT_COMBO_HEIGHT" == "$EXPECTED" ]; then
    echo "✅ COMPACT ComboBox height = ${COMPACT_COMBO_HEIGHT}px"
    ((VALIDATED++))
else
    echo "❌ COMPACT ComboBox height = ${COMPACT_COMBO_HEIGHT}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$COMPACT_COMBO_MIN" == "$EXPECTED" ]; then
    echo "✅ COMPACT ComboBox min_height = ${COMPACT_COMBO_MIN}px"
    ((VALIDATED++))
else
    echo "❌ COMPACT ComboBox min_height = ${COMPACT_COMBO_MIN}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$COMPACT_COMBO_MAX" == "$EXPECTED" ]; then
    echo "✅ COMPACT ComboBox max_height = ${COMPACT_COMBO_MAX}px"
    ((VALIDATED++))
else
    echo "❌ COMPACT ComboBox max_height = ${COMPACT_COMBO_MAX}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

# Check COMPACT input (lines 275-279)
COMPACT_INPUT_HEIGHT=$(sed -n "276p" $CONFIG_FILE | grep -oP "'height':\s*\K\d+")
COMPACT_INPUT_MIN=$(sed -n "277p" $CONFIG_FILE | grep -oP "'min_height':\s*\K\d+")
COMPACT_INPUT_MAX=$(sed -n "278p" $CONFIG_FILE | grep -oP "'max_height':\s*\K\d+")

if [ "$COMPACT_INPUT_HEIGHT" == "$EXPECTED" ]; then
    echo "✅ COMPACT Input height = ${COMPACT_INPUT_HEIGHT}px"
    ((VALIDATED++))
else
    echo "❌ COMPACT Input height = ${COMPACT_INPUT_HEIGHT}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$COMPACT_INPUT_MIN" == "$EXPECTED" ]; then
    echo "✅ COMPACT Input min_height = ${COMPACT_INPUT_MIN}px"
    ((VALIDATED++))
else
    echo "❌ COMPACT Input min_height = ${COMPACT_INPUT_MIN}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

if [ "$COMPACT_INPUT_MAX" == "$EXPECTED" ]; then
    echo "✅ COMPACT Input max_height = ${COMPACT_INPUT_MAX}px"
    ((VALIDATED++))
else
    echo "❌ COMPACT Input max_height = ${COMPACT_INPUT_MAX}px (expected ${EXPECTED}px)"
    ((ERRORS++))
fi

# Summary
echo ""
echo "======================================================================"
if [ $ERRORS -gt 0 ]; then
    echo "❌ VALIDATION FAILED"
    echo ""
    echo "Total errors: $ERRORS"
    echo "Validated correctly: $VALIDATED"
    exit 1
else
    echo "✅ VALIDATION PASSED"
    echo ""
    echo "✨ All $VALIDATED widget dimensions correctly set to ${EXPECTED}px!"
    echo "   NORMAL and COMPACT profiles are now unified."
    echo ""
    echo "   Widgets validated:"
    echo "   - ComboBox (height, min_height, max_height)"
    echo "   - Input (height, min_height, max_height)"
    exit 0
fi
