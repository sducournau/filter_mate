#!/bin/bash
# Script to move obsolete documentation files to archived folders

cd "$(dirname "$0")"

# Move configuration-related docs
mv CONFIG_OK_CANCEL_BEHAVIOR.md archived/configuration/ 2>/dev/null

# Move website deployment docs  
mv DOCUSAURUS_IMPLEMENTATION.md archived/website-deployment/ 2>/dev/null
mv QUICK_START_DEPLOY.md archived/website-deployment/ 2>/dev/null

# Move UI validation docs
mv UI_CONFIG_VALIDATION.md archived/ui-validation/ 2>/dev/null
mv UI_STYLE_HARMONIZATION.md archived/ui-validation/ 2>/dev/null

echo "Documentation files archived successfully!"
