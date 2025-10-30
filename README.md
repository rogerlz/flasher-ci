# Kalico Web Flasher - Build System

Backend build system for compiling Kalico firmware for multiple targets with various configurations.

## Directory Structure

```
flasher-ci/
├── index-template.json # Source configuration (vendors, targets, configurations)
├── index.json          # Generated file (template + builds array) - git ignored
├── kconfigs/           # Kalico configuration files (.kconfig)
├── builds/             # Generated firmware builds (organized by version)
│   └── v0.12.0-123/
│       ├── metadata.json
│       └── *.bin       # Compiled firmware files
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

Check which `.kconfig` files are missing:

```bash
python build.py validate
```

### build

Compile all firmware targets for a specific version:

```bash
python build.py build v0.12.0-125 --kalico-dir /path/to/kalico --commit-url https://github.com/KalicoCrew/kalico/commit/abc123
```

**Options:**
- `--commit-url`: GitHub commit URL (optional but recommended)
- `--dry-run`: Test without compiling
- `--root-dir`: Project root directory (default: current)

**What it does:**
1. Compiles firmware for all target+permutation combinations
2. Saves firmware to `builds/{version}/`
3. Generates `builds/{version}/metadata.json`
4. Automatically updates `index.json` builds array with timestamp

### sync

Upload `index.json` and `builds/` to S3 and invalidate CloudFront cache:

```bash
python build.py sync
```

**Options:**
- `--dry-run`: Preview what would be uploaded

**Requirements:**
- AWS credentials configured (`aws configure` or environment variables)
- S3 bucket: `kalico-flasher`
- CloudFront distribution ID set in `build.py`

**What it does:**
1. Uploads `index.json` to S3 root
2. Uploads all files in `builds/` directory
3. Invalidates CloudFront cache for immediate updates

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
- `configuration`:
  - `firmwareFilenameTemplate`: Output firmware filename pattern
  - `kconfigFilenameTemplate`: Input kconfig filename pattern
  - `permutations`: Build variants (e.g., USB vs CAN interfaces)

**Filename Template Variables:**
- `{targetId}` - Target board ID
- `{vendorId}` - Vendor ID
- Any permutation key (e.g., `{interface}`)

### Example Target

```json
{
  "targetId": "manta_m8p_v1.1",
  "vendorId": "bigtreetech",
  "displayName": "Manta M8P V1.1",
  "flashMethods": ["dfu-util-webserial"],
  "links": {
    "manualUrl": "https://github.com/bigtreetech/Manta-M8P/blob/master/..."
  },
  "configuration": {
    "firmwareFilenameTemplate": "{targetId}_{vendorId}_{interface}.bin",
    "kconfigFilenameTemplate": "{targetId}_{vendorId}_{interface}.kconfig",
    "permutations": {
      "interface": [
        "usb_pa11pa12",
        "usb2can_pa11pa12_pd0pd1_500k",
        "usb2can_pa11pa12_pd0pd1_1M",
        "can_pd0pd1_500k",
        "can_pd0pd1_1M"
      ]
    }
  }
}
```

**Generates 5 firmware files:**
- `manta_m8p_v1.1_bigtreetech_usb_pa11pa12.bin`
- `manta_m8p_v1.1_bigtreetech_usb2can_pa11pa12_pd0pd1_500k.bin`
- `manta_m8p_v1.1_bigtreetech_usb2can_pa11pa12_pd0pd1_1M.bin`
- `manta_m8p_v1.1_bigtreetech_can_pd0pd1_500k.bin`
- `manta_m8p_v1.1_bigtreetech_can_pd0pd1_1M.bin`

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
1. Create `.kconfig` files in `kconfigs/` directory
2. Run `check-configurations` to verify all permutations have displayNames
3. Run `validate` to check kconfig file coverage

### Build & Deploy
1. Build firmware: `build v0.12.0-125 --kalico-dir ../kalico --commit-url <url>`
2. Deploy to S3: `sync`
3. Done! CloudFront cache is automatically invalidated

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
- ✅ Kconfig file existence
- ✅ Vendor consistency (all vendors in targets are defined)
- ✅ Target schema validation
- ✅ Build schema validation

All checks must pass before merging PRs.

## Notes

- Automatically generates Cartesian product of all permutation values
- Missing kconfig files are skipped with warnings
- Parallel builds using `make -j` with CPU count
- Build output captured (shown only on errors)
- `--dry-run` available for all commands
