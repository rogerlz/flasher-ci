# Kalico Web Flasher - Build System

Backend build system for compiling Kalico firmware for multiple targets with various configurations.

## Directory Structure

```
flasher-ci/
├── index-template.json # Source configuration (vendors, targets, configurations)
├── index.json          # Generated file (template + builds array) - git ignored
├── kconfigs/           # Kalico & Katapult configuration files (.kconfig)
├── images/             # Product images for boards (referenced in meta.productImagePath)
├── builds/             # Generated firmware builds (organized by version)
│   └── v0.12.0-123/
│       ├── metadata.json
│       ├── kalico-*.bin      # Kalico firmware files
│       └── katapult-*.bin    # Katapult bootloader files
└── build.py            # Build script
```

## Quick Start

```bash
# Install dependencies
pip install -e .

# Check configuration completeness
python build.py check-configurations
python build.py validate

# Build firmware
python build.py build v0.12.0-125 --kalico-dir ../kalico --commit-url https://github.com/KalicoCrew/kalico/commit/abc123

# Deploy to S3 + CloudFront
python build.py sync
```

## Commands

### check-configurations

Verify all permutation values have display names:

```bash
python build.py check-configurations
```

### validate

Validate all required `.kconfig` files and product images exist:

```bash
python build.py validate
```

**What it checks:**
- ✓ All required kconfig files for Kalico and Katapult
- ✓ All product images referenced in `meta.productImagePath`
- Shows completion percentage and missing files
- Provides `KCONFIG_CONFIG` commands to create missing files

**Note:** Reads from `index-template.json` (source of truth), not generated `index.json`

### build

Compile all firmware targets for a specific version:

```bash
python build.py build v0.12.0-125 --kalico-dir /path/to/kalico --katapult-dir /path/to/katapult --commit-url https://github.com/KalicoCrew/kalico/commit/abc123
```

**Options:**
- `--kalico-dir`: Path to Kalico source (required)
- `--katapult-dir`: Path to Katapult source (optional)
- `--commit-url`: GitHub commit URL (optional but recommended)
- `--dry-run`: Test without compiling
- `--root-dir`: Project root directory (default: current)

**What it does:**
1. Compiles both Kalico and Katapult firmware for all target+permutation combinations
2. Saves firmware to `builds/{version}/`
3. Generates `builds/{version}/metadata.json` (includes product image paths)
4. Automatically updates `index.json` builds array with timestamp and commit URL

### sync

Upload `index.json`, `builds/`, and `images/` to S3 with automatic cleanup:

```bash
python build.py sync
```

**Options:**
- `--dry-run`: Preview what would be uploaded/deleted

**Requirements:**
- AWS credentials configured (`aws configure` or environment variables)
- S3 bucket: `kalico-flasher`
- CloudFront distribution ID set in `build.py`

**What it does:**
1. Uploads `index.json` to S3 root
2. Uploads all files in `builds/` directory
3. Uploads all files in `images/` directory (product images)
4. **Deletes stale files** from S3 that don't exist locally (like `aws s3 sync --delete`)
5. Invalidates CloudFront cache for immediate updates

**Content Types:**
- JSON files: `application/json`
- Firmware files (.bin, .elf, .uf2, .hex): `application/octet-stream`
- Images (.png, .jpg, .svg, .webp): Proper image MIME types

### rebuild-index

Reconstruct the `builds` array in `index.json` from filesystem:

```bash
python build.py rebuild-index
```

**Note:** Rarely needed since `build` command auto-updates the index. Use only for recovery or manual corrections.

## Configuration Files

### index-template.json (Source)

Template configuration defining (committed to git):
- **vendors**: Vendor information (ID, display name, website)
- **targets**: Board targets with build configurations
- **builds**: Empty array `[]` (populated dynamically by build.py)
- **configurations**: Catalog of permutation options with human-readable display names

### index.json (Generated)

Generated file (git-ignored) created by `build.py` from `index-template.json` + builds from `builds/` directory.
**Do not edit manually** - edit `index-template.json` instead.

### Target Configuration

Each target defines:
- `targetId`: Unique board identifier
- `vendorId`: Reference to vendor
- `displayName`: Human-readable board name
- `flashMethods`: Array of flash method(s) for the board (`dfu-util-webserial`, `rp-reset-uf2drive`)
- `links`: Optional URLs to documentation, manuals, schematics, pinouts
- `meta`: Metadata like `productImagePath` for board images
- `configuration`:
  - `firmwareFilenameTemplate`: Output firmware filename pattern
  - `kalicoKconfigFilenameTemplate`: Kalico kconfig filename pattern
  - `katapultKconfigFilenameTemplate`: Katapult kconfig filename pattern
  - `permutations`: Build variants (e.g., interface, bootloader options)

