#!/usr/bin/env python3
"""
Kalico Firmware Build System
Builds Kalico firmware for multiple targets with permutations
"""

import json
import os
import sys
import argparse
import shutil
import subprocess
from pathlib import Path
from itertools import product
from typing import Dict, List, Any


class KalicoBuilder:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.index_file = self.root_dir / "index.json"
        self.kconfigs_dir = self.root_dir / "kconfigs"
        self.builds_dir = self.root_dir / "builds"

    def load_index(self) -> Dict[str, Any]:
        """Load the index.json file"""
        with open(self.index_file, "r") as f:
            return json.load(f)

    def save_index(self, data: Dict[str, Any]):
        """Save the index.json file"""
        with open(self.index_file, "w") as f:
            json.dump(data, f, indent=4)
            f.write("\n")

    def generate_permutations(self, target: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate all permutation combinations for a target"""
        config = target.get("configuration", {})
        permutations = config.get("permutations", {})

        if not permutations:
            return [{}]

        # Get all permutation keys and their values
        keys = list(permutations.keys())
        values = [permutations[key] for key in keys]

        # Generate all combinations
        combinations = []
        for combo in product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    def format_filename(
        self, template: str, target: Dict[str, Any], permutation: Dict[str, str]
    ) -> str:
        """Format a filename using the template and permutation values"""
        params = {
            "targetId": target.get("targetId"),
            "vendorId": target.get("vendorId"),
            **permutation,
        }
        return template.format(**params)

    def get_kconfig_filename(
        self, target: Dict[str, Any], permutation: Dict[str, str]
    ) -> str:
        """Get the kconfig filename for a target and permutation"""
        config = target.get("configuration", {})

        # Handle both naming conventions
        template = config.get("kconfigFilenameTemplate") or config.get(
            "kconfigTemplate"
        )

        if not template:
            # Default template if not specified
            template = "{targetId}_{vendorId}.kconfig"

        return self.format_filename(template, target, permutation)

    def get_firmware_filename(
        self, target: Dict[str, Any], permutation: Dict[str, str]
    ) -> str:
        """Get the firmware filename for a target and permutation"""
        config = target.get("configuration", {})

        # Handle both naming conventions
        template = config.get("firmwareFilenameTemplate") or config.get("fileTemplate")

        if not template:
            # Default template if not specified
            template = "{targetId}_{vendorId}.bin"

        return self.format_filename(template, target, permutation)

    def compile_kalico(
        self,
        kconfig_path: Path,
        output_path: Path,
        kalico_dir: Path,
        dry_run: bool = False,
    ) -> bool:
        """Compile Kalico firmware with a given kconfig"""
        print(f"  Building firmware with config: {kconfig_path.name}")

        try:
            # Copy kconfig to Kalico .config
            kconfig_dest = kalico_dir / ".config"
            if dry_run:
                print(f"    [DRY RUN] cp {kconfig_path} {kconfig_dest}")
            else:
                shutil.copy(kconfig_path, kconfig_dest)

            # Clean previous build
            clean_cmd = ["make", "clean"]
            if dry_run:
                print(f"    [DRY RUN] cd {kalico_dir} && {' '.join(clean_cmd)}")
            else:
                subprocess.run(
                    clean_cmd, cwd=kalico_dir, check=True, capture_output=True
                )

            # Build
            build_cmd = ["make", "-j", str(os.cpu_count() or 1)]
            if dry_run:
                print(f"    [DRY RUN] cd {kalico_dir} && {' '.join(build_cmd)}")
            else:
                subprocess.run(
                    build_cmd, cwd=kalico_dir, check=True, capture_output=True
                )

            # Copy output firmware
            firmware_source = kalico_dir / "out" / "klipper.bin"
            if dry_run:
                print(f"    [DRY RUN] cp {firmware_source} {output_path}")
                print(f"    ✓ [DRY RUN] Would build: {output_path.name}")
                return True
            elif firmware_source.exists():
                shutil.copy(firmware_source, output_path)
                print(f"    ✓ Built: {output_path.name}")
                return True
            else:
                # Try other possible firmware names
                firmware_source = kalico_dir / "out" / "klipper.elf"
                if firmware_source.exists():
                    shutil.copy(firmware_source, output_path)
                    print(f"    ✓ Built: {output_path.name}")
                    return True

                print("    ✗ Error: No firmware output found")
                return False

        except subprocess.CalledProcessError as e:
            print(f"    ✗ Build failed: {e}")
            return False
        except Exception as e:
            print(f"    ✗ Error: {e}")
            return False

    def build(self, version: str, kalico_dir: str, dry_run: bool = False):
        """Build all firmware targets"""
        kalico_path = Path(kalico_dir).resolve()

        if not dry_run and not kalico_path.exists():
            print(f"Error: Kalico directory not found: {kalico_dir}")
            sys.exit(1)

        if dry_run:
            print("[DRY RUN MODE] No actual compilation will occur\n")

        print(f"Loading index from {self.index_file}")
        index = self.load_index()

        # Create version build directory
        version_dir = self.builds_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)

        print(f"Building firmware to {version_dir}")

        # Track metadata
        metadata = {"targets": []}

        targets = index.get("targets", [])
        total_builds = 0
        successful_builds = 0

        for target in targets:
            target_id = target.get("targetId")
            vendor_id = target.get("vendorId")
            print(f"\n[{target_id}] Processing target")

            permutations = self.generate_permutations(target)
            print(f"  Generating {len(permutations)} permutation(s)")

            # Add target to metadata
            target_metadata = {
                "targetId": target_id,
                "vendorId": vendor_id,
            }

            # Add configuration if exists
            if "configuration" in target:
                config = target["configuration"]
                target_metadata.update(
                    {
                        k: v
                        for k, v in config.items()
                        if k
                        in [
                            "firmwareFilenameTemplate",
                            "kconfigFilenameTemplate",
                            "fileTemplate",
                            "kconfigTemplate",
                            "permutations",
                        ]
                    }
                )

            # Add flashMethod if exists
            if "flashMethod" in target:
                target_metadata["flashMethod"] = target["flashMethod"]

            metadata["targets"].append(target_metadata)

            for permutation in permutations:
                total_builds += 1

                # Get filenames
                kconfig_filename = self.get_kconfig_filename(target, permutation)
                firmware_filename = self.get_firmware_filename(target, permutation)

                kconfig_path = self.kconfigs_dir / kconfig_filename
                firmware_path = version_dir / firmware_filename

                # Check if kconfig exists
                if not kconfig_path.exists():
                    print(f"    ⚠ Warning: kconfig not found: {kconfig_filename}")
                    continue

                # Compile
                if self.compile_kalico(
                    kconfig_path, firmware_path, kalico_path, dry_run
                ):
                    successful_builds += 1

        # Save metadata
        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)
            f.write("\n")

        print(f"\n{'=' * 60}")
        print(f"Build complete: {successful_builds}/{total_builds} successful")
        print(f"Output directory: {version_dir}")
        print(f"Metadata saved to: {metadata_path}")

    def rebuild_index(self):
        """Rebuild the builds array in index.json by scanning builds/ directory"""
        print(f"Scanning builds directory: {self.builds_dir}")

        if not self.builds_dir.exists():
            print("Error: builds/ directory not found")
            sys.exit(1)

        # Find all version directories
        versions = []
        for entry in self.builds_dir.iterdir():
            if entry.is_dir():
                version = entry.name
                versions.append({"version": version})
                print(f"  Found: {version}")

        # Sort versions (newest first, assuming semantic versioning)
        versions.sort(key=lambda x: x["version"], reverse=True)

        # Update index
        index = self.load_index()
        index["builds"] = versions
        self.save_index(index)

        print(f"\n✓ Updated index.json with {len(versions)} build(s)")

    def validate_kconfigs(self):
        """Validate that all required kconfig files exist"""
        print(f"Validating kconfig files in {self.kconfigs_dir}\n")

        index = self.load_index()
        targets = index.get("targets", [])

        missing_files = []
        existing_files = []
        total_configs = 0

        for target in targets:
            permutations = self.generate_permutations(target)

            for permutation in permutations:
                total_configs += 1
                kconfig_filename = self.get_kconfig_filename(target, permutation)
                kconfig_path = self.kconfigs_dir / kconfig_filename

                if kconfig_path.exists():
                    existing_files.append(kconfig_filename)
                else:
                    missing_files.append(kconfig_filename)

        # Summary
        print(f"{'=' * 60}")
        print("Validation Summary:")
        print(f"  Total configs required: {total_configs}")
        print(
            f"  Found: {len(existing_files)} ({len(existing_files) * 100 // total_configs if total_configs > 0 else 0}%)"
        )
        print(
            f"  Missing: {len(missing_files)} ({len(missing_files) * 100 // total_configs if total_configs > 0 else 0}%)"
        )

        if missing_files:
            print("\nMissing kconfig files. Use:")
            print("   cd /path/to/kalico")
            for filename in missing_files:
                kconfig_path = self.kconfigs_dir / filename
                print(f"   KCONFIG_CONFIG={kconfig_path} make menuconfig")
            sys.exit(1)
        else:
            print("\n✓ All kconfig files are present!")


def main():
    parser = argparse.ArgumentParser(
        description="Kalico Firmware Build System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all required kconfig files exist
  %(prog)s validate

  # Build all firmware for version v0.12.0-124
  %(prog)s build v0.12.0-124 --kalico-dir ../kalico

  # Dry run (echo commands only)
  %(prog)s build v0.12.0-124 --kalico-dir ../kalico --dry-run

  # Rebuild the builds index
  %(prog)s rebuild-index
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build firmware for all targets")
    build_parser.add_argument("version", help="Version string (e.g., v0.12.0-124)")
    build_parser.add_argument(
        "--kalico-dir", required=True, help="Path to Kalico source directory"
    )
    build_parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without executing them"
    )
    build_parser.add_argument(
        "--root-dir", default=".", help="Root directory (default: current directory)"
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate all required kconfig files exist"
    )
    validate_parser.add_argument(
        "--root-dir", default=".", help="Root directory (default: current directory)"
    )

    # Rebuild-index command
    rebuild_parser = subparsers.add_parser(
        "rebuild-index", help="Rebuild builds array in index.json"
    )
    rebuild_parser.add_argument(
        "--root-dir", default=".", help="Root directory (default: current directory)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    builder = KalicoBuilder(args.root_dir)

    if args.command == "build":
        builder.build(args.version, args.kalico_dir, getattr(args, "dry_run", False))
    elif args.command == "validate":
        builder.validate_kconfigs()
    elif args.command == "rebuild-index":
        builder.rebuild_index()


if __name__ == "__main__":
    main()
