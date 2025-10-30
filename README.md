# Kalico Web Flasher - Build System

Backend build system for compiling Kalico firmware for multiple targets with various configurations.

## Directory Structure

```
flasher-ci/
├── index.json          # Main configuration with vendors, targets, and builds
├── kconfigs/           # Kalico configuration files (.kconfig)
├── builds/             # Generated firmware builds (organized by version)
│   └── v0.12.0-123/
│       ├── metadata.json
│       └── *.bin       # Compiled firmware files
└── build.py            # Build script
```

## Usage

### Validate Configuration Files

Check which `.kconfig` files are missing before building:

```bash
python build.py validate
```

This will scan all targets and their permutations, then report:
- ✓ Which kconfig files exist
- ✗ Which kconfig files are missing
- Summary with percentage complete

### Build Firmware

Compile all firmware targets for a specific version:

```bash
python build.py build v0.12.0-124 --kalico-dir /path/to/kalico
```

### Dry Run

Test the build process without actually compiling (prints commands only):

```bash
python build.py build v0.12.0-124 --kalico-dir /path/to/kalico --dry-run
```

This will:
1. Read `index.json` to get all targets and their permutations
2. For each target+permutation combination:
   - Find the matching `.kconfig` file in `kconfigs/`
   - Compile Kalico using that configuration
   - Save firmware to `builds/{version}/{filename}.bin`
3. Generate `builds/{version}/metadata.json`

### Rebuild Index

Update the `builds` array in `index.json` by scanning the `builds/` directory:

```bash
python build.py rebuild-index
```

This scans all version directories in `builds/` and updates `index.json` with:
```json
{
  "builds": [
    {"version": "v0.12.0-124"},
    {"version": "v0.12.0-123"}
  ]
}
```

## Configuration Files

### index.json

Main configuration defining:
- **vendors**: Vendor information (ID, display name, website)
- **targets**: Board targets with build configurations
- **builds**: Array of available build versions (managed by `rebuild-index`)

### Target Configuration

Each target defines:
- `targetId`: Unique board identifier
- `vendorId`: Reference to vendor
- `flashMethod`: Flash method(s) for the board
- `configuration`:
  - `firmwareFilenameTemplate`: Output firmware filename pattern
  - `kconfigFilenameTemplate`: Input kconfig filename pattern
  - `permutations`: Build variants (e.g., USB vs CAN interfaces, speeds)

**Filename Template Variables:**
- `{targetId}` - Target board ID
- `{vendorId}` - Vendor ID
- `{interface}` - Interface type from permutations
- `{can_speed}` - CAN speed from permutations

### Example Target

```json
{
  "targetId": "manta_m8p_v1.1",
  "vendorId": "bigtreetech",
  "flashMethod": "dfu-util-webserial",
  "configuration": {
    "firmwareFilenameTemplate": "{targetId}_{vendorId}_{interface}_{can_speed}.bin",
    "kconfigFilenameTemplate": "{targetId}_{vendorId}_{interface}_{can_speed}.kconfig",
    "permutations": {
      "interface": ["usb_pa11_pa12", "can_pd0_pd1"],
      "can_speed": ["500k", "1M"]
    }
  }
}
```

This generates 4 builds:
- `manta_m8p_v1.1_bigtreetech_usb_pa11_pa12_500k.bin`
- `manta_m8p_v1.1_bigtreetech_usb_pa11_pa12_1M.bin`
- `manta_m8p_v1.1_bigtreetech_can_pd0_pd1_500k.bin`
- `manta_m8p_v1.1_bigtreetech_can_pd0_pd1_1M.bin`

## Requirements

- Python 3.7+
- Kalico source code
- Build tools (make, gcc-arm-none-eabi, etc.)

## Workflow

1. **Create initial kconfig files**: Start creating `.kconfig` files in `kconfigs/` directory
2. **Validate progress**: Run `build.py validate` to see which kconfig files are still needed
3. **Complete kconfig setup**: Continue creating kconfig files until validation passes
4. **Test with dry-run**: Run `build.py build --dry-run` to verify build process
5. **Build firmware**: Run `build.py build` with version and Kalico directory
6. **Update index**: Run `build.py rebuild-index` to update the builds list
7. **Deploy**: Use the generated firmware and metadata for your web flasher frontend

## Notes

- The script automatically handles the Cartesian product of all permutation values
- Missing `.kconfig` files will be skipped with a warning
- Build output is captured and only shown on errors
- The script uses `make -j` with CPU count for parallel builds
- Use `--dry-run` to test your configuration without compiling