**Filename Template Variables:**
- `{targetId}` - Target board ID
- `{vendorId}` - Vendor ID
- Any permutation key (e.g., `{interface}`, `{bootloader}`)

### Example Target

```json
{
  "targetId": "manta_m4p",
  "vendorId": "bigtreetech",
  "displayName": "Manta M4P",
  "flashMethods": ["dfu-util-webserial"],
  "links": {
    "manualUrl": "https://github.com/bigtreetech/Manta-M4P/blob/master/..."
  },
  "meta": {
    "productImagePath": "/images/bigtreetech_manta_m4p.png"
  },
  "configuration": {
    "firmwareFilenameTemplate": "{targetId}_{vendorId}_{interface}.bin",
    "kalicoKconfigFilenameTemplate": "kalico-{targetId}_{vendorId}_{interface}_{bootloader}.kconfig",
    "katapultKconfigFilenameTemplate": "katapult-{targetId}_{vendorId}_{interface}_{bootloader}.kconfig",
    "permutations": {
      "interface": [
        "usb_pa11pa12",
        "usb2can_pa11pa12_pd0pd1_500k",
        "can_pd0pd1_500k"
      ],
      "bootloader": [
        "katapult",
        "none"
      ]
    }
  }
}
```

**Generates 6 firmware files (3 interfaces × 2 bootloaders):**
- `manta_m4p_bigtreetech_usb_pa11pa12.bin`
- `manta_m4p_bigtreetech_usb2can_pa11pa12_pd0pd1_500k.bin`
- `manta_m4p_bigtreetech_can_pd0pd1_500k.bin`

**Requires 12 kconfig files (6 for Kalico + 6 for Katapult):**
- `kalico-manta_m4p_bigtreetech_usb_pa11pa12_katapult.kconfig`
- `kalico-manta_m4p_bigtreetech_usb_pa11pa12_none.kconfig`
- `katapult-manta_m4p_bigtreetech_usb_pa11pa12_katapult.kconfig`
- ... (and so on)

## Requirements

**Build:**
- Python 3.13+
- Kalico source code
- Build tools (make, gcc-arm-none-eabi, etc.)

**Deploy:**
- boto3 (included in dependencies)
- AWS credentials with S3 and CloudFront permissions

## Workflow

### Initial Setup
1. Add board images to `images/` directory
2. Create `.kconfig` files in `kconfigs/` directory (both Kalico and Katapult)
3. Run `check-configurations` to verify all permutations have displayNames
4. Run `validate` to check kconfig files and images

### Build & Deploy
1. Build firmware: `build v0.12.0-125 --kalico-dir ../kalico --katapult-dir ../katapult --commit-url <url>`
2. Test sync: `sync --dry-run` (preview changes)
3. Deploy to S3: `sync`
4. Done! Files uploaded, stale files deleted, CloudFront cache invalidated

## Configuration

**S3 Bucket:** Set in `build.py` → `S3_BUCKET = "kalico-flasher"`
**CloudFront Distribution:** Set in `build.py` → `CLOUDFRONT_DISTRIBUTION_ID = "E12YCK1HLQNF8F"`

## Development

### Pre-commit Hooks

Install pre-commit hooks to automatically validate changes:

```bash
pip install pre-commit
pre-commit install
```

This will automatically run on every commit:
- Python formatting (ruff format)
- Python linting (ruff check)
- JSON formatting validation
- Trailing whitespace removal

### Manual Validation

Run all validations locally:

```bash
./scripts/validate-all.sh
```

Or run individual checks:
```bash
ruff format --check .          # Check Python formatting
ruff check .                   # Lint Python code
python build.py check-configurations  # Check displayNames
python build.py validate       # Check kconfig files
```

### CI/CD

GitHub Actions automatically validates:
- ✅ Python code formatting and linting (ruff)
- ✅ JSON formatting
- ✅ Configuration displayNames completeness
- ✅ Kconfig file existence (Kalico and Katapult)
- ✅ Product image existence
- ✅ Vendor consistency (all vendors in targets are defined)
- ✅ Target schema validation
- ✅ Build schema validation

All checks must pass before merging PRs.

## Notes

- Automatically generates Cartesian product of all permutation values
- Builds both Kalico and Katapult firmware for each configuration
- Missing kconfig files are skipped with warnings during build
- Parallel builds using `make -j` with CPU count
- Build output captured (shown only on errors)
- `--dry-run` available for build and sync commands
- Validation reads from `index-template.json` (source), not `index.json` (generated)
- S3 sync automatically cleans up stale files (equivalent to `aws s3 sync --delete`)
