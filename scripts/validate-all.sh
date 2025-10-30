#!/bin/bash
# Comprehensive validation script for local development

set -e

echo "🔍 Running all validations..."
echo ""

# Python formatting
echo "📝 Checking Python formatting..."
ruff format --check .
echo "✓ Python formatting OK"
echo ""

# Python linting
echo "🔎 Linting Python code..."
ruff check .
echo "✓ Python linting OK"
echo ""

# JSON formatting
echo "📋 Checking JSON formatting..."
python -m json.tool index-template.json > /tmp/index-template.json
if ! diff -q index-template.json /tmp/index-template.json > /dev/null; then
    echo "❌ index-template.json is not properly formatted"
    echo "Run: python -m json.tool index-template.json > index-template.json.tmp && mv index-template.json.tmp index-template.json"
    exit 1
fi
echo "✓ JSON formatting OK"
echo ""

# Generate index.json from template
echo "🔨 Generating index.json from template..."
python build.py rebuild-index 2>/dev/null || echo "⚠ No builds directory found, creating empty index"
echo ""

# Configuration completeness
echo "🎯 Checking configuration displayNames..."
python build.py check-configurations
echo ""

# Kconfig files
echo "📦 Checking kconfig files..."
python build.py validate
echo ""

# Vendor consistency
echo "🏢 Checking vendor consistency..."
python -c "
import json
import sys

with open('index-template.json') as f:
    data = json.load(f)

vendor_ids = {v['vendorId'] for v in data.get('vendors', [])}
target_vendor_ids = {t['vendorId'] for t in data.get('targets', [])}
missing_vendors = target_vendor_ids - vendor_ids

if missing_vendors:
    print(f'❌ Missing vendor definitions for: {sorted(missing_vendors)}')
    sys.exit(1)

print(f'✓ All {len(target_vendor_ids)} vendors are defined')
"
echo ""

# Target schema
echo "🎯 Validating target schema..."
python -c "
import json
import sys

with open('index-template.json') as f:
    data = json.load(f)

errors = []

for target in data.get('targets', []):
    target_id = target.get('targetId', 'unknown')
    required_fields = ['targetId', 'vendorId', 'displayName', 'flashMethods', 'configuration']
    
    for field in required_fields:
        if field not in target:
            errors.append(f'{target_id}: missing {field}')

if errors:
    for error in errors:
        print(f'❌ {error}')
    sys.exit(1)

print(f'✓ All {len(data.get(\"targets\", []))} targets valid')
"
echo ""

echo "✅ All validations passed!"
