# Contributing to Kalico Flasher CI

Thank you for contributing! This guide will help you add new targets, vendors, or configurations.

## Adding a New Target

1. **Add target to `index-template.json`:**

```json
{
  "targetId": "new_board_v1",
  "vendorId": "manufacturer",
  "displayName": "New Board V1",
  "flashMethods": ["dfu-util-webserial"],
  "links": {
    "manualUrl": "https://...",
    "pinoutUrl": "https://...",
    "schematicUrl": "https://..."
  },
  "configuration": {
    "firmwareFilenameTemplate": "{targetId}_{vendorId}_{interface}.bin",
    "kconfigFilenameTemplate": "{targetId}_{vendorId}_{interface}.kconfig",
    "permutations": {
      "interface": ["usb_pa11pa12", "can_pd0pd1_500k"]
    }
  }
}
```

2. **Create kconfig files in `kconfigs/`:**

For each permutation combination, create a `.kconfig` file:
- `new_board_v1_manufacturer_usb_pa11pa12.kconfig`
- `new_board_v1_manufacturer_can_pd0pd1_500k.kconfig`

3. **Validate:**

```bash
python build.py check-configurations
python build.py validate
```

## Adding a New Vendor

1. **Add to `index-template.json` vendors array:**

```json
{
  "vendorId": "newvendor",
  "displayName": "New Vendor Inc.",
  "websiteUrl": "https://newvendor.com/"
}
```

2. **Validate:**

```bash
./scripts/validate-all.sh
```

## Adding New Permutation Values

1. **Add permutation to target configuration:**

```json
"permutations": {
  "interface": ["usb_pa11pa12", "new_interface_type"]
}
```

2. **Add displayName to `configurations` array:**

```json
{
  "id": "new_interface_type",
  "displayName": "New Interface Type Description"
}
```

3. **Create corresponding kconfig files**

4. **Validate:**

```bash
python build.py check-configurations
python build.py validate
```

## Pre-commit Checklist

Before committing:

- [ ] Run `./scripts/validate-all.sh`
- [ ] All kconfig files created for new targets
- [ ] All permutation values have displayNames
- [ ] Vendor exists in vendors array
- [ ] Target has all required fields
- [ ] JSON is properly formatted
- [ ] Python code passes ruff checks

## Automated Checks

GitHub Actions will automatically verify:

1. **Python Code Quality**
   - Formatting (ruff format)
   - Linting (ruff check)

2. **JSON Formatting**
   - Proper indentation (4 spaces)
   - Valid JSON syntax

3. **Configuration Completeness**
   - All permutation values have displayNames
   - All kconfig files exist

4. **Schema Validation**
   - Vendors consistency
   - Target schema (required fields)
   - Build schema (version, buildDate, githubCommitUrl)

## Common Issues

### Missing kconfig file

**Error:** `⚠ target_vendor_interface.kconfig - not found`

**Fix:** Create the kconfig file in `kconfigs/` directory using:
```bash
cd /path/to/kalico
KCONFIG_CONFIG=/path/to/flasher-ci/kconfigs/target_vendor_interface.kconfig make menuconfig
```

### Missing displayName

**Error:** `Missing configuration displayNames: new_interface`

**Fix:** Add to `index-template.json` configurations array:
```json
{
  "id": "new_interface",
  "displayName": "Human Readable Name"
}
```

### Undefined vendor

**Error:** `Missing vendor definitions for: ['newvendor']`

**Fix:** Add vendor to `index-template.json` vendors array:
```json
{
  "vendorId": "newvendor",
  "displayName": "New Vendor",
  "websiteUrl": "https://..."
}
```

### JSON formatting

**Error:** `index-template.json is not properly formatted`

**Fix:**
```bash
python -m json.tool index-template.json > index-template.json.tmp && mv index-template.json.tmp index-template.json
```

### Note on index.json

`index.json` is **generated automatically** from `index-template.json` by `build.py`. 
- ✅ Edit `index-template.json` (committed to git)
- ❌ Don't edit `index.json` (git-ignored, generated file)

## Questions?

Open an issue or discussion on GitHub!
